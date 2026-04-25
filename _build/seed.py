#!/usr/bin/env python3
"""One-shot migration: emit src/<collection>/_poems.yml from
designs/finalists/data.js (metadata) + each <collection>/~index.md (curated order).

Run once, verify output, delete this script.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

# Paths relative to this script.
ROOT = Path(__file__).resolve().parent.parent          # src/
REPO = ROOT.parent                                      # ~/src/poems/
DATA_JS = REPO / "designs" / "finalists" / "data.js"


# Hand-extracted from data.js. Source of truth for collection-level metadata
# and the "kind" overrides (limerick, draft) per poem file.
COLLECTION_META: dict[str, dict[str, Any]] = {
    "sulol-songroho": {
        "title": "সুলল সংগ্রহ",
        "roman": "Sulol Songroho",
        "blurb": "early earnest Bengali verses",
        "lang": "bn",
        "icon": "🌿",
    },
    "second-seconds": {
        "title": "Second Seconds",
        "subtitle": "A Conversation with Self",
        "blurb": "a conversation with self",
        "lang": "mixed",
        "icon": "🪞",
    },
    "semi-structured-output": {
        "title": "Semi-structured Output",
        "blurb": "an analysis of the surroundings",
        "lang": "en",
        "icon": "⚙",
    },
    "life-untitled": {
        "title": "Life, Untitled",
        "blurb": "yet to be written",
        "lang": "en",
        "icon": "🪷",
    },
    "other-scripts": {
        "title": "Other Scripts",
        "blurb": "stanzas for future poems",
        "lang": "mixed",
        "icon": "🖋",
    },
}

# Per-file kind/lang overrides extracted from data.js. Keyed by bare filename
# (no directory). Files not listed here inherit the collection's default lang.
POEM_KINDS: dict[str, dict[str, str]] = {
    # sulol-songroho
    "limerick-1.md": {"kind": "limerick"},
    "limerick-2.md": {"kind": "limerick"},
    "limerick-3.md": {"kind": "limerick"},
    "limerick-4.md": {"kind": "limerick"},
    "limerick-5.md": {"kind": "limerick"},
    "limerick-6.md": {"kind": "limerick"},
    "limerick-7.md": {"kind": "limerick"},
    "limerick-8.md": {"kind": "limerick"},
    "limerick-9.md": {"kind": "limerick"},
    "limerick-10.md": {"kind": "limerick"},
    # second-seconds
    "a-monument-draft.md": {"kind": "draft"},
}

# Margin notes from 410-rc.html (prefix-match on lowercased title, first ~12 chars).
# Moved into each poem entry so the yaml is the only place that holds them.
MARGIN_NOTES: dict[str, str] = {
    "inventory of": "(auction notes!)",
    "view from my": "written on couch",
    "a settlement": "came in one sit",
    "cluttered wi": "yes, exactly this",
    "shattered sw": "the hard one",
    "numbed angui": "keep returning",
    "freedom to b": "question or stat",
    "amber abluti": "love the light",
    "an erosion":   "slow & right",
    "confetti":     "like rain, like",
    "the ice-crea": "summer of '18?",
    "the faithful": "contradiction",
    "barramundi r": "unexpected joy",
    "the tulip":    "delicate force",
    "l's dancefl":  "heard the music",
    "a view from":  "altitude = clarity",
    "a very good":  "this bird! yes",
    "shrimp wonto": "thursday night",
    "8th and 14th": "two dates, one",
    "a walk?":      "question mark earns",
    "just here":    "just here. period.",
    "blunt":        "shortest & sharpest",
    "a bicycle an": "still life, moving",
    "lavender mil": "colour as distance",
    "worlds":       "plural, always",
    "a monument (": "still drafting",
    "they are the": "presence, not ghost",
    "lull":         "the pause breathes",
    "wing":         "one word, whole sky",
    "company":      "who is with you?",
    "shadow's edg": "liminal — exact",
    "stable":       "a verb not a noun",
    "she":          "just the pronoun",
    "saratoga sce": "place becomes poem",
    "the system":   "also: every system",
    "the ventril":  "who speaks? who hears?",
    "tab 16":       "open tabs = open",
    "shorts":       "compressed, potent",
    "seeds / blur": "origin materials",
    "exemplary po": "what is exemplary?",
}


def lookup_margin(title: str) -> str | None:
    """Match margin note by prefix (same algorithm as the original 410-rc theme)."""
    key = title.lower()[:12]
    for k, v in MARGIN_NOTES.items():
        n = min(len(k), len(key))
        if key[:n] == k[:n]:
            return v
    return None


# Regex for numbered markdown links: "N. [title](file.md) ~ optional date"
INDEX_RE = re.compile(r"^\s*\d+\.\s*\[([^\]]+)\]\(([^)]+\.md)\)\s*(?:~\s*(.+))?\s*$")


def parse_index(path: Path) -> list[tuple[str, str, str | None]]:
    """Return [(title, filename, date_or_None), ...] in the order listed."""
    if not path.exists():
        return []
    out: list[tuple[str, str, str | None]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        m = INDEX_RE.match(line)
        if m:
            title, filename, date = m.group(1), m.group(2), m.group(3)
            # Skip self-references
            if filename.startswith("~index"):
                continue
            out.append((title, filename, date.strip() if date else None))
    return out


def detect_lang(text: str, default: str) -> str:
    """Bengali is U+0980–U+09FF. Return 'bn' if any Bengali char present."""
    for ch in text:
        if "\u0980" <= ch <= "\u09ff":
            return "bn"
    return default if default != "mixed" else "en"


def to_yaml(collection_id: str) -> str:
    meta = COLLECTION_META[collection_id]
    coll_dir = ROOT / collection_id
    index_path = coll_dir / "~index.md"
    entries = parse_index(index_path)

    lines: list[str] = []
    lines.append(f"# Per-book manifest for {collection_id}.")
    lines.append("# Edit this file to reorder poems, add new ones, or update metadata.")
    lines.append("# The build script generates the live site from this + the .md files.")
    lines.append("")
    lines.append(f"id: {collection_id}")
    # Scalar fields in the order a reader would expect.
    for key in ("title", "subtitle", "roman", "blurb", "lang", "icon"):
        if key in meta:
            val = meta[key]
            # Quote strings that contain YAML-special chars or non-ASCII handled by unicode.
            if isinstance(val, str) and any(c in val for c in [":", "'", '"', "#", "["]):
                esc = val.replace('"', '\\"')
                lines.append(f'{key}: "{esc}"')
            elif isinstance(val, str):
                lines.append(f"{key}: {val}")
            else:
                lines.append(f"{key}: {val}")
    lines.append("")
    lines.append("poems:")
    if not entries:
        lines.append("  []")
    else:
        for title, filename, date in entries:
            bare = filename.rsplit("/", 1)[-1]
            lang = detect_lang(title, meta.get("lang", "en"))
            # Quote title safely for YAML
            t_quoted = '"' + title.replace('"', '\\"') + '"'
            lines.append(f"  - t: {t_quoted}")
            lines.append(f"    f: {filename}")
            lines.append(f"    lang: {lang}")
            if bare in POEM_KINDS:
                k = POEM_KINDS[bare].get("kind")
                if k:
                    lines.append(f"    kind: {k}")
            if date:
                d_quoted = '"' + date.replace('"', '\\"') + '"'
                lines.append(f"    date: {d_quoted}")
            note = lookup_margin(title)
            if note:
                n_quoted = '"' + note.replace('"', '\\"') + '"'
                lines.append(f"    note: {n_quoted}")
    return "\n".join(lines) + "\n"


def main() -> None:
    for cid in COLLECTION_META:
        out_path = ROOT / cid / "_poems.yml"
        yaml = to_yaml(cid)
        out_path.write_text(yaml, encoding="utf-8")
        entries = parse_index(ROOT / cid / "~index.md")
        print(f"wrote {out_path.relative_to(REPO)} ({len(entries)} poems)")


if __name__ == "__main__":
    main()
