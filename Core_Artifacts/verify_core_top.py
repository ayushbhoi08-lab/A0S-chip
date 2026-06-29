#!/usr/bin/env python3
"""
Ansh-108 Core S4 -- Python verification leg for the integrated core_top.
========================================================================
Leg 1 of the standing 5-leg gate for Phase-2 front-end (opcode_decode +
result_mode + rns_reduce + core_top, reusing the proven datapath cores).

This leg does three jobs, all anchored on the S1 source-of-truth golden_model.py:

  (A) REDUCE (opcode 3) is a thin wrapper around the S3-proven Barrett reducer.
      We RE-PROVE barrett28(a) == a mod q EXHAUSTIVELY over all 2^28 inputs (the
      same complete proof as S3/barrett_check.c) -> REDUCE numeric correctness is
      complete. (Full-correctness via SMT is the modulo-reference wall; owned here.)

  (B) Emit a golden PROGRAM (core_top_program.txt): random packets for the six
      value-deterministic ops {MUL,ADD,SUB,REDUCE,VERIFY,FOLD}, each with its
      expected result computed by golden_model.execute(). The iverilog TB (Leg 2)
      replays this exact program and checks the DUT in-order against these golden
      values -> the RTL is verified against golden_model.py directly.

  (C) Cross-check the on-chip tick semantics (carry-free RNS residues -> host CRT
      recombine) against golden_model's RnsCounter across the Maha-Yuga wrap, and
      re-confirm FOLD order-sensitivity / determinism vs golden.

No on-chip op is value-checked by anything except golden_model (or an exhaustive
proof). READ_TICK's value is cycle-dependent, so it is latency/reconstruct-checked
in the TB and its math is proven here against golden; it is not in the replay set.
"""
import os, sys, random
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from golden_model import (                                            # noqa: E402
    AnshCoreGolden, RnsCounter, crt_reconstruct, COUNTER_MODULI, MAHA_YUGA,
    encode_packet, encode_data_packet, fold_text,
    MUL, ADD, SUB, REDUCE, FOLD, VERIFY, Q, FOLD_B, FOLD_SEED)

HERE = os.path.dirname(os.path.abspath(__file__))
MU = 21843                       # floor(2^28 / 12289), same constant as ntt/fold
MASK28 = (1 << 28) - 1


def barrett28(a):                # bit-exact scalar model of rns_reduce.v
    qest = (a * MU) >> 28
    r = a - qest * Q
    return (r - Q) if r >= Q else r


def main():
    fails = 0

    def check(name, cond):
        nonlocal fails
        print(f"  [{'PASS' if cond else 'FAIL'}] {name}")
        if not cond:
            fails += 1

    print("Ansh-108 S4 -- core_top integration verification leg")

    # (A) EXHAUSTIVE REDUCE/Barrett proof over all 2^28 inputs ------------------ #
    total = 1 << 28
    chunk = 1 << 23
    bad = 0
    for start in range(0, total, chunk):
        a = np.arange(start, min(start + chunk, total), dtype=np.int64)
        am = a * MU
        qest = am >> 28
        r = a - qest * Q
        out = np.where(r >= Q, r - Q, r)
        bad += int(np.count_nonzero(out != (a % Q)))
        if bad:
            break
    check(f"REDUCE: barrett28(a) == a mod q for ALL {total:,} inputs a in [0,2^28)",
          bad == 0)

    # spot-confirm the scalar model used to build the program matches numpy
    check("REDUCE scalar model == numpy over corners",
          all(barrett28(v) == v % Q for v in
              [0, 1, Q - 1, Q, Q + 1, 12288, 12289, MASK28, (1 << 27), 268435455]))

    # (B) GOLDEN PROGRAM (golden_model authoritative) --------------------------- #
    random.seed(108)
    core = AnshCoreGolden()                 # fresh: fold h = seed = 1 (TB flushes first)
    NPROG = 6000
    ops_arith = [MUL, ADD, SUB]
    lines = []
    counts = {MUL: 0, ADD: 0, SUB: 0, REDUCE: 0, VERIFY: 0, FOLD: 0}
    for _ in range(NPROG):
        op = random.choice([MUL, ADD, SUB, REDUCE, VERIFY, FOLD])
        if op in ops_arith:
            x, y = random.randrange(Q), random.randrange(Q)
            pkt = encode_packet(op, x, y)
        elif op == VERIFY:
            x = random.randrange(Q)
            y = x if random.random() < 0.5 else random.randrange(Q)
            pkt = encode_packet(op, x, y)
        elif op == REDUCE:
            d = random.randrange(1 << 28)
            pkt = encode_data_packet(op, d)
        else:  # FOLD
            d = random.randrange(1 << 28)
            pkt = encode_data_packet(op, d)
        exp = core.execute(pkt).value       # GOLDEN value (fold chains in `core`)
        lines.append(f"{pkt & 0xFFFFFFFF:08x} {exp & 0x7FFFFF:06x}")
        counts[op] += 1

    prog_path = os.path.join(HERE, "core_top_program.txt")
    with open(prog_path, "w") as fh:
        fh.write("\n".join(lines) + "\n")
    check(f"wrote golden program {NPROG} ops -> core_top_program.txt "
          f"(MUL {counts[MUL]} ADD {counts[ADD]} SUB {counts[SUB]} "
          f"RED {counts[REDUCE]} VER {counts[VERIFY]} FOLD {counts[FOLD]})",
          os.path.exists(prog_path) and len(lines) == NPROG)

    # sanity: golden program values equal independent % math (golden == arithmetic)
    core2 = AnshCoreGolden()
    ok = True
    for ln in lines:
        pkt = int(ln.split()[0], 16)
        exp = int(ln.split()[1], 16)
        op = (pkt >> 28) & 0xF
        data = pkt & MASK28
        x = data & 0x3FFF
        y = (data >> 14) & 0x3FFF
        if op == MUL:
            ref = (x * y) % Q
        elif op == ADD:
            ref = (x + y) % Q
        elif op == SUB:
            ref = (x - y) % Q
        elif op == REDUCE:
            ref = data % Q
        elif op == VERIFY:
            ref = 1 if x == y else 0
        else:  # FOLD
            ref = None
        g = core2.execute(pkt).value
        if ref is not None and not (ref == exp == g):
            ok = False
            break
        if ref is None and exp != g:
            ok = False
            break
    check("golden program: stored expected == golden_model == arithmetic", ok)

    # FOLD streaming burst reference (for the TB's back-to-back throughput test)
    random.seed(4242)
    burst = [random.randrange(1 << 28) for _ in range(64)]
    h = FOLD_SEED
    for d in burst:
        h = (h * FOLD_B + d) % Q
    with open(os.path.join(HERE, "core_top_foldburst.txt"), "w") as fh:
        for d in burst:
            fh.write(f"{d & MASK28:07x}\n")
        fh.write(f"# final_h {h:04x}\n")
    # confirm vs golden
    cb = AnshCoreGolden()
    cb.h = FOLD_SEED
    for d in burst:
        gh = cb.execute(encode_data_packet(FOLD, d)).value
    check("FOLD burst final hash == golden Horner chain", gh == h)

    # (C) tick semantics: on-chip residues -> host CRT == golden RnsCounter ------ #
    counter = RnsCounter()
    test_Ns = [0, 1, 255, 256, 27, 625, 4096, 100000, MAHA_YUGA - 1, MAHA_YUGA,
               MAHA_YUGA + 7, 2 * MAHA_YUGA + 123]
    tok = True
    for N in test_Ns:
        res = (N % 256, N % 27, N % 625)            # what tick_counter.v holds after N ticks
        recon = crt_reconstruct(list(res), COUNTER_MODULI)
        if recon != N % MAHA_YUGA:
            tok = False
            break
    # and equality vs an actually-ticked golden counter over a contiguous run
    counter2 = RnsCounter()
    for N in range(0, 2000):
        res = counter2.residues()
        if (res[0] != N % 256 or res[1] != N % 27 or res[2] != N % 625
                or counter2.value() != N % MAHA_YUGA):
            tok = False
            break
        counter2.tick(1)
    check("tick residues -> host CRT == golden counter value (incl. Maha-Yuga wrap)", tok)

    # (D) FOLD order / determinism vs golden (carry-forward from S3) ------------- #
    check("FOLD order matters (aA vs Aa)", fold_text("aA") != fold_text("Aa"))
    check("FOLD deterministic (same text -> same stamp)",
          fold_text("aAaAbcD") == fold_text("aAaAbcD"))

    print(f"\n{'ALL PASS' if fails == 0 else str(fails) + ' FAILURE(S)'}")
    return fails


if __name__ == "__main__":
    raise SystemExit(main())
