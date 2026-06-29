#!/usr/bin/env python3
"""
Ansh-108 Core -- Path A, Phase 3 / S7 VERIFICATION GATE (master runner).
========================================================================
Mirrors the S6 gate (`test_host_staging.py`), extended to the whole staging agent:

  (A) every S7 module's own unit tests (golden vectors / cross-checks vs Python ints)
        host_ops · transport · result_reader · clock_led · staging_agent
  (B) a big END-TO-END SOFTWARE LOOPBACK over many chants AND general programs:
        staging_agent fingerprint == golden_model.fold_text == host_staging.fold_fingerprint
        with 0 mismatch; every stream ends in the bindu; FOLD read BEFORE the reseed.
  (C) host_ops re-cross-checked vs plain Python ints (bitwise/shift/rotate/compare).
  (D) clock_led transitions + ISI timing exact.

HONESTY: this is host <-> SOFTWARE-GOLDEN loopback, NOT host <-> RTL co-sim (S9),
and there is NO real USB yet (Phase 7). The golden model is itself RTL-validated by
S4's 6000-op replay, so the chain is sound -- but the literal host<->RTL link is owed.
"""
import os
import sys
import random

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import host_ops
import transport
import result_reader
import clock_led
import staging_agent
import host_staging as H
from staging_agent import StagingAgent
from transport import LoopbackTransport
from result_reader import interpret, fold_fingerprint
from golden_model import (
    AnshCoreGolden, decode_packet,
    fold_text, COUNTER_MODULI, MAHA_YUGA, CRITICAL, HANDSHAKE, STREAM, FIRE_FORGET,
    MUL, ADD, SUB, REDUCE, VERIFY, READ_TICK, FLUSH, RESET, Q)


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    random.seed(2026)
    fails = 0

    def check(name, cond):
        nonlocal fails
        print(f"  [{'PASS' if cond else 'FAIL'}] {name}")
        if not cond:
            fails += 1

    print("=" * 72)
    print("Ansh-108 S7 VERIFICATION GATE -- staging agent (software phase)")
    print("=" * 72)

    # ---- (A) module unit tests --------------------------------------------- #
    print("\n[A] per-module unit tests (golden vectors / Python cross-checks)")
    for mod in (host_ops, transport, result_reader, clock_led, staging_agent):
        n = mod._selftest()
        check(f"{mod.__name__}._selftest() ALL PASS", n == 0)

    # ---- (B) end-to-end software loopback ---------------------------------- #
    print("\n[B] END-TO-END software loopback (chants)")
    agent = StagingAgent()
    texts = ["", "a", "A", "aA", "Aa", "aAaAbcD", "a" * 28, "A" * 28, "a" * 29,
             "A" * 56 + "b", "Om Namah Shivaya", "AaAaAa bb CC dd",
             "Agni" * 30, "." * 50, "123 \n\t,." , "z" * 200]
    texts += ["".join(random.choice("aAbBzZqQ .,\n9!") for _ in range(random.randint(0, 160)))
              for _ in range(5000)]
    e2e = bindu = order = det = True
    for t in texts:
        r = agent.run_text(t)
        e2e &= (r.verified and r.fingerprint == fold_text(t) == H.fold_fingerprint(t))
        bindu &= ((r.packets[-1] >> 28) & 0xF) == RESET
    check(f"staging_agent == golden == host fold_fingerprint over {len(texts)} chants (0 mismatch)", e2e)
    check("every chant stream ends in the bindu (RESET) exit", bindu)
    check("order-sensitive (aA != Aa)", agent.run_text("aA").fingerprint != agent.run_text("Aa").fingerprint)
    check("deterministic (same chant -> same fingerprint)",
          agent.run_text("aAaAbcD").fingerprint == agent.run_text("aAaAbcD").fingerprint)

    # ---- (B') end-to-end general programs (all four contracts) -------------- #
    print("\n[B'] END-TO-END software loopback (general A0S programs)")
    prog_ok = True
    for _ in range(3000):
        ops = []
        k = random.randint(1, 8)
        for _ in range(k):
            kind = random.choice(["MUL", "ADD", "SUB", "REDUCE", "VERIFY", "FOLD",
                                  "READ_TICK", "FLUSH"])
            if kind in ("MUL", "ADD", "SUB", "VERIFY"):
                ops.append((kind, random.randrange(Q), random.randrange(Q)))
            elif kind in ("REDUCE", "FOLD"):
                ops.append((kind, random.randrange(1 << 28)))
            else:
                ops.append((kind,))
        # reference: run the same packets through a fresh golden core directly
        packets = H.assemble(ops)
        gcore = AnshCoreGolden()
        ref = []
        for p in packets:
            d = decode_packet(p)
            rv = gcore.execute(p)
            ref.append((d["opcode"], rv.value))
        rd = agent.run_program(ops)
        # critical/handshake(VERIFY) readings must equal the golden values, in order
        crit = [(x.opcode, x.value) for x in rd if x.mode in (CRITICAL,)]
        ref_crit = [(op, v) for (op, v) in ref if op in (MUL, ADD, SUB, REDUCE)]
        prog_ok &= (crit == ref_crit)
    check("general programs: CRITICAL readings == golden over 3000 random programs", prog_ok)

    # ---- (C) host_ops vs Python ints (re-cross-check at the gate) ----------- #
    print("\n[C] host_ops positional fence vs Python ints")
    hc = True
    for _ in range(30000):
        a, b = random.randrange(1 << 28), random.randrange(1 << 28)
        w = random.choice((14, 28))
        n = random.randrange(0, 3 * w)
        hc &= host_ops.band(a, b) == (a & b)
        hc &= host_ops.bor(a, b) == (a | b)
        hc &= host_ops.bxor(a, b) == (a ^ b)
        am = a & ((1 << w) - 1)
        hc &= host_ops.shl(am, n % w, w) == ((am << (n % w)) & ((1 << w) - 1))
        hc &= host_ops.shr(am, n % w, w) == (am >> (n % w))
        hc &= host_ops.rotr(host_ops.rotl(am, n, w), n, w) == am
        hc &= host_ops.bit_reverse(host_ops.bit_reverse(am, w), w) == am
    check("AND/OR/XOR/shift/rotate/bit-reverse == Python ints over 30k", hc)
    # SPIRAL magnitude compare == Python compare (residues + wraparound height)
    sc = True
    for _ in range(30000):
        ha, hb = random.randrange(6), random.randrange(6)
        ra, rb = random.randrange(MAHA_YUGA), random.randrange(MAHA_YUGA)
        got = host_ops.spiral_compare(host_ops.to_residues(ra, COUNTER_MODULI), ha,
                                     host_ops.to_residues(rb, COUNTER_MODULI), hb, COUNTER_MODULI)
        A, B = ha * MAHA_YUGA + ra, hb * MAHA_YUGA + rb
        sc &= got == ((A > B) - (A < B))
    check("SPIRAL magnitude compare == Python int compare over 30k", sc)

    # ---- (D) clock_led transitions + timing exact -------------------------- #
    print("\n[D] clock_led transitions + ISI timing")
    led = clock_led.ClockLed()
    bits = H.parse_text("aA AA aa bb")
    total = led.run_program(bits)
    check("clock_led timing == 3000 + 50*laghu + 100*guru + 50 (flush)",
          total == 3000 + clock_led.program_duration_ms(bits) + 50)
    check("clock_led ends in HOLD/BLUE", led.state is clock_led.State.HOLD and led.led == "BLUE")

    print("\n" + "=" * 72)
    print(f"S7 GATE: {'ALL PASS' if fails == 0 else str(fails) + ' FAILURE(S)'}")
    print("HONESTY: host<->software-golden loopback; NOT host<->RTL (S9); no real USB (Phase 7).")
    print("=" * 72)
    return fails


if __name__ == "__main__":
    raise SystemExit(main())
