#!/usr/bin/env python3
"""
Ansh-108 Core S2 -- Python verification leg for rns_add.v / rns_sub.v
=====================================================================
Leg 1 of the standing 5-leg gate. Two independent things are checked:

  (A) A *bit-exact* model of each RTL reducer (the exact 15-bit subtract / 14-bit
      truncating add the Verilog performs) is verified EXHAUSTIVELY over its entire
      reachable input domain. Because the reducer's output depends only on the raw
      sum / difference, sweeping every possible sum (add) and every possible signed
      difference (sub) is a COMPLETE proof of the reduction logic -- not a sample.

  (B) The same bit-exact model is cross-checked against golden_model.py's ADD/SUB
      ops over millions of random packets, confirming the RTL algorithm and the
      source-of-truth agree on the real packet operand domain.

Honesty note: this proves the *algorithm*. The RTL register transfer itself (latency,
the actual gate behaviour) is covered by legs 2 (iverilog) and 3 (SymbiYosys).
"""
import os, sys, random

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from golden_model import AnshCoreGolden, encode_packet, ADD, SUB, Q  # noqa: E402

MASK14 = (1 << 14) - 1
MASK15 = (1 << 15) - 1


# --- bit-exact models of the two RTL reducers (mirror the .v exactly) --------- #
def rtl_add(x, y):
    """rns_add.v: s1 = x+y (15-bit); out = (s1>=Q)? s1-Q : s1[13:0]."""
    s1 = (x + y) & MASK15
    return (s1 - Q) if s1 >= Q else (s1 & MASK14)


def rtl_sub(x, y):
    """rns_sub.v: d1 = ({0,x}-{0,y}) 15-bit; out = d1[14]? (d1[13:0]+Q)&14b : d1[13:0]."""
    d1 = (x - y) & MASK15
    if (d1 >> 14) & 1:                       # borrow -> x < y
        return ((d1 & MASK14) + Q) & MASK14
    return d1 & MASK14


def main():
    fails = 0

    def check(name, cond):
        nonlocal fails
        print(f"  [{'PASS' if cond else 'FAIL'}] {name}")
        if not cond:
            fails += 1

    print("Ansh-108 S2 -- rns_add / rns_sub verification leg")

    # (A) EXHAUSTIVE reducer proofs ------------------------------------------- #
    # add: sweep every reachable sum s in [0, 2Q-2]; reducer must equal s % Q.
    add_ok = all(((s - Q) if s >= Q else s) == s % Q for s in range(0, 2 * Q - 1))
    check(f"ADD reducer exact over all {2*Q-1} sums [0,2q-2]  (complete)", add_ok)

    # also drive the model the way the RTL does, over every legal operand-pair sum
    add_ok2 = all(rtl_add(x, y) == (x + y) % Q
                  for x in (0, 1, Q - 1, 6144, 6145, 12288) for y in range(Q))
    check("ADD model == (x+y) mod q over key x x all y  (sweep)", add_ok2)

    # sub: sweep every possible signed difference delta in [-(Q-1), Q-1]; the
    # reducer maps the wrapped 15-bit form back to the true residue. Complete.
    sub_ok = True
    for delta in range(-(Q - 1), Q):
        d1 = delta & MASK15
        out = ((d1 & MASK14) + Q) & MASK14 if (d1 >> 14) & 1 else (d1 & MASK14)
        if out != delta % Q:
            sub_ok = False
            break
    check(f"SUB reducer exact over all {2*Q-1} diffs [-(q-1),q-1]  (complete)", sub_ok)

    # (B) cross-check the bit-exact model vs the golden model over random packets #
    random.seed(108)
    core = AnshCoreGolden()
    N = 2_000_000
    am = sm = True
    for _ in range(N):
        x, y = random.randrange(Q), random.randrange(Q)
        ga = core.execute(encode_packet(ADD, x, y)).value
        gs = core.execute(encode_packet(SUB, x, y)).value
        am &= (rtl_add(x, y) == ga == (x + y) % Q)
        sm &= (rtl_sub(x, y) == gs == (x - y) % Q)
        if not (am and sm):
            break
    check(f"ADD: RTL-model == golden_model == true mod q over {N:,} random pairs", am)
    check(f"SUB: RTL-model == golden_model == true mod q over {N:,} random pairs", sm)

    # directed corners incl. sub borrow path
    corners = [(0, 0), (Q - 1, Q - 1), (Q - 1, 0), (0, Q - 1), (1, 2), (12288, 1)]
    ca = all(rtl_add(x, y) == (x + y) % Q for x, y in corners)
    cs = all(rtl_sub(x, y) == (x - y) % Q for x, y in corners)
    check("ADD corners exact", ca)
    check("SUB corners exact (incl. borrow x<y)", cs)

    print(f"\n{'ALL PASS' if fails == 0 else str(fails) + ' FAILURE(S)'}")
    return fails


if __name__ == "__main__":
    raise SystemExit(main())
