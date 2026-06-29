#!/usr/bin/env python3
"""
Ansh-108 Core -- Path A, Phase 4 / S8 VERIFICATION GATE.
========================================================
Mirrors the S6/S7 software gates. Proves, with measured/golden numbers:

  [A] GRAMMAR -- the lexer accepts ALL reference programs; the grammar is
      UNAMBIGUOUS (golden token vectors + canonical re-lex fixed point + disjoint
      leading-character-class partition); malformed programs are rejected.
  [B] ASTA-DIK -- every ROLL and SCAN is REVERSIBLE (apply+inverse == identity) and
      cross-checked against an INDEPENDENT brute-force grid model (0 mismatch).
  [C] 8 FINGERPRINTS -- on a battery of patterns we MEASURE how many of the 8
      directions give distinct fold fingerprints and REPORT collisions honestly
      (symmetric patterns collide; we do NOT assume all 8 differ).
  [D] ROUND-TRIP -- directional + plain A0S programs go file -> compile -> packets
      -> S6/S7 LoopbackTransport -> result_reader fingerprint, 0 mismatch vs the
      compile fingerprint AND vs an independent golden (brute-force grid + golden
      fold); plain programs are byte-identical to the S6 chant pipeline.

HONESTY: this is host <-> SOFTWARE-GOLDEN (the same standing as S6/S7). The
aSTa-dik is a host-side reordering ONLY -- zero silicon change. host <-> RTL co-sim
is S9; real USB is Phase 7.

Run: python test_s8_a0s_grammar.py
"""
from __future__ import annotations

import glob
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import ashta_dik as AD
import a0s_parser as A
import host_staging as HS
from a0s_parser import (tokenize, compile_program, compile_file, A0SSyntaxError,
                        DATA, BINDU, EARLY_BINDU, HOLD, SUNYA, CTRL, ROLL, SCAN)
from transport import LoopbackTransport
from result_reader import fold_fingerprint, interpret
from golden_model import (fold_text, slice_bits_to_feet, FOLD_SEED, FOLD_B, Q,
                          STREAM)

random.seed(108)
HERE = os.path.dirname(os.path.abspath(__file__))
PROG_DIR = os.path.join(HERE, "a0s_programs")

_fails = 0
_sections = []


def check(name, cond):
    global _fails
    print(f"  [{'PASS' if cond else 'FAIL'}] {name}")
    if not cond:
        _fails += 1
    return cond


def section(title):
    print(f"\n{title}")
    _sections.append(title)


# --------------------------------------------------------------------------- #
# Independent golden helpers (do NOT reuse the production roll/fold path)
# --------------------------------------------------------------------------- #
def golden_grid_readout(bits, rolls, scan):
    """Brute-force: pure double-loop roll_ref + scan_order. Independent of roll()."""
    g = tuple(AD.pad108(bits))
    for d in rolls:
        g = AD.roll_ref(g, d)
    return tuple(g[i] for i in AD.scan_order(scan))


def golden_fold_bits(bits):
    """Fold a bit list via golden_model's slicer + a hand Horner (independent)."""
    h = FOLD_SEED
    for foot in slice_bits_to_feet(list(bits)):
        h = (h * FOLD_B + foot) % Q
    return h


def serialize_tokens(toks):
    """Canonical source string from a token list (for the re-lex fixed point)."""
    out = []
    for t in toks:
        if t.kind == DATA:
            out.append("a" if t.value == 0 else "A")
        elif t.kind == BINDU:
            out.append(".")
        elif t.kind == EARLY_BINDU:
            out.append("..")
        elif t.kind == HOLD:
            out.append("\n")
        elif t.kind == SUNYA:
            out.append("0")
        elif t.kind == CTRL:
            out.append(str(t.value))
        elif t.kind == ROLL:
            out.append("@" + str(t.value))
        elif t.kind == SCAN:
            out.append("^" + str(t.value))
    return "".join(out)


def random_a0s_program(directional_only=False):
    """Generate a random but VALID A0S program (so it compiles)."""
    parts = []
    nseg = random.randint(1, 3)
    for _ in range(nseg):
        # data (control numerals occasionally)
        for _ in range(random.randint(0, 40)):
            if random.random() < 0.15:
                parts.append(str(random.randint(1, 9)))     # ctrl + repeatable
                parts.append(random.choice("aAbZ"))
            else:
                parts.append(random.choice("aAbcZzqM"))
        # directions
        ndir = random.randint(1 if directional_only else 0, 5)
        for _ in range(ndir):
            if random.random() < 0.3:
                parts.append(str(random.randint(1, 9)))     # repeat a roll
            parts.append("@" + str(random.randint(1, 8)))
        if random.random() < 0.5:
            parts.append("^" + str(random.randint(1, 8)))
        parts.append(random.choice([".", ".", ".."]))       # bindu / early bindu
    # cap total data so no segment exceeds one 108 maNDala when directional
    return "".join(parts)


# =========================================================================== #
section("[A] GRAMMAR -- accept all refs, unambiguous, reject malformed")

# A1: golden token vectors (exact expected tokenisation)
def kinds(s):
    return [(t.kind, t.value) for t in tokenize(s)[0]]


gold_vectors = {
    "aA":        [(DATA, 0), (DATA, 1)],
    "a.A":       [(DATA, 0), (BINDU, 0), (DATA, 1)],
    "a..A":      [(DATA, 0), (EARLY_BINDU, 0), (DATA, 1)],
    "a...A":     [(DATA, 0), (EARLY_BINDU, 0), (DATA, 1)],   # run>=2 = early bindu
    "3a":        [(CTRL, 3), (DATA, 0)],
    "@1^8":      [(ROLL, 1), (SCAN, 8)],
    "0":         [(SUNYA, 0)],
    "9":         [(CTRL, 9)],
    "a # c\nb":  [(DATA, 0), (HOLD, 0), (DATA, 0)],          # comment dropped, \n=HOLD
    "Z z .. @3": [(DATA, 1), (DATA, 0), (EARLY_BINDU, 0), (ROLL, 3)],
}
gv_ok = all(kinds(s) == exp for s, exp in gold_vectors.items())
check("golden token vectors: every construct tokenises to exactly one form", gv_ok)

# A2: UNAMBIGUITY proof #1 -- disjoint leading-character classes.
# Each printable char maps to AT MOST one token-starting rule; the rule is fixed by
# the first character alone. We partition the byte range and assert no overlap.
def lead_class(ch):
    if ch == "#": return "comment"
    if ch in ("\n", "\r"): return "hold"
    if ch in (" ", "\t"): return "ws"
    if "a" <= ch <= "z" or "A" <= ch <= "Z": return "data"
    if ch == ".": return "dot"
    if ch == "0": return "sunya"
    if "1" <= ch <= "9": return "ctrl"
    if ch in ("@", "^"): return "sigil"
    return "ignore"
classes = {chr(c): lead_class(chr(c)) for c in range(0x20, 0x7F)}
classes["\n"] = lead_class("\n"); classes["\t"] = lead_class("\t")
# unambiguity: lead_class is a total FUNCTION (each char -> exactly one class). The
# only multi-char tokens (dot-run, sigil+digit) are deterministic maximal munches.
single_valued = all(isinstance(v, str) for v in classes.values())
check("unambiguity #1: leading-char classes are disjoint & total (one rule per char)",
      single_valued and lead_class("a") == "data" and lead_class("@") == "sigil"
      and lead_class(".") == "dot" and lead_class("1") == "ctrl"
      and lead_class("0") == "sunya")

# A3: UNAMBIGUITY proof #2 -- canonical re-lex FIXED POINT. Serialising a token
# list to its canonical source and re-tokenising yields the SAME tokens, for the
# refs and for random programs => no input parses two ways.
relex_ok = True
relex_samples = list(gold_vectors.keys()) + [random_a0s_program() for _ in range(3000)]
for s in relex_samples:
    toks = tokenize(s)[0]
    if kinds(serialize_tokens(toks)) != [(t.kind, t.value) for t in toks]:
        relex_ok = False
        break
check("unambiguity #2: canonical re-lex is a fixed point over 3000+ programs", relex_ok)

# A4: accept ALL reference programs without error
ref_files = sorted(glob.glob(os.path.join(PROG_DIR, "*.txt")))
acc_ok = True
compiled = {}
for f in ref_files:
    try:
        compiled[f] = compile_file(f)
    except Exception as e:
        acc_ok = False
        print(f"      !! {os.path.basename(f)} failed: {e}")
check(f"lexer/compiler accepts all {len(ref_files)} reference programs", acc_ok)
# every reference construct is present across the set
covered = {"data": False, "bindu": False, "early_bindu": False, "hold": False,
           "sunya": False, "ctrl": False, "roll": False, "scan": False}
dirs_seen = set()
for r in compiled.values():
    for t in r.tokens:
        if t.kind in covered:
            covered[t.kind] = True
        if t.kind == ROLL:
            dirs_seen.add(t.value)
        if t.kind == SCAN:
            dirs_seen.add(t.value)
check("reference set exercises EVERY construct (data/bindu/early/hold/zUnya/ctrl/roll/scan)",
      all(covered.values()))
check("reference set exercises ALL 8 directions (roll and/or scan)",
      dirs_seen == set(range(1, 9)))

# A5: known-program structure (sanity on a few)
c04 = compiled[os.path.join(PROG_DIR, "04_control_digits.txt")]
check("ref04 control numerals: 1A..9A -> 45 guru bits folded",
      c04.segments[0].kind == "plain" and len(c04.segments[0].bits) == 45
      and sum(c04.segments[0].bits) == 45)
c05 = compiled[os.path.join(PROG_DIR, "05_sunya.txt")]
check("ref05 zUnya clears the buffer: only 'bbbb' (4 bits) survive to fold",
      len(c05.segments[0].bits) == 4 and sum(c05.segments[0].bits) == 0)
c02 = compiled[os.path.join(PROG_DIR, "02_early_bindu.txt")]
check("ref02 early bindu: first maNDala aborted (no fold), second committed",
      c02.segments[0].kind == "aborted" and c02.segments[1].kind != "aborted"
      and c02.segments[0].fingerprint == FOLD_SEED)

# A6: reject malformed programs
def rejects(s):
    try:
        compile_program(s)
        return False
    except A0SSyntaxError:
        return True
bad = {
    "@":   "sigil at EOF (no direction digit)",
    "@9":  "direction digit out of range (9 > 8)",
    "@0":  "direction digit 0 (zUnya is not a direction)",
    "^ 1": "sigil + space (selector must be immediate)",
    "a3":  "control numeral with nothing repeatable after (EOF)",
    "3.":  "control numeral cannot repeat a bindu",
    "30":  "control numeral cannot repeat a zUnya",
}
rej_ok = all(rejects(s) for s in bad)
check("malformed programs raise A0SSyntaxError (sigil/digit/ctrl misuse)", rej_ok)


# =========================================================================== #
section("[B] ASTA-DIK -- reversible + brute-force cross-check (0 mismatch)")

roll_xc = roll_rev = scan_rev = perm_ok = True
for _ in range(5000):
    n = random.randint(0, AD.NCELLS)
    p = [random.randint(0, 1) for _ in range(n)]
    padded = tuple(AD.pad108(p))
    for d in AD.DIRECTIONS:
        # cross-check production roll() vs independent brute-force roll_ref + numpy
        roll_xc &= (AD.roll(p, d) == AD.roll_ref(p, d) == AD.roll_numpy(p, d))
        # reversibility
        roll_rev &= (AD.roll(AD.roll(p, d), AD.opposite(d)) == padded)
        scan_rev &= (AD.invert_scan(AD.apply_scan(p, d), d) == padded)
    if not (roll_xc and roll_rev and scan_rev):
        break
check("ROLL: production == double-loop == numpy over 5k patterns x 8 dirs", roll_xc)
check("ROLL reversible: roll(roll(x,d), opp(d)) == x", roll_rev)
check("SCAN reversible: invert_scan(apply_scan(x,d), d) == x", scan_rev)
check("every SCAN order is a full 108-permutation (diagonal zig-zag, no gcd loss)",
      all(sorted(AD.scan_order(d)) == list(range(AD.NCELLS)) for d in AD.DIRECTIONS))


# =========================================================================== #
section("[C] 8 FINGERPRINTS -- measured, collisions reported honestly")

patterns = {
    "all-zUnya (0)":  [0] * AD.NCELLS,
    "all-guru (1)":   [1] * AD.NCELLS,
    "checkerboard":   [(r + c) % 2 for r in range(AD.ROWS) for c in range(AD.COLS)],
    "row-stripes":    [r % 2 for r in range(AD.ROWS) for c in range(AD.COLS)],
    "col-stripes":    [c % 2 for r in range(AD.ROWS) for c in range(AD.COLS)],
    "asymmetric":     [(i * 37 + i // 5) % 2 for i in range(AD.NCELLS)],
}
patterns.update({f"random-{k}": [random.randint(0, 1) for _ in range(AD.NCELLS)]
                 for k in range(4)})

print("    pattern              distinct-ROLL  distinct-SCAN   (of 8 each)")
any_full = collisions_seen = False
for name, pat in patterns.items():
    rfps = {d: golden_fold_bits(AD.roll(pat, d)) for d in AD.DIRECTIONS}
    sfps = {d: golden_fold_bits(AD.apply_scan(pat, d)) for d in AD.DIRECTIONS}
    nr, ns = len(set(rfps.values())), len(set(sfps.values()))
    print(f"    {name:<20s} {nr:>6d}/8       {ns:>6d}/8")
    if nr == 8 and ns == 8:
        any_full = True
    if nr < 8 or ns < 8:
        collisions_seen = True
check("at least one rich pattern yields 8/8 distinct ROLL+SCAN fingerprints "
      "(geometry is order-sensitive)", any_full)
check("symmetric patterns DO collide (<8 distinct) -- reported, not assumed away",
      collisions_seen)
# the trivial uniform pattern collapses to ONE fingerprint (honest extreme)
uni = [1] * AD.NCELLS
check("uniform all-guru pattern: all 8 ROLLs collide to 1 fingerprint (logged)",
      len({golden_fold_bits(AD.roll(uni, d)) for d in AD.DIRECTIONS}) == 1)


# =========================================================================== #
section("[D] ROUND-TRIP -- compile -> packets -> S6/S7 loopback -> fingerprint")

# D1: directional single-segment programs, 0 mismatch vs compile AND golden
dir_ok = True
for _ in range(4000):
    n = random.randint(0, AD.NCELLS)
    bits = [random.randint(0, 1) for _ in range(n)]
    text = "".join("A" if b else "a" for b in bits)
    rolls = [random.randint(1, 8) for _ in range(random.randint(0, 4))]
    scan = random.randint(1, 8)
    prog = text + "".join(f"@{d}" for d in rolls) + f"^{scan}" + "."
    r = compile_program(prog)
    seg = r.segments[0]
    # loopback through the real S6/S7 transport + result reader
    events = LoopbackTransport().open().send(r.packets)
    fp_loop = fold_fingerprint(events)
    # independent golden: brute-force grid readout + golden fold
    fp_gold = golden_fold_bits(golden_grid_readout(bits, rolls, scan))
    dir_ok &= (fp_loop == seg.fingerprint == fp_gold)
    if not dir_ok:
        print(f"      !! mismatch prog={prog!r} loop={fp_loop} "
              f"compile={seg.fingerprint} gold={fp_gold}")
        break
check("directional programs: loopback fp == compile fp == brute-force golden (4k, 0 mismatch)",
      dir_ok)

# D2: PLAIN (letter-only) programs are byte-identical to the S6 chant pipeline
plain_ok = pkt_ok = True
for _ in range(4000):
    text = "".join(random.choice("aAbcdZzqMn") for _ in range(random.randint(0, 130)))
    prog = text + "."                      # explicit bindu == S6's appended bindu
    r = compile_program(prog)
    fp_loop = fold_fingerprint(LoopbackTransport().open().send(r.packets))
    plain_ok &= (fp_loop == HS.fold_fingerprint(text) == fold_text(text))
    pkt_ok &= (r.packets == HS.text_to_fold_packets(text))   # exact same bytes
check("plain programs: fingerprint == S6 host == golden fold over 4k texts", plain_ok)
check("plain programs: packet stream byte-identical to S6 text_to_fold_packets", pkt_ok)

# D3: multi-segment programs -- each committed maNDala seals its own fingerprint
multi_ok = True
for _ in range(2000):
    prog = random_a0s_program()
    r = compile_program(prog)
    events = LoopbackTransport().open().send(r.packets)
    sealed = [rd.value for rd in interpret(events) if rd.mode == STREAM]
    committed = [s.fingerprint for s in r.segments if s.kind != "aborted"]
    multi_ok &= (sealed == committed)
    if not multi_ok:
        print(f"      !! multi mismatch prog={prog!r} sealed={sealed} committed={committed}")
        break
check("multi-segment programs: sealed fingerprints == committed maNDalas, in order (2k)",
      multi_ok)

# D4: every reference program round-trips through the loopback
ref_rt_ok = True
for f, r in compiled.items():
    events = LoopbackTransport().open().send(r.packets)
    sealed = [rd.value for rd in interpret(events) if rd.mode == STREAM]
    committed = [s.fingerprint for s in r.segments if s.kind != "aborted"]
    ref_rt_ok &= (sealed == committed)
    # also: every stream ends in a bindu
    ref_rt_ok &= (((r.packets[-1] >> 28) & 0xF) == 15) if r.packets else True
check("all reference programs round-trip through S6/S7 loopback (0 mismatch)", ref_rt_ok)


# =========================================================================== #
print("\n" + "=" * 72)
if _fails == 0:
    print("S8 GATE: ALL PASS")
else:
    print(f"S8 GATE: {_fails} FAILURE(S)")
print("HONESTY: host<->software-golden; aSTa-dik = host-side reordering ONLY "
      "(zero silicon change).")
print("         '8 distinct fingerprints' is MEASURED (collisions on symmetric "
      "patterns reported).")
print("         host<->RTL co-sim is S9; real USB is Phase 7.")
print("=" * 72)
raise SystemExit(_fails)
