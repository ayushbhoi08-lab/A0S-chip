# ANSH-108 Core — A-PQC: Falcon-512 real-signature INTEROP

### The chip-NTT verifier accepts a GENUINE Falcon signature (bit-level)

*Upgrades the Falcon verify model to consume real Falcon byte strings, and proves
it against a genuine signature from the official reference. Created 2026-06-30.
Standing rule honored. Code: `apqc_falcon_codec.py`, `apqc_interop_vector.py`,
vector `falcon512_interop_vector.json`.*

---

## 1. What was added

- **`apqc_falcon_codec.py`** — the Falcon wire-format codec: public-key decode
  (PQClean/FIPS `modq_encode`, 14-bit MSB-first, header 0x09, 897 bytes) and
  signature **Compress/Decompress** (sign bit · 7 low bits · unary high; header
  0x39 · 40-byte salt · 625-byte body = 666 total). Self-test 8/8: exact
  round-trips + rejection of negative-zero, non-zero padding, bad headers/lengths.
- **`apqc_interop_vector.py`** — a reproducible, **offline** gate that replays a
  frozen genuine signature through the codec + the chip-NTT verifier.
- **`falcon512_interop_vector.json`** — a real Falcon-512 `(public key, message,
  signature)` produced by the official **Prest `falcon.py`** reference (a Falcon
  author's implementation), frozen for reproducibility.

---

## 2. The interop result — ALL PASS (5/5), offline & reproducible

`python apqc_interop_vector.py`

- real signature is 666 bytes, header 0x39 ✓
- **codec parses the real reference signature** (salt 40, s2 512) — *signature
  wire-format interop* ✓
- PQClean pk codec decodes to the real `h` ✓
- **chip-NTT verifier ACCEPTS the genuine signature** (sqnorm 26,887,941 ≤
  34,034,726) — *verification-math interop* ✓
- chip-NTT verifier REJECTS a tampered message (sqnorm 6.39×10⁹) ✓

Cross-checked at generation time: the reference's own `verify` accepts the same
signature, and my HashToPoint (SHAKE-256 reject-≥5q) matches the reference (a
mismatch there would make the genuine signature fail).

**Why this is the real thing:** a signature this verifier never saw during design,
produced by independent reference code, is parsed from its standard bytes and
accepted by the chip's 12289 NTT math — and only when genuine.

---

## 3. Honest scope (what is / isn't proven)

- ✅ **Signature wire-format interop**: the codec parses real, standard 666-byte
  Falcon-512 signatures (header + salt + Compress) — demonstrated on a genuine one.
- ✅ **Verification-math interop**: HashToPoint + `s2·h` (chip NTT) + norm accept a
  genuine signature and reject tampering.
- ✅ **NIST-KAT cross-check now DONE** — see `Ansh_108_Core_APQC_FalconKAT.md`: the
  chip-NTT verifier accepts all 100 official Falcon-512 KAT signatures (this also
  closes the pk-byte gap below). The reference-vector test here remains as the
  first, simplest interop demonstration.
- ⚠️ **Public-key byte cross-check**: my pk codec is the FIPS `modq_encode` form and
  round-trips the real `h`, but the Prest reference uses a *non-standard headerless*
  pk packing, so it isn't an external pk-byte oracle; the committed
  `pk_pqclean_hex` is rebuilt from the real `h`. Full pk-byte cross-validation
  wants a PQClean/FIPS pk vector.
- ⛔ Still a **verifier**, not a signer — signing (NTRU trapdoor + Gaussian sampler)
  remains out of scope; unforgeability rests on that + lattice hardness, untested here.

---

## 4. Reproduce / regenerate

```sh
python apqc_falcon_codec.py        # codec self-test (8/8)
python apqc_interop_vector.py      # interop gate vs the frozen genuine signature (5/5)
```
To mint a fresh vector (needs the reference + `pip install pycryptodome numpy beartype`):
clone `github.com/tprest/falcon.py`, keygen+sign, then dump `(msg, sig, h)` — see the
session's `scratchpad/gen_interop.py`.

### Cross-references
- Verifier + meaning: `Ansh_108_Core_APQC_FalconVerify.md`
- NTT engine + prime correction: `Ansh_108_Core_APQC_FalconNTT.md`
- Code: `../Core_Artifacts/{apqc_falcon_codec.py, apqc_interop_vector.py}` + the vector JSON
