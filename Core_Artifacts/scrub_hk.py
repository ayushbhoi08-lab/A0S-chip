#!/usr/bin/env python3
"""
scrub_hk.py -- strict Harvard-Kyoto ASCII scrub of Sanskrit (IAST) diacritics.
Deterministic, case-sensitive, applied identically across every target file so
cross-file tokens stay consistent. NFC-normalizes first, then a fixed char map.
Math/arrow/emoji/brand glyphs are NOT diacritics and are left as-is (reported).
"""
import os
import sys
import glob
import unicodedata

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

# IAST -> Harvard-Kyoto (case-sensitive). str.translate supports multi-char values.
HK = {
    "ā": "A", "ī": "I", "ū": "U", "ṛ": "R", "ṝ": "RR", "ḷ": "lR", "ḹ": "lRR",
    "ṃ": "M", "ṁ": "M", "ḥ": "H", "ṅ": "G", "ñ": "J", "ṭ": "T", "ṭh": "Th",
    "ḍ": "D", "ṇ": "N", "ś": "z", "ṣ": "S",
    "Ā": "A", "Ī": "I", "Ū": "U", "Ṛ": "R", "Ṝ": "RR",
    "Ṃ": "M", "Ḥ": "H", "Ṅ": "G", "Ñ": "J", "Ṭ": "T", "Ḍ": "D", "Ṇ": "N",
    "Ś": "z", "Ṣ": "S",
    # Latin diaeresis/accents that may appear in prose (e.g. "naive")
    "ï": "i", "î": "i", "í": "i", "ì": "i",
    "ë": "e", "é": "e", "è": "e", "ê": "e",
    "ä": "a", "á": "a", "à": "a", "â": "a",
    "ö": "o", "ó": "o", "ò": "o", "ô": "o",
    "ü": "u", "ú": "u", "ù": "u", "û": "u", "ç": "c",
}
TABLE = {ord(k): v for k, v in HK.items() if len(k) == 1}

ART = os.path.dirname(os.path.abspath(__file__))
SB = os.path.dirname(ART)
MEM = r"C:\Users\Ayush\.claude\projects\c--Users-Ayush-Desktop-Project-ansh\memory"

CODE = ["ashta_dik.py", "a0s_parser.py", "test_s8_a0s_grammar.py", "host_ops.py",
        "host_staging.py", "golden_model.py", "transport.py", "clock_led.py",
        "staging_agent.py", "result_reader.py", "test_host_staging.py",
        "test_s7_staging_agent.py"]
DOCS = ["A0S_Assembly_Spec.md", "Ansh_108_Core_PathA_S8_AshtaDik.md"]

targets = [os.path.join(ART, f) for f in CODE + DOCS]
targets += sorted(glob.glob(os.path.join(ART, "a0s_programs", "*.txt")))
targets += [os.path.join(SB, "Ansh_108_Core_PathA_Build_Plan.md")]
targets += [os.path.join(SB, "Ansh_108_Watch_and_Applications_Plan.md")]
targets += sorted(glob.glob(os.path.join(SB, "Ansh_108_Core_PathA_S*.md")))  # S2..S8 writeups
targets += [os.path.join(MEM, "project_ansh108_pathA_build.md")]


def nonascii_report(text):
    rem = {}
    for ch in text:
        if ord(ch) > 127:
            rem[ch] = rem.get(ch, 0) + 1
    return rem


total_repl = 0
for path in targets:
    if not os.path.exists(path):
        print(f"  [skip] missing: {path}")
        continue
    with open(path, "r", encoding="utf-8") as fh:
        orig = fh.read()
    text = unicodedata.normalize("NFC", orig)
    # count diacritics that will be replaced
    repl = sum(text.count(chr(o)) for o in TABLE)
    new = text.translate(TABLE)
    if new != orig:
        with open(path, "w", encoding="utf-8", newline="") as fh:
            fh.write(new)
    changed = sum(1 for a, b in zip(orig, new) if a != b) + abs(len(new) - len(orig))
    total_repl += repl
    rem = nonascii_report(new)
    rem_s = ", ".join(f"{c!r}x{n}" for c, n in sorted(rem.items())) if rem else "none"
    print(f"  {os.path.basename(path):34s} diacritics_replaced={repl:4d}  remaining_nonascii=[{rem_s}]")

print(f"\nTOTAL diacritics replaced = {total_repl}")
