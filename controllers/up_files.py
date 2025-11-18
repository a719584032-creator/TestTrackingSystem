# -*- coding: utf-8 -*-
"""Utilities for parsing uploaded Excel test case files."""

from __future__ import annotations

import re
from io import BytesIO
from pathlib import Path
from typing import Any, BinaryIO, Dict, List, Tuple
import json

import pandas as pd

SKIP_PREFIX = (
    "Section :",
    "Workloading :",
    "Leadingtime :",
    "Phase :",
    "Test Log Mandatory :",
)
STEP_SPLIT_RE = re.compile(r"(?:^|\n)\s*(\d+)[\.\)\、:：]\s*", re.M)
TITLE_KEYWORD_RE = re.compile(r"\[([^\]]+)\]")  # capture inner token


def _normalize_text(value: Any) -> str:
    if isinstance(value, str):
        text = value.strip()
        return "" if text.lower() == "nan" else text
    if pd.isna(value):  # type: ignore[arg-type]
        return ""
    return str(value).strip()


def extract_folder_name(df: pd.DataFrame) -> str:
    if df.shape[0] > 1 and df.shape[1] > 3:
        value = df.iloc[1, 3]
        return _normalize_text(value)
    return ""


def extract_subfolder_name(df: pd.DataFrame) -> str:
    """Read the subdirectory name from column B, row 2 (Excel notation: B2)."""

    if df.shape[0] > 1 and df.shape[1] > 1:
        value = df.iloc[1, 1]
        return _normalize_text(value)
    return ""


def find_header_idx(df: pd.DataFrame) -> int | None:
    for i in range(len(df)):
        v = _normalize_text(df.iloc[i, 0])
        if "Test case item" in v:
            return i
    return None


def is_title_row(df: pd.DataFrame, index: int) -> bool:
    title = _normalize_text(df.iloc[index, 0])
    expected = _normalize_text(df.iloc[index, 4]) if df.shape[1] > 4 else ""
    if not title:
        return False
    if any(title.startswith(prefix) for prefix in SKIP_PREFIX):
        return False
    return expected == ""


def has_step_and_expected(df: pd.DataFrame, index: int) -> bool:
    action = _normalize_text(df.iloc[index, 0])
    expected = _normalize_text(df.iloc[index, 4]) if df.shape[1] > 4 else ""
    return bool(action) and bool(expected)


def split_numbered(text: str) -> List[Tuple[int, str]]:
    source = (text or "").strip()
    if not source:
        return []

    matches = list(STEP_SPLIT_RE.finditer(source))
    if not matches:
        lines = [ln.strip() for ln in source.splitlines() if ln.strip()]
        return [(idx + 1, ln) for idx, ln in enumerate(lines or [source])]

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


def parse_excel_cases(data: BinaryIO | BytesIO | Path, sheet: int = 0) -> Tuple[str, str, List[Dict[str, Any]]]:
    """Parse the uploaded Excel file and return folder/subfolder names plus case payloads."""

    if isinstance(data, (bytes, bytearray)):
        buffer: BytesIO | BinaryIO = BytesIO(data)
    else:
        buffer = data  # type: ignore[assignment]

    df = pd.read_excel(buffer, sheet_name=sheet, header=None)
    df = _ensure_min_columns(df)

    folder = extract_folder_name(df)
    subfolder = extract_subfolder_name(df)
    header = find_header_idx(df)

    index = (header + 1) if header is not None else 0
    order = 1
    cases: List[Dict[str, Any]] = []

    combined_folder = "/".join(part for part in (folder, subfolder) if part)

    while index < len(df) - 1:
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

                title, keywords = extract_title_and_keywords(raw_title)
                steps_split = split_numbered(steps_text)

                steps_payload = [
                    {
                        "no": number,
                        "action": action,
                        "keyword": "",
                        "note": "",
                        "expected": "",
                    }
                    for number, action in steps_split
                ]

                cases.append(
                    {
                        "order": order,
                        "folder": combined_folder or folder or subfolder,
                        "root_folder": folder,
                        "subfolder": subfolder,
                        "title": title or raw_title,
                        "keywords": keywords,
                        "expected_result": expected_text,
                        "steps": steps_payload,
                    }
                )

                order += 1
                index = inner_index + 1
                continue

        index += 1

    return folder, subfolder, cases


__all__ = [
    "parse_excel_cases",
    "extract_folder_name",
    "extract_subfolder_name",
    "split_numbered",
]


def print_case_details(case: Dict[str, Any], index: int) -> None:
    """打印单个测试用例的详细信息"""
    print(f"\n{'=' * 60}")
    print(f"测试用例 #{index + 1}")
    print(f"{'=' * 60}")
    print(f"顺序: {case.get('order', 'N/A')}")
    folder_path = case.get('folder') or 'N/A'
    print(f"文件目录: {folder_path}")
    root_folder = case.get('root_folder')
    if root_folder:
        print(f"  根目录: {root_folder}")
    subfolder = case.get('subfolder')
    if subfolder:
        print(f"  子目录: {subfolder}")
    print(f"标题: {case.get('title', 'N/A')}")
    print(f"关键词: {case.get('keywords', [])}")
    print(f"预期结果: {case.get('expected_result', 'N/A')}")

    steps = case.get('steps', [])
    if steps:
        print(f"\n测试步骤 (共{len(steps)}步):")
        print("-" * 40)
        for step in steps:
            print(f"  步骤 {step.get('no', 'N/A')}: {step.get('action', 'N/A')}")
            if step.get('keyword'):
                print(f"    关键词: {step.get('keyword')}")
            if step.get('note'):
                print(f"    备注: {step.get('note')}")
            if step.get('expected'):
                print(f"    预期: {step.get('expected')}")
    else:
        print("\n测试步骤: 无")


if __name__ == "__main__":  # pragma: no cover - manual debug helper
    sample_path = Path(__file__).with_name("01 Mouse Test information.xlsx")

    if sample_path.exists():
        print(f"🔍 正在解析Excel文件: {sample_path.name}")
        print("=" * 80)

        try:
            with sample_path.open("rb") as file:
                folder_name, subfolder_name, parsed_cases = parse_excel_cases(file)

            # 基本信息
            print(f"📁 文件夹名称: {folder_name or '未指定'}")
            print(f"📊 解析到的测试用例总数: {len(parsed_cases)}")

            if parsed_cases:
                print(f"\n🎯 开始打印所有测试用例详情...")

                # 打印每个测试用例的详细信息
                for index, case in enumerate(parsed_cases):
                    print_case_details(case, index)

                # 统计信息
                print(f"\n{'=' * 80}")
                print("📈 统计信息:")
                print(f"{'=' * 80}")

                total_steps = sum(len(case.get('steps', [])) for case in parsed_cases)
                cases_with_keywords = sum(1 for case in parsed_cases if case.get('keywords'))
                cases_with_expected = sum(1 for case in parsed_cases if case.get('expected_result'))

                print(f"总测试用例数: {len(parsed_cases)}")
                print(f"总测试步骤数: {total_steps}")
                print(f"平均每个用例步骤数: {total_steps / len(parsed_cases):.1f}")
                print(f"包含关键词的用例数: {cases_with_keywords}")
                print(f"包含预期结果的用例数: {cases_with_expected}")

                # 关键词统计
                all_keywords = []
                for case in parsed_cases:
                    all_keywords.extend(case.get('keywords', []))

                if all_keywords:
                    from collections import Counter

                    keyword_count = Counter(all_keywords)
                    print(f"\n🏷️  关键词使用频率:")
                    for keyword, count in keyword_count.most_common(10):  # 显示前10个最常用的关键词
                        print(f"  {keyword}: {count}次")

                # JSON格式输出（可选）
                print(f"\n💾 是否需要JSON格式输出? (y/N): ", end="")
                try:
                    choice = input().strip().lower()
                    if choice in ['y', 'yes']:
                        print(f"\n📄 JSON格式输出:")
                        print("-" * 80)
                        output_data = {
                            "folder_name": folder_name,
                            "total_cases": len(parsed_cases),
                            "cases": parsed_cases
                        }
                        output_data["subfolder_name"] = subfolder_name
                        print(json.dumps(output_data, ensure_ascii=False, indent=2))
                except (EOFError, KeyboardInterrupt):
                    print("跳过JSON输出")

            else:
                print("\n⚠️  未解析到任何测试用例")
                print("可能的原因:")
                print("1. Excel文件格式不符合预期")
                print("2. 文件中没有有效的测试用例数据")
                print("3. 表头识别失败")

        except Exception as e:
            print(f"❌ 解析Excel文件时发生错误: {e}")
            import traceback

            traceback.print_exc()

    else:
        print(f"❌ 示例Excel文件未找到: {sample_path}")
        print("请确保在同一目录下有名为 '01 Mouse Test information.xlsx' 的文件")
        print("或者修改代码中的文件路径")
