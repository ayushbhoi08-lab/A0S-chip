#!/usr/bin/env python3
"""
Ansh-108 Core — A-PQC : Falcon byte-format CODEC (toward bit-exact interop)
===========================================================================
The piece that upgrades `apqc_falcon_verify.py` from a math model to a verifier
that consumes REAL Falcon byte strings: public-key decode and signature
Compress/Decompress, implemented exactly per the Falcon spec.

Falcon-512 (logn=9, n=512, q=12289) wire formats:
  - Public key : header (0x00|logn) || modq_encode(h)   = 1 + 896 = 897 bytes
                 (each of n coeffs in [0,q) packed in 14 bits, MSB-first)
  - Signature  : header (0x30|logn) || salt(40) || Compress(s2, slen)
                 = 1 + 40 + 625 = 666 bytes
  - Compress(x): sign bit, 7 low bits of |x| (MSB-first), then (|x|>>7) zeros and
                 a terminating 1; stream zero-padded to slen bytes.

This module is pure host-side (de)serialization — the residue arithmetic stays on
the chip via `apqc_falcon_verify`. Round-trip + format checks below are exact;
end-to-end interop against reference vectors is exercised by `apqc_interop_vector.py`.

Pure Python 3.8+. `python apqc_falcon_codec.py` runs the codec self-test.
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from apqc_ntt import Q

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# Falcon-512 parameters
LOGN = 9
N = 1 << LOGN                       # 512
SALT_LEN = 40
SIG_BYTES = 666                     # total signature length, Falcon-512
PK_BYTES = 897
HEAD_PK = 0x00 | LOGN              # 0x09
HEAD_SIG = 0x30 | LOGN            # 0x39  (compressed signature format)
SLEN = SIG_BYTES - 1 - SALT_LEN    # 625 compressed bytes
HIGH_CAP = 2047 >> 7               # bound the unary run (|x| <= 2047)


# --------------------------------------------------------------------------- #
# bit helpers
# --------------------------------------------------------------------------- #
def _bytes_to_bits(b):
    bits = []
    for byte in b:
        for k in range(7, -1, -1):
            bits.append((byte >> k) & 1)
    return bits


def _bits_to_bytes(bits):
    assert len(bits) % 8 == 0
    out = bytearray()
    for i in range(0, len(bits), 8):
        v = 0
        for k in range(8):
            v = (v << 1) | bits[i + k]
        out.append(v)
    return bytes(out)


# --------------------------------------------------------------------------- #
# public key:  14-bit MSB-first packing of n coefficients in [0,q)
# --------------------------------------------------------------------------- #
def encode_public_key(h, n=N):
    assert len(h) == n and all(0 <= x < Q for x in h)
    acc = 0
    accbits = 0
    out = bytearray([HEAD_PK])
    for v in h:
        acc = (acc << 14) | v
        accbits += 14
        while accbits >= 8:
            accbits -= 8
            out.append((acc >> accbits) & 0xFF)
    assert accbits == 0, "512*14 is byte-aligned"
    return bytes(out)


def decode_public_key(buf, n=N):
    if len(buf) != PK_BYTES or buf[0] != HEAD_PK:
        raise ValueError(f"bad public-key header/length ({buf[0]:#04x}, {len(buf)})")
    acc = 0
    accbits = 0
    h = []
    for byte in buf[1:]:
        acc = (acc << 8) | byte
        accbits += 8
        if accbits >= 14:
            accbits -= 14
            v = (acc >> accbits) & 0x3FFF
            if v >= Q:
                raise ValueError("public-key coefficient out of range")
            h.append(v)
    if len(h) != n:
        raise ValueError("public-key coefficient count mismatch")
    return h


# --------------------------------------------------------------------------- #
# signature s2:  Falcon Compress / Decompress
# --------------------------------------------------------------------------- #
def compress_sig(s, slen=SLEN):
    """Falcon Compress: returns slen bytes, or None if it does not fit."""
    bits = []
    for x in s:
        bits.append(1 if x < 0 else 0)
        y = abs(x)
        for i in range(6, -1, -1):          # 7 low bits, MSB-first
            bits.append((y >> i) & 1)
        bits.extend([0] * (y >> 7))         # high bits in unary
        bits.append(1)
    if len(bits) > slen * 8:
        return None                          # signer would retry
    bits.extend([0] * (slen * 8 - len(bits)))
    return _bits_to_bytes(bits)


def decompress_sig(buf, n=N):
    """Falcon Decompress: returns the s2 polynomial, or raises on a malformed
    encoding (negative zero, over-long unary, or non-zero trailing padding)."""
    bits = _bytes_to_bits(buf)
    pos = 0
    s = []
    for _ in range(n):
        if pos + 8 > len(bits):
            raise ValueError("truncated signature")
        sign = bits[pos]; pos += 1
        low = 0
        for _ in range(7):
            low = (low << 1) | bits[pos]; pos += 1
        high = 0
        while True:
            if pos >= len(bits):
                raise ValueError("truncated unary run")
            b = bits[pos]; pos += 1
            if b:
                break
            high += 1
            if high > HIGH_CAP:
                raise ValueError("over-long unary (coefficient too large)")
        x = (high << 7) | low
        if sign and x == 0:
            raise ValueError("invalid negative-zero encoding")
        s.append(-x if sign else x)
    for j in range(pos, len(bits)):          # trailing padding must be zero
        if bits[j]:
            raise ValueError("non-zero trailing padding")
    return s


# --------------------------------------------------------------------------- #
# signature container:  header || salt || Compress(s2)
# --------------------------------------------------------------------------- #
def parse_signature(buf, n=N):
    if len(buf) != SIG_BYTES:
        raise ValueError(f"bad signature length {len(buf)} (expected {SIG_BYTES})")
    if buf[0] != HEAD_SIG:
        raise ValueError(f"bad signature header {buf[0]:#04x} (expected {HEAD_SIG:#04x})")
    salt = buf[1:1 + SALT_LEN]
    s2 = decompress_sig(buf[1 + SALT_LEN:], n)
    return salt, s2


def build_signature(salt, s2):
    body = compress_sig(s2)
    if body is None:
        raise ValueError("s2 does not fit in the compressed length")
    return bytes([HEAD_SIG]) + bytes(salt) + body


def parse_nist_signed_message(sm, mlen, n=N):
    """Parse a NIST-KAT crypto_sign 'sm' for Falcon. Empirically-confirmed layout:
        [siglen : 2 bytes BE] [nonce : 40] [message : mlen] [header : 1]
        [Compress(s2) : siglen-1]
    The header nibble differs from the standalone 0x39 form (the NIST API emits
    0x20|logn); we skip the single header byte, then Decompress the remainder.
    Returns (message, salt, s2)."""
    if len(sm) < 2 + SALT_LEN + mlen + 1:
        raise ValueError("signed message too short")
    slen = (sm[0] << 8) | sm[1]
    salt = sm[2:2 + SALT_LEN]
    msg = sm[2 + SALT_LEN:2 + SALT_LEN + mlen]
    rest = sm[2 + SALT_LEN + mlen:2 + SALT_LEN + mlen + slen]
    if len(rest) != slen or slen < 1:
        raise ValueError("signed-message length / siglen mismatch")
    if (rest[0] & 0x0F) != LOGN:
        raise ValueError(f"unexpected signature header {rest[0]:#04x}")
    s2 = decompress_sig(rest[1:], n)            # skip the 1-byte header
    return msg, salt, s2


# --------------------------------------------------------------------------- #
# self-test (exact round-trips + format/rejection checks)
# --------------------------------------------------------------------------- #
def _selftest():
    import random
    fails = 0

    def check(name, cond):
        nonlocal fails
        print(f"  [{'PASS' if cond else 'FAIL'}] {name}")
        if not cond:
            fails += 1

    print("A-PQC Falcon codec — self-test")
    rng = random.Random(2026)

    # public-key round-trip + format constants
    h = [rng.randrange(Q) for _ in range(N)]
    pk = encode_public_key(h)
    check(f"public key is {PK_BYTES} bytes, header {HEAD_PK:#04x}",
          len(pk) == PK_BYTES and pk[0] == HEAD_PK)
    check("decode(encode(h)) == h", decode_public_key(pk) == h)

    # signature s2 Compress/Decompress round-trip over many short polynomials
    ok = True
    for _ in range(200):
        s2 = [max(-2047, min(2047, round(rng.gauss(0, 90)))) for _ in range(N)]
        body = compress_sig(s2)
        if body is None:                     # too long to fit -> skip (signer retries)
            continue
        ok &= len(body) == SLEN and decompress_sig(body) == s2
    check("Decompress(Compress(s2)) == s2 (200 short polys, 625-byte body)", ok)

    # full container round-trip
    salt = bytes(rng.randrange(256) for _ in range(SALT_LEN))
    s2 = [max(-2047, min(2047, round(rng.gauss(0, 90)))) for _ in range(N)]
    sig = build_signature(salt, s2)
    psalt, ps2 = parse_signature(sig)
    check(f"signature is {SIG_BYTES} bytes, header {HEAD_SIG:#04x}",
          len(sig) == SIG_BYTES and sig[0] == HEAD_SIG)
    check("parse(build(salt,s2)) == (salt,s2)", psalt == salt and ps2 == s2)

    # rejection: negative-zero encoding is invalid
    bad = bytearray(compress_sig([0] * N))
    bad[0] |= 0x80                            # set sign bit of the first coeff (|x|=0)
    rej = False
    try:
        decompress_sig(bytes(bad))
    except ValueError:
        rej = True
    check("negative-zero encoding rejected", rej)

    # rejection: non-zero trailing padding
    s2 = [0] * N
    body = bytearray(compress_sig(s2))
    body[-1] |= 0x01                          # flip a padding bit
    rej = False
    try:
        decompress_sig(bytes(body))
    except ValueError:
        rej = True
    check("non-zero trailing padding rejected", rej)

    # rejection: wrong headers / lengths
    rej = 0
    for mut in (bytes([0x00]) + pk[1:], pk[:-1], bytes([HEAD_SIG]) + sig[1:1]):
        try:
            decode_public_key(mut) if len(mut) >= 2 and mut[0] != HEAD_SIG else parse_signature(mut)
        except ValueError:
            rej += 1
    check("malformed headers/lengths rejected", rej >= 2)

    print(f"\n{'ALL PASS' if fails == 0 else str(fails) + ' FAILURE(S)'}")
    return fails


if __name__ == "__main__":
    raise SystemExit(_selftest())
