#!/usr/bin/env python3
"""
Ansh-108 Core S3 -- Python verification leg for rns_verify.v / fold_hash.v
==========================================================================
Leg 1 of the standing 5-leg gate.

fold_hash's correctness reduces to two things, both checked here:
  (A) the Barrett reducer barrett28(a) == a mod q for EVERY a in [0, 2^28) --
      proven EXHAUSTIVELY (numpy, chunked) over all 268,435,456 inputs. This is
      the authoritative reducer proof (the S3 analogue of barrett_check.c).
  (B) given a correct reducer, the Horner step is the algebraic identity
      next_h = (barrett28(h*108) + barrett28(data)) mod q = (h*108 + data) mod q.
      Cross-checked bit-exact vs golden_model.py FOLD over millions of random
      (h, data) one-step updates, plus the golden feet/order/determinism tests.

rns_verify is the trivial residue-equality flag; checked vs golden VERIFY.
"""
import os, sys, random
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from golden_model import (AnshCoreGolden, encode_packet, encode_data_packet,    # noqa: E402
                          FOLD, VERIFY, Q, FOLD_B, FOLD_SEED, fold_text)

MU = 21843                       # floor(2^28 / 12289), same constant as ntt
MASK28 = (1 << 28) - 1


# --- bit-exact scalar model of the RTL Barrett reducer (mirrors fold_hash.v) -- #
def barrett28(a):
    am = a * MU
    qest = am >> 28
    r = a - qest * Q
    return (r - Q) if r >= Q else r


def next_h(h, d):
    """RTL Horner step: reduce the two summands then modular-add."""
    return (barrett28(h * FOLD_B) + barrett28(d & MASK28)) % Q


def main():
    fails = 0

    def check(name, cond):
        nonlocal fails
        print(f"  [{'PASS' if cond else 'FAIL'}] {name}")
        if not cond:
            fails += 1

    print("Ansh-108 S3 -- rns_verify / fold_hash verification leg")

    # (A) EXHAUSTIVE Barrett proof over all 2^28 inputs (numpy, chunked) -------- #
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
    check(f"barrett28(a) == a mod q for ALL {total:,} inputs a in [0,2^28) (complete)",
          bad == 0)

    # (B) Horner step bit-exact vs golden_model over random (h, data) ----------- #
    random.seed(108)
    core = AnshCoreGolden()
    N = 2_000_000
    ok = True
    for _ in range(N):
        h0 = random.randrange(Q)
        d = random.randrange(1 << 28)
        core.h = h0
        gh = core.execute(encode_data_packet(FOLD, d)).value   # golden FOLD
        if not (next_h(h0, d) == gh == (h0 * FOLD_B + d) % Q):
            ok = False
            break
    check(f"RTL Horner step == golden FOLD == (h*108+data) mod q over {N:,} pairs", ok)

    # directed: term > q, seed behaviour, order-sensitivity, determinism
    feet = [5, 9, (1 << 28) - 1]      # last term is the full 28-bit max
    h = FOLD_SEED
    for f in feet:
        h = next_h(h, f)
    core.h = FOLD_SEED
    for f in feet:
        gh = core.execute(encode_data_packet(FOLD, f)).value
    check("RTL feet-chain == golden feet-chain (incl. 28-bit-max term)", h == gh)
    check("FOLD order matters (aA vs Aa)", fold_text("aA") != fold_text("Aa"))
    check("FOLD deterministic (same text -> same stamp)",
          fold_text("aAaAbcD") == fold_text("aAaAbcD"))

    # seed: a fresh fold starting from h0=1 (Horner can't collapse to 0)
    check("seed h0 = 1 (blank wax)", FOLD_SEED == 1 and next_h(1, 0) == 108 % Q)

    # (C) rns_verify model vs golden VERIFY ------------------------------------ #
    vcore = AnshCoreGolden()
    vok = True
    for _ in range(200000):
        x = random.randrange(Q)
        y = x if random.random() < 0.5 else random.randrange(Q)
        gv = vcore.execute(encode_packet(VERIFY, x, y)).value
        if not ((1 if x == y else 0) == gv):
            vok = False
            break
    corners = [(0, 0), (Q - 1, Q - 1), (0, Q - 1), (7, 7), (7, 8)]
    cok = all((1 if x == y else 0) == vcore.execute(encode_packet(VERIFY, x, y)).value
              for x, y in corners)
    check("VERIFY (x==y) == golden over 200k random (half equal)", vok)
    check("VERIFY corners exact", cok)

    print(f"\n{'ALL PASS' if fails == 0 else str(fails) + ' FAILURE(S)'}")
    return fails


if __name__ == "__main__":
    raise SystemExit(main())
