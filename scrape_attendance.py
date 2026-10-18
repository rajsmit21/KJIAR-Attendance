#!/usr/bin/env python3
"""Fetch the college's public attendance page and write attendance-data.json.
Uses requests plus Python standard-library parsing only.
"""
import csv
import html
import json
import os
import re
import sys
from datetime import datetime, timezone
from urllib.request import Request, urlopen

try:
    import requests
except ImportError:
    print("Missing requests. Install with: python -m pip install requests", file=sys.stderr)
    raise

URL = "https://www.kjiar.edu.in/9-2-msr-ccim/attendance/students"
OUTPUT = "attendance-data.json"
# Current BAMS First Professional cohort; edit if the college changes its enrollment range.
ENROLLMENT_MIN = int(os.getenv("ENROLLMENT_MIN", "2501"))
ENROLLMENT_MAX = int(os.getenv("ENROLLMENT_MAX", "2560"))
MONTH_ORDER = [
    "December 2025", "January 2026", "February 2026", "March 2026",
    "April 2026", "May 2026", "June 2026", "July 2026",
    "August 2026", "September 2026", "October 2026", "November 2026",
    "December 2026"
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; AttendWiseStudentTracker/1.0)",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

def clean(value):
    value = re.sub(r"(?is)<br\s*/?>", " / ", value)
    value = re.sub(r"(?is)<[^>]+>", " ", value)
    value = html.unescape(value)
    return re.sub(r"\s+", " ", value).strip()

def parse_rows(section):
    output = []
    for row_html in re.findall(r"<tr\b[^>]*>(.*?)</tr\s*>", section, re.I | re.S):
        cells = []
        for cell in re.findall(r"<t[dh]\b[^>]*>(.*?)</t[dh]\s*>", row_html, re.I | re.S):
            cells.append(clean(cell))
        if cells:
            output.append(cells)
    return output

def expand_header(section):
    grid = []
    pending = {}
    for row_html in re.findall(r"<tr\b[^>]*>(.*?)</tr\s*>", section, re.I | re.S):
        row, col = [], 0
        cells = re.findall(r"<t[dh]\b([^>]*)>(.*?)</t[dh]\s*>", row_html, re.I | re.S)
        def fill():
            nonlocal col
            while col in pending:
                val, rem = pending[col]
                row.append(val)
                if rem > 1:
                    pending[col] = (val, rem - 1)
                else:
                    del pending[col]
                col += 1
        for attrs, content in cells:
            fill()
            val = clean(content)
            cm = re.search(r'\bcolspan\s*=\s*["\']?(\d+)', attrs, re.I)
            rm = re.search(r'\browspan\s*=\s*["\']?(\d+)', attrs, re.I)
            colspan = int(cm.group(1)) if cm else 1
            rowspan = int(rm.group(1)) if rm else 1
            for off in range(colspan):
                row.append(val)
                if rowspan > 1:
                    pending[col + off] = (val, rowspan - 1)
            col += colspan
        fill()
        if row:
            grid.append(row)
    return grid

def normalize_subject(label):
    label = re.sub(r"\s*/?\s*\(AyUG-[^)]+\)", "", label, flags=re.I).strip()
    label = re.sub(r"\s+", " ", label).strip(" /-`")
    label = label.replace("SAMHITA ADHYAYAN - 1", "SAMHITA ADHYAYAN-1")
    return label

def month_from_context(page, table_start):
    before = page[max(0, table_start - 1800):table_start]
    headings = re.findall(r"<h[1-6]\b[^>]*>(.*?)</h[1-6]\s*>", before, re.I | re.S)
    if not headings:
        return None
    title = clean(headings[-1])
    match = re.search(r"Attendance\s*:\s*([A-Za-z]+\s+\d{4})", title, re.I)
    return match.group(1).title() if match else None

def parse_page(page):
    students = {}
    months_found = set()
    table_matches = list(re.finditer(r"<table\b[^>]*>(.*?)</table\s*>", page, re.I | re.S))

    for table_match in table_matches:
        table_html = table_match.group(1)
        month = month_from_context(page, table_match.start())
        if not month:
            continue

        thead = re.search(r"<thead\b[^>]*>(.*?)</thead\s*>", table_html, re.I | re.S)
        tbody = re.search(r"<tbody\b[^>]*>(.*?)</tbody\s*>", table_html, re.I | re.S)
        if not thead or not tbody:
            continue

        header_grid = expand_header(thead.group(1))
        body_rows = parse_rows(tbody.group(1))
        if not header_grid or not body_rows:
            continue

        width = max(len(r) for r in header_grid)
        headers = []
        for i in range(width):
            parts = []
            for hr in header_grid:
                if i < len(hr):
                    value = hr[i].strip()
                    if value and (not parts or parts[-1] != value):
                        parts.append(value)
            headers.append(" - ".join(parts))

        # Locate the stable identifying columns.
        enrollment_idx = next((i for i,h in enumerate(headers) if "enroll" in h.lower()), None)
        name_idx = next((i for i,h in enumerate(headers) if "name of student" in h.lower()), None)
        if enrollment_idx is None or name_idx is None:
            # Fallback to common first columns: serial, enrollment, name.
            enrollment_idx, name_idx = 1, 2

        months_found.add(month)
        for row in body_rows:
            if len(row) <= max(enrollment_idx, name_idx):
                continue
            enrollment = row[enrollment_idx].strip()
            name = row[name_idx].strip()
            if not enrollment.isdigit() or not name:
                continue
            number = int(enrollment)
            if not ENROLLMENT_MIN <= number <= ENROLLMENT_MAX:
                continue

            subjects = {}
            for i, header in enumerate(headers):
                if i >= len(row):
                    continue
                h = header.strip()
                match = re.match(r"(.+?)\s*-\s*(Theory|NLHT\s*\+\s*NLHP)\s*$", h, re.I)
                if not match:
                    continue
                subject = normalize_subject(match.group(1))
                stream = re.sub(r"\s+", " ", match.group(2)).upper()
                try:
                    value = float(row[i].replace("%", "").strip())
                except (ValueError, AttributeError):
                    continue
                if not 0 <= value <= 100:
                    continue
                subjects.setdefault(subject, {})[stream] = value

            if not subjects:
                continue
            student = students.setdefault(enrollment, {
                "enrollment": enrollment, "name": name, "months": {}
            })
            student["name"] = name
            # Prefer the last matching table for a month if duplicate table fragments occur.
            student["months"][month] = {"subjects": subjects}

    if not students:
        raise RuntimeError(
            "No student records extracted. The website layout may have changed or blocked the request; "
            "keeping the previous data file."
        )

    months = sorted(
        months_found,
        key=lambda m: (int(re.search(r"\d{4}", m).group()), 
                       ["January","February","March","April","May","June","July","August","September","October","November","December"].index(m.split()[0]))
    )
    return {
        "source": URL,
        "generatedAt": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
        "cohort": f"BAMS First Professional (enrollment numbers {ENROLLMENT_MIN}–{ENROLLMENT_MAX})",
        "months": months,
        "students": sorted(students.values(), key=lambda s: int(s["enrollment"])),
        "note": "Calculated from publicly displayed attendance percentages; verify official requirements with the college."
    }

def main():
    old = None
    if os.path.exists(OUTPUT):
        try:
            with open(OUTPUT, encoding="utf-8") as f:
                old = json.load(f)
        except Exception:
            old = None

    response = requests.get(URL, headers=HEADERS, timeout=90)
    response.raise_for_status()
    if len(response.text) < 10000:
        raise RuntimeError("Response is unexpectedly small; refusing to overwrite existing data.")

    data = parse_page(response.text)
    # Keep the old good data if the source unexpectedly returns far fewer records.
    if old and len(data["students"]) < max(10, int(len(old.get("students", [])) * 0.5)):
        raise RuntimeError("Extracted student count dropped sharply; refusing to overwrite existing data.")

    with open(OUTPUT, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
    print(f"Updated {OUTPUT}: {len(data['students'])} students, {len(data['months'])} months.")

if __name__ == "__main__":
    main()
