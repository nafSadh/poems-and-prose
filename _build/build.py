#!/usr/bin/env python3
"""Static-site generator for poems.nafsadh.com.

Reads:  src/_site.yml, src/<collection>/_contents.yml, src/<collection>/*.md
Writes: src/_site/**  (home, book, content pages; all pre-rendered HTML)

Each content item becomes its own page at /<collection>/<id>/ for clean URLs.
The generated tree is what the GitHub Actions workflow uploads to Pages.

Each entry in `contents:` uses a polymorphic type-key for its title:
    - poem: "Title"      → rendered as a poem (stanzas, line-break preserved)
    - story: "Title"     → rendered as prose
    - article: "Title"   → rendered as prose
The key name doubles as the type indicator; the value is the title.
"""

from __future__ import annotations

import html
import re
import shutil
import sys
import unicodedata
from pathlib import Path

try:
    import yaml
except ImportError:
    sys.exit("missing dependency: pip install pyyaml")


# ── Paths ─────────────────────────────────────────────────────────────────────
SRC = Path(__file__).resolve().parent.parent
TEMPLATES = SRC / "_build" / "templates"
OUT = SRC / "_site"

ROMAN = ["I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X"]
P_ROMAN = [
    "i", "ii", "iii", "iv", "v", "vi", "vii", "viii", "ix", "x",
    "xi", "xii", "xiii", "xiv", "xv", "xvi", "xvii", "xviii", "xix", "xx",
    "xxi", "xxii", "xxiii", "xxiv", "xxv", "xxvi", "xxvii", "xxviii", "xxix", "xxx",
    "xxxi", "xxxii", "xxxiii", "xxxiv", "xxxv", "xxxvi", "xxxvii", "xxxviii", "xxxix", "xl",
    "xli", "xlii", "xliii", "xliv", "xlv", "xlvi", "xlvii", "xlviii", "xlix", "l",
]


# ── Templates / substitution ──────────────────────────────────────────────────
SVG_DIR = SRC / "_svg"


def load_templates() -> dict[str, str]:
    names = ["base.html", "home.html", "book.html", "poem.html"]
    out = {n: (TEMPLATES / n).read_text(encoding="utf-8") for n in names}
    # SVG defs live under _svg/ (theme symbols + per-collection art).
    defs = (SVG_DIR / "defs.html").read_text(encoding="utf-8")
    extras: list[str] = []
    for p in sorted(SVG_DIR.glob("art-*.html")):
        extras.append(f"    <!-- from {p.name} -->\n    " + p.read_text(encoding="utf-8").strip())
    if extras:
        injected = "\n" + "\n".join(extras) + "\n  "
        defs = defs.replace("</defs>", injected + "</defs>", 1)
        # Also emit the merged defs so _svg/preview.html can pick them up.
        # This file is a build artifact; safe to blow away.
        (SVG_DIR / "_all-symbols.html").write_text(defs, encoding="utf-8")
    out["svg-defs.html"] = defs
    return out


def subst(tpl: str, vars: dict[str, str]) -> str:
    out = tpl
    for k, v in vars.items():
        out = out.replace("{{" + k + "}}", v)
    return out


# ── Config loading ────────────────────────────────────────────────────────────
def load_site_config() -> dict:
    return yaml.safe_load((SRC / "_site.yml").read_text(encoding="utf-8"))


# Polymorphic content types. Each entry in `contents:` uses one of these as its
# key, with the title as its value (e.g. `- poem: "Title"`, `- story: "Title"`).
CONTENT_TYPES = ("poem", "story", "article", "prose", "essay")


def item_type_and_title(p: dict) -> tuple[str, str]:
    """Extract (type, title) from a content entry. The first matching type-key
    wins; raises KeyError if none is present."""
    for k in CONTENT_TYPES:
        if k in p:
            return k, p[k]
    raise KeyError(f"content entry missing a type key (one of {CONTENT_TYPES}): {p!r}")


# Display-word for the home card's "<n> <word>" meta. If a collection is
# all-one-type, use that type; otherwise "pieces". `prose` stays singular.
TYPE_PLURALS = {
    "poem": ("poem", "poems"),
    "story": ("story", "stories"),
    "article": ("article", "articles"),
    "essay": ("essay", "essays"),
    "prose": ("prose", "prose"),
}


def count_word(pages: list[dict], cnt: int) -> str:
    types = {item_type_and_title(p)[0] for p in pages}
    if len(types) == 1:
        sg, pl = TYPE_PLURALS[next(iter(types))]
        return sg if cnt == 1 else pl
    return "piece" if cnt == 1 else "pieces"


def load_collections(site_cfg: dict) -> list[dict]:
    """Merge _site.yml collection entries (order + glyph IDs) with each
    collection's _contents.yml (title, metadata, contents)."""
    result = []
    for entry in site_cfg["collections"]:
        cid = entry["id"]
        yml_path = SRC / cid / "_contents.yml"
        if not yml_path.exists():
            print(f"  [skip] {cid}: no _contents.yml", file=sys.stderr)
            continue
        book = yaml.safe_load(yml_path.read_text(encoding="utf-8"))
        book.setdefault("contents", [])
        book["ill"] = entry.get("ill", "ill-life")
        book["mark"] = entry.get("mark", "mark-life")
        book["corner"] = entry.get("corner", "")
        book["pool"] = entry.get("pool") or []
        result.append(book)
    return result


# ── Markdown → stanza HTML (mirrors 410-rc.html renderBody) ───────────────────
HEAD_RE = re.compile(r"^(#{1,3}\s+.+)$", re.M)
STANZA_SPLIT_RE = re.compile(r"\n\s*\n")


PROSE_TYPES = {"story", "article", "prose", "essay"}


def inline_md(esc: str) -> str:
    """Apply inline markdown contracts to an HTML-escaped string. Order matters:
    code spans first (their contents are opaque and shouldn't be re-processed),
    then **bold** / __bold__ before single-marker italics, then ~~strike~~,
    then links. Underscore italics use word-boundary guards so `snake_case`
    is left alone."""
    # Code: `x` → <code>x</code>. Done first so emphasis markers inside code
    # stay literal. Backslash-escape the contents to dodge later regex passes.
    def _code_sub(m):
        body = m.group(1).replace("\\", r"\\")
        return f"<code>{body}</code>"
    esc = re.sub(r"`([^`\n]+)`", _code_sub, esc)
    # Links: [text](url) → <a href="url">text</a>
    esc = re.sub(r"\[([^\]]+)\]\(([^)\s]+)\)", r'<a href="\2">\1</a>', esc)
    # Bold (both markers) before italics so the leftovers are unambiguous.
    esc = re.sub(r"\*\*([^*\n]+)\*\*", r"<strong>\1</strong>", esc)
    esc = re.sub(r"(?<!\w)__([^_\n]+?)__(?!\w)", r"<strong>\1</strong>", esc)
    # Italics: *x* and _x_. Underscore form needs word-boundary guards so
    # identifiers like `snake_case` aren't mangled.
    esc = re.sub(r"\*([^*\n]+)\*", r"<em>\1</em>", esc)
    esc = re.sub(r"(?<!\w)_([^_\n]+?)_(?!\w)", r"<em>\1</em>", esc)
    # Strikethrough: ~~x~~ → <s>x</s>
    esc = re.sub(r"~~([^~\n]+)~~", r"<s>\1</s>", esc)
    return esc


def render_body(text: str, content_type: str = "poem") -> str:
    """Convert markdown body to HTML.
    - `#`/`##` headings (after the first `#` title is stripped in parse_poem_md)
      become section titles — use this for diptychs / multi-part pieces.
    - `###` becomes a small uppercase variant label (for alt drafts etc.).
    - `> text` lines become <blockquote class="poem-quote">.
    - Blank lines split content into chunks.
    - Per-chunk rendering depends on `content_type`:
      * poem (default): <div class="stanza"> with line breaks preserved as <br>.
      * prose/story/article/essay: <p class="prose-para"> with source line breaks
        collapsed to spaces (browser handles wrapping).
    - A standalone chunk of `---` / `***` / `___` becomes <hr class="md-hr">.
    - Inline transforms (see `inline_md`): *x* / _x_ → <em>, **x** / __x__ →
      <strong>, ~~x~~ → <s>, `x` → <code>, [text](url) → <a>, plus the
      poem-specific escapes `\\-` → — and `\\!` → !.
    - Hard line break (`<sp><sp>\\n`) becomes <br> in both prose and poems
      (markdown convention). Poems additionally treat any newline as <br> for
      stanza shape; prose collapses other newlines to spaces.
    """
    is_prose = content_type in PROSE_TYPES
    parts = HEAD_RE.split(text)
    chunks: list[str] = []
    for part in parts:
        part = part.strip()
        if not part:
            continue
        hm = HEAD_RE.match(part)
        if hm:
            level = len(re.match(r"^(#+)", part).group(1))
            label = re.sub(r"^#{1,3}\s+", "", part)
            chunks.append('<hr class="variant-sep">')
            if level <= 2:
                chunks.append(f'<h2 class="sub-poem-title">{html.escape(label)}</h2>')
            else:
                chunks.append(f'<div class="variant-label">{html.escape(label)}</div>')
        else:
            for stanza in STANZA_SPLIT_RE.split(part):
                s = stanza.strip()
                if not s:
                    continue
                # Horizontal rule: a chunk that is just `---`/`***`/`___` (3+ chars).
                if re.fullmatch(r"(?:-{3,}|\*{3,}|_{3,})", s):
                    chunks.append('<hr class="md-hr">')
                    continue
                # Blockquote: every non-empty line starts with `>`.
                lines = s.split("\n")
                if all(line.strip().startswith(">") for line in lines if line.strip()):
                    cleaned = "\n".join(
                        line.strip().lstrip(">").strip() for line in lines if line.strip()
                    )
                    esc = html.escape(cleaned)
                    esc = esc.replace("\n", " ") if is_prose else esc.replace("\n", "<br>")
                    chunks.append(f'<blockquote class="poem-quote">{inline_md(esc)}</blockquote>')
                    continue
                esc = html.escape(s)
                # Restore the markdown-specific escapes AFTER HTML escaping so <>& stay safe.
                esc = esc.replace("\\-", "—").replace("\\!", "!")
                if is_prose:
                    # Honor the markdown hard-break convention (two trailing spaces
                    # before a newline) before collapsing the rest of the wrapping.
                    esc = esc.replace("  \n", "<br>")
                    esc = re.sub(r"\s*\n\s*", " ", esc)
                else:
                    # Poetry: double-space + newline → <br> (the markdown hard-break
                    # convention); plain newline also breaks for stanza shape.
                    esc = esc.replace("  \n", "<br>").replace("\n", "<br>")
                esc = inline_md(esc)
                tag = "p" if is_prose else "div"
                cls = "prose-para" if is_prose else "stanza"
                chunks.append(f'<{tag} class="{cls}">{esc}</{tag}>')
    return "\n".join(chunks)


def parse_poem_md(path: Path, fallback_title: str, content_type: str = "poem") -> tuple[str, str, int, str]:
    """Return (title, rendered_html_body, longest_line_chars, author). Strips
    YAML front matter and HTML comments first (so `<!-- … -->` notes in the .md
    never reach the page), then pulls the first `# Heading` line as the title
    (falls back to yml title). The longest-line count drives whether to push
    the side art into the gutter (wide) vs. tuck it near the margin note
    (narrow). The author is extracted from `<by: …/>` or `<স্বনামে: …/>` meta
    tags before they're stripped from the body."""
    text = path.read_text(encoding="utf-8")
    # Strip YAML front matter.
    text = re.sub(r"^---[\s\S]*?---\s*", "", text)
    # Strip HTML comments (supports multi-line blocks).
    text = re.sub(r"<!--[\s\S]*?-->", "", text)
    # Pull author from `<by: …/>` or `<স্বনামে: …/>` before tag-strip.
    am = re.search(r"<(?:by|স্বনামে):\s*([^/<>]+?)\s*/>", text)
    author = am.group(1).strip() if am else ""
    # Strip custom self-closing meta tags like `<date: March 31, 2026 />`, `<তারিখ: ফেব্রুয়ারি ৪, ২০১৪ />`, `<status: draft />`.
    # Only matches tags with a colon + self-close — won't touch real HTML tags.
    # Tag name allows ASCII letters/digits/hyphens and Bengali (U+0980–U+09FF).
    text = re.sub(r"<[a-zA-Zঀ-৿][a-zA-Z0-9ঀ-৿-]*:[^<>]*?/>", "", text)
    title = fallback_title
    m = re.match(r"^#\s+(.+)$", text, re.M)
    if m:
        title = m.group(1).strip()
        text = re.sub(r"^#\s+.+$", "", text, count=1, flags=re.M).strip()
    # Count graphemes (base chars + spacing combining), not codepoints. Bengali
    # uses combining vowel signs / halants that are separate codepoints but
    # render as part of a single visible cluster — len() overcounts those.
    # For Latin text grapheme count == len() so this is a no-op.
    longest = 0
    for raw_line in text.splitlines():
        s = raw_line.strip()
        if not s or s.startswith("#") or s.startswith(">"):
            continue
        # Trailing two-space hard-break is invisible — don't count it.
        s = s.rstrip()
        n = sum(1 for c in s if unicodedata.category(c) not in ("Mn", "Mc"))
        if n > longest:
            longest = n
    return title, render_body(text, content_type), longest, author


# ── Helpers ───────────────────────────────────────────────────────────────────
def is_bengali(s: str) -> bool:
    return any("\u0980" <= c <= "\u09ff" for c in s)


def content_is_page(p: dict) -> bool:
    """Skip preface entries (they're collection-level markers, not standalone pages)."""
    return p.get("kind") != "preface"


def canonical_for(site_cfg: dict, path: str) -> str:
    """Build a canonical https://<domain>/<path> URL."""
    domain = site_cfg["site"]["domain"]
    return f"https://{domain}{path}"


def wrap_page(templates: dict, site_cfg: dict, *, title: str, desc: str, canonical: str,
              og_type: str, content: str, lang: str) -> str:
    vars = {
        "LANG": lang,
        "TITLE": html.escape(title),
        "DESCRIPTION": html.escape(desc),
        "CANONICAL": html.escape(canonical),
        "OG_TYPE": og_type,
        "OG_TITLE": html.escape(title),
        "OG_DESCRIPTION": html.escape(desc),
        "STYLES_HREF": f"/styles.css?v={int((TEMPLATES / 'styles.css').stat().st_mtime)}",
        "SVG_DEFS": templates["svg-defs.html"],
        "CONTENT": content,
    }
    return subst(templates["base.html"], vars)


# ── Page builders ─────────────────────────────────────────────────────────────
def build_home(templates: dict, site_cfg: dict, collections: list[dict]) -> str:
    """Home page — lists every collection as a 'book' card."""
    site = site_cfg["site"]
    cards: list[str] = []
    for i, c in enumerate(collections):
        pages = [p for p in c["contents"] if content_is_page(p)]
        cnt = len(pages)
        roman = ROMAN[i] if i < len(ROMAN) else str(i + 1)
        title_cls = "bn" if c.get("lang") == "bn" else ""
        subtitle = c.get("subtitle") or (c.get("roman") if c.get("lang") == "bn" else "")
        sub_html = f'<em>{html.escape(subtitle)}</em>' if subtitle else ""
        blurb = c.get("blurb") or ""
        blurb_html = f'<p class="blurb">{html.escape(blurb)}.</p>' if blurb else ""
        count_str = str(cnt) if cnt else "—"
        poem_word = count_word(pages, cnt) if pages else "poems"
        card = f'''    <a class="book" href="/{c["id"]}/">
      <div class="glyph">
        <svg viewBox="0 0 140 140" aria-hidden="true"><use href="#{c["mark"]}"/></svg>
      </div>
      <span class="no">Book <span class="sep">{roman}</span></span>
      <h2 class="{title_cls}">{html.escape(c["title"])}{sub_html}</h2>
      {blurb_html}
      <span class="meta"><span class="cnt">{count_str}</span> {poem_word} <span class="dot">·</span> {html.escape(c.get("lang","en"))}</span>
    </a>'''
        cards.append(card)

    home_content = subst(templates["home.html"], {
        "AUTHOR": html.escape(site["author"].lower()),
        "AUTHOR_LOWER": html.escape(site["author"].lower()),
        "DOMAIN": html.escape(site["domain"]),
        "EMAIL": "nafsadh@gmail.com",
        "BOOK_CARDS": "\n".join(cards),
    })
    return wrap_page(
        templates, site_cfg,
        title=site["title"],
        desc=site["description"],
        canonical=canonical_for(site_cfg, "/"),
        og_type="website",
        content=home_content,
        lang="en",
    )


def build_book(templates: dict, site_cfg: dict, collections: list[dict], idx: int) -> str:
    site = site_cfg["site"]
    c = collections[idx]
    total = len(collections)
    pages = [p for p in c["contents"] if content_is_page(p)]
    cnt = len(pages)

    roman = ROMAN[idx] if idx < len(ROMAN) else str(idx + 1)
    roman_last = ROMAN[total - 1] if total - 1 < len(ROMAN) else str(total)
    title_cls = "bn" if c.get("lang") == "bn" else ""
    subtitle = c.get("subtitle") or ""
    sub_html = f'<em>{html.escape(subtitle)}</em>' if subtitle else ""
    blurb = c.get("blurb") or ""
    blurb_html = f'"{html.escape(blurb)}."' if blurb else ""

    # Content list.
    poem_items: list[str] = []
    if not pages:
        poem_items.append('    <li class="book-empty">— this book is still being written —</li>')
    else:
        for pi, p in enumerate(pages):
            roman_small = P_ROMAN[pi] if pi < len(P_ROMAN) else str(pi + 1)
            t_cls = "p-title bn" if p.get("lang") == "bn" else "p-title"
            kind = p.get("kind") or ""
            kind_cls = f" kind-{kind}" if kind else ""
            _, p_title = item_type_and_title(p)
            poem_items.append(f'''    <li class="poem-row{kind_cls}">
      <a href="/{c["id"]}/{p["id"]}/" style="display:contents">
        <span class="roman">{roman_small}.</span>
        <span class="{t_cls}">{html.escape(p_title)}</span>
        <span class="kind">{html.escape(kind)}</span>
      </a>
    </li>''')

    # Book siblings (prev / next book across the whole site).
    prev_link = '    <span></span>'
    next_link = '    <span></span>'
    if idx > 0:
        pc = collections[idx - 1]
        pnm = pc.get("roman") or pc["title"]
        pnm_cls = " bn" if pc.get("lang") == "bn" and not pc.get("roman") else ""
        prev_link = f'''    <a class="prev" href="/{pc["id"]}/">
      <svg><use href="#arrow"/></svg>
      <span class="text-block"><span class="lbl">previous book</span><span class="nm{pnm_cls}">{html.escape(pnm)}</span></span>
    </a>'''
    if idx < total - 1:
        nc = collections[idx + 1]
        nnm = nc.get("roman") or nc["title"]
        nnm_cls = " bn" if nc.get("lang") == "bn" and not nc.get("roman") else ""
        next_link = f'''    <a class="next" href="/{nc["id"]}/">
      <span class="text-block"><span class="lbl">next book</span><span class="nm{nnm_cls}">{html.escape(nnm)}</span></span>
      <svg><use href="#arrow"/></svg>
    </a>'''

    lang_label = c.get("lang", "en").upper()

    book_content = subst(templates["book.html"], {
        "ROMAN": roman,
        "ROMAN_LAST": roman_last,
        "ILL_ID": c["ill"],
        "TITLE_CLASS": title_cls,
        "BOOK_TITLE": html.escape(c["title"]),
        "SUBTITLE_HTML": sub_html,
        "BLURB": blurb_html,
        "COUNT": str(cnt) if cnt else "—",
        "LANG_LABEL": html.escape(lang_label),
        "POEM_LIST": "\n".join(poem_items),
        "PREV_LINK": prev_link,
        "NEXT_LINK": next_link,
        "DOMAIN": html.escape(site["domain"]),
        "AUTHOR_LOWER": html.escape(site["author"].lower()),
        "EMAIL": "nafsadh@gmail.com",
    })

    page_title = c.get("roman") or c["title"]
    return wrap_page(
        templates, site_cfg,
        title=f'{page_title} — {site["title"]}',
        desc=blurb or page_title,
        canonical=canonical_for(site_cfg, f'/{c["id"]}/'),
        og_type="book",
        content=book_content,
        lang="bn" if c.get("lang") == "bn" else "en",
    )


def build_poem(templates: dict, site_cfg: dict, collections: list[dict],
               c_idx: int, p_idx: int, pages: list[dict]) -> str:
    site = site_cfg["site"]
    c = collections[c_idx]
    p = pages[p_idx]
    total_p = len(pages)

    p_type, p_title = item_type_and_title(p)
    md_path = SRC / c["id"] / f'{p["id"]}.md'
    if not md_path.exists():
        print(f"  [warn] missing markdown: {md_path.relative_to(SRC)}", file=sys.stderr)
        body_html = '<div class="stanza">— text not available —</div>'
        title = p_title
        longest_line = 0
        author = ""
    else:
        title, body_html, longest_line, author = parse_poem_md(md_path, p_title, p_type)

    # Three-tier width based on longest-line graphemes. Drives where the side
    # art sits:
    #   wide   — line fills the column → push art into the gutter
    #   narrow — short lines → art comes further left, into body's right area
    #   default — sits between, art at page-wrap right edge (margin-note column)
    # `wide:` / `narrow:` in _contents.yml override auto-detection. Wide wins if
    # both happen to be set. Bengali auto-wide is disabled (rendering width
    # varies too much for a clean threshold) — set `wide: true` per poem.
    is_prose = p_type in PROSE_TYPES
    if "wide" in p:
        is_wide = bool(p["wide"])
    elif is_prose:
        # Prose flows naturally; wider column reads like a story page.
        is_wide = True
    elif p.get("lang") == "bn":
        is_wide = False
    else:
        is_wide = longest_line >= 45

    if is_wide:
        is_narrow = False
    elif "narrow" in p:
        is_narrow = bool(p["narrow"])
    elif p.get("lang") == "bn":
        is_narrow = longest_line <= 18
    else:
        is_narrow = longest_line <= 30

    wide_class = " is-wide" if is_wide else (" is-narrow" if is_narrow else "")
    if is_prose:
        wide_class += " is-prose"

    roman = ROMAN[c_idx] if c_idx < len(ROMAN) else str(c_idx + 1)
    idx_str = f"{p_idx + 1:02d}"
    cnt_str = f"{total_p:02d}"

    title_cls = "bn" if p.get("lang") == "bn" else ""
    body_lang_cls = " bn" if p.get("lang") == "bn" else ""
    from_cls = "bn" if c.get("lang") == "bn" else ""

    # Top-art resolution order: explicit `art:` on the poem → per-collection `pool`
    # rotation (deterministic by index) → fall back to the collection's single `ill`.
    if p.get("art"):
        top_art = p["art"]
    elif c["pool"]:
        top_art = c["pool"][p_idx % len(c["pool"])]
    else:
        top_art = c["ill"]

    # Byline under title: "AUTHOR · DATE" (either part may be empty).
    # Date comes from yml (synced from md); author comes from md `<by:>`/`<স্বনামে:>` tag.
    # Letter-spacing + uppercase tracking is for Latin caps; Bengali drops both
    # (no casing, and tracking breaks up conjuncts).
    date = p.get("date") or ""
    parts = [s for s in (author, date) if s]
    if parts:
        byline = " · ".join(html.escape(s) for s in parts)
        bn = is_bengali(byline)
        spacing = "letter-spacing:2.5px;text-transform:uppercase;" if not bn else "letter-spacing:1.5px;"
        date_line = f'<div class="poem-date" style="font-family:\'Inter\',sans-serif;font-size:10px;{spacing}color:var(--dim);font-weight:500;margin-top:12px">{byline}</div>'
    else:
        date_line = ""

    # Margin note.
    note = p.get("note") or ""
    if note:
        margin_note = f'<span class="margin-note">{html.escape(note)}</span>'
        mobile_note = f'<div class="mobile-note">{html.escape(note)}</div>'
    else:
        margin_note = ""
        mobile_note = ""

    # Prev / next poem within this book.
    prev_p = pages[p_idx - 1] if p_idx > 0 else None
    next_p = pages[p_idx + 1] if p_idx < total_p - 1 else None
    nav_parts: list[str] = []
    if prev_p:
        _, prev_title = item_type_and_title(prev_p)
        prev_title_cls = " bn" if prev_p.get("lang") == "bn" else ""
        nav_parts.append(f'''    <a class="pn-link prev" href="/{c["id"]}/{prev_p["id"]}/">
      <span class="pn-dir"><svg><use href="#arrow"/></svg><span>previous</span></span>
      <span class="pn-title{prev_title_cls}">{html.escape(prev_title)}</span>
    </a>''')
    else:
        nav_parts.append('    <span></span>')
    if next_p:
        _, next_title = item_type_and_title(next_p)
        next_title_cls = " bn" if next_p.get("lang") == "bn" else ""
        nav_parts.append(f'''    <a class="pn-link right" href="/{c["id"]}/{next_p["id"]}/">
      <span class="pn-dir"><span>next</span><svg><use href="#arrow"/></svg></span>
      <span class="pn-title{next_title_cls}">{html.escape(next_title)}</span>
    </a>''')
    else:
        nav_parts.append('    <span></span>')

    poem_content = subst(templates["poem.html"], {
        "ROMAN": roman,
        "INDEX_STR": idx_str,
        "COUNT_STR": cnt_str,
        "FROM_CLASS": from_cls,
        "COLLECTION_ID": c["id"],
        "BOOK_TITLE_ONLY": html.escape(c["title"]),
        "MARK_ID": c["mark"],
        "TITLE_CLASS": title_cls,
        "POEM_TITLE": html.escape(title),
        "DATE_LINE": date_line,
        "TOP_ART": top_art,
        "WIDE_CLASS": wide_class,
        "BODY_LANG_CLASS": body_lang_cls,
        "BODY_HTML": body_html,
        "MOBILE_NOTE": mobile_note,
        "MARGIN_NOTE": margin_note,
        "POEM_NAV": "\n".join(nav_parts),
        "COLLECTION_ROMAN_OR_TITLE": html.escape(c.get("roman") or c["title"]),
        "DOMAIN": html.escape(site["domain"]),
        "AUTHOR_LOWER": html.escape(site["author"].lower()),
        "EMAIL": "nafsadh@gmail.com",
    })

    # First-stanza snippet for social meta description.
    first_stanza = ""
    m = re.search(r'<(?:div class="stanza"|p class="prose-para")>(.*?)</(?:div|p)>', body_html, re.S)
    if m:
        first_stanza = re.sub(r"<[^>]+>", " ", m.group(1))
        first_stanza = re.sub(r"\s+", " ", first_stanza).strip()[:180]

    return wrap_page(
        templates, site_cfg,
        title=f'{title} · {c.get("roman") or c["title"]} · {site["title"]}',
        desc=first_stanza or title,
        canonical=canonical_for(site_cfg, f'/{c["id"]}/{p["id"]}/'),
        og_type="article",
        content=poem_content,
        lang="bn" if p.get("lang") == "bn" else "en",
    )


# ── Writers ───────────────────────────────────────────────────────────────────
def write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def copy_static() -> None:
    """Copy raw assets to _site/: styles.css, CNAME, .nojekyll, and raw .md files
    (so /second-seconds/lull.md still resolves for anyone who wants the source)."""
    shutil.copy2(TEMPLATES / "styles.css", OUT / "styles.css")
    for name in ("CNAME", ".nojekyll"):
        src = SRC / name
        if src.exists():
            shutil.copy2(src, OUT / name)
    # Copy every .md file under collection dirs (not _site itself).
    for md in SRC.rglob("*.md"):
        rel = md.relative_to(SRC)
        if rel.parts[0] in ("_site", "_build"):
            continue
        dst = OUT / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(md, dst)


# ── Main ──────────────────────────────────────────────────────────────────────
def main() -> None:
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)

    site_cfg = load_site_config()
    collections = load_collections(site_cfg)
    templates = load_templates()

    print(f"Building to {OUT.relative_to(SRC.parent)}/")
    print(f"  site: {site_cfg['site']['domain']}")
    print(f"  collections: {len(collections)}")

    # Home page.
    write(OUT / "index.html", build_home(templates, site_cfg, collections))

    # Per-collection pages (book view + per-content pages).
    total_pages = 0
    for ci, c in enumerate(collections):
        write(OUT / c["id"] / "index.html", build_book(templates, site_cfg, collections, ci))
        pages = [p for p in c["contents"] if content_is_page(p)]
        for pi, p in enumerate(pages):
            page_html = build_poem(templates, site_cfg, collections, ci, pi, pages)
            write(OUT / c["id"] / p["id"] / "index.html", page_html)
            total_pages += 1

    copy_static()

    print(f"  pages: {total_pages}")
    print(f"  done.")


if __name__ == "__main__":
    main()
