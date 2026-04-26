#!/usr/bin/env python3
"""Generate pen-mock.html in _site/ for the pen·sadh rebrand preview.
Re-run after build.py wipes _site/."""

from pathlib import Path

SITE = Path(__file__).resolve().parent.parent / "_site"
SRC = SITE / "index.html"


HERO_TEXT_OLD = '''    <div class="hero-text">
      <h1><em>poems</em></h1>
      <p class="sub">by sadh</p>
    </div>'''

HERO_TEXT_NEW = '''    <div class="hero-text">
      <h1><em>pen</em><svg viewBox="0 0 24 24" aria-hidden="true" style="width:.3em;height:.3em;color:var(--azure);display:inline-block;vertical-align:middle;margin:0 .04em"><use href="#bar-mark"/></svg>sadh</h1>
      <p class="sub" style="font-family:'Caveat',cursive;font-style:normal;font-weight:500;font-size:clamp(20px,2.4vw,26px);letter-spacing:0;margin-top:clamp(4px,2.0vw,26px);margin-left:.85em;max-width:none;color:var(--ink-soft);font-variation-settings:normal">poems &amp; prose</p>
    </div>'''


def rebrand(html: str) -> str:
    h = html
    h = h.replace("<title>Poems by Sadh</title>", "<title>pen · sadh</title>")
    h = h.replace(
        "Sadh&#x27;s poetry collections — Bengali and English, curated into books.",
        "Sadh&#x27;s writing — poems &amp; prose.",
    )
    h = h.replace("https://poems.nafsadh.com/", "https://pen.nafsadh.com/")
    h = h.replace('content="Poems by Sadh"', 'content="pen · sadh"')
    h = h.replace(
        '<div class="home-domain">poems.nafsadh.com</div>',
        '<div class="home-domain">pen.nafsadh.com</div>',
    )
    h = h.replace(
        "<span>poems.nafsadh.com</span>",
        "<span>pen.nafsadh.com</span>",
    )
    assert HERO_TEXT_OLD in h, "hero-text block not found"
    h = h.replace(HERO_TEXT_OLD, HERO_TEXT_NEW)
    return h


FONT_VARIANTS = [
    ("caveat",   "Caveat",                  "font-family:'Caveat',cursive;font-style:normal;font-weight:500;font-size:clamp(20px,2.4vw,26px);letter-spacing:0"),
    ("imfell",   "IM Fell English italic",  "font-family:'IM Fell English',serif;font-style:italic;font-weight:400;font-size:clamp(15px,1.65vw,19px);letter-spacing:.01em"),
    ("fraunces", "Fraunces regular",        "font-family:'Fraunces',serif;font-style:normal;font-weight:400;font-size:clamp(14px,1.5vw,17px);letter-spacing:.01em;font-variation-settings:'opsz' 144,'SOFT' 100"),
    ("inter",    "Inter italic",            "font-family:'Inter',sans-serif;font-style:italic;font-weight:400;font-size:clamp(13px,1.4vw,16px);letter-spacing:.005em"),
]


def hero_with_font(style: str) -> str:
    return f'''    <div class="hero-text">
      <h1><em>pen</em><svg viewBox="0 0 24 24" aria-hidden="true" style="width:.3em;height:.3em;color:var(--azure);display:inline-block;vertical-align:middle;margin:0 .04em"><use href="#bar-mark"/></svg>sadh</h1>
      <p class="sub" style="{style};margin-top:clamp(4px,2.0vw,26px);margin-left:.85em;max-width:none;color:var(--ink-soft);font-variation-settings:normal">poems &amp; prose</p>
    </div>'''


HERO_A = '''    <div class="hero-text">
      <h1><em>pen</em><svg viewBox="0 0 24 24" aria-hidden="true" style="width:.3em;height:.3em;color:var(--azure);display:inline-block;vertical-align:middle;margin:0 .04em"><use href="#bar-mark"/></svg>sadh</h1>
      <p class="sub" style="font-family:'IM Fell English',serif;font-style:italic;font-weight:400;font-size:clamp(22px,2.7vw,34px);letter-spacing:.005em;margin-top:18px;margin-left:0;max-width:none;color:var(--ink-soft);font-variation-settings:normal">poems &amp; prose</p>
    </div>'''

HERO_B = '''    <div class="hero-text">
      <div style="display:inline-block">
        <h1><em>pen</em><svg viewBox="0 0 24 24" aria-hidden="true" style="width:.3em;height:.3em;color:var(--azure);display:inline-block;vertical-align:middle;margin:0 .04em"><use href="#bar-mark"/></svg>sadh</h1>
        <p style="font-family:'Inter',sans-serif;font-size:11px;letter-spacing:4px;text-transform:uppercase;color:var(--azure);font-weight:600;margin-top:18px;margin-bottom:0;text-align:center">poems &amp; prose</p>
      </div>
    </div>
    <style>
      /* B-only: two-column books grid */
      .books{max-width:1080px;display:grid;grid-template-columns:repeat(2,1fr);gap:8vh 56px;padding:4vh 36px 4vh}
      .book{padding:0!important}
      .book + .book::before{display:none}
      .book:nth-child(odd):last-child{grid-column:1 / -1;justify-self:center;width:50%}
      @media(max-width:760px){.books{grid-template-columns:1fr;gap:6vh 0}}
    </style>'''

# C: move the tagline up into the top home-domain strip, color azure, drop subtitle from hero.
HERO_C = '''    <div class="hero-text">
      <h1><em>pen</em><svg viewBox="0 0 24 24" aria-hidden="true" style="width:.3em;height:.3em;color:var(--azure);display:inline-block;vertical-align:middle;margin:0 .04em"><use href="#bar-mark"/></svg>sadh</h1>
    </div>'''

HOME_DOMAIN_C = (
    '<style>.home-domain::before,.home-domain::after{animation:none!important}</style>'
    '<div class="home-domain" style="color:var(--azure);font-size:clamp(16px,1.6vw,20px);font-weight:500;gap:22px;padding-top:48px">'
    'poems &amp; prose &nbsp;·&nbsp; pen.nafsadh.com'
    '</div>'
)


def main() -> None:
    if not SRC.exists():
        raise SystemExit(f"missing {SRC} — run build.py first")
    base = rebrand(SRC.read_text(encoding="utf-8"))

    # Default mock keeps the current main pick (Caveat).
    out = SITE / "pen-mock.html"
    out.write_text(base, encoding="utf-8")
    print(f"wrote {out.relative_to(SITE.parent)}")

    # One file per font variant for side-by-side review.
    for slug, _label, style in FONT_VARIANTS:
        variant = base.replace(HERO_TEXT_NEW, hero_with_font(style))
        f = SITE / f"pen-mock-{slug}.html"
        f.write_text(variant, encoding="utf-8")
        print(f"wrote {f.relative_to(SITE.parent)}")

    # A/B layout experiments.
    for slug, hero in (("a", HERO_A), ("b", HERO_B)):
        f = SITE / f"pen-mock-{slug}.html"
        f.write_text(base.replace(HERO_TEXT_NEW, hero), encoding="utf-8")
        print(f"wrote {f.relative_to(SITE.parent)}")

    # C: tagline moves into the top domain strip; hero is wordmark only.
    variant_c = base.replace(HERO_TEXT_NEW, HERO_C)
    variant_c = variant_c.replace(
        '<div class="home-domain">pen.nafsadh.com</div>',
        HOME_DOMAIN_C,
    )
    fc = SITE / "pen-mock-c.html"
    fc.write_text(variant_c, encoding="utf-8")
    print(f"wrote {fc.relative_to(SITE.parent)}")


if __name__ == "__main__":
    main()
