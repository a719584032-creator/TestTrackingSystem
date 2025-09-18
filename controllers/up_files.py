# -*- coding: utf-8 -*-
# Update parser per new rules:
# - keywords: array of strings WITHOUT brackets, e.g. ["时间+1","S3+5"]
# - steps: keep expected empty in each step dict
# - case-level expected_result: put the entire expected_text
import re, json
import pandas as pd
from pathlib import Path


SRC = Path(r"C:\Users\71958\Downloads\01 Mouse Test information.xlsx")
SHEET = 0

SKIP_PREFIX = ('Section :', 'Workloading :', 'Leadingtime :', 'Phase :', 'Test Log Mandatory :')
STEP_SPLIT_RE = re.compile(r'(?:^|\n)\s*(\d+)[\.\)\、:：]\s*', re.M)
TITLE_KEYWORD_RE = re.compile(r'\[([^\]]+)\]')  # capture inner token

def extract_folder_name(df):
    return str(df.iloc[1, 3]).strip() if pd.notna(df.iloc[1, 3]) else ""

def find_header_idx(df):
    for i in range(len(df)):
        v = str(df.iloc[i, 0]) if pd.notna(df.iloc[i, 0]) else ""
        if "Test case item" in v:
            return i
    return None

def is_title_row(df, i):
    a = df.iloc[i, 0]; e = df.iloc[i, 4] if df.shape[1] > 4 else None
    if pd.isna(a) or str(a).strip()=="":
        return False
    a = str(a).strip()
    if any(a.startswith(k) for k in SKIP_PREFIX):
        return False
    return (pd.isna(e) or str(e).strip()=="")

def has_step_and_expected(df, i):
    a = df.iloc[i, 0]; e = df.iloc[i, 4] if df.shape[1] > 4 else None
    return pd.notna(a) and str(a).strip()!="" and pd.notna(e) and str(e).strip()!=""

def split_numbered(text: str):
    s = (text or "").strip()
    if not s: return []
    parts, ms = [], list(STEP_SPLIT_RE.finditer(s))
    if ms:
        if ms[0].start()!=0:
            head = s[:ms[0].start()].strip()
            if head: parts.append((1, head))
        for i, m in enumerate(ms):
            no = int(m.group(1))
            start, end = m.end(), (ms[i+1].start() if i+1<len(ms) else len(s))
            chunk = s[start:end].strip()
            if chunk: parts.append((no, chunk))
    else:
        lines = [ln.strip() for ln in s.splitlines() if ln.strip()]
        parts = [(i+1, ln) for i, ln in enumerate(lines or [""])]
    return parts

def extract_title_and_keywords(title: str):
    s = title or ""
    # keywords: inner token without brackets, trimmed
    kws = [m.strip() for m in TITLE_KEYWORD_RE.findall(s)]
    cleaned = TITLE_KEYWORD_RE.sub('', s).strip()
    cleaned = re.sub(r'\s{2,}', ' ', cleaned).strip(' -—_/')
    return cleaned, kws

def parse_excel(path: Path, sheet):
    df = pd.read_excel(path, sheet_name=sheet, header=None)
    df.columns = ['A','B','C','D','E','F','G','H']
    folder = extract_folder_name(df)
    header = find_header_idx(df)

    i = (header + 1) if header is not None else 0
    order, cases, preview_rows = 1, [], []
    while i < len(df)-1:
        if is_title_row(df, i):
            raw_title = str(df.iloc[i,0]).strip()
            j = i + 1
            while j < len(df) and not has_step_and_expected(df, j):
                if is_title_row(df, j): break
                j += 1
            if j < len(df) and has_step_and_expected(df, j):
                steps_text = str(df.iloc[j,0]).strip()
                expected_text = str(df.iloc[j,4]).strip()

                title, keywords = extract_title_and_keywords(raw_title)
                steps_split = split_numbered(steps_text)

                steps_payload = [{
                    "no": no,
                    "action": act,
                    "keyword": "",
                    "note": "",
                    "expected": ""     # step-level expected intentionally empty
                } for no, act in steps_split]

                cases.append({
                    "order": order,
                    "folder": folder,
                    "title": title,
                    "keywords": keywords,           # e.g. ["时间+1","S3+5"]
                    "expected_result": expected_text,  # full expected into case field
                    "steps": steps_payload
                })

                preview_rows.append({
                    "order": order,
                    "folder": folder,
                    "raw_title": raw_title,
                    "title": title,
                    "keywords": ", ".join(keywords),
                    "expected_result": expected_text,
                    "steps_obj": json.dumps(steps_payload, ensure_ascii=False)
                })
                order += 1
                i = j + 1
                continue
        i += 1
    return folder, cases, pd.DataFrame(preview_rows)

folder, cases, preview_df = parse_excel(SRC, SHEET)

# outputs
json_path = "test_cases_for_backend_v2.json"
xlsx_path = "test_cases_for_backend_v2.xlsx"
with open(json_path, "w", encoding="utf-8") as f:
    json.dump(cases, f, ensure_ascii=False, indent=2)
preview_df.to_excel(xlsx_path, index=False)

# display_dataframe_to_user("Parsed Cases (v2 preview)", preview_df)

print(f"Folder: {folder}")
print(f"Total cases: {len(cases)}")
print(f"JSON saved to: {json_path}")
print(f"XLSX saved to: {xlsx_path}")
print("\n--- FULL JSON ---\n")
print(json.dumps(cases, ensure_ascii=False, indent=2))
