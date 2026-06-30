# ANSH-108 Core — A-FP: Stream-integrity / Content Fingerprinting

### Track-A application #2, built on the proven multi-chain FOLD — no FPGA board

*Implements the two A-FP deliverables from `Ansh_108_Watch_and_Applications_Plan.md`.
Reuses the multi-chain FOLD from A-TS (which extends the proven `golden_model.py`
FOLD); adds only the fingerprint/dedup layer. Created 2026-06-30. Standing rule
honored: measured or proven, negatives kept, no number is a hope. Code:
`Core_Artifacts/afp_fingerprint.py`.*

---

## 1. What it is

Turn any byte stream into a **wide deterministic content fingerprint** (8 chains ≈
108.7 bits), then use those fingerprints for **exact-duplicate detection / content-ID**
over a real corpus. Same engine as A-TS, different application: A-TS bound the hash to a
monotonic *tick* for proof-of-order; A-FP uses the bare hash as a *content identity*.

**Honest framing (firewall):** a deterministic integrity/dedup/provenance fingerprint,
**not** a keyed cryptographic hash. Strength = the birthday bound of the chosen width,
**measured** below.

---

## 2. Verification gate — ALL PASS (6/6)

`python afp_fingerprint.py`

- deterministic (same bytes → same fingerprint) ✓
- exact copy → identical fingerprint (**dedup works**) ✓
- single-byte change → different fingerprint (**integrity**) ✓
- empty input well-defined (proven slicer returns `[0]`) ✓
- 8-chain width ≈ 108.7 bits ✓
- more chains → later first collision (monotone strength) ✓

---

## 3. A-FP-1 — collision curve vs chain count (MEASURED)

`python afp_fingerprint.py --measure` (reproducible, seed = 108)

**Random birthday — matches √(πQᴺ/2) and confirms ×Q-per-chain scaling:**

| Chains | Width (bit) | Birthday prediction | **Measured** first collision |
|---|---|---|---|
| 1 | 13.6 | 139 | **136** (30 trials) |
| 2 | 27.2 | 15,402 | **15,125** (6 trials) |
| 3 | 40.8 | 1.71×10⁶ | *projected* |
| 4 | 54.3 | 1.89×10⁸ | *projected* |
| 8 | 108.7 | 2.86×10¹⁶ | *projected* |

The two measured points sit within ~2% of prediction; the 3/4/8-chain rows are projected
from that confirmed scaling, **not** brute-forced.

**Collisions exhibited on the real corpus by deliberately narrowing the width** (15 files):

| Keep bits | Distinct | Collisions |
|---|---|---|
| 4 | 10 | **5** |
| 6 | 14 | **1** |
| 8 | 15 | 0 |
| 16 | 15 | 0 |
| 108 | 15 | 0 |

This is the honest demonstration of *why width matters*: at 4 bits the 15 real files
collide; at full 108-bit width they don't.

---

## 4. A-FP-2 — dedup / content-ID over the real corpus

`python afp_fingerprint.py --demo` — 15 real files (5 `cosim_chants/` + 10 `a0s_programs/`).

- All 15 produce **distinct** fingerprints → 0 false duplicates.
- **Exact copy** of `gAyatrI.txt` → identical fingerprint (**deduped**).
- **1-bit edit** of `gAyatrI.txt` → different fingerprint (**integrity break detected**).

`7b611b67592b2964f5dcdad41911` (original) == exact copy; `4625b0c771159b9c0687b25be8ed`
(1-bit edit) differs.

---

## 5. Honesty ledger

- ✅ Reuses A-TS `MultiChainFold` / `bytes_to_feet` (→ proven golden FOLD); no hash re-implemented.
- ✅ Collision curve **measured** at 1–2 chains; higher widths projected from the *confirmed*
  scaling, explicitly not a 2⁵⁴ search.
- ✅ Real-corpus collisions are *shown* (via truncation), not asserted.
- ⚠️ Not a keyed/adversarial hash — an attacker who can pick inputs freely is bounded only by
  the birthday width, and there is no key/trapdoor (Z/12289 is unkeyed).
- ⚠️ Near-duplicate *similarity* (fuzzy match) is **out of scope** — this is exact content-ID;
  any edit yields a fully different ID by design (that's the integrity property, not a bug).

---

## 6. Where it goes next

- Fold over the **SHOALKS audio corpus** (host-extract features → fingerprint) for real
  provenance/dedup of the BG_/chant recordings — the A-AC track; honest scope = fingerprinting
  *extracted features*, not a general audio-DSP engine.
- Shares the **S9 host↔RTL co-sim** echo with A-TS: a routed FOLD chain reproduces chain 0.

### Cross-references
- Plan: `../Plans/Ansh_108_Watch_and_Applications_Plan.md` (A-FP-1/2)
- Sibling app: `Ansh_108_Core_ATS_Notarizer.md` (multi-chain FOLD source)
- Reused (not rebuilt): `../Core_Artifacts/ats_notarizer.py`, `golden_model.py`
- Code: `../Core_Artifacts/afp_fingerprint.py` (`--measure`, `--demo`)
