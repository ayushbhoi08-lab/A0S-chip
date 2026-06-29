#!/usr/bin/env python3
"""
Ansh-108 Core -- Path A, Phase 3 / S6: HOST STAGING AGENT front-end.
====================================================================
parser + slicer + assembler -- turn an `a/A` text file (the chant) into the EXACT
32-bit packet stream that core_top consumes. Pure software (the "front chamber");
the FPGA back chamber stays blind. This is the staging agent's data path; the
clock/LED state machine, USB streaming, and host positional ops (aSTa-dik) are S7.

Independent implementation of the locked spec, cross-checked against the S1 source
of truth golden_model.py in test_host_staging.py (two implementations agreeing).

Locked spec (golden_model.py / plan §2):
  - packet = [31:28] opcode | [27:0] data ; fast lane X=data[13:0], Y=data[27:14].
  - laghu 'a..z' -> 0, guru 'A..Z' -> 1 ; everything else stripped.
  - foot = 28 data bits, MSB-first; the FINAL foot is zUnya-padded (zeros) on the
    right so the chant's tail still folds.
  - FOLD = 4 (the whole-pattern fingerprint); RESET = 15 is the BINDU exit packet
    ("sequence complete, apply final result policy") appended after the feet.

Python 3.8+, no third-party deps. Importable (functions) + CLI (`host_staging.py f.txt`).
"""
from dataclasses import dataclass
from typing import List, Sequence, Tuple, Union
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
# constants come from the single source of truth; the ALGORITHMS below are
# implemented independently and cross-checked against golden_model in the tests.
from golden_model import (                                            # noqa: E402
    DATA_BITS, OPND_BITS, DATA_MASK, OPND_MASK, Q, FOLD_B, FOLD_SEED,
    MUL, ADD, SUB, REDUCE, FOLD, VERIFY, READ_TICK, SEED_FROM_TICK, FLUSH, RESET)

FOOT_BITS = DATA_BITS            # 28-bit chant foot = the packet data field

_OP_BY_NAME = {
    "MUL": MUL, "ADD": ADD, "SUB": SUB, "REDUCE": REDUCE, "FOLD": FOLD,
    "VERIFY": VERIFY, "READ_TICK": READ_TICK, "SEED_FROM_TICK": SEED_FROM_TICK,
    "FLUSH": FLUSH, "RESET": RESET,
}
_FAST_OPS = {"MUL", "ADD", "SUB", "VERIFY"}     # use the X|Y fast lane
_DATA_OPS = {"REDUCE", "FOLD"}                   # use the 28-bit flexible lane
_NOARG_OPS = {"READ_TICK", "SEED_FROM_TICK", "FLUSH", "RESET"}


# --------------------------------------------------------------------------- #
# 1. PARSER -- text -> bitstream  (laghu/guru; strip everything else)
# --------------------------------------------------------------------------- #
def parse_text(text: str) -> List[int]:
    """Map a..z -> 0 (laghu), A..Z -> 1 (guru); ignore all other characters."""
    bits: List[int] = []
    for ch in text:
        if "a" <= ch <= "z":
            bits.append(0)
        elif "A" <= ch <= "Z":
            bits.append(1)
    return bits


def parse_file(path: str) -> List[int]:
    with open(path, "r", encoding="utf-8", errors="ignore") as fh:
        return parse_text(fh.read())


# --------------------------------------------------------------------------- #
# 2. SLICER -- bitstream -> 28-bit feet (MSB-first; zUnya-pad the final foot)
# --------------------------------------------------------------------------- #
@dataclass
class SliceResult:
    feet: List[int]        # 28-bit data words, in order
    pad_bits: int          # number of zUnya (zero) bits added to the final foot
    n_bits: int            # original bit count (so the host knows the true length)
    final_index: int       # index of the last (final) foot


def slice_feet(bits: Sequence[int], width: int = FOOT_BITS) -> SliceResult:
    """Pack bits MSB-first into width-bit feet; the final foot is left-aligned and
    zUnya-padded with zeros on the right. Empty input -> a single all-zUnya foot."""
    feet: List[int] = []
    n = len(bits)
    pad = 0
    for i in range(0, n, width):
        chunk = bits[i:i + width]
        v = 0
        for b in chunk:
            v = (v << 1) | (b & 1)
        shift = width - len(chunk)        # left-align the final short chunk
        v <<= shift
        feet.append(v)
        if i + width >= n:                # this was the last chunk
            pad = shift
    if not feet:
        feet = [0]
        pad = width
    return SliceResult(feet=feet, pad_bits=pad, n_bits=n, final_index=len(feet) - 1)


# --------------------------------------------------------------------------- #
# 3. ASSEMBLER -- feet/ops -> 32-bit packets (+ bindu exit)
# --------------------------------------------------------------------------- #
def pkt_fast(op: int, x: int = 0, y: int = 0) -> int:
    """Fast-lane packet: data = Y<<14 | X (each 14-bit)."""
    data = ((y & OPND_MASK) << OPND_BITS) | (x & OPND_MASK)
    return ((op & 0xF) << DATA_BITS) | (data & DATA_MASK)


def pkt_data(op: int, data28: int = 0) -> int:
    """Flexible-lane packet: the full 28-bit data field (FOLD foot / REDUCE value)."""
    return ((op & 0xF) << DATA_BITS) | (data28 & DATA_MASK)


def assemble_fold(feet: Sequence[int], with_bindu: bool = True) -> List[int]:
    """Build the FOLD packet stream for a chant, then append the bindu exit (RESET)."""
    pkts = [pkt_data(FOLD, f) for f in feet]
    if with_bindu:
        pkts.append(pkt_data(RESET, 0))    # bindu: sequence complete
    return pkts


def assemble(ops: Sequence[tuple], with_bindu: bool = True) -> List[int]:
    """General assembler. ops = list of tuples whose first element is the op name:
        ("MUL", x, y) | ("ADD", x, y) | ("SUB", x, y) | ("VERIFY", x, y)
        ("FOLD", d)   | ("REDUCE", d)
        ("READ_TICK",)| ("FLUSH",) | ("RESET",) | ("SEED_FROM_TICK",)
    A bindu exit (RESET) is appended unless the program already ends in RESET."""
    out: List[int] = []
    for op in ops:
        name = op[0]
        code = _OP_BY_NAME[name]
        if name in _FAST_OPS:
            out.append(pkt_fast(code, op[1], op[2]))
        elif name in _DATA_OPS:
            out.append(pkt_data(code, op[1]))
        elif name in _NOARG_OPS:
            out.append(pkt_data(code, 0))
        else:
            raise ValueError(f"unknown op {name!r}")
    if with_bindu and (not ops or ops[-1][0] != "RESET"):
        out.append(pkt_data(RESET, 0))
    return out


# --------------------------------------------------------------------------- #
# Full pipeline + the host's expected fingerprint (for the loopback contract)
# --------------------------------------------------------------------------- #
def text_to_fold_packets(src: str, is_file: bool = False) -> List[int]:
    """parse -> slice -> assemble FOLD stream (+ bindu). The headline pipeline."""
    bits = parse_file(src) if is_file else parse_text(src)
    return assemble_fold(slice_feet(bits).feet, with_bindu=True)


def fold_fingerprint(src: str, is_file: bool = False) -> int:
    """The whole-pattern fingerprint the host expects the core's FOLD stream to
    produce (Horner h <- (h*108 + foot) mod q, seed 1), read BEFORE the bindu."""
    bits = parse_file(src) if is_file else parse_text(src)
    h = FOLD_SEED
    for foot in slice_feet(bits).feet:
        h = (h * FOLD_B + foot) % Q
    return h


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def _cli(argv: List[str]) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    if len(argv) < 2:
        print("usage: host_staging.py <chant.txt>")
        return 1
    path = argv[1]
    bits = parse_file(path)
    sr = slice_feet(bits)
    pkts = assemble_fold(sr.feet, with_bindu=True)
    fp = fold_fingerprint(path, is_file=True)
    print(f"# file           : {path}")
    print(f"# laghu/guru bits : {sr.n_bits}  ({sr.n_bits - bits.count(1)} laghu / {bits.count(1)} guru)")
    print(f"# feet            : {len(sr.feet)}  (final foot zUnya-padded with {sr.pad_bits} bits)")
    print(f"# packets         : {len(pkts)}  (incl. 1 bindu exit)")
    print(f"# fold fingerprint: {fp}  (0x{fp:04x})")
    for p in pkts:
        op = (p >> DATA_BITS) & 0xF
        print(f"{p:08x}  op={op:2d}")
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli(sys.argv))
