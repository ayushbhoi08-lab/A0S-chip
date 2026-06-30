#!/usr/bin/env python3
"""
Ansh-108 Core — A-PQC : Falcon-512 INTEROP gate (real reference signature)
==========================================================================
Reproducible, offline proof that the chip-NTT Falcon verifier interoperates with
a GENUINE Falcon-512 signature produced by the official reference implementation
(Thomas Prest's `falcon.py`, by a Falcon author). The signature, message, and
public key are frozen in `falcon512_interop_vector.json`; this gate replays them
through the host codec (`apqc_falcon_codec`) and the chip-NTT verifier
(`apqc_falcon_verify`) — no reference code or network needed at run time.

What this proves (bit-level, on a real artifact):
  - the host CODEC parses the real 666-byte reference signature (header 0x39 +
    40-byte salt + 625-byte Compress(s2)) — signature wire-format interop;
  - HashToPoint (SHAKE-256 reject->=5q) matches the reference (else verify fails);
  - the chip's 12289 negacyclic NTT computes s2*h, and the verifier ACCEPTS the
    genuine signature and REJECTS a tampered message — verification-math interop;
  - the PQClean/FIPS public-key codec round-trips the real public key h.

Honest scope: the vector comes from the official *reference*, not the NIST KAT
file; the Prest reference's own public-key serialization is non-standard
(headerless), so the committed `pk_pqclean_hex` is the FIPS `modq_encode` form
rebuilt from the real h (round-trip-checked here) — full pk-byte cross-check vs an
external PQClean encoder still wants a PQClean KAT. Signature-format + verify-math
interop are genuinely demonstrated.

Run:  python apqc_interop_vector.py
"""
import sys
import os
import json

ART = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ART)
from apqc_falcon_codec import parse_signature, decode_public_key, HEAD_SIG, SIG_BYTES
from apqc_falcon_verify import verify

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

VECTOR = os.path.join(ART, "falcon512_interop_vector.json")


def main():
    fails = 0

    def check(name, cond):
        nonlocal fails
        print(f"  [{'PASS' if cond else 'FAIL'}] {name}")
        if not cond:
            fails += 1

    print("A-PQC Falcon-512 interop gate (genuine reference signature)")
    with open(VECTOR, encoding="ascii") as fh:
        v = json.load(fh)
    print(f"  vector source: {v['source']}")

    msg = bytes.fromhex(v["msg_hex"])
    sig = bytes.fromhex(v["sig_hex"])
    pk = bytes.fromhex(v["pk_pqclean_hex"])
    h = v["h"]

    # signature wire-format: my codec parses the real reference bytes
    check(f"real signature is {SIG_BYTES} bytes, header {HEAD_SIG:#04x}",
          len(sig) == SIG_BYTES and sig[0] == HEAD_SIG)
    salt, s2 = parse_signature(sig)
    check("codec parsed real reference signature (salt 40, s2 512)",
          len(salt) == 40 and len(s2) == 512)

    # PQClean public-key codec round-trips the real key
    check("PQClean pk codec decodes to the real h", decode_public_key(pk) == h)

    # chip-NTT verifier ACCEPTS the genuine signature
    acc, nrm = verify(msg, (salt, s2), h)
    check(f"chip-NTT verifier ACCEPTS the genuine signature (sqnorm {nrm})",
          acc and v["expect_accept"])

    # ... and REJECTS a tampered message
    acc_t, nrm_t = verify(msg + b"!", (salt, s2), h)
    check(f"chip-NTT verifier REJECTS a tampered message (sqnorm {nrm_t})", not acc_t)

    print(f"\n{'ALL PASS' if fails == 0 else str(fails) + ' FAILURE(S)'}")
    return 0 if fails == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
