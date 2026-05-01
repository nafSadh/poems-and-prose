#!/usr/bin/env python3
"""Sort second-seconds by date and regenerate index files.

Dates live in each `.md` as `<date: ... />` (English) or `<তারিখ: ... />`
(Bengali). For `second-seconds` only, this script reorders the entries in
`_contents.yml` chronologically by md date and rewrites
`second-seconds/~index.md` and the master `src/~index.md` second-seconds
section to match.

`_contents.yml` no longer carries `date:` lines — the .md is the single source
of truth for dates.

Run whenever you update dates in any second-seconds .md files:
    cd src && python3 _build/sync-dates.py && python3 _build/build.py
"""

from __future__ import annotations
import re
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent
YML = SRC / "second-seconds" / "_contents.yml"
IDX = SRC / "second-seconds" / "~index.md"
MASTER = SRC / "~index.md"
MD_DIR = SRC / "second-seconds"

# Collections that get sorted by md date. Only second-seconds today; others
# keep their hand-curated yml order, so they don't appear here.
COLLECTIONS = [
    {"id": "second-seconds", "sort": True},
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


# Polymorphic content type-keys (mirrors CONTENT_TYPES in build.py).
TYPE_KEY_RE = r"(?:poem|story|article|prose|essay)"


def sort_yml(yml_path: Path, date_map: dict[str, str], sort: bool):
    """Walk yml entries and (optionally) reorder them by md date. Return list
    of (sort_key, fname_with_md, title, entry_text) — in sorted order if
    `sort`, else original yml order. `fname_with_md` is the bare md filename
    (id + ".md") so date_map lookups still work.

    Supports both flat (`  - poem: …`) and sectioned (`      - poem: …` under
    `  - section:` / `    entries:`) layouts. For sectioned manifests the
    sort happens INSIDE each section; section order itself is preserved."""
    text = yml_path.read_text(encoding="utf-8")
    header, _, body = text.partition("\ncontents:\n")
    assert body, f"couldn't find 'contents:' section in {yml_path}"

    # Split body into flat entries OR section blocks. A section block starts
    # at `^  - section: ` and runs until the next section or EOF.
    section_re = re.compile(r"(?m)(?=^  - section: )")
    flat_entry_re = re.compile(rf"(?m)(?=^  - {TYPE_KEY_RE}: )")

    fixed: list[tuple[tuple[int, int, int], str, str, str]] = []

    if section_re.search(body):
        # Sectioned: split into sections, sort entries within each.
        sections = [s for s in section_re.split(body) if s.strip()]
        rebuilt: list[str] = []
        for sec in sections:
            # Header is everything up to the first nested entry; entries are
            # 6-space indented and prefixed with a type-key.
            entry_re = re.compile(rf"(?m)(?=^      - {TYPE_KEY_RE}: )")
            parts = entry_re.split(sec)
            sec_header = parts[0]
            sec_entries = [e for e in parts[1:] if e.strip()]
            sec_fixed: list[tuple[tuple[int, int, int], str, str, str]] = []
            for entry in sec_entries:
                im = re.search(r"^        id:\s*(\S+)\s*$", entry, flags=re.M)
                item_id = im.group(1) if im else ""
                fname = f"{item_id}.md" if item_id else ""
                tm = re.search(rf'^      - {TYPE_KEY_RE}:\s*"?(.+?)"?\s*$', entry, flags=re.M)
                title = tm.group(1) if tm else ""
                date_str = date_map.get(fname, "")
                sec_fixed.append((parse_date(date_str), fname, title, entry))
            if sort:
                sec_fixed.sort(key=lambda x: (x[0], x[2].lower()))
            fixed.extend(sec_fixed)
            rebuilt.append(sec_header + "".join(e[3] for e in sec_fixed))
        new_body = "".join(rebuilt)
    else:
        # Flat layout.
        raw = [e for e in flat_entry_re.split(body) if e.strip()]
        for entry in raw:
            im = re.search(r"^    id:\s*(\S+)\s*$", entry, flags=re.M)
            item_id = im.group(1) if im else ""
            fname = f"{item_id}.md" if item_id else ""
            tm = re.search(rf'^  - {TYPE_KEY_RE}:\s*"?(.+?)"?\s*$', entry, flags=re.M)
            title = tm.group(1) if tm else ""
            date_str = date_map.get(fname, "")
            fixed.append((parse_date(date_str), fname, title, entry))
        if sort:
            fixed.sort(key=lambda x: (x[0], x[2].lower()))
        new_body = "".join(e[3] for e in fixed)

    if sort:
        out = header + "\ncontents:\n" + new_body
        if not out.endswith("\n"):
            out += "\n"
        yml_path.write_text(out, encoding="utf-8")
        print(f"  {yml_path.parent.name}/yml: {len(fixed)} entries reordered by md date")
    else:
        print(f"  {yml_path.parent.name}/yml: {len(fixed)} entries (order preserved)")
    return fixed


def write_idx(sorted_entries, date_map: dict[str, str]):
    header = (
        "# Second Seconds - A Conversation with Self\n"
        "\n"
        "## Table of Contents\n"
        "\n"
    )
    lines: list[str] = []
    for i, (_, fname, title, _entry) in enumerate(sorted_entries, start=1):
        date_str = date_map.get(fname, "")
        suffix = f" ~ {date_str}" if date_str else ""
        lines.append(f"{i}. [{title}]({fname}){suffix}\n")
    IDX.write_text(header + "".join(lines), encoding="utf-8")
    print(f"  second-seconds/~index.md: rewritten")


def write_master(sorted_entries, date_map: dict[str, str]):
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
    for i, (_, fname, title, _entry) in enumerate(sorted_entries, start=1):
        if has_dates:
            date_str = date_map.get(fname, "")
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
        yml_path = SRC / cid / "_contents.yml"
        if not yml_path.exists():
            print(f"[skip] {cid}: no _contents.yml")
            continue
        date_map = md_dates(md_dir)
        print(f"{cid}: found {len(date_map)} md files with date tags")
        entries = sort_yml(yml_path, date_map, sort=col["sort"])
        # Index regen is second-seconds-specific for now.
        if cid == "second-seconds":
            write_idx(entries, date_map)
            write_master(entries, date_map)


if __name__ == "__main__":
    main()
