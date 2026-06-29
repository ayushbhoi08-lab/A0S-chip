#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Phase 5 math proof: the 5-modulus RNS over Z/41580.
Moduli {4,27,5,7,11}. Proves (a) pairwise coprime, (b) the CRT map is a
bijection over all 41,580 states, (c) computes the reconstruction idempotents,
(d) verifies branch-free track-wise multiply reconstructs the true product."""
import random
from math import gcd
from functools import reduce

MODS = [4, 27, 5, 7, 11]
M = reduce(lambda a, b: a * b, MODS)
print(f"moduli = {MODS}")
print(f"M = product = {M}")
assert M == 41580, M

# (a) pairwise coprime
ok = True
for i in range(len(MODS)):
    for j in range(i + 1, len(MODS)):
        g = gcd(MODS[i], MODS[j])
        if g != 1:
            ok = False
            print(f"  NOT coprime: {MODS[i]},{MODS[j]} gcd={g}")
print(f"(a) pairwise coprime : {'PASS' if ok else 'FAIL'}")

# (c) CRT idempotents: e_i with e_i = 1 mod m_i, 0 mod m_j (j!=i).
#     reconstruct: x = (sum e_i * r_i) mod M.
def modinv(a, m):
    return pow(a, -1, m)

idemp = []
for m_i in MODS:
    Mi = M // m_i
    e_i = (Mi * modinv(Mi % m_i, m_i)) % M
    idemp.append(e_i)
print("(c) idempotents (reconstruction weights), x = (sum e_i*r_i) mod M:")
for m_i, e_i in zip(MODS, idemp):
    # sanity: e_i = 1 mod m_i, 0 mod every other
    assert e_i % m_i == 1
    assert all(e_i % m_j == 0 for m_j in MODS if m_j != m_i)
    print(f"    e[mod {m_i:>2}] = {e_i}")

def residues(x):
    return tuple(x % m for m in MODS)

def reconstruct(rs):
    return sum(e * r for e, r in zip(idemp, rs)) % M

# (b) bijection over all 41,580 states
seen = set()
bij = True
for x in range(M):
    t = residues(x)
    if t in seen:
        bij = False
        break
    seen.add(t)
    if reconstruct(t) != x:
        bij = False
        break
print(f"(b) CRT bijection over all {M} states : {'PASS' if bij else 'FAIL'} "
      f"({len(seen)} distinct residue-tuples)")

# (d) branch-free multiply: track-wise multiply then reconstruct == true product
def mul_tracks(rx, ry):
    return tuple((a * b) % m for a, b, m in zip(rx, ry, MODS))

random.seed(1)
N = 3_000_000
bad = 0
# structured edge cases first
edge = [(0, 0), (1, 1), (M - 1, M - 1), (M - 1, 2), (12345, 6789), (41579, 41579)]
for x, y in edge:
    if reconstruct(mul_tracks(residues(x), residues(y))) != (x * y) % M:
        bad += 1
for _ in range(N):
    x = random.randrange(M); y = random.randrange(M)
    if reconstruct(mul_tracks(residues(x), residues(y))) != (x * y) % M:
        bad += 1
print(f"(d) branch-free multiply, {N:,} random + {len(edge)} edge pairs : "
      f"{'PASS' if bad == 0 else f'FAIL ({bad} mismatches)'}")

# also verify add, for completeness
bad_add = 0
for _ in range(500_000):
    x = random.randrange(M); y = random.randrange(M)
    radd = tuple((a + b) % m for a, b, m in zip(residues(x), residues(y), MODS))
    if reconstruct(radd) != (x + y) % M:
        bad_add += 1
print(f"(e) branch-free add, 500,000 random pairs : "
      f"{'PASS' if bad_add == 0 else f'FAIL ({bad_add})'}")

print("\n--- constants for RTL (Phase 5 core) ---")
print(f"M = {M}  (needs {M.bit_length()}-bit output)")
print(f"max input = {M-1}  (needs {(M-1).bit_length()}-bit input ports)")
print(f"idempotents e = {idemp}")
maxsum = sum(e * (m - 1) for e, m in zip(idemp, MODS))
print(f"max weighted sum before final mod = {maxsum}  "
      f"({maxsum.bit_length()}-bit) -> final reduction is mod {M} of an "
      f"{maxsum.bit_length()}-bit value")
