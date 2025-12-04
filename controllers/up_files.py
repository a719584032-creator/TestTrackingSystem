# -*- coding: utf-8 -*-
"""最终版：解析 Excel 用例，支持 Section 作为三级目录。"""

from __future__ import annotations

import re
from io import BytesIO
from pathlib import Path
from typing import Any, BinaryIO, Dict, List, Tuple
import json
import pandas as pd

# =========================================================================================
# 🔥 新增：A 列关键字，不能当作标题识别（Excel 为键值结构）
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
TITLE_KEYWORD_RE = re.compile(r"\[([^\]]+)\]")  # 捕获标题中 [] 的关键词

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

    # ⭐ 关键修复：这些绝不能是标题
    if title in A_COL_METADATA_KEYS:
        return False

    # 原逻辑：标题行 expected 列必须为空
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


def extract_title_and_keywords(title: str) -> Tuple[str, List[str]]:
    tokens = TITLE_KEYWORD_RE.findall(title or "")
    keywords = [token.strip() for token in tokens if token.strip()]
    cleaned = TITLE_KEYWORD_RE.sub("", title or "").strip()
    cleaned = re.sub(r"\s{2,}", " ", cleaned).strip(" -—_/")
    return cleaned, keywords


def _ensure_min_columns(df: pd.DataFrame, count: int = 8) -> pd.DataFrame:
    df = df.reindex(columns=range(count))
    labels = [chr(ord("A") + idx) for idx in range(count)]
    df.columns = labels
    return df


# =========================================================================================
# ⭐⭐ 最终版解析器 ⭐⭐
# =========================================================================================

def parse_excel_cases(data: BinaryIO | BytesIO | Path, sheet: int = 0):
    """解析 Excel 用例，识别 Section 为三级目录路径。"""

    # 读取 Excel 并保证列数充足
    buffer = BytesIO(data) if isinstance(data, (bytes, bytearray)) else data
    df = pd.read_excel(buffer, sheet_name=sheet, header=None)
    df = _ensure_min_columns(df)

    # 解析一级/二级目录以及表头行
    folder = extract_folder_name(df)
    subfolder = extract_subfolder_name(df)
    combined_folder = "/".join([p for p in (folder, subfolder) if p])
    header = find_header_idx(df)

    index = (header + 1) if header is not None else 0
    order = 1
    cases = []

    current_section = None  # ⭐ 当前 Section（三级目录）

    # 按行扫描，识别 Section 与用例标题
    while index < len(df):

        a_col = _normalize_text(df.iloc[index, 0]).lower()

        # ==========================================================================
        # ⭐ Section : 关键行位于 A 列，真实值在 B 列
        # ==========================================================================
        if a_col == "section :":
            section_value = _normalize_text(df.iloc[index, 1])
            if section_value:
                current_section = section_value   # 记录当前 Section
            index += 1
            continue

        # ==========================================================================
        # 标题检测（排除掉 metadata 行）
        # ==========================================================================
        if is_title_row(df, index):
            raw_title = _normalize_text(df.iloc[index, 0])
            inner_index = index + 1

            # 找到同时包含步骤与预期的有效行
            while inner_index < len(df) and not has_step_and_expected(df, inner_index):
                # 如果遇到另一个标题行，则说明当前标题无步骤，跳出
                if is_title_row(df, inner_index):
                    break
                inner_index += 1

            # 找到有效步骤
            if inner_index < len(df) and has_step_and_expected(df, inner_index):
                steps_text = _normalize_text(df.iloc[inner_index, 0])
                expected_text = _normalize_text(df.iloc[inner_index, 4])

                title, keywords = extract_title_and_keywords(raw_title)
                steps_split = split_numbered(steps_text)
                steps_payload = [
                    {"no": n, "action": a, "keyword": "", "note": "", "expected": ""}
                    for n, a in steps_split
                ]

                # ⭐ 三级目录：folder / subfolder / section
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
                    "title": title or raw_title,
                    "keywords": keywords,
                    "expected_result": expected_text,
                    "steps": steps_payload,
                })

                order += 1
                index = inner_index + 1
                continue

        index += 1

    return folder, subfolder, cases


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
    print(f"预期结果: {case.get('expected_result')}")

    print(f"\n测试步骤:")
    for step in case.get("steps", []):
        print(f"  步骤 {step['no']}: {step['action']}")


# =========================================================================================
# 调试入口
# =========================================================================================

if __name__ == "__main__":  # pragma: no cover
    sample_path = Path(r"C:\Users\71958\Downloads\01 Keyboard Test information.xlsx")

    if sample_path.exists():
        print(f"🔍 正在解析Excel: {sample_path.name}")
        with sample_path.open("rb") as f:
            folder, subfolder, cases = parse_excel_cases(f)

        print(f"📁 文件夹名称: {folder}")
        print(f"2ji 文件夹名称: {subfolder}")
        print(f"📊 解析到的测试用例总数: {len(cases)}")

        for i, c in enumerate(cases):
            print_case_details(c, i)

    else:
        print("❌ 未找到示例文件，请检查路径")
