#!/usr/bin/env python3
"""
Ansh-108 Core -- Path A, Phase 4 / S8: A0S ASSEMBLY PARSER / COMPILER.
======================================================================
The human-facing A0S `.txt` language: turns a chant-program into the EXACT packet
stream core_top consumes, plus the host-side aSTa-dik geometry. This EXTENDS the S6
host parser (`host_staging.parse_text`, which only mapped a/A and stripped the rest)
into the full grammar:

    a..z  -> laghu data bit 0          A..Z  -> guru data bit 1
    .     -> bindu  (terminate + execute the maNDala)
    ..    -> early bindu (abort: void this maNDala WITHOUT folding)   [run of >=2 dots]
    Enter -> HOLD   (host clock/LED pause; folds nothing, no packet)
    0     -> zUnya  (clear the current maNDala buffer)
    1..9  -> Sanskrit control numerals eka..nava: REPEAT the next repeatable token
    @d    -> ROLL the maNDala one step toward diz d   (d = 1..8, aSTa-dik order)
    ^d    -> SCAN (readout traversal) in diz d         (d = 1..8)
    #...  -> comment to end of line
    space/tab and any other char -> ignored separator

UNAMBIGUITY (proven in the S8 gate): the lexer is driven by DISJOINT leading
character classes -- at any position the first character alone selects exactly one
rule, so no input can parse two ways. The only multi-character tokens are (i) a
maximal run of dots (length 1 = bindu, length >=2 = early bindu) and (ii) a sigil
(`@`/`^`) immediately followed by one direction digit -- both deterministic.

PATH-A FENCE: the directions are host-side grid permutations (ashta_dik); they emit
NO new chip opcode. A maNDala with a direction operator is laid into the locked
9×12=108 grid (zUnya-padded), transformed, read out, then FOLD-streamed. A maNDala
with NO direction operator folds the raw bitstream EXACTLY as S6 (the geometry layer
is strictly additive -- plain programs stay byte-identical to the S6/S7 pipeline).

Pure Python 3.8+. Importable + `python a0s_parser.py <prog.txt>` (compile + report).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Sequence, Tuple
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import host_staging as H                                               # noqa: E402
import ashta_dik as AD                                                 # noqa: E402
from golden_model import FOLD, RESET, FOLD_B, FOLD_SEED, Q             # noqa: E402

# the chant-ingestion (lenient, a/A only) parser is unchanged from S6:
parse_text_plain = H.parse_text          # re-exported; A0S below is the extension


class A0SSyntaxError(ValueError):
    """Raised on a malformed A0S program (e.g. a sigil with no direction digit,
    or a control numeral with nothing repeatable after it)."""


# --------------------------------------------------------------------------- #
# Tokens
# --------------------------------------------------------------------------- #
DATA, BINDU, EARLY_BINDU, HOLD, SUNYA, CTRL, ROLL, SCAN = (
    "data", "bindu", "early_bindu", "hold", "sunya", "ctrl", "roll", "scan")

_REPEATABLE = {DATA, ROLL, SCAN}


@dataclass(frozen=True)
class Token:
    kind: str
    value: int          # data: 0/1 ; ctrl: 1..9 ; roll/scan: dir 1..8 ; else 0
    pos: int            # source offset (for error messages / golden vectors)


@dataclass
class LexStats:
    ignored: int = 0    # characters skipped as separators / unknown
    comments: int = 0   # comment characters skipped


def tokenize(text: str) -> Tuple[List[Token], LexStats]:
    """Single-pass, maximal-munch lexer. Disjoint leading-char classes => the kind
    of every token is fixed by its first character (the unambiguity guarantee)."""
    toks: List[Token] = []
    st = LexStats()
    i, n = 0, len(text)
    while i < n:
        ch = text[i]
        if ch == "#":                                   # comment to end of line
            j = i
            while j < n and text[j] not in ("\n", "\r"):
                j += 1
            st.comments += j - i
            i = j
        elif ch in ("\n", "\r"):                        # HOLD (Enter)
            toks.append(Token(HOLD, 0, i))
            i += 1
        elif ch in (" ", "\t"):                         # whitespace separator
            st.ignored += 1
            i += 1
        elif "a" <= ch <= "z":                          # laghu data bit
            toks.append(Token(DATA, 0, i))
            i += 1
        elif "A" <= ch <= "Z":                          # guru data bit
            toks.append(Token(DATA, 1, i))
            i += 1
        elif ch == ".":                                 # dot-run: bindu / early-bindu
            j = i
            while j < n and text[j] == ".":
                j += 1
            toks.append(Token(BINDU if j - i == 1 else EARLY_BINDU, 0, i))
            i = j
        elif ch == "0":                                 # zUnya (clear)
            toks.append(Token(SUNYA, 0, i))
            i += 1
        elif "1" <= ch <= "9":                          # eka..nava control numeral
            toks.append(Token(CTRL, ord(ch) - ord("0"), i))
            i += 1
        elif ch in ("@", "^"):                          # direction sigil + selector
            kind = ROLL if ch == "@" else SCAN
            if i + 1 >= n or not ("1" <= text[i + 1] <= "8"):
                got = repr(text[i + 1]) if i + 1 < n else "end-of-file"
                raise A0SSyntaxError(
                    f"'{ch}' at offset {i} must be followed by a direction digit "
                    f"1..8 (aSTa-dik); got {got}")
            toks.append(Token(kind, ord(text[i + 1]) - ord("0"), i))
            i += 2
        else:                                           # any other char: ignored
            st.ignored += 1
            i += 1
    return toks, st


# --------------------------------------------------------------------------- #
# Compiled output
# --------------------------------------------------------------------------- #
@dataclass
class Segment:
    kind: str                       # "plain" | "directional" | "aborted"
    bits: Tuple[int, ...]           # the readout bits actually folded (() if aborted)
    rolls: Tuple[int, ...]          # directions rolled, in textual order
    scan: int                       # readout diz (PURVA = row-major default)
    feet: List[int]                 # 28-bit FOLD feet
    packets: List[int]              # FOLD feet + the bindu (RESET)
    fingerprint: int                # expected fold fingerprint (read before bindu)
    early: bool                     # True if closed by an early bindu (abort)
    implicit: bool                  # True if closed by EOF (no explicit bindu)


@dataclass
class CompileResult:
    source: str
    tokens: List[Token]
    segments: List[Segment]
    packets: List[int]              # flat stream across all segments
    holds: int
    sunyas: int
    stats: LexStats

    @property
    def fingerprint(self) -> int:
        """Fingerprint of the last COMMITTED (non-aborted) maNDala, or the seed."""
        for s in reversed(self.segments):
            if s.kind != "aborted":
                return s.fingerprint
        return FOLD_SEED


# --------------------------------------------------------------------------- #
# Fold helper (Horner over feet) -- matches golden_model / fold_hash exactly
# --------------------------------------------------------------------------- #
def _fold_feet(feet: Sequence[int]) -> int:
    h = FOLD_SEED
    for f in feet:
        h = (h * FOLD_B + f) % Q
    return h


def _finalize(pattern: List[int], rolls: List[int], scan: int,
              directional: bool, *, implicit: bool) -> Segment:
    if directional:
        bits = list(AD.grid_readout(pattern, rolls, scan))
        kind = "directional"
    else:
        bits = list(pattern)
        kind = "plain"
    feet = H.slice_feet(bits).feet
    packets = [H.pkt_data(FOLD, f) for f in feet] + [H.pkt_data(RESET, 0)]
    return Segment(kind=kind, bits=tuple(bits), rolls=tuple(rolls), scan=scan,
                   feet=feet, packets=packets, fingerprint=_fold_feet(feet),
                   early=False, implicit=implicit)


def _finalize_abort() -> Segment:
    """Early bindu '..': void the maNDala WITHOUT folding -- only the bindu packet
    goes out, so reading the fingerprint (before the bindu) yields the seed."""
    return Segment(kind="aborted", bits=(), rolls=(), scan=AD.PURVA, feet=[],
                   packets=[H.pkt_data(RESET, 0)], fingerprint=FOLD_SEED,
                   early=True, implicit=False)


# --------------------------------------------------------------------------- #
# Compiler: tokens -> segments -> packet stream
# --------------------------------------------------------------------------- #
def compile_program(text: str, source: str = "<text>") -> CompileResult:
    toks, st = tokenize(text)
    segments: List[Segment] = []
    holds = sunyas = 0

    # current maNDala (segment) state
    pattern: List[int] = []
    rolls: List[int] = []
    scan = AD.PURVA
    directional = False
    open_seg = False

    def reset_seg():
        nonlocal pattern, rolls, scan, directional, open_seg
        pattern, rolls, scan, directional, open_seg = [], [], AD.PURVA, False, False

    def apply_repeatable(tok: Token, times: int):
        nonlocal scan, directional, open_seg
        if tok.kind == DATA:
            pattern.extend([tok.value] * times)
        elif tok.kind == ROLL:
            rolls.extend([tok.value] * times)
            directional = True
        elif tok.kind == SCAN:
            scan = tok.value            # later scan wins; repeating it is idempotent
            directional = True
        open_seg = True

    i = 0
    while i < len(toks):
        t = toks[i]
        if t.kind == CTRL:
            if i + 1 >= len(toks):
                raise A0SSyntaxError(
                    f"control numeral {t.value} at offset {t.pos} has nothing to repeat")
            nxt = toks[i + 1]
            if nxt.kind not in _REPEATABLE:
                raise A0SSyntaxError(
                    f"control numeral {t.value} at offset {t.pos} cannot repeat a "
                    f"'{nxt.kind}' token (only data syllables, @roll, ^scan are repeatable)")
            apply_repeatable(nxt, t.value)
            i += 2
            continue

        if t.kind in _REPEATABLE:
            apply_repeatable(t, 1)
        elif t.kind == SUNYA:
            reset_seg()                  # void the buffer (cleared maNDala)
            sunyas += 1
        elif t.kind == HOLD:
            holds += 1                    # host clock/LED only; no packet, no fold
        elif t.kind == BINDU:
            segments.append(_finalize(pattern, rolls, scan, directional, implicit=False))
            reset_seg()
        elif t.kind == EARLY_BINDU:
            segments.append(_finalize_abort())
            reset_seg()
        i += 1

    if open_seg:                          # EOF: implicit bindu closes an open maNDala
        segments.append(_finalize(pattern, rolls, scan, directional, implicit=True))

    packets = [p for s in segments for p in s.packets]
    return CompileResult(source=source, tokens=toks, segments=segments,
                         packets=packets, holds=holds, sunyas=sunyas, stats=st)


def compile_file(path: str) -> CompileResult:
    with open(path, "r", encoding="utf-8", errors="ignore") as fh:
        return compile_program(fh.read(), source=path)


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def _cli(argv: List[str]) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    if len(argv) < 2:
        print("usage: a0s_parser.py <program.txt>")
        return 1
    r = compile_file(argv[1])
    print(f"# source      : {r.source}")
    print(f"# tokens      : {len(r.tokens)}  (holds={r.holds}, zUnya={r.sunyas}, "
          f"ignored={r.stats.ignored}, comment chars={r.stats.comments})")
    print(f"# maNDalas    : {len(r.segments)}")
    for k, s in enumerate(r.segments):
        rolls = ",".join(AD.DIRECTIONS[d].ascii for d in s.rolls) or "-"
        note = " (early/abort)" if s.early else (" (implicit bindu)" if s.implicit else "")
        print(f"    [{k}] {s.kind:<11s} bits={len(s.bits):>3d} rolls=[{rolls}] "
              f"scan={AD.DIRECTIONS[s.scan].ascii:<8s} feet={len(s.feet)} "
              f"fp={s.fingerprint}{note}")
    print(f"# packets     : {len(r.packets)}")
    print(f"# fingerprint : {r.fingerprint}  (0x{r.fingerprint:04x})  "
          f"[last committed maNDala]")
    for p in r.packets:
        op = (p >> 28) & 0xF
        print(f"    {p:08x}  op={op:2d}")
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli(sys.argv))
