#!/usr/bin/env python3
"""
Ansh-108 Core -- Path A, Phase 3 / S7: RESULT READER (the four result contracts).
=================================================================================
core_top exposes four result-mode contracts (opcode_decode.result_mode / the
golden RESULT_MODE table). This module interprets the `CoreEvent` stream a
transport returns, honoring each contract exactly:

  * CRITICAL  (MUL/ADD/SUB/REDUCE): await out_valid, read the held result.
  * STREAM    (FOLD): collect each pushed fold result as it streams.
  * HANDSHAKE (VERIFY/READ_TICK): VERIFY -> 1-bit pass/fail; READ_TICK -> the raw
                tick residues, which the HOST CRT-recombines (host_ops) into an
                absolute tick (the residue chip never reconstructs -- Path-A fence).
  * FIRE-FORGET (FLUSH/RESET): no result; RESET also fires the bindu pulse.

CRITICAL CONTRACT (the S6 rule): the FOLD fingerprint must be read from the stream
BEFORE the trailing bindu (RESET) reseeds the fold accumulator. `interpret()` and
`fold_fingerprint()` capture the last STREAM push that precedes the first bindu --
never the post-reseed value.

Pure Python 3.8+, no third-party deps. Importable + `python result_reader.py` test.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Sequence, Tuple
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from golden_model import (                                            # noqa: E402
    CRITICAL, STREAM, HANDSHAKE, FIRE_FORGET, COUNTER_MODULI, FOLD_SEED,
    MUL, ADD, SUB, REDUCE, FOLD, VERIFY, READ_TICK, FLUSH, RESET, MAHA_YUGA)
from transport import CoreEvent                                       # noqa: E402
import host_ops                                                       # noqa: E402


# --------------------------------------------------------------------------- #
# One interpreted reading
# --------------------------------------------------------------------------- #
@dataclass
class Reading:
    opcode: int
    opname: str
    mode: str
    value: Optional[int]          # interpreted result (arith / fingerprint / tick / bool)
    detail: str                   # human-readable line


# --------------------------------------------------------------------------- #
# Per-contract readers (operate on a single CoreEvent, except STREAM)
# --------------------------------------------------------------------------- #
def read_critical(ev: CoreEvent) -> Reading:
    """CRITICAL: the host awaited out_valid and reads the held result word."""
    return Reading(ev.opcode, ev.opname, CRITICAL, ev.value,
                   f"{ev.opname} = {ev.value}")


def read_handshake(ev: CoreEvent, moduli: Sequence[int] = COUNTER_MODULI) -> Reading:
    """HANDSHAKE: VERIFY -> bool; READ_TICK -> CRT-recombine residues host-side."""
    if ev.opcode == VERIFY:
        ok = bool(ev.value)
        return Reading(ev.opcode, ev.opname, HANDSHAKE, ev.value,
                       f"VERIFY -> {'EQUAL' if ok else 'NOT EQUAL'}")
    if ev.opcode == READ_TICK:
        if ev.tick_residues is None:
            raise ValueError("READ_TICK event carries no tick residues")
        # Path-A fence: the chip handed back residues; the HOST reconstructs.
        tick = host_ops.reconstruct(ev.tick_residues, moduli)
        # independent positional cross-check (Garner) -- must agree
        assert host_ops.mixed_radix_value(ev.tick_residues, moduli) == tick
        return Reading(ev.opcode, ev.opname, HANDSHAKE, tick,
                       f"READ_TICK residues {tuple(ev.tick_residues)} -> tick {tick} "
                       f"(within-period; absolute across Pralayas via SpiralHeightTracker)")
    raise ValueError(f"opcode {ev.opcode} is not a handshake op")


def read_fire_forget(ev: CoreEvent) -> Reading:
    """FIRE-FORGET: no result. RESET also raises the bindu pulse -- watch for it."""
    note = "bindu (sequence-complete) pulse" if ev.bindu else "no result"
    return Reading(ev.opcode, ev.opname, FIRE_FORGET, None,
                   f"{ev.opname} -> {note}")


# --------------------------------------------------------------------------- #
# STREAM collector -- the read-before-bindu fold fingerprint
# --------------------------------------------------------------------------- #
@dataclass
class StreamCollector:
    """Collect FOLD pushes as they stream. The fingerprint is the last push seen
    BEFORE a bindu (RESET) reseeds the accumulator. Feeding events after the bindu
    starts a fresh sequence (the seed)."""
    last: Optional[int] = None
    pushes: int = 0
    _sealed: bool = field(default=False, repr=False)

    def feed(self, ev: CoreEvent) -> None:
        if ev.result_mode == STREAM:
            self.last = ev.held_fold        # the value pushed this cycle
            self.pushes += 1
        elif ev.bindu:                       # the trailing bindu seals the fingerprint
            self._sealed = True

    @property
    def fingerprint(self) -> int:
        return self.last if self.last is not None else FOLD_SEED

    @property
    def sealed(self) -> bool:
        return self._sealed


def fold_fingerprint(events: Sequence[CoreEvent]) -> int:
    """The whole-pattern fingerprint = the last FOLD push BEFORE the first bindu."""
    last = None
    for ev in events:
        if ev.result_mode == STREAM:
            last = ev.held_fold
        elif ev.bindu:
            break                            # read before the reseed
    return last if last is not None else FOLD_SEED


# --------------------------------------------------------------------------- #
# Whole-stream interpreter (router over the four contracts)
# --------------------------------------------------------------------------- #
def interpret(events: Sequence[CoreEvent],
              moduli: Sequence[int] = COUNTER_MODULI) -> List[Reading]:
    """Walk a CoreEvent stream and produce human-readable Readings, honoring the
    read-before-bindu rule: pooled FOLD pushes are sealed into ONE fingerprint
    Reading at the bindu, captured before the reseed."""
    out: List[Reading] = []
    collector = StreamCollector()
    for ev in events:
        if ev.result_mode == STREAM:
            collector.feed(ev)               # pool; do not emit per-foot
        elif ev.bindu:
            # seal the fold fingerprint (before reseed), then note the bindu
            if collector.pushes:
                out.append(Reading(FOLD, "FOLD", STREAM, collector.fingerprint,
                                   f"FOLD fingerprint = {collector.fingerprint} "
                                   f"(over {collector.pushes} feet, read before bindu)"))
            out.append(read_fire_forget(ev))
            collector = StreamCollector()    # next sequence
        elif ev.result_mode == CRITICAL:
            out.append(read_critical(ev))
        elif ev.result_mode == HANDSHAKE:
            out.append(read_handshake(ev, moduli))
        elif ev.result_mode == FIRE_FORGET:
            out.append(read_fire_forget(ev))
    # a stream that never hit a bindu still yields its running fingerprint
    if collector.pushes and not collector.sealed:
        out.append(Reading(FOLD, "FOLD", STREAM, collector.fingerprint,
                           f"FOLD fingerprint = {collector.fingerprint} "
                           f"(over {collector.pushes} feet, no bindu seen)"))
    return out


# --------------------------------------------------------------------------- #
# Self-test
# --------------------------------------------------------------------------- #
def _selftest() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    import random
    import host_staging as H
    from transport import LoopbackTransport
    from golden_model import fold_text as _ft, encode_packet as _ep
    random.seed(108)
    fails = 0

    def check(name, cond):
        nonlocal fails
        print(f"  [{'PASS' if cond else 'FAIL'}] {name}")
        if not cond:
            fails += 1

    print("Ansh-108 S7 -- result_reader (four result contracts) self-test")

    # ---- CRITICAL: arith readings == golden --------------------------------- #
    t = LoopbackTransport().open()
    cok = True
    for _ in range(20000):
        x, y = random.randrange(12289), random.randrange(12289)
        for op, ref in ((MUL, (x * y) % 12289), (ADD, (x + y) % 12289), (SUB, (x - y) % 12289)):
            ev = t.send([_ep(op, x, y)])[0]
            r = read_critical(ev)
            cok &= (r.value == ref and r.mode == CRITICAL)
    check("CRITICAL MUL/ADD/SUB readings == golden over 60k", cok)

    # ---- STREAM: fold fingerprint read BEFORE bindu == fold_text ------------ #
    sok = interp_ok = True
    texts = ["", "a", "A", "aA", "Aa", "Om Namah Shivaya", "A" * 56 + "b"]
    texts += ["".join(random.choice("aAbZz .,9") for _ in range(random.randint(0, 90)))
              for _ in range(3000)]
    for txt in texts:
        pk = H.text_to_fold_packets(txt)
        tr = LoopbackTransport().open()
        ev = tr.send(pk)
        sok &= (fold_fingerprint(ev) == _ft(txt))
        # interpret() yields exactly one fold-fingerprint reading + one bindu reading
        rd = interpret(ev)
        fps = [r for r in rd if r.mode == STREAM]
        bns = [r for r in rd if r.opcode == RESET]
        interp_ok &= (len(fps) == 1 and fps[0].value == _ft(txt) and len(bns) == 1)
    check(f"STREAM fingerprint (read before bindu) == fold_text over {len(texts)}", sok)
    check("interpret() seals exactly one fold fingerprint + one bindu per chant", interp_ok)

    # ---- HANDSHAKE: VERIFY bool + READ_TICK host CRT reconstruct ------------- #
    t = LoopbackTransport().open()
    v_eq = read_handshake(t.send([_ep(VERIFY, 1234, 1234)])[0])
    v_ne = read_handshake(t.send([_ep(VERIFY, 1234, 1235)])[0])
    check("HANDSHAKE VERIFY -> True/False", v_eq.value == 1 and v_ne.value == 0)

    # READ_TICK: send N filler packets then READ_TICK; host reconstruct == count.
    rt_ok = True
    for n in (0, 1, 5, 26, 27, 100, 624, 625, 4000):
        tr = LoopbackTransport(ticks_per_packet=1).open()
        seq = H.assemble([("FOLD", 0)] * n + [("READ_TICK",)], with_bindu=False)
        ev = tr.send(seq)
        r = read_handshake(ev[-1])
        rt_ok &= (r.value == n % MAHA_YUGA)        # within-period absolute tick
    check("HANDSHAKE READ_TICK host-CRT reconstruct == tick count (within period)", rt_ok)

    # cross-period absolute tick via host_ops.SpiralHeightTracker over READ_TICK reads
    trk = host_ops.SpiralHeightTracker(COUNTER_MODULI)
    tr = LoopbackTransport(ticks_per_packet=1).open()
    span_ok = True
    sent = 0                                    # global packets before the current send
    # take a READ_TICK every `gap` packets, several times across >2 Pralayas
    gap = MAHA_YUGA // 3                          # < M, so samples never alias
    for _ in range(8):
        seq = H.assemble([("FLUSH",)] * (gap - 1) + [("READ_TICK",)], with_bindu=False)
        ev = tr.send(seq)
        # READ_TICK is the last packet; it captured the tick at its own global index
        expected = sent + gap - 1
        sent += gap
        absolute = trk.update(ev[-1].tick_residues)
        span_ok &= (absolute == expected)
    check("READ_TICK + SpiralHeightTracker absolute tick across a Pralaya == cumulative", span_ok)

    # ---- FIRE-FORGET: FLUSH/RESET no result; RESET fires bindu -------------- #
    t = LoopbackTransport().open()
    ev_flush = t.send([H.pkt_data(FLUSH, 0)])[0]
    ev_reset = t.send([H.pkt_data(RESET, 0)])[0]
    rf = read_fire_forget(ev_flush)
    rr = read_fire_forget(ev_reset)
    check("FIRE-FORGET FLUSH no result / RESET fires bindu",
          rf.value is None and not ev_flush.bindu and rr.value is None and ev_reset.bindu)

    # ---- mixed program routes to the right contracts ------------------------ #
    prog = [("MUL", 6, 7), ("VERIFY", 9, 9), ("FOLD", 3), ("FOLD", 4),
            ("READ_TICK",), ("FLUSH",)]
    ev = LoopbackTransport().open().send(H.assemble(prog))   # appends bindu
    rd = interpret(ev)
    modes = [r.mode for r in rd]
    route_ok = (CRITICAL in modes and HANDSHAKE in modes and STREAM in modes
                and FIRE_FORGET in modes and rd[0].value == 42)
    check("interpret() routes a mixed program to all four contracts", route_ok)

    print(f"\n{'ALL PASS' if fails == 0 else str(fails) + ' FAILURE(S)'}")
    return fails


if __name__ == "__main__":
    raise SystemExit(_selftest())
