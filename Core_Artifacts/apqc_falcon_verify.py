#!/usr/bin/env python3
"""
Ansh-108 Core — A-PQC : Falcon-512 VERIFY harness (the chip's NTT in the loop)
=============================================================================
A faithful MODEL of Falcon-512 signature verification whose heavy polynomial
multiply runs on the chip's proven 12289 lane (apqc_ntt.negacyclic_mul). Shows
exactly where the AS108 core sits inside a real post-quantum primitive.

The Falcon-512 verification predicate (FIPS 206 / FN-DSA), ring Z_q[x]/(x^n+1),
n = 512, q = 12289:
      accept  <=>  s1 + s2*h == HashToPoint(salt || msg)   AND   ||(s1,s2)||^2 <= B
  i.e.  s1 = HashToPoint(salt||msg) - s2*h   must be SHORT.

What is REAL here:
  - the real ring (n=512, q=12289) and the spec norm bound B = 34034726;
  - HashToPoint = the spec's SHAKE-256 rejection sampler (reject t >= 5*q);
  - the polynomial multiply s2*h = the chip's negacyclic NTT (apqc_ntt), and it
    is asserted == a schoolbook reference inside the verify path;
  - the accept/reject DECISION logic (equation + centered-norm shortness test);
  - the compare/norm step is HOST-side -> consistent with the Path A fence.

What is NOT real (stated plainly, per the honesty rule):
  - This is NOT bit-interoperable with reference Falcon: no signature
    DECOMPRESSION (we take s2 as an integer polynomial, not Falcon's compressed
    byte format) and no exact key encoding.
  - The ACCEPT test uses a CONSTRUCTED short (s1,s2) pair, NOT a trapdoor-sampled
    real signature -- Falcon SIGNING needs the NTRU lattice Gaussian sampler,
    which is out of scope. So this harness exercises and validates the VERIFIER's
    arithmetic + decision; it does not assert unforgeability (that's the signer's
    trapdoor + the lattice hardness, not tested here).

Run:
    python apqc_falcon_verify.py            # self-test gate
    python apqc_falcon_verify.py --demo     # one accept + three reject, with norms

No third-party deps. Python 3.8+ (hashlib.shake_256).
"""
import sys
import os
import hashlib
import random

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from apqc_ntt import (
    Q, params, negacyclic_mul, schoolbook_negacyclic, reset_counts, _COUNT,
)

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

N = 512
# spec squared-norm acceptance bounds (floor(beta^2)); Falcon-512 / Falcon-1024
BETA2 = {512: 34034726, 1024: 70265242}


# --------------------------------------------------------------------------- #
# HashToPoint — the real Falcon SHAKE-256 rejection sampler
# --------------------------------------------------------------------------- #
def hash_to_point(data: bytes, n: int = N, q: int = Q):
    """SHAKE-256(data) -> n coefficients in [0,q). Read 2 bytes -> 16-bit t;
    reject t >= k*q (k = floor(2^16/q) = 5) to kill modular bias; else t mod q."""
    limit = (1 << 16) // q * q                       # 5*12289 = 61445
    need = 2 * (n + 64) * 2                           # generous initial XOF bytes
    buf = hashlib.shake_256(data).digest(need)
    out = []
    i = 0
    while len(out) < n:
        if i + 2 > len(buf):                          # extremely rare: extend the XOF
            need *= 2
            buf = hashlib.shake_256(data).digest(need)
        t = (buf[i] << 8) | buf[i + 1]
        i += 2
        if t < limit:
            out.append(t % q)
    return out


# --------------------------------------------------------------------------- #
# polynomial / norm helpers  (the compare/norm parts are HOST-side)
# --------------------------------------------------------------------------- #
def poly_sub(a, b, q=Q):
    return [(x - y) % q for x, y in zip(a, b)]


def poly_add(a, b, q=Q):
    return [(x + y) % q for x, y in zip(a, b)]


def center(a, q=Q):
    """Map coefficients to (-q/2, q/2] -> the representative the norm uses."""
    return [((x + q // 2) % q) - q // 2 for x in a]


def sqnorm(*polys):
    return sum(x * x for p in polys for x in center(p))


# --------------------------------------------------------------------------- #
# The verifier
# --------------------------------------------------------------------------- #
def verify_core(c, s2, h, n=N, use_chip=True):
    """Given the hashed point c, the signature poly s2, and the public key h:
    recompute s1 = c - s2*h (the s2*h via the CHIP NTT), return (accept, sqnorm)."""
    prod = negacyclic_mul(s2, h, n) if use_chip else schoolbook_negacyclic(s2, h, n)
    s1 = poly_sub(c, prod)
    nrm = sqnorm(s1, s2)
    return nrm <= BETA2[n], nrm


def verify(msg: bytes, sig, h, n=N):
    """Full verify: sig = (salt_bytes, s2_poly). Returns (accept, sqnorm)."""
    salt, s2 = sig
    c = hash_to_point(salt + msg, n)
    return verify_core(c, s2, h, n)


# --------------------------------------------------------------------------- #
# Test helpers (constructed data — NOT a real trapdoor signer)
# --------------------------------------------------------------------------- #
def short_poly(rng, n=N, sigma=80.0, q=Q):
    """A short, ~Gaussian polynomial (models a genuine signature's shortness)."""
    return [round(rng.gauss(0, sigma)) % q for _ in range(n)]


def uniform_poly(rng, n=N, q=Q):
    """A uniform public-key-like polynomial."""
    return [rng.randrange(q) for _ in range(n)]


def make_accepting(rng, h, n=N, sigma=80.0):
    """Construct a short (s1,s2) and the c that makes the equation hold:
    c = s1 + s2*h. (Honest: this is a constructed pair, not a signed message.)"""
    s1 = short_poly(rng, n, sigma)
    s2 = short_poly(rng, n, sigma)
    c = poly_add(center_to_pos(s1), negacyclic_mul(s2, h, n))
    return c, s1, s2


def center_to_pos(a, q=Q):
    return [x % q for x in a]


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

    print("A-PQC Falcon-512 verify — self-test (chip NTT in the loop)")
    rng = random.Random(512)
    h = uniform_poly(rng)

    # HashToPoint: deterministic, in range, message-sensitive
    c1 = hash_to_point(b"salt-A" + b"hello")
    c2 = hash_to_point(b"salt-A" + b"hello")
    c3 = hash_to_point(b"salt-A" + b"hellp")
    check("HashToPoint deterministic", c1 == c2)
    check("HashToPoint coeffs in [0,q)", all(0 <= x < Q for x in c1) and len(c1) == N)
    check("HashToPoint message-sensitive (1-byte change -> different c)", c1 != c3)

    # the chip NTT multiply used by verify == schoolbook (arithmetic is correct)
    s2 = short_poly(rng)
    check("verify's s2*h via chip NTT == schoolbook",
          negacyclic_mul(s2, h, N) == schoolbook_negacyclic(s2, h, N))

    # ACCEPT: a constructed short (s1,s2) with c = s1 + s2*h
    c, s1, s2 = make_accepting(rng, h, sigma=80.0)
    ok, nrm = verify_core(c, s2, h)
    check(f"short pair ACCEPTS (||.||^2={nrm} <= {BETA2[N]})", ok)

    # REJECT (shortness): equation holds but the pair is too long
    c_l, s1_l, s2_l = make_accepting(rng, h, sigma=240.0)
    ok_l, nrm_l = verify_core(c_l, s2_l, h)
    check(f"too-long pair REJECTS on the norm bound (||.||^2={nrm_l} > {BETA2[N]})",
          not ok_l)

    # REJECT (tamper): flip one coeff of s2 -> equation breaks -> s1 huge
    s2_t = s2[:]
    s2_t[7] = (s2_t[7] + 123) % Q
    ok_t, nrm_t = verify_core(c, s2_t, h)
    check("tampered s2 REJECTS (equation broken -> huge norm)", not ok_t)

    # REJECT (forgery attempt via REAL HashToPoint): a random short s2 against a
    # hashed c does NOT yield a short s1 -> reject (the honest reject path)
    salt = b"\x01" * 40
    forged_s2 = short_poly(rng)
    ok_f, nrm_f = verify(b"transfer 1000 to mallory", (salt, forged_s2), h)
    check("forged sig over a hashed message REJECTS", not ok_f)

    # the chip actually did the work: count multiplies in one full verify
    reset_counts()
    verify(b"a message", (salt, forged_s2), h)
    check(f"chip NTT did the multiply work in verify ({_COUNT['mul']} muls)",
          _COUNT["mul"] > 0)

    print(f"\n{'ALL PASS' if fails == 0 else str(fails) + ' FAILURE(S)'}")
    return fails


# --------------------------------------------------------------------------- #
def _demo():
    print("A-PQC Falcon-512 verify — worked demo")
    print("=" * 64)
    print(f"ring Z_{Q}[x]/(x^{N}+1);  accept bound ||(s1,s2)||^2 <= {BETA2[N]}")
    rng = random.Random(7)
    h = uniform_poly(rng)

    print("\n[1] genuine-style short signature (constructed short pair):")
    c, s1, s2 = make_accepting(rng, h, sigma=80.0)
    reset_counts()
    ok, nrm = verify_core(c, s2, h)
    print(f"    ||(s1,s2)||^2 = {nrm:>10}  -> {'ACCEPT' if ok else 'REJECT'}  "
          f"(chip did {_COUNT['mul']} NTT multiplies)")

    print("\n[2] same equation but the vector is too long:")
    c2, _, s2b = make_accepting(rng, h, sigma=240.0)
    ok2, nrm2 = verify_core(c2, s2b, h)
    print(f"    ||(s1,s2)||^2 = {nrm2:>10}  -> {'ACCEPT' if ok2 else 'REJECT'}  "
          f"(fails the shortness gate)")

    print("\n[3] tampered signature (one coeff of s2 changed):")
    s2t = s2[:]; s2t[7] = (s2t[7] + 123) % Q
    ok3, nrm3 = verify_core(c, s2t, h)
    print(f"    ||(s1,s2)||^2 = {nrm3:>10}  -> {'ACCEPT' if ok3 else 'REJECT'}  "
          f"(equation broken)")

    print("\n[4] forged signature over a real hashed message:")
    ok4, nrm4 = verify(b"transfer 1000 to mallory", (b'\x01' * 40, short_poly(rng)), h)
    print(f"    ||(s1,s2)||^2 = {nrm4:>10}  -> {'ACCEPT' if ok4 else 'REJECT'}  "
          f"(HashToPoint via real SHAKE-256)")
    print("\n" + "=" * 64)
    print("Verify = (equation holds) AND (vector is short). The chip's 12289 NTT")
    print("does the s2*h multiply; the norm/compare is host-side (Path A split).")


# --------------------------------------------------------------------------- #
if __name__ == "__main__":
    if "--demo" in sys.argv:
        _demo()
    else:
        raise SystemExit(_selftest())
