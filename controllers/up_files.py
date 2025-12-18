# -*- coding: utf-8 -*-
"""Excel test case parser.

支持两类模板：
1) metadata 模板：A 列有 Section/test case item 等键值，标题行后接步骤/预期。
2) 表格型模板：表头行包含标题/步骤/预期等列，例如《测试用例模板.xls》。

解析策略：优先尝试 metadata 模板；失败后回退表格模板；两者都失败抛出明确错误。
"""

from __future__ import annotations

import re
from io import BytesIO
from pathlib import Path
from typing import Any, BinaryIO, Dict, List, Tuple
import json
import pandas as pd

# =========================================================================================
# 新版：A 列关键字，不能当作标题识别（Excel 为键值结构）
# =========================================================================================
A_COL_METADATA_KEYS = {
    "section :",
    "workloading :",
    "leadingtime :",
    "phase :",
    "priority :",
    "test log mandatory :",
    "case type :",
    "case name :",
    "version :",
    "keywords :",
    "auto type :",
    "creator :",
    "objective :",
    "type matrix :",
}

STEP_SPLIT_RE = re.compile(r"(?:^|\n)\s*(\d+)[\.\)\、:：]\s*", re.M)
TITLE_KEYWORD_RE = re.compile(r"\[([^\]]+)\]")  # capture inner token
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

# =========================================================================================
# 工具函数
# =========================================================================================


def _normalize_text(value: Any) -> str:
    if isinstance(value, str):
        text = value.strip()
        return "" if text.lower() == "nan" else text
    if pd.isna(value):
        return ""
    return str(value).strip()


def _cell_text(value: Any) -> str:
    """Return cell text without stripping inner newlines; only coerce NaN to empty."""
    if isinstance(value, str):
        return "" if value.lower() == "nan" else value
    if pd.isna(value):
        return ""
    return str(value)


def extract_folder_name(df: pd.DataFrame) -> str:
    return _normalize_text(df.iloc[1, 3]) if df.shape[0] > 1 else ""


def extract_subfolder_name(df: pd.DataFrame) -> str:
    return _normalize_text(df.iloc[1, 1]) if df.shape[0] > 1 else ""


def find_header_idx(df: pd.DataFrame) -> int | None:
    for i in range(len(df)):
        v = _normalize_text(df.iloc[i, 0]).lower()
        if "test case item" in v:
            return i
    return None


# ⭐ 新版判定：A 列是 metadata（如 Section :），绝不是标题
def is_title_row(df: pd.DataFrame, index: int) -> bool:
    title = _normalize_text(df.iloc[index, 0]).lower()
    expected = _normalize_text(df.iloc[index, 4])

    if not title:
        return False

    if title in A_COL_METADATA_KEYS:
        return False

    return expected == ""


def has_step_and_expected(df: pd.DataFrame, index: int) -> bool:
    action = _normalize_text(df.iloc[index, 0])
    expected = _normalize_text(df.iloc[index, 4])
    return bool(action) and bool(expected)


def split_numbered(text: str) -> List[Tuple[int, str]]:
    source = (text or "").strip()
    if not source:
        return []

    matches = list(STEP_SPLIT_RE.finditer(source))
    if not matches:
        lines = [ln.strip() for ln in source.splitlines() if ln.strip()]
        return [(idx + 1, ln) for idx, ln in enumerate(lines)] or [(1, source)]

    parts: List[Tuple[int, str]] = []

    if matches[0].start() != 0:
        head = source[: matches[0].start()].strip()
        if head:
            parts.append((1, head))

    for idx, match in enumerate(matches):
        number = int(match.group(1))
        start = match.end()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(source)
        chunk = source[start:end].strip()
        if chunk:
            parts.append((number, chunk))

    return parts


def _strip_leading_label(text: str) -> str:
    """
    Remove common labels like "操作步骤：" / "测试步骤：" / "预期结果：" so they don't become steps.
    """
    if not text:
        return ""
    pattern = r"^(操作步骤|测试步骤|步骤|测试点|预期结果|测试标准)\s*[：:]?\s*"
    return re.sub(pattern, "", text, flags=re.IGNORECASE)


def _parse_workload_minutes(value: str) -> int | None:
    """Parse workload string (e.g., '10min', '0.5h', '10分钟') into minutes."""
    if not value:
        return None
    text = str(value).strip().lower()
    match = re.search(r"(\d+(?:\.\d+)?)", text)
    if not match:
        return None
    number = float(match.group(1))
    # detect unit
    if any(u in text for u in ["h", "小时"]):
        minutes = int(round(number * 60))
    else:
        minutes = int(round(number))
    return minutes if minutes >= 0 else None


def _parse_datetime_cell(value: Any):
    """Parse excel datetime cell into a Python datetime."""
    if value is None or value == "":
        return None
    try:
        ts = pd.to_datetime(value, errors="coerce")
        if pd.isna(ts):
            return None
        return ts.to_pydatetime()
    except Exception:
        return None


def _normalize_priority(text: str) -> str | None:
    """
    Map priority cell text to internal priority.
    high -> P0, medium -> P1, low -> P2, explicit P3 kept.
    """
    if not text:
        return None
    t = text.strip().lower()
    if t in {"p0", "high", "最高", "高"}:
        return "P0"
    if t in {"p1", "medium", "mid", "中", "中等"}:
        return "P1"
    if t in {"p2", "low", "低"}:
        return "P2"
    if t in {"p3"}:
        return "P3"
    return None


def extract_title_and_keywords(title: str) -> Tuple[str, List[str]]:
    """抽取标题中的 [keyword] 作为关键词，并返回去掉标记后的标题。"""
    source = title or ""
    tokens = TITLE_KEYWORD_RE.findall(source)
    keywords = [token.strip() for token in tokens if token.strip() and token.strip() != "通用"]
    cleaned = TITLE_KEYWORD_RE.sub("", source).strip()
    cleaned = re.sub(r"\s{2,}", " ", cleaned).strip(" -—_/")
    return cleaned, keywords


def _ensure_min_columns(df: pd.DataFrame, count: int = 8) -> pd.DataFrame:
    """确保列数不少于 count，不截断原列。"""
    current_cols = list(df.columns)
    if len(current_cols) < count:
        extra = list(range(len(current_cols), count))
        df[extra] = None
        current_cols = current_cols + extra
    labels = [chr(ord("A") + idx) for idx in range(len(current_cols))]
    return df.rename(columns=dict(zip(current_cols, labels)))


# =========================================================================================
# 模板类型检测 / 解析
# =========================================================================================


def _detect_tabular_header(df: pd.DataFrame) -> tuple[int, Dict[str, int]] | None:
    """
    Try to find the header row for table-style templates.

    The newer template (测试用例模板.xls) uses Chinese headers and may omit optional fields.
    We try to match both the older gibberish headers and readable Chinese/English ones.
    """
    max_cols = min(len(df.columns), 20)
    for idx in range(len(df)):
        cells_raw = [_normalize_text(df.iloc[idx, col]) for col in range(max_cols)]
        cells_lower = [c.lower() for c in cells_raw]
        if not any(cells_lower):
            continue

        def find_col(*keywords: str) -> int | None:
            lowered = [kw.lower() for kw in keywords]
            for col, (text, text_lower) in enumerate(zip(cells_raw, cells_lower)):
                for kw, kw_lower in zip(keywords, lowered):
                    if kw and kw in text:
                        return col
                    if kw_lower and kw_lower in text_lower:
                        return col
            return None

        title_col = find_col(
            "title",
            "用例名称",
            "用例名称(必填)",
            "用例标题",
            "用例名",
            "测试项",
            "test case item",
        )
        case_type_col = find_col(
            "case type",
            "用例类型",
            "类型",
        )
        workload_col = find_col(
            "工作负载",
            "工作量",
            "workload",
            "workloading",
        )
        priority_col = find_col(
            "priority",
            "优先级",
            "prio",
        )
        created_col = find_col(
            "创建时间",
            "创建日期",
            "create time",
            "created at",
        )
        step_col = find_col(
            "步骤",
            "操作步骤",
            "测试步骤",
            "step",
            "steps",
        )
        expected_col = find_col(
            "预期",
            "预期结果",
            "期望",
            "测试标准",
            "expected",
        )
        pre_cond_col = find_col(
            "前置",
            "前提",
            "预置条件",
            "测试准备",
            "precondition",
        )
        keyword_col = find_col(
            "关键字",
            "关键词",
            "标签",
            "keywords",
        )
        dir1_col = find_col(
            "类别目录第一层级",
            "一级目录",
            "目录1",
            "directory1",
            "root folder",
        )
        dir2_col = find_col(
            "类别目录第二层级",
            "二级目录",
            "目录2",
            "directory2",
        )
        dir3_col = find_col(
            "类别目录第三层级",
            "三级目录",
            "目录3",
            "directory3",
        )
        dir4_col = find_col(
            "类别目录第四层级",
            "四级目录",
            "目录4",
            "directory4",
        )

        if title_col is not None and (step_col is not None or expected_col is not None):
            mapping = {
            "title": title_col,
            "case_type": case_type_col,
            "workload": workload_col,
            "priority": priority_col,
            "created": created_col,
            "steps": step_col,
            "expected": expected_col,
            "preconditions": pre_cond_col,
            "keywords": keyword_col,
            "dir1": dir1_col,
                "dir2": dir2_col,
                "dir3": dir3_col,
                "dir4": dir4_col,
            }
            return idx, mapping
    return None


def _parse_tabular_cases(df: pd.DataFrame) -> Tuple[str, str, List[Dict[str, Any]]]:
    """解析表格型模板（如《测试用例模板.xls》）。"""
    header_info = _detect_tabular_header(df)
    if not header_info:
        raise ValueError("未找到有效的表头，无法解析测试用例模板")

    header_idx, mapping = header_info
    order = 1
    cases: List[Dict[str, Any]] = []

    for row_idx in range(header_idx + 1, len(df)):
        title = _normalize_text(df.iloc[row_idx, mapping["title"]])
        if not title:
            continue

        case_type_raw = (
            _normalize_text(df.iloc[row_idx, mapping["case_type"]])
            if mapping.get("case_type") is not None
            else ""
        )
        created_raw = (
            df.iloc[row_idx, mapping["created"]]
            if mapping.get("created") is not None
            else None
        )
        priority_raw = (
            _normalize_text(df.iloc[row_idx, mapping["priority"]])
            if mapping.get("priority") is not None
            else ""
        )
        workload_raw = (
            _normalize_text(df.iloc[row_idx, mapping["workload"]])
            if mapping.get("workload") is not None
            else ""
        )
        steps_raw = _cell_text(df.iloc[row_idx, mapping["steps"]]) if mapping["steps"] is not None else ""
        expected_raw = _cell_text(df.iloc[row_idx, mapping["expected"]]) if mapping["expected"] is not None else ""
        pre_raw = _normalize_text(df.iloc[row_idx, mapping["preconditions"]]) if mapping["preconditions"] is not None else ""
        keywords_raw = _normalize_text(df.iloc[row_idx, mapping["keywords"]]) if mapping["keywords"] is not None else ""
        dir1 = _normalize_text(df.iloc[row_idx, mapping["dir1"]]) if mapping.get("dir1") is not None else ""
        dir2 = _normalize_text(df.iloc[row_idx, mapping["dir2"]]) if mapping.get("dir2") is not None else ""
        dir3 = _normalize_text(df.iloc[row_idx, mapping["dir3"]]) if mapping.get("dir3") is not None else ""
        dir4 = _normalize_text(df.iloc[row_idx, mapping["dir4"]]) if mapping.get("dir4") is not None else ""

        keywords = [kw.strip() for kw in re.split(r"[,，;；\s]+", keywords_raw) if kw.strip()] if keywords_raw else []

        # Keep steps/expected as single row without splitting
        clean_steps = _strip_leading_label(steps_raw)
        clean_expected = _strip_leading_label(expected_raw)
        steps_payload = [{
            "no": 1,
            "action": clean_steps or steps_raw,
            "keyword": "",
            "note": "",
            "expected": clean_expected or expected_raw,
        }]

        cases.append({
            "order": order,
            "root_folder": dir1,
            "subfolder": dir2,
            "section": dir3,
            "level3_folder": "/".join([part for part in (dir1, dir2, dir3, dir4) if part]),
            "folder": "/".join([part for part in (dir1, dir2, dir3, dir4) if part]),
            "title": title,
            "keywords": keywords,
            "compatibility_testing": True,
            "expected_result": clean_expected or expected_raw,
            "steps": steps_payload,
            "preconditions": pre_raw or None,
            "case_type": case_type_raw,
            "workload_minutes": _parse_workload_minutes(workload_raw),
            "priority": _normalize_priority(priority_raw),
            "created_at": _parse_datetime_cell(created_raw),
        })
        order += 1

    if not cases:
        raise ValueError("未解析到任何用例，请检查表头是否包含“标题/步骤/预期”等字段")

    return "", "", cases


def _parse_metadata_cases(df: pd.DataFrame) -> Tuple[str, str, List[Dict[str, Any]]]:
    """原始 metadata 模板解析。"""
    folder = extract_folder_name(df)
    subfolder = extract_subfolder_name(df)
    combined_folder = "/".join([p for p in (folder, subfolder) if p])
    header = find_header_idx(df)

    index = (header + 1) if header is not None else 0
    order = 1
    cases = []

    current_section = None  # ⭐ location of section (third-level folder)

    while index < len(df):

        a_col = _normalize_text(df.iloc[index, 0]).lower()

        if a_col == "section :":
            section_value = _normalize_text(df.iloc[index, 1])
            if section_value:
                current_section = section_value
            index += 1
            continue

        if is_title_row(df, index):
            raw_title = _normalize_text(df.iloc[index, 0])
            inner_index = index + 1

            while inner_index < len(df) and not has_step_and_expected(df, inner_index):
                if is_title_row(df, inner_index):
                    break
                inner_index += 1

            if inner_index < len(df) and has_step_and_expected(df, inner_index):
                steps_text = _normalize_text(df.iloc[inner_index, 0])
                expected_text = _normalize_text(df.iloc[inner_index, 4])

                has_general_marker = "[通用]" in raw_title
                cleaned_title = raw_title.replace("[通用]", "").strip()
                title, keywords = extract_title_and_keywords(cleaned_title)
                steps_split = split_numbered(steps_text)
                steps_payload = [
                    {"no": n, "action": a, "keyword": "", "note": "", "expected": ""}
                    for n, a in steps_split
                ]

                level3_folder = (
                    f"{combined_folder}/{current_section}"
                    if current_section else combined_folder
                )

                cases.append({
                    "order": order,
                    "folder": combined_folder,
                    "root_folder": folder,
                    "subfolder": subfolder,
                    "section": current_section,
                    "level3_folder": level3_folder,
                    "title": title or cleaned_title or raw_title,
                    "keywords": keywords,
                    "compatibility_testing": not has_general_marker,
                    "expected_result": expected_text,
                    "steps": steps_payload,
                })

                order += 1
                index = inner_index + 1
                continue

        index += 1

    return folder, subfolder, cases


# =========================================================================================
# 入口
# =========================================================================================


def parse_excel_cases(data: BinaryIO | BytesIO | Path, sheet: int = 0):
    """Parse Excel into structured test cases。

    先尝试 metadata 模板（原有逻辑），失败后回退表格型模板；两者都失败则报错。
    """
    buffer = BytesIO(data) if isinstance(data, (bytes, bytearray)) else data
    df = pd.read_excel(buffer, sheet_name=sheet, header=None)
    df = _ensure_min_columns(df)

    # 优先 metadata 模板
    try:
        if find_header_idx(df) is not None:
            return _parse_metadata_cases(df)
    except Exception:
        pass

    # 回退表格模板
    return _parse_tabular_cases(df)


# =========================================================================================
# 打印函数（保持不变）
# =========================================================================================


def print_case_details(case: Dict[str, Any], index: int) -> None:
    print(f"\n{'=' * 60}")
    print(f"测试用例 #{index + 1}")
    print(f"{'=' * 60}")

    print(f"顺序: {case.get('order')}")
    print(f"目录路径: {case.get('level3_folder')}")
    print(f"Section: {case.get('section')}")
    print(f"标题: {case.get('title')}")
    print(f"关键词: {case.get('keywords')}")
    print(f"兼容性测试: {case.get('compatibility_testing')}")
    print(f"预期结果: {case.get('expected_result')}")
    print(f"步骤数: {len(case.get('steps', []))}")


def print_cases(cases: List[Dict[str, Any]]) -> None:
    print(f"共解析到 {len(cases)} 条测试用例")
    for idx, case in enumerate(cases):
        print_case_details(case, idx)


if __name__ == "__main__":
    # 示例：从文件读取并打印
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("file", help="Excel file path")
    parser.add_argument("--sheet", type=int, default=0)
    args = parser.parse_args()

    with open(args.file, "rb") as f:
        folder, subfolder, cases = parse_excel_cases(f.read(), sheet=args.sheet)
        print(f"folder={folder}, subfolder={subfolder}")
        print_cases(cases)
