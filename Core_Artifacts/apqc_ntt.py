#!/usr/bin/env python3
"""
Ansh-108 Core — Track A / A-PQC : Post-Quantum (Falcon) NTT accelerator model
=============================================================================
Track-A application #3, host-side, NO FPGA board. Maps the negacyclic NTT used
by lattice signatures onto the chip's proven q = 12289 lane: every butterfly
multiply is exactly the chip's measured `ntt_mul12289` op `(x*y) mod 12289`
(routed 109.3 MHz, 178 LUT/2 DSP, bitwuzla full-correctness proof), and every
butterfly add/sub is `(x +/- y) mod 12289`.

  ***  HONESTY CORRECTION to the Watch & Applications Plan  ***
The plan says "12289 is the Kyber/ML-KEM & Dilithium NTT prime." That is WRONG:
  - Kyber / ML-KEM (FIPS 203)     q = 3329
  - Dilithium / ML-DSA (FIPS 204) q = 8380417
  - Falcon / FN-DSA (FIPS 206)    q = 12289      <-- the chip's prime
  - NewHope (deprecated)          q = 12289
So this lane natively accelerates FALCON / NewHope, NOT Kyber/Dilithium. Kyber
and Dilithium use a *different* modulus -> a different datapath (Class B), not
this core. q-1 = 12288 = 2^12*3, so 12289 supports a negacyclic NTT up to n=2048
(Falcon uses n=512 and n=1024).

Delivers the three A-PQC items:
  A-PQC-1  forward+inverse negacyclic NTT on the 12289 lane; every multiply routed
           through the proven chip op; validated vs schoolbook negacyclic mult.
  A-PQC-2  constant-time scope (the butterfly network is data-independent control
           flow -> defeats TIMING channels; power/EM explicitly out of scope).
  A-PQC-3  op-count benchmark + the honest verdict (not a per-op CPU-beater; wins
           on constant-time determinism + perf/watt + replication).  -> `--measure`

Run:
    python apqc_ntt.py            # self-test gate (roundtrip + vs schoolbook)
    python apqc_ntt.py --measure  # op counts, cycle estimate, honest verdict

No third-party deps. Python 3.8+.
"""
import sys
import os
import random

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from golden_model import Q                      # 12289, the proven lane prime

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

G = 11                                          # a primitive root of 12289 (order 12288)

# instrumentation: count the chip ops so the benchmark is honest
_COUNT = {"mul": 0, "add": 0, "sub": 0}


def chip_mul(x, y):
    """The proven ntt_mul12289 op: (x*y) mod 12289."""
    _COUNT["mul"] += 1
    return (x * y) % Q


def chip_add(x, y):
    _COUNT["add"] += 1
    return (x + y) % Q


def chip_sub(x, y):
    _COUNT["sub"] += 1
    return (x - y) % Q


def reset_counts():
    for k in _COUNT:
        _COUNT[k] = 0


# --------------------------------------------------------------------------- #
# Per-n parameters: psi = primitive 2n-th root, omega = psi^2 (n-th root)
# --------------------------------------------------------------------------- #
def params(n):
    assert (Q - 1) % (2 * n) == 0, f"q=12289 does not support negacyclic n={n}"
    psi = pow(G, (Q - 1) // (2 * n), Q)
    return {
        "psi": psi,
        "psi_inv": pow(psi, -1, Q),
        "omega": (psi * psi) % Q,
        "omega_inv": pow((psi * psi) % Q, -1, Q),
        "n_inv": pow(n, -1, Q),
    }


# --------------------------------------------------------------------------- #
# Iterative cyclic NTT / INTT  (Cooley-Tukey, all ops via chip primitives)
# --------------------------------------------------------------------------- #
def _bitrev(a):
    a = a[:]
    n = len(a)
    j = 0
    for i in range(1, n):
        bit = n >> 1
        while j & bit:
            j ^= bit
            bit >>= 1
        j ^= bit
        if i < j:
            a[i], a[j] = a[j], a[i]
    return a


def ntt(a, omega):
    a = _bitrev(a)
    n = len(a)
    length = 2
    while length <= n:
        wlen = pow(omega, n // length, Q)        # one-time twiddle (host precompute)
        for i in range(0, n, length):
            w = 1
            half = length >> 1
            for j in range(half):
                u = a[i + j]
                v = chip_mul(a[i + j + half], w)
                a[i + j] = chip_add(u, v)
                a[i + j + half] = chip_sub(u, v)
                w = chip_mul(w, wlen)
        length <<= 1
    return a


def intt(a, omega_inv, n_inv):
    a = ntt(a, omega_inv)
    return [chip_mul(x, n_inv) for x in a]


# --------------------------------------------------------------------------- #
# Negacyclic multiply in Z_q[x]/(x^n + 1) via psi pre/post scaling
# --------------------------------------------------------------------------- #
def negacyclic_mul(a, b, n, p=None):
    p = p or params(n)
    psi_pow = [pow(p["psi"], i, Q) for i in range(n)]        # host twiddle tables
    psii_pow = [pow(p["psi_inv"], i, Q) for i in range(n)]
    ah = [chip_mul(a[i], psi_pow[i]) for i in range(n)]
    bh = [chip_mul(b[i], psi_pow[i]) for i in range(n)]
    A = ntt(ah, p["omega"])
    B = ntt(bh, p["omega"])
    C = [chip_mul(A[i], B[i]) for i in range(n)]
    ch = intt(C, p["omega_inv"], p["n_inv"])
    return [chip_mul(ch[i], psii_pow[i]) for i in range(n)]


def schoolbook_negacyclic(a, b, n):
    """Reference: (a*b) mod (x^n + 1), the ground truth the NTT must match."""
    c = [0] * n
    for i in range(n):
        for j in range(n):
            k = i + j
            t = (a[i] * b[j]) % Q
            if k < n:
                c[k] = (c[k] + t) % Q
            else:
                c[k - n] = (c[k - n] - t) % Q       # x^n = -1
    return c


# --------------------------------------------------------------------------- #
# Self-test gate
# --------------------------------------------------------------------------- #
def _selftest():
    fails = 0

    def check(name, cond):
        nonlocal fails
        print(f"  [{'PASS' if cond else 'FAIL'}] {name}")
        if not cond:
            fails += 1

    print("A-PQC Falcon NTT (q=12289) — self-test")
    print(f"  q=12289 = Falcon/NewHope prime (NOT Kyber 3329 / Dilithium 8380417)")

    rng = random.Random(12289)

    for n in (256, 512, 1024):                  # Falcon uses 512 and 1024
        p = params(n)
        a = [rng.randrange(Q) for _ in range(n)]

        # NTT then INTT is the identity
        rt = intt(ntt(a[:], p["omega"]), p["omega_inv"], p["n_inv"])
        check(f"n={n}: INTT(NTT(a)) == a (roundtrip)", rt == a)

        # NTT-based negacyclic mult == schoolbook, over several random pairs
        ok = True
        for _ in range(5):
            x = [rng.randrange(Q) for _ in range(n)]
            y = [rng.randrange(Q) for _ in range(n)]
            ok &= negacyclic_mul(x, y, n, p) == schoolbook_negacyclic(x, y, n)
        check(f"n={n}: NTT mult == schoolbook negacyclic (5 random pairs)", ok)

    # constant-time structure: op count depends ONLY on n, never on the data
    n = 512
    p = params(n)
    reset_counts()
    negacyclic_mul([0] * n, [0] * n, n, p)
    zeros = dict(_COUNT)
    reset_counts()
    negacyclic_mul([rng.randrange(Q) for _ in range(n)],
                   [rng.randrange(Q) for _ in range(n)], n, p)
    rand = dict(_COUNT)
    check("constant-time: op counts identical for all-zero vs random input",
          zeros == rand)

    # the multiply is literally the proven chip op
    check("chip_mul == (x*y) mod 12289 (the proven ntt_mul12289 op)",
          all(chip_mul(x, y) == (x * y) % Q for x, y in
              [(0, 0), (1, 1), (12288, 12288), (6000, 7000), (12288, 2)]))

    print(f"\n{'ALL PASS' if fails == 0 else str(fails) + ' FAILURE(S)'}")
    return fails


# --------------------------------------------------------------------------- #
# A-PQC-3 : op-count benchmark + honest verdict
# --------------------------------------------------------------------------- #
def _measure():
    import time
    print("A-PQC benchmark — Falcon negacyclic mult on the 12289 lane")
    print("=" * 66)
    print("q=12289 = Falcon/NewHope prime. Kyber(3329)/Dilithium(8380417) would")
    print("need a different modulus = a different datapath (Class B), not this core.")
    FMAX = 109.3e6     # measured ntt_mul12289 routed clock; 1 result/cycle pipelined

    rng = random.Random(7)
    print(f"\n{'n':>6} {'fwd-NTT muls':>13} {'1x neg-mul muls':>16} "
          f"{'mul-bound cycles':>17} {'@109.3MHz':>11} {'py model':>10}")
    for n in (512, 1024):
        p = params(n)
        a = [rng.randrange(Q) for _ in range(n)]
        b = [rng.randrange(Q) for _ in range(n)]

        reset_counts()
        ntt(a[:], p["omega"])
        fwd_muls = _COUNT["mul"]

        reset_counts()
        t0 = time.perf_counter()
        negacyclic_mul(a, b, n, p)
        dt = time.perf_counter() - t0
        muls = _COUNT["mul"]

        # mul-bound lower bound on a single pipelined ntt_mul core (1 result/cycle)
        cyc = muls
        secs = cyc / FMAX
        print(f"{n:>6} {fwd_muls:>13} {muls:>16} {cyc:>17} "
              f"{secs*1e6:>9.2f}us {dt*1e6:>8.1f}us")

    print("\nHonest verdict (carry-forward firewall):")
    print("  - The multiply IS the proven chip op (bitwuzla-verified, 109.3 MHz).")
    print("  - 'cycles' counts MULTIPLIES only (a single ntt_mul core, pipelined);")
    print("    adds/subs, host orchestration, and memory traffic are NOT counted,")
    print("    so the us figure is a multiply-bound LOWER bound, not a wall-clock.")
    print("  - NOT a per-op CPU-beater: a modern CPU does one 12289-mul about as")
    print("    fast. The chip's win is CONSTANT-TIME determinism (no data-dependent")
    print("    branch -> no timing side-channel), perf/watt, and REPLICATION")
    print("    (many ntt_mul cores running independent butterflies in lockstep).")
    print("  - Side-channel scope: constant-time defeats TIMING channels only,")
    print("    and only if the whole host datapath stays constant-time; power/EM")
    print("    are out of scope and need separate countermeasures.")
    print("\n" + "=" * 66)


# --------------------------------------------------------------------------- #
if __name__ == "__main__":
    if "--measure" in sys.argv:
        _measure()
    else:
        raise SystemExit(_selftest())
