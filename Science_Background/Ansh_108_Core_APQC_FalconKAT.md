# ANSH-108 Core — A-PQC: NIST KAT cross-check (the gold standard)

### The chip-NTT verifier accepts all 100 official Falcon-512 KAT signatures

*Closes the last canonical interop box: validation against the official NIST
Known-Answer-Test vectors. Created 2026-06-30. Standing rule honored. Code:
`apqc_kat_check.py` + `falcon512-KAT.rsp`; uses `apqc_falcon_codec` +
`apqc_falcon_verify` (chip 12289 NTT).*

---

## 1. Result — ALL PASS (100/100), offline & reproducible

`python apqc_kat_check.py`

- KAT sha256: `dd75c946fdedef4ec46a2bee7e10c65c9126f1a839b9ced6921fd45f7354b5cd`
- 100 records parsed
- **all 100 KAT messages recovered from `sm`** ✓
- **chip-NTT verifier ACCEPTS all 100 genuine KAT signatures (100/100)** ✓
- tampered KAT message REJECTS ✓ (in 0.8 s total)

These signatures were produced by the Falcon reference's NIST `crypto_sign` API —
the canonical PQC test vectors — entirely independent of this project. Our
independent verifier accepts every one and rejects tampering.

---

## 2. Why this is the gold standard (vs the earlier reference vector)

The earlier interop (`..._FalconInterop.md`) used one signature we generated from
the Prest reference. This step uses the **official, externally-published KAT set**
(100 signatures, NIST PQCsignKAT format), so it is canonical and non-circular.

**Self-evidencing authenticity:** the vector file is mirrored from a third-party
repo, but its authenticity does not rest on trusting that repo — an *independent*
verifier (already validated against the Prest reference) accepts all 100 and
rejects tampering, which only genuine Falcon signatures over the given keys can do.
The sha256 is pinned above for integrity.

---

## 3. What the cross-check exercised (the chip's role, end to end)

For each of the 100 records:
1. **`pk` (897 B, FIPS `modq_encode`, header 0x09)** → `decode_public_key` (our codec) → `h`.
2. **`sm`** → `parse_nist_signed_message` → `(msg, nonce, s2)`. The empirically
   confirmed NIST layout is
   `[siglen:2 BE][nonce:40][message:mlen][header:1][Compress(s2):siglen−1]`
   (the NIST API header nibble is `0x20|logn`, distinct from the standalone `0x39`).
3. **`c = HashToPoint(nonce‖msg)`** (SHAKE-256, reject ≥ 5q).
4. **`s1 = c − s2·h`**, with `s2·h` on the **chip's 12289 negacyclic NTT**.
5. accept iff `‖(s1,s2)‖² ≤ 34034726`.

So the chip's native op (the NTT multiply) sits inside acceptance of every official
NIST Falcon-512 test vector; the hashing and norm/compare are host-side (Path A split).

---

## 4. Honesty ledger

- ✅ Official NIST KAT set, 100/100 accepted by the independent chip-NTT verifier;
  tamper rejected; sha256 pinned; runs offline.
- ✅ Public-key **byte format** now cross-checked against canonical vectors (the KAT
  pk is the FIPS 897-byte form our codec decodes) — this closes the pk-byte gap left
  open in `..._FalconInterop.md`.
- ⚠️ Vector file is mirrored from a community repo, not fetched from NIST directly;
  integrity is pinned by sha256 and corroborated by independent verification.
- ⛔ Still a **verifier**: this validates verification interop, not signing/unforgeability.

---

## 5. Reproduce

```sh
python apqc_kat_check.py     # 100/100 vs falcon512-KAT.rsp
```
Source of the KAT: `github.com/QubitEthereum/falcon` → `KAT/falcon512-KAT.rsp`
(Falcon submission NIST PQCsignKAT vectors).

### Cross-references
- Codec + reference-vector interop: `Ansh_108_Core_APQC_FalconInterop.md`
- Verifier + meaning: `Ansh_108_Core_APQC_FalconVerify.md`
- NTT engine + prime correction: `Ansh_108_Core_APQC_FalconNTT.md`
- Code: `../Core_Artifacts/{apqc_kat_check.py, falcon512-KAT.rsp}`
