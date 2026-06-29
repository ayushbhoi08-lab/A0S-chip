#!/usr/bin/env python3
"""
Professional family-summary PDF builder.

Renders the plain-words summary as a *designed* document via HTML/CSS + a
headless Chrome/Edge print engine -- which gives real typographic layout
(serif body, sans headings, banded tables, callouts, proper page margins),
instead of the flat python-docx/Word look.

Pipeline:  source .md  ->  readable-English fold  ->  Markdown->HTML
           ->  wrap in a styled HTML template  ->  Chrome --print-to-pdf

Outputs (in Science_Background/):
    Ansh_108_Core_Family_Summary.md     (readable-English source)
    Ansh_108_Core_Family_Summary.html   (the designed page, openable in any browser)
    Ansh_108_Core_Family_Summary.pdf    (the print)
"""
import os
import re
import sys
import subprocess
import unicodedata
import markdown

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

ART = os.path.dirname(os.path.abspath(__file__))
SB = os.path.join(os.path.dirname(ART), "Science_Background")  # 01_CHIP_A0S/Science_Background (reorg Phase 2)
SRC = os.path.join(SB, "archive", "Ansh_108_Core_For_Family_Plain_Summary.md")
OUT_MD = os.path.join(SB, "Ansh_108_Core_Family_Summary.md")
OUT_HTML = os.path.join(SB, "Ansh_108_Core_Family_Summary.html")
OUT_PDF = os.path.join(SB, "Ansh_108_Core_Family_Summary.pdf")

# Sanskrit/IAST + Devanagari -> plain readable English (family-friendly).
READ = {
    "ā": "a", "ī": "i", "ū": "u", "ṛ": "ri", "ṝ": "ri", "ḷ": "l", "ḹ": "l",
    "ṅ": "n", "ñ": "n", "ṭ": "t", "ḍ": "d", "ṇ": "n", "ś": "sh", "ṣ": "sh",
    "ṃ": "m", "ṁ": "m", "ḥ": "h",
    "Ā": "A", "Ī": "I", "Ū": "U", "Ṛ": "Ri", "Ṅ": "N", "Ñ": "N", "Ṭ": "T",
    "Ḍ": "D", "Ṇ": "N", "Ś": "Sh", "Ṣ": "Sh", "Ṃ": "M", "Ḥ": "H",
    "ï": "i", "î": "i", "é": "e", "è": "e", "ê": "e", "ä": "a", "â": "a",
    "ö": "o", "ô": "o", "ü": "u", "û": "u", "ç": "c",
    "अंश": "amsha",
}


def fold(t):
    t = unicodedata.normalize("NFC", t)
    for k, v in READ.items():
        t = t.replace(k, v)
    return t


CSS = r"""
@page {
    size: A4;
    margin: 20mm 18mm 18mm 18mm;
}
:root {
    --ink:    #1c2733;
    --muted:  #5a6b7b;
    --accent: #1f4e79;   /* deep blue */
    --accent2:#2e74b5;   /* lighter blue */
    --rule:   #d7dee6;
    --band:   #eef3f8;   /* table stripe */
    --okgreen:#1a7f37;
    --callout:#f4f7fb;
}
* { box-sizing: border-box; }
body {
    font-family: Georgia, "Cambria", "Times New Roman", serif;
    font-size: 10.8pt;
    line-height: 1.55;
    color: var(--ink);
    margin: 0;
    -webkit-print-color-adjust: exact;
    print-color-adjust: exact;
}
p { margin: 0 0 9px 0; text-align: justify; }
em { color: var(--muted); }
strong { color: var(--ink); }

/* ---------- title block ---------- */
.cover {
    text-align: center;
    padding: 6px 0 16px 0;
    border-bottom: 2px solid var(--accent);
    margin-bottom: 20px;
}
.cover .eyebrow {
    font-family: "Segoe UI", Arial, sans-serif;
    letter-spacing: 3px;
    font-size: 9pt;
    text-transform: uppercase;
    color: var(--accent2);
    margin-bottom: 8px;
}
.cover h1 {
    font-family: "Segoe UI Semibold", "Segoe UI", Arial, sans-serif;
    font-size: 27pt;
    line-height: 1.12;
    color: var(--accent);
    margin: 0 0 8px 0;
    font-weight: 600;
}
.cover .subtitle {
    font-style: italic;
    font-size: 13pt;
    color: var(--muted);
    margin: 0 0 12px 0;
}
.cover .byline {
    font-family: "Segoe UI", Arial, sans-serif;
    font-size: 10pt;
    color: var(--ink);
}
.lead {
    background: var(--callout);
    border-left: 3px solid var(--accent2);
    padding: 12px 16px;
    border-radius: 3px;
    margin: 0 0 20px 0;
    font-size: 10.3pt;
}
.lead em, .lead { color: #3c4a57; }

/* ---------- headings ---------- */
h2 {
    font-family: "Segoe UI Semibold", "Segoe UI", Arial, sans-serif;
    font-size: 15pt;
    color: var(--accent);
    font-weight: 600;
    margin: 26px 0 10px 0;
    padding-bottom: 5px;
    border-bottom: 1px solid var(--rule);
    page-break-after: avoid;
}
h3 {
    font-family: "Segoe UI", Arial, sans-serif;
    font-size: 12pt;
    color: var(--accent2);
    font-weight: 600;
    margin: 18px 0 7px 0;
    page-break-after: avoid;
}

/* ---------- lists ---------- */
ul { margin: 0 0 11px 0; padding-left: 22px; }
li { margin: 0 0 5px 0; }

/* ---------- blockquote (the big idea) ---------- */
blockquote {
    margin: 14px 0;
    padding: 14px 20px;
    background: linear-gradient(0deg, var(--callout), var(--callout));
    border-left: 4px solid var(--accent);
    border-radius: 3px;
    font-size: 12pt;
    font-style: italic;
    color: var(--accent);
}
blockquote p { margin: 0; text-align: left; }

/* ---------- tables ---------- */
table {
    border-collapse: collapse;
    width: 100%;
    margin: 12px 0 16px 0;
    font-family: "Segoe UI", Arial, sans-serif;
    font-size: 9.6pt;
    page-break-inside: auto;
}
thead { display: table-header-group; }
th {
    background: var(--accent);
    color: #ffffff;
    text-align: left;
    font-weight: 600;
    padding: 8px 10px;
    border: none;
}
td {
    padding: 7px 10px;
    border-bottom: 1px solid var(--rule);
    vertical-align: top;
}
tbody tr:nth-child(even) { background: var(--band); }
tr { page-break-inside: avoid; }

/* ---------- accents ---------- */
.ok { color: var(--okgreen); font-weight: 700; }
hr { border: none; border-top: 1px solid var(--rule); margin: 22px 0; }

.signoff {
    margin-top: 26px;
    padding-top: 14px;
    border-top: 2px solid var(--accent);
    text-align: center;
}
.signoff em { font-size: 11.5pt; color: var(--accent); }
.signoff .author {
    font-family: "Segoe UI", Arial, sans-serif;
    margin-top: 6px;
    color: var(--ink);
    font-weight: 600;
}
"""


def build_html(md_body):
    html_body = markdown.markdown(
        md_body, extensions=["tables", "sane_lists", "attr_list"]
    )
    # clean checkmarks: friendly but professional (green tick, no emoji-font bloat)
    html_body = (html_body
                 .replace("✅", '<span class="ok">&#10003;</span>')
                 .replace("✔", '<span class="ok">&#10003;</span>')
                 .replace("❌", '<span style="color:#c0392b;font-weight:700;">&#10007;</span>')
                 .replace("✗", '<span style="color:#c0392b;font-weight:700;">&#10007;</span>'))
    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        "<title>The Ansh-108 Core - In Plain Words</title>"
        f"<style>{CSS}</style></head><body>\n{html_body}\n</body></html>"
    )


def restructure(md_text):
    """Pull the leading title/subtitle/byline/lead into a styled cover block.

    The source starts: '# Title' / '### Subtitle' / '**byline**' / italic lead
    paragraphs, up to the first '---'. We hand-render that header, then let
    Markdown handle the body from the first '## ' onward.
    """
    lines = md_text.split("\n")
    # find first '## ' (start of body) -- everything above is the header region
    body_start = next((i for i, l in enumerate(lines) if l.startswith("## ")), 0)
    head = [l for l in lines[:body_start]]
    body = "\n".join(lines[body_start:])

    title = subtitle = byline = ""
    lead_parts = []
    for l in head:
        s = l.strip()
        if s.startswith("# "):
            title = s[2:].strip()
        elif s.startswith("### "):
            subtitle = s[4:].strip()
        elif s.startswith("**") and not byline:
            byline = re.sub(r"\*\*", "", s).replace("·", "&middot;")
        elif s == "---" or not s:
            continue
        else:
            lead_parts.append(s)
    # the lead paragraphs are wrapped in single '*...*' italics in source
    lead_html = ""
    if lead_parts:
        joined = " ".join(lead_parts)
        lead_html = markdown.markdown(joined)

    # split off the final sign-off block ('*"..."*' + '**-- Ayush...**') if present
    signoff_html = ""
    m = re.search(r"\n---\s*\n+(\*\"[^\n]+\"[^\n]*)\n+(\*\*[^\n]+\*\*)\s*$", body)
    if m:
        quote = re.sub(r"^\*|\*$", "", m.group(1).strip())
        author = re.sub(r"\*\*", "", m.group(2).strip())
        signoff_html = (
            f'<div class="signoff"><em>{quote}</em>'
            f'<div class="author">{author}</div></div>'
        )
        body = body[:m.start()]

    cover = (
        '<div class="cover">'
        '<div class="eyebrow">Project ANSH</div>'
        f"<h1>{title}</h1>"
        f'<div class="subtitle">{subtitle}</div>'
        f'<div class="byline">{byline}</div>'
        "</div>"
        + (f'<div class="lead">{lead_html}</div>' if lead_html else "")
    )
    return cover, body, signoff_html


def find_browser():
    for p in (
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    ):
        if os.path.exists(p):
            return p
    return None


def main():
    with open(SRC, "r", encoding="utf-8") as fh:
        raw = fold(fh.read())
    with open(OUT_MD, "w", encoding="utf-8") as fh:
        fh.write(raw)

    cover, body, signoff = restructure(raw)
    body_html = markdown.markdown(
        body, extensions=["tables", "sane_lists", "attr_list"]
    )
    body_html = (body_html
                 .replace("✅", '<span class="ok">&#10003;</span>')
                 .replace("✔", '<span class="ok">&#10003;</span>')
                 .replace("❌", '<span style="color:#c0392b;font-weight:700;">&#10007;</span>')
                 .replace("✗", '<span style="color:#c0392b;font-weight:700;">&#10007;</span>'))
    full = (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        "<title>The Ansh-108 Core - In Plain Words</title>"
        f"<style>{CSS}</style></head><body>\n"
        f"{cover}\n{body_html}\n{signoff}\n</body></html>"
    )
    with open(OUT_HTML, "w", encoding="utf-8") as fh:
        fh.write(full)
    print("WROTE", OUT_MD)
    print("WROTE", OUT_HTML)

    browser = find_browser()
    if not browser:
        print("NO browser found; HTML written, open it and Print->Save as PDF.")
        return
    if os.path.exists(OUT_PDF):
        try:
            os.remove(OUT_PDF)
        except Exception:
            pass
    url = "file:///" + OUT_HTML.replace("\\", "/")
    cmd = [
        browser, "--headless=new", "--disable-gpu", "--no-pdf-header-footer",
        "--run-all-compositor-stages-before-draw",
        "--virtual-time-budget=10000",
        f"--print-to-pdf={OUT_PDF}", url,
    ]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if os.path.exists(OUT_PDF):
        kb = os.path.getsize(OUT_PDF) / 1024
        print(f"WROTE {OUT_PDF}  ({kb:.0f} KB)  via {os.path.basename(browser)}")
    else:
        print("PDF NOT created. stderr:\n", r.stderr[-1500:])


if __name__ == "__main__":
    main()
