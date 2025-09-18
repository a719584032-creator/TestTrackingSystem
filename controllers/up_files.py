# -*- coding: utf-8 -*-
"""Utilities for parsing uploaded Excel test case files."""

from __future__ import annotations

import re
from io import BytesIO
from pathlib import Path
from typing import Any, BinaryIO, Dict, List, Tuple

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


def parse_excel_cases(data: BinaryIO | BytesIO | Path, sheet: int = 0) -> Tuple[str, List[Dict[str, Any]]]:
    """Parse the uploaded Excel file and return folder name plus case payloads."""

    if isinstance(data, (bytes, bytearray)):
        buffer: BytesIO | BinaryIO = BytesIO(data)
    else:
        buffer = data  # type: ignore[assignment]

    df = pd.read_excel(buffer, sheet_name=sheet, header=None)
    df = _ensure_min_columns(df)

    folder = extract_folder_name(df)
    header = find_header_idx(df)

    index = (header + 1) if header is not None else 0
    order = 1
    cases: List[Dict[str, Any]] = []

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
                        "folder": folder,
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

    return folder, cases


__all__ = [
    "parse_excel_cases",
    "extract_folder_name",
    "split_numbered",
]


if __name__ == "__main__":  # pragma: no cover - manual debug helper
    sample_path = Path(__file__).with_name("01 Mouse Test information.xlsx")
    if sample_path.exists():
        with sample_path.open("rb") as file:
            folder_name, parsed_cases = parse_excel_cases(file)
        print(f"Folder: {folder_name}")
        print(f"Total cases: {len(parsed_cases)}")
    else:
        print("Sample Excel file not found.")
