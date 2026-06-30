# ANSH-108 Core — A-PQC: Falcon-512 VERIFY harness

### The chip's 12289 NTT inside a real post-quantum verification predicate

*Builds on `apqc_ntt.py` (the Falcon NTT). Models Falcon-512 signature
verification with the heavy polynomial multiply running on the chip's proven
12289 lane. Created 2026-06-30. Standing rule honored. Code:
`Core_Artifacts/apqc_falcon_verify.py`.*

---

## 1. What Falcon-512 verification means

Falcon (NIST **FN-DSA**, FIPS 206) is a post-quantum signature. Falcon-512 lives
in **Z₁₂₂₈₉[x]/(x⁵¹²+1)** — the chip's ring. Given a public key `h`, a message,
and a signature `(salt, s2)`, the verifier accepts iff:

> **`s1 = HashToPoint(salt‖msg) − s2·h`  (mod x⁵¹²+1, mod 12289)  is SHORT**,
> i.e. `‖(s1, s2)‖² ≤ 34034726` (the Falcon-512 spec bound).

Verification = **(the equation holds) AND (the vector is short)**. Three stages:
1. **HashToPoint** — message+salt → polynomial `c` (SHAKE-256 rejection sampler).
2. **`s1 = c − s2·h`** — the multiply `s2·h` in the ring **is the negacyclic NTT**,
   run on the **chip's 12289 lane** (the compute-heavy step).
3. **shortness** — `‖(s1,s2)‖²` vs the bound — a compare/norm, **host-side**
   (exactly the Path A fence: magnitude/compare never touches the residue datapath).

---

## 2. Verification gate — ALL PASS (9/9)

`python apqc_falcon_verify.py`

- HashToPoint deterministic, in-range, message-sensitive (real SHAKE-256) ✓
- verify's `s2·h` via the **chip NTT == schoolbook** (arithmetic correct) ✓
- short pair **ACCEPTS** (‖·‖²=6,270,240 ≤ 34,034,726) ✓
- too-long pair **REJECTS** on the norm bound (‖·‖²=58,917,152) ✓
- tampered `s2` **REJECTS** (equation broken → huge norm) ✓
- forged sig over a real hashed message **REJECTS** ✓
- the chip did the work: **16,384 NTT multiplies per verify** ✓

Worked demo (`--demo`): ACCEPT 6.4M · too-long 60.9M · tampered 6.7×10⁹ ·
forged 6.3×10⁹ — the shortness bound is the live gate.

---

## 3. Honest scope (what this is / is NOT)

**Real:** the ring (n=512, q=12289), the spec norm bound (34034726), HashToPoint
(spec SHAKE-256 reject-≥5q sampler), the `s2·h` multiply on the chip NTT
(asserted == schoolbook), and the full accept/reject decision logic.

**Not real (stated plainly):**
- **Not bit-interoperable with reference Falcon** — no signature *decompression*
  (we take `s2` as an integer polynomial, not Falcon's compressed byte format) and
  no exact key encoding. Interop would need the codec, not new math.
- **The ACCEPT case uses a constructed short `(s1,s2)`**, not a trapdoor-sampled
  real signature. Falcon **signing** needs the NTRU-lattice Gaussian sampler —
  out of scope. So this validates the **verifier's arithmetic + decision**; it does
  **not** demonstrate unforgeability (that rests on the signer's trapdoor + lattice
  hardness, neither tested here).
- The reject-via-forgery test *is* end-to-end real (real HashToPoint), and a random
  `s2` correctly fails — but that is one sample, not a security proof.

---

## 4. Why it matters

This is the clearest statement of the chip's place in PQC: **the heavy, constant-time
polynomial multiply in Falcon verification is the chip's native op**, while the
hashing and the norm-compare are host-side — the Path A division of labor, demonstrated
inside an actual NIST signature predicate. (Per `Ansh_108_Core_APQC_FalconNTT.md`:
12289 is Falcon's prime, not Kyber's/Dilithium's.)

---

## 5. Next steps

- Add the Falcon signature **decompression codec** + real test vectors (e.g. from
  PQClean / the reference) to upgrade this from a faithful model to a bit-exact,
  interoperable verifier.
- Benchmark verify throughput vs a reference Falcon verifier (host), reporting the
  NTT-multiply share that the chip would own.

### Cross-references
- NTT engine: `Ansh_108_Core_APQC_FalconNTT.md` · prime correction lives there
- Code: `../Core_Artifacts/apqc_falcon_verify.py` (`--demo`) on `apqc_ntt.py`
