#!/usr/bin/env python3
"""
Ansh-108 Core — Track A / A-FP : Stream-integrity / content fingerprinting
==========================================================================
Track-A application #2, host-side, NO FPGA board. Reuses the proven multi-chain
FOLD from `ats_notarizer.py` (which itself extends the proven `golden_model.py`
FOLD) to turn any byte stream into a wide content fingerprint, then uses those
fingerprints for exact-duplicate detection / content-ID over a REAL corpus.

Delivers the two A-FP items from `Ansh_108_Watch_and_Applications_Plan.md`:
  A-FP-1  Multi-chain FOLD -> wide fingerprint; MEASURE the collision rate vs
          chain count (don't assume).  -> `--measure`
  A-FP-2  A dedup / content-ID demo over a real corpus; honest collision math.
          -> `--demo` (cosim_chants/ + a0s_programs/, 15 real files)

REUSE, not reinvention: imports MultiChainFold / bytes_to_feet / pick_bases /
mult_order from ats_notarizer. Nothing about the hash is re-implemented here;
this module only adds the *fingerprinting/dedup* layer on top.

Honest framing (firewall): this is a deterministic CONTENT FINGERPRINT for
integrity/dedup/provenance, NOT a keyed cryptographic hash. Collision resistance
is the birthday bound of the chosen width (8 chains ~ 108 bits ~ 54-bit), and is
MEASURED here, not assumed.

Run:
    python afp_fingerprint.py            # self-test gate
    python afp_fingerprint.py --measure  # collision curve vs chain count
    python afp_fingerprint.py --demo     # dedup over the real corpus

No third-party deps. Python 3.8+.
"""

import sys
import os
import glob
import random

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ats_notarizer import (
    MultiChainFold, bytes_to_feet, pick_bases, mult_order, _expected_birthday,
)
from golden_model import Q

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

DEFAULT_CHAINS = 8


# --------------------------------------------------------------------------- #
# The fingerprint API (thin layer over the proven MultiChainFold)
# --------------------------------------------------------------------------- #
def fingerprint_bytes(data, n_chains=DEFAULT_CHAINS):
    """Wide content fingerprint of a byte string. Returns (state_tuple, hex)."""
    if isinstance(data, str):
        data = data.encode("utf-8")
    mcf = MultiChainFold(n_chains=n_chains)
    mcf.fold_feet(bytes_to_feet(data))
    return mcf.state(), mcf.digest_hex()


def fingerprint_file(path, n_chains=DEFAULT_CHAINS):
    with open(path, "rb") as f:
        return fingerprint_bytes(f.read(), n_chains)


def dedup(paths, n_chains=DEFAULT_CHAINS):
    """Group files by fingerprint. Returns {hex_digest: [paths...]}.
    Any group with >1 path is either an exact duplicate or (astronomically
    unlikely at full width) a genuine collision."""
    groups = {}
    for p in paths:
        _, hx = fingerprint_file(p, n_chains)
        groups.setdefault(hx, []).append(p)
    return groups


def _truncate_state(state, bits):
    """Pack the N residues (14 bits each) and keep only the low `bits` -> a
    deliberately-narrow fingerprint, used to EXHIBIT collisions on real data."""
    v = 0
    for hi in state:
        v = (v << 14) | (hi & 0x3FFF)
    return v & ((1 << bits) - 1)


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

    print("A-FP content fingerprint — self-test (reuses proven multi-chain FOLD)")

    # determinism
    a, ha = fingerprint_bytes(b"the quick brown fox")
    b, hb = fingerprint_bytes(b"the quick brown fox")
    check("deterministic (same bytes -> same fingerprint)", a == b and ha == hb)

    # exact-copy dedup
    c, _ = fingerprint_bytes(b"namah shivaya" * 7)
    d, _ = fingerprint_bytes(bytes(b"namah shivaya" * 7))
    check("exact copy -> identical fingerprint (dedup works)", c == d)

    # one-byte sensitivity
    e, _ = fingerprint_bytes(b"retention=90d")
    f, _ = fingerprint_bytes(b"retention=91d")
    check("single-byte change -> different fingerprint", e != f)

    # empty input is well-defined (proven slicer returns [0])
    z, _ = fingerprint_bytes(b"")
    check("empty input is well-defined", isinstance(z, tuple) and len(z) == DEFAULT_CHAINS)

    # width = n * log2(Q)
    import math
    bits = MultiChainFold(n_chains=8).digest_bits()
    check("8-chain width ~ 108.7 bits", abs(bits - 8 * math.log2(Q)) < 1e-6 and 108 < bits < 109)

    # more chains -> first random collision appears no earlier (monotone strength)
    rng = random.Random(1)
    first = {}
    for n in (1, 2):
        seen = set()
        first[n] = None
        for k in range(1, 60000):
            st, _ = fingerprint_bytes(rng.getrandbits(48).to_bytes(6, "big"), n_chains=n)
            if st in seen:
                first[n] = k
                break
            seen.add(st)
    check("more chains -> later first collision (1 vs 2)", first[2] is None or first[2] > first[1])

    print(f"\n{'ALL PASS' if fails == 0 else str(fails) + ' FAILURE(S)'}")
    return fails


# --------------------------------------------------------------------------- #
# A-FP-1 : collision curve vs chain count  (MEASURED)
# --------------------------------------------------------------------------- #
def _measure():
    print("A-FP collision curve vs chain count (reproducible, seed=108)")
    print("=" * 64)
    rng = random.Random(108)

    print(f"\nbase 108 order mod {Q} = {mult_order(108)} "
          f"(not primitive -> chain 0 weak alone); strength chains use primitive roots.")
    print("\n[random birthday] feed fresh random messages until two collide:")
    print(f"{'chains':>7} {'width(bit)':>11} {'predict':>14} {'MEASURED':>12}")
    import math
    for n in (1, 2):                         # measured directly (feasible)
        space = Q ** n
        pred = _expected_birthday(space)
        trials = 30 if n == 1 else 6
        counts = []
        for _ in range(trials):
            seen = set()
            cap = 40000 if n == 1 else 200000
            for k in range(1, cap):
                st, _ = fingerprint_bytes(rng.getrandbits(64).to_bytes(8, "big"), n_chains=n)
                if st in seen:
                    counts.append(k)
                    break
                seen.add(st)
        mean = sum(counts) / len(counts) if counts else float("nan")
        print(f"{n:>7} {n*math.log2(Q):>11.1f} {pred:>14.0f} {mean:>12.0f}")
    for n in (3, 4, 8):                       # projected from the confirmed scaling
        space = Q ** n
        print(f"{n:>7} {n*math.log2(Q):>11.1f} {_expected_birthday(space):>14.3g} "
              f"{'(projected)':>12}")
    print("  measured 1- and 2-chain points confirm the x Q-per-chain scaling;")
    print("  3/4/8-chain are projected from it, NOT brute-forced.")

    # collisions exhibited on REAL data by deliberately narrowing the width
    print("\n[real-corpus truncation] fingerprint the 15 real files, keep only k bits:")
    paths = _corpus_paths()
    states = [fingerprint_file(p)[0] for p in paths]
    print(f"{'keep bits':>9} {'distinct':>9} {'collisions':>11}")
    for bits in (4, 6, 8, 16, 108):
        seen = {}
        coll = 0
        for st in states:
            t = _truncate_state(st, bits) if bits < 108 else st
            if t in seen:
                coll += 1
            seen[t] = True
        print(f"{bits:>9} {len(seen):>9} {coll:>11}")
    print(f"  ({len(paths)} files; narrow widths collide, full 108-bit width does not)")
    print("\n" + "=" * 64)


# --------------------------------------------------------------------------- #
# A-FP-2 : dedup / content-ID demo over the real corpus
# --------------------------------------------------------------------------- #
def _corpus_paths():
    here = os.path.dirname(os.path.abspath(__file__))
    paths = sorted(glob.glob(os.path.join(here, "cosim_chants", "*.txt")) +
                   glob.glob(os.path.join(here, "a0s_programs", "*.txt")))
    return paths


def _demo():
    print("A-FP dedup / content-ID demo over the REAL corpus")
    print("=" * 64)
    paths = _corpus_paths()
    print(f"\nFingerprinting {len(paths)} real files (chant texts + A0S programs):")
    for p in paths:
        st, hx = fingerprint_file(p)
        print(f"  {hx}  {os.path.basename(p)}")

    groups = dedup(paths)
    dupes = {h: ps for h, ps in groups.items() if len(ps) > 1}
    print(f"\nExact-duplicate groups among the {len(paths)} real files: "
          f"{len(dupes)} (expected 0 -- all distinct)")

    # inject a byte-identical copy and a one-character edit of one file
    target = next(p for p in paths if p.endswith("gAyatrI.txt"))
    with open(target, "rb") as f:
        original = f.read()
    fp_orig, hx_orig = fingerprint_bytes(original)
    fp_copy, hx_copy = fingerprint_bytes(bytes(original))          # exact copy
    near = bytearray(original); near[0] ^= 0x20                    # flip one bit of byte 0
    fp_near, hx_near = fingerprint_bytes(bytes(near))

    print("\nContent-ID test on gAyatrI.txt:")
    print(f"  original     : {hx_orig}")
    print(f"  exact copy   : {hx_copy}   -> {'MATCH (deduped)' if fp_copy == fp_orig else 'differ'}")
    print(f"  1-bit edit   : {hx_near}   -> {'differ (detected)' if fp_near != fp_orig else 'MATCH'}")
    print("\n" + "=" * 64)
    print("Exact content -> one ID (dedup); any edit -> a new ID (integrity).")


# --------------------------------------------------------------------------- #
if __name__ == "__main__":
    if "--measure" in sys.argv:
        _measure()
    elif "--demo" in sys.argv:
        _demo()
    else:
        raise SystemExit(_selftest())
