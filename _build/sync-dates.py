#!/usr/bin/env python3
"""Sync collection dates from markdown (source of truth) into yml + indexes.

Reads every `.md` file in each configured collection, extracts its
`<date: ... />` (English) or `<তারিখ: ... />` (Bengali) tag if present, and:
  1. Updates `_poems.yml` date field to match the md tag.
  2. For `second-seconds` only: sorts entries chronologically and regenerates
     `second-seconds/~index.md` + master `src/~index.md` second-seconds section.
     Other collections keep their hand-curated yml order.

Run whenever you update dates in any .md files:
    cd src && python3 _build/sync-dates.py && python3 _build/build.py
"""

from __future__ import annotations
import re
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent
YML = SRC / "second-seconds" / "_poems.yml"
IDX = SRC / "second-seconds" / "~index.md"
MASTER = SRC / "~index.md"
MD_DIR = SRC / "second-seconds"

# Collections that get their yml dates synced from md. `sort`=True also reorders
# entries chronologically; False preserves the hand-curated order.
COLLECTIONS = [
    {"id": "second-seconds", "sort": True},
    {"id": "sulol-songroho", "sort": False},
]

MONTH = {
    "jan": 1, "january": 1,
    "feb": 2, "february": 2,
    "mar": 3, "march": 3,
    "apr": 4, "april": 4,
    "may": 5,
    "jun": 6, "june": 6,
    "jul": 7, "july": 7,
    "aug": 8, "august": 8,
    "sep": 9, "sept": 9, "september": 9,
    "oct": 10, "october": 10,
    "nov": 11, "november": 11,
    "dec": 12, "december": 12,
    # Bengali month names (Gregorian transliteration as used in md files).
    "জানুয়ারি": 1, "ফেব্রুয়ারি": 2, "মার্চ": 3, "এপ্রিল": 4,
    "মে": 5, "জুন": 6, "জুলাই": 7, "আগস্ট": 8,
    "সেপ্টেম্বর": 9, "অক্টোবর": 10, "নভেম্বর": 11, "ডিসেম্বর": 12,
}

# Bengali → ASCII digit translation table.
BN_DIGITS = str.maketrans("০১২৩৪৫৬৭৮৯", "0123456789")


def parse_date(s: str) -> tuple[int, int, int]:
    """Parse human date strings to sortable (year, month, day). Uses the
    FIRST date in a range (e.g., 'April–May 2025' → April 1, 2025).
    Accepts Bengali digits and month names."""
    if not s:
        return (9999, 12, 31)
    s = s.strip()
    # Normalize Bengali digits to ASCII for year/day parsing.
    norm = s.translate(BN_DIGITS)
    y = re.search(r"\b(\d{4})\b", norm)
    year = int(y.group(1)) if y else 9999
    first = re.split(r"\s*[–\-]\s*(?=\d|[A-Za-z])", norm, maxsplit=1)[0].strip()
    m = re.match(r"([A-Za-zঀ-৿]+)\s*(\d{1,2})?", first)
    if m:
        month = MONTH.get(m.group(1).lower(), MONTH.get(m.group(1), 1))
        day = int(m.group(2)) if m.group(2) else 1
    else:
        month, day = 1, 1
    return (year, month, day)


def md_dates(md_dir: Path) -> dict[str, str]:
    """Scan all .md files in `md_dir` for `<date: ... />` or `<তারিখ: ... />`
    tags. Returns a {filename: date_string} map."""
    out: dict[str, str] = {}
    for p in md_dir.glob("*.md"):
        if p.name == "~index.md":
            continue
        text = p.read_text(encoding="utf-8")
        m = re.search(r"<(?:date|তারিখ):\s*([^/]+?)\s*/>", text)
        if m:
            out[p.name] = m.group(1).strip()
    return out


def sync_yml(yml_path: Path, date_map: dict[str, str], sort: bool):
    """Update yml dates from md. Sort entries chronologically if `sort`.
    Return list of (sort_key, filename, title, entry_text) — in sorted order
    if `sort`, otherwise original yml order."""
    text = yml_path.read_text(encoding="utf-8")
    header, _, body = text.partition("\npoems:\n")
    assert body, f"couldn't find 'poems:' section in {yml_path}"

    raw = [e for e in re.split(r"(?m)(?=^  - t: )", body) if e.strip()]

    fixed: list[tuple[tuple[int, int, int], str, str, str]] = []
    updates = 0
    for entry in raw:
        fm = re.search(r"^    f:\s*(\S+)\s*$", entry, flags=re.M)
        fname = fm.group(1) if fm else ""
        tm = re.search(r'^  - t:\s*"?(.+?)"?\s*$', entry, flags=re.M)
        title = tm.group(1) if tm else ""

        # If md has a date, override yml.
        if fname in date_map:
            new_date = date_map[fname]
            dm_old = re.search(r'^    date:\s*"([^"]+)"', entry, flags=re.M)
            old_date = dm_old.group(1) if dm_old else None
            if old_date != new_date:
                if old_date:
                    entry = re.sub(
                        r'^(    date:\s*)"[^"]*"',
                        lambda m_: f'{m_.group(1)}"{new_date}"',
                        entry, count=1, flags=re.M,
                    )
                else:
                    # No existing date: insert one after the `f:` line.
                    entry = re.sub(
                        r'(^    f:\s*\S+\n)',
                        lambda m_: f'{m_.group(1)}    date: "{new_date}"\n',
                        entry, count=1, flags=re.M,
                    )
                updates += 1

        dm = re.search(r'^    date:\s*"([^"]+)"', entry, flags=re.M)
        date_str = dm.group(1) if dm else ""
        fixed.append((parse_date(date_str), fname, title, entry))

    if sort:
        fixed.sort(key=lambda x: (x[0], x[2].lower()))

    out = header + "\npoems:\n" + "".join(e[3] for e in fixed)
    if not out.endswith("\n"):
        out += "\n"
    yml_path.write_text(out, encoding="utf-8")
    verb = "reordered" if sort else "in original order"
    print(f"  {yml_path.parent.name}/yml: {updates} dates updated, {len(fixed)} entries ({verb})")
    return fixed


def write_idx(sorted_entries):
    header = (
        "# Second Seconds - A Conversation with Self\n"
        "\n"
        "## Table of Contents\n"
        "\n"
    )
    lines: list[str] = []
    for i, (_, fname, title, entry) in enumerate(sorted_entries, start=1):
        dm = re.search(r'^    date:\s*"([^"]+)"', entry, flags=re.M)
        date_str = dm.group(1) if dm else ""
        suffix = f" ~ {date_str}" if date_str else ""
        lines.append(f"{i}. [{title}]({fname}){suffix}\n")
    IDX.write_text(header + "".join(lines), encoding="utf-8")
    print(f"  second-seconds/~index.md: rewritten")


def write_master(sorted_entries):
    text = MASTER.read_text(encoding="utf-8")
    hdr_re = re.compile(
        r"(?m)^(## \[Second Seconds[^\]]*\]\(second-seconds/~index\.md\)\s*\n)"
    )
    m = hdr_re.search(text)
    if not m:
        print("  [warn] master: second-seconds section not found")
        return
    start = m.end()
    next_hdr = re.search(r"(?m)^## ", text[start:])
    end = start + next_hdr.start() if next_hdr else len(text)

    has_dates = bool(re.search(r"~\s+[A-Za-z]", text[start:end]))
    parts = ["\n"]
    for i, (_, fname, title, entry) in enumerate(sorted_entries, start=1):
        if has_dates:
            dm = re.search(r'^    date:\s*"([^"]+)"', entry, flags=re.M)
            date_str = dm.group(1) if dm else ""
            parts.append(f"{i}. [{title}](second-seconds/{fname}) ~ {date_str}\n" if date_str else f"{i}. [{title}](second-seconds/{fname})\n")
        else:
            parts.append(f"{i}. [{title}](second-seconds/{fname})\n")
    parts.append("\n")

    MASTER.write_text(text[:start] + "".join(parts) + text[end:], encoding="utf-8")
    print(f"  master ~index.md: second-seconds section rewritten")


def main():
    for col in COLLECTIONS:
        cid = col["id"]
        md_dir = SRC / cid
        yml_path = SRC / cid / "_poems.yml"
        if not yml_path.exists():
            print(f"[skip] {cid}: no _poems.yml")
            continue
        date_map = md_dates(md_dir)
        print(f"{cid}: found {len(date_map)} md files with date tags")
        entries = sync_yml(yml_path, date_map, sort=col["sort"])
        # Index regen is second-seconds-specific for now.
        if cid == "second-seconds":
            write_idx(entries)
            write_master(entries)


if __name__ == "__main__":
    main()
