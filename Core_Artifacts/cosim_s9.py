#!/usr/bin/env python3
"""
Ansh-108 Core -- Path A, Phase 5 / S9: HOST <-> RTL CO-SIM DRIVER (Leg 1).
==========================================================================
Closes the last pre-silicon gap. Every prior ledger owed the same item: the host
packet stream was proven only against the SOFTWARE golden model, never against the
RTL `core_top`. S9 drives the REAL RTL with the REAL host pipeline and proves they
agree end to end:

    chant .txt / A0S program / op program
        -> the REAL host path (host_staging.text_to_fold_packets / a0s_parser /
           host_staging.assemble)                                  [no re-impl]
        -> the exact 32-bit packet stream
        -> cosim_vectors.txt        (one packet/line, with a record tag + pid)
        -> [tb_cosim_s9.v drives Icarus-simulated core_top, writes cosim_rtl_out.txt]
        -> check_cosim_s9.py: RTL fingerprint == golden, per program.

This module is Leg 1: it computes the golden expected values with the REAL S6/S7/S8
code (asserted below to be IMPORTS, not copies) and emits the driver vectors +
the golden sidecar. It does NOT touch any proven module.

Battery: corners (empty / 1 bit / exact-28 / 29 / 56+1 / a long mantra) + order
pair (aA vs Aa) + real chant .txt (sample_chant + cosim_chants/*) + every S8
a0s_programs/*.txt + op programs exercising VERIFY / REDUCE / arith / READ_TICK.

Pure Python 3.8+, no third-party deps.  `python cosim_s9.py` (re)writes the vectors.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Sequence, Tuple
import glob
import os
import sys

ART = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ART)

# --- the REAL host + golden code (imports, NOT copies) ---------------------- #
import golden_model as G                                               # noqa: E402
import host_staging as H                                               # noqa: E402
import a0s_parser as A                                                 # noqa: E402
import result_reader as R                                              # noqa: E402
from transport import LoopbackTransport                                # noqa: E402
from golden_model import (                                             # noqa: E402
    FOLD, RESET, FLUSH, FOLD_SEED, STREAM,
    MUL, ADD, SUB, REDUCE, VERIFY, READ_TICK)

# Leg-1 honesty: assert we are using the proven modules, not re-implementations.
assert H.text_to_fold_packets.__module__ == "host_staging", "host path must be S6"
assert H.assemble.__module__ == "host_staging", "assembler must be S6"
assert A.compile_program.__module__ == "a0s_parser", "A0S compiler must be S8"
assert G.fold_text.__module__ == "golden_model", "golden must be S1"
assert R.fold_fingerprint.__module__ == "result_reader", "reader must be S7"

VEC_FILE = os.path.join(ART, "cosim_vectors.txt")
GOLD_FILE = os.path.join(ART, "cosim_golden.txt")

# record tags consumed by tb_cosim_s9.v
REC_FOLD, REC_RESET, REC_FLUSH, REC_OP = 0, 1, 2, 3
# sentinel emitted in the golden file for READ_TICK (value is hardware-cycle
# determined; the comparator checks range + host CRT reconstruction instead).
TICK_SENTINEL = 0xFFFFFFFF


def _opcode(pkt: int) -> int:
    return (pkt >> 28) & 0xF


def _classify(pkt: int) -> int:
    op = _opcode(pkt)
    if op == FOLD:
        return REC_FOLD
    if op == RESET:
        return REC_RESET
    if op == FLUSH:
        return REC_FLUSH
    return REC_OP


# --------------------------------------------------------------------------- #
# Program record
# --------------------------------------------------------------------------- #
@dataclass
class Program:
    name: str
    kind: str                       # "chant" | "a0s" | "op"
    packets: List[int]
    fp: int                         # golden fingerprint (last committed maNDala)
    resets: int                     # # RESET/bindu packets (== # committed+aborted maNDalas)
    pushes: int                     # # FOLD packets (committed feet)
    ops: List[Tuple[int, Optional[int]]] = field(default_factory=list)  # (opcode, expected)


# --------------------------------------------------------------------------- #
# Independent golden fingerprint over a multi-segment stream (last-committed
# rule), via the REAL S7 loopback -- the SAME rule tb_cosim_s9.v applies to the
# RTL. For single-segment chants this collapses to fold_fingerprint == fold_text.
# --------------------------------------------------------------------------- #
def last_committed_fp(packets: Sequence[int]) -> int:
    events = LoopbackTransport().open().send(list(packets))
    prog_fp = FOLD_SEED
    seg_last: Optional[int] = None
    for ev in events:
        if ev.result_mode == STREAM:
            seg_last = ev.held_fold
        elif ev.bindu:
            if seg_last is not None:          # a committed maNDala
                prog_fp = seg_last
            seg_last = None
    return prog_fp


def _counts(packets: Sequence[int]) -> Tuple[int, int]:
    resets = sum(1 for p in packets if _opcode(p) == RESET)
    pushes = sum(1 for p in packets if _opcode(p) == FOLD)
    return resets, pushes


# --------------------------------------------------------------------------- #
# Battery builders (each uses the REAL host path)
# --------------------------------------------------------------------------- #
def chant_text(name: str, text: str) -> Program:
    pkts = H.text_to_fold_packets(text)                       # S6 host path
    fp_host = H.fold_fingerprint(text)                        # S6
    fp_gold = G.fold_text(text)                               # S1
    fp_lb = R.fold_fingerprint(LoopbackTransport().open().send(pkts))  # S7
    assert fp_host == fp_gold == fp_lb == last_committed_fp(pkts), \
        f"golden disagreement on {name!r}"
    resets, pushes = _counts(pkts)
    assert resets == 1, "a chant is a single committed maNDala"
    assert _opcode(pkts[-1]) == RESET, "stream must end in the bindu"
    return Program(name, "chant", pkts, fp_host, resets, pushes)


def chant_file(name: str, path: str) -> Program:
    pkts = H.text_to_fold_packets(path, is_file=True)         # S6 host path
    fp_host = H.fold_fingerprint(path, is_file=True)          # S6
    with open(path, "r", encoding="utf-8", errors="ignore") as fh:
        fp_gold = G.fold_text(fh.read())                      # S1
    fp_lb = R.fold_fingerprint(LoopbackTransport().open().send(pkts))
    assert fp_host == fp_gold == fp_lb == last_committed_fp(pkts), \
        f"golden disagreement on {name!r}"
    resets, pushes = _counts(pkts)
    return Program(name, "chant", pkts, fp_host, resets, pushes)


def a0s_file(name: str, path: str) -> Program:
    cr = A.compile_file(path)                                 # S8 A0S compiler
    pkts = cr.packets
    fp = cr.fingerprint                                       # last committed maNDala
    assert fp == last_committed_fp(pkts), f"A0S golden disagreement on {name!r}"
    resets, pushes = _counts(pkts)
    assert _opcode(pkts[-1]) == RESET, "A0S stream must end in a bindu"
    return Program(name, "a0s", pkts, fp, resets, pushes)


def op_program(name: str, ops: Sequence[tuple]) -> Program:
    pkts = H.assemble(ops)                                    # S6 assembler (+bindu)
    resets, pushes = _counts(pkts)
    # Only the gated, result-producing ops (those that classify as REC_OP) get a
    # golden O-line, in stream order. FLUSH/RESET fillers are fire-and-forget.
    expected: List[Tuple[int, Optional[int]]] = []
    for op in ops:
        opname = op[0]
        code = H._OP_BY_NAME[opname]
        if opname == "READ_TICK":
            expected.append((code, None))                    # tick = sentinel
        elif opname in H._FAST_OPS:                          # MUL/ADD/SUB/VERIFY
            v = G.AnshCoreGolden().execute(G.encode_packet(code, op[1], op[2])).value
            expected.append((code, v))
        elif opname == "REDUCE":                             # gated 28-bit reduce
            v = G.AnshCoreGolden().execute(G.encode_data_packet(code, op[1])).value
            expected.append((code, v))
        elif opname in ("FLUSH", "RESET", "SEED_FROM_TICK"):
            continue                                         # fire-forget filler
        else:
            raise ValueError(f"op program: unsupported op {opname}")
    # op programs fold nothing -> fingerprint is the seed (read before the bindu)
    return Program(name, "op", pkts, FOLD_SEED, resets, pushes, expected)


# a long mantra corner -- a few hundred syllables of real text (many feet).
_LONG = (("oM bhUr bhuvaH svaH tat savitur vareNyaM bhargo devasya dhImahi "
          "dhiyo yo naH pracodayAt ") * 4 +
         ("oM tryambakaM yajAmahe sugandhiM puSTivardhanam urvArukam iva "
          "bandhanAn mRtyor mukSIya mAmRtAt ") * 4)


def build_battery() -> List[Program]:
    progs: List[Program] = []

    # ---- corner cases (the boundary geometry of the slicer) ---------------- #
    progs.append(chant_text("empty", ""))                    # -> single zUnya foot
    progs.append(chant_text("one_laghu", "a"))               # 1 bit
    progs.append(chant_text("one_guru", "A"))                # 1 bit (MSB set)
    progs.append(chant_text("exact_28", "a" * 28))           # exactly one full foot
    progs.append(chant_text("twentynine", "a" * 29))         # 1 over -> 2 feet
    progs.append(chant_text("fiftysix_plus1", "A" * 56 + "b"))  # 2 full + 1 -> 3 feet
    progs.append(chant_text("long_mantra", _LONG))           # many feet

    # ---- order sensitivity pair (checked on the RTL) ----------------------- #
    progs.append(chant_text("order_aA", "aA"))
    progs.append(chant_text("order_Aa", "Aa"))

    # ---- real chant .txt files -------------------------------------------- #
    progs.append(chant_file("sample_chant", os.path.join(ART, "sample_chant.txt")))
    for path in sorted(glob.glob(os.path.join(ART, "cosim_chants", "*.txt"))):
        progs.append(chant_file("chant_" + os.path.splitext(os.path.basename(path))[0], path))

    # ---- every S8 A0S reference program ----------------------------------- #
    for path in sorted(glob.glob(os.path.join(ART, "a0s_programs", "*.txt"))):
        progs.append(a0s_file("a0s_" + os.path.splitext(os.path.basename(path))[0], path))

    # ---- op programs: VERIFY / REDUCE / arith / READ_TICK ----------------- #
    progs.append(op_program("op_verify", [
        ("VERIFY", 777, 777), ("VERIFY", 777, 778),
        ("VERIFY", 0, 0), ("VERIFY", 12288, 12288), ("VERIFY", 1, 12288)]))
    progs.append(op_program("op_reduce", [
        ("REDUCE", (1 << 28) - 1), ("REDUCE", G.Q), ("REDUCE", 2 * G.Q),
        ("REDUCE", 0), ("REDUCE", 12345)]))
    progs.append(op_program("op_arith", [
        ("MUL", 12345, 6789), ("ADD", 9000, 9000), ("SUB", 3, 10),
        ("MUL", 0, 9999), ("ADD", 12288, 1)]))
    progs.append(op_program("op_readtick", [
        ("READ_TICK",), ("FLUSH",), ("FLUSH",), ("FLUSH",), ("READ_TICK",)]))

    return progs


# --------------------------------------------------------------------------- #
# Emit the driver vectors + golden sidecar
# --------------------------------------------------------------------------- #
def write_vectors(progs: Sequence[Program]) -> Tuple[int, int]:
    total_pkts = 0
    with open(VEC_FILE, "w", encoding="ascii", newline="\n") as vf:
        for pid, prog in enumerate(progs):
            for pkt in prog.packets:
                vf.write(f"{pid} {_classify(pkt)} {pkt:08x}\n")
                total_pkts += 1
    with open(GOLD_FILE, "w", encoding="ascii", newline="\n") as gf:
        for pid, prog in enumerate(progs):
            gf.write(f"P {pid} {prog.fp:04x} {prog.resets} {prog.resets} "
                     f"{prog.pushes} {prog.kind} {prog.name}\n")
            for opidx, (code, exp) in enumerate(prog.ops):
                ev = TICK_SENTINEL if exp is None else exp
                gf.write(f"O {pid} {opidx} {code} {ev:08x}\n")
    return len(progs), total_pkts


def _cli(argv: List[str]) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    progs = build_battery()
    n, total = write_vectors(progs)
    print("Ansh-108 S9 -- co-sim driver (Leg 1: real host path -> vectors + golden)")
    print(f"  battery     : {n} programs, {total} packets")
    print(f"  vectors     : {VEC_FILE}")
    print(f"  golden side : {GOLD_FILE}")
    nfold = sum(1 for p in progs if p.kind == "chant")
    na0s = sum(1 for p in progs if p.kind == "a0s")
    nop = sum(1 for p in progs if p.kind == "op")
    print(f"  composition : {nfold} chant, {na0s} A0S, {nop} op programs")
    print("  per-program golden (fp = last committed maNDala, read before bindu):")
    for pid, p in enumerate(progs):
        opnote = f"  ops={len(p.ops)}" if p.ops else ""
        print(f"    [{pid:2d}] {p.name:<22s} {p.kind:<5s} fp={p.fp:5d} (0x{p.fp:04x})"
              f"  feet={p.pushes}  bindus={p.resets}{opnote}")
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli(sys.argv))
