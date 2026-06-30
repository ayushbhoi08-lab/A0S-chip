# ANSH-108 Core — A-AC: Acoustic / rhythm fingerprinting

### Track-A application #4, chant domain — built on the proven FOLD, no board

*Extracts a rhythm/acoustic feature stream on the host, then fingerprints it with
the chip's multi-chain FOLD. Created 2026-06-30. Standing rule honored. Code:
`Core_Artifacts/aac_acoustic.py`.*

---

## 1. What it does (and what it deliberately does NOT)

**Does:** turns audio into the chip's deterministic ~108-bit fingerprint by
(1) extracting a **binary rhythm code** on the host — per-frame RMS energy above/below
the adaptive median → 1/0, an audio analogue of the project's **Laghu/Guru** sequence
— and (2) FOLDing it through the proven `slice_bits_to_feet` + multi-chain FOLD
(chain 0 == golden FOLD, asserted). The feature extraction is host-side; the chip
does the FOLD.

**Does NOT:** it is **not** an audio-DSP/FFT engine, and **not** a perceptual
(Shazam-style) fingerprint. FOLD is an *exact* hash:
- identical feature streams → identical fingerprint;
- two different performances of the same chant → different features → different
  fingerprints. It will **not** cluster "perceptually similar" audio.

So the honest use cases are **exact dedup, provenance/integrity of a specific
rendition, and order-sensitive rhythm signatures** — not similarity search.

---

## 2. Verification gate — ALL PASS (synthesized audio, no files committed)

`python aac_acoustic.py`

- deterministic + exact copy → identical fingerprint ✓
- one rhythm beat changed → different fingerprint ✓
- reversed rhythm → different fingerprint (order-sensitive) ✓
- **chain 0 == golden FOLD over the rhythm feet** (reuse, not reinvention) ✓
- noise sensitivity is real and **measured** (3/3 noise levels altered the exact
  fingerprint) — the honest limit, stated as a property ✓

Tests synthesize their own chant-like rhythm audio in code, so **no audio is
committed** — the real chant recordings stay private.

---

## 3. Demo + the honest limit

`python aac_acoustic.py --demo` — six takes (two identical each of three rhythms):

```
6 takes (2 each of 3 rhythms) -> 3 clusters (expect 3)
  gayatri-like#1, gayatri-like#2     -> one fingerprint
  tristubh-like#1, tristubh-like#2   -> one fingerprint
  anustubh-like#1, anustubh-like#2   -> one fingerprint
```
Exact-rhythm dedup works cleanly. Then the limit: a **noisy take of the same rhythm
→ a DIFFERENT fingerprint**. That is by design (exact, not perceptual); coarser
feature quantization trades discrimination for grouping.

Real file (`--wav FILE`, validated locally on a 95.6 s copyright-free instrument):
4779 frames → 2389 "guru" → an 8-chain ~108-bit fingerprint. Point it at a local
recording to fingerprint it privately; nothing is uploaded or committed.

---

## 4. Honesty ledger

- ✅ Reuses the proven multi-chain FOLD (chain 0 == golden FOLD); stdlib-only (`wave`),
  runs on a fresh clone with no `pip install`.
- ✅ The non-perceptual, noise-sensitive nature is **measured and stated**, not hidden.
- ⚠️ Class B: the feature extractor is deliberately simple (RMS rhythm code). Richer
  host features (librosa MFCC/chroma/onset) could be swapped in — but that does not
  make FOLD perceptual; robustness would still require a similarity-preserving hash
  (LSH), which FOLD is not.
- ⚠️ "Rhythm code" is a coarse stress proxy, not the validated Laghu/Guru analysis in
  `03_RESEARCH_RHYTHM/` — it's a fingerprint feature, not a rhythm-science claim.
- ⛔ Not speaker/chant recognition, not similarity search, not transcription.

---

## 5. Where it goes next

- Swap in a similarity-preserving front end (quantized onset histogram or an LSH over
  MFCCs) if *grouping by similarity* is the goal — then FOLD the LSH bucket id.
- Tie to the real Laghu/Guru extractor in `03_RESEARCH_RHYTHM/` to fingerprint the
  *validated* rhythm code rather than the RMS proxy.

### Cross-references
- FOLD source: `Ansh_108_Core_ATS_Notarizer.md` (multi-chain FOLD), `golden_model.py`
- Sibling: `Ansh_108_Core_AFP_Fingerprint.md` (byte-stream fingerprinting)
- Code: `../Core_Artifacts/aac_acoustic.py` (`--demo`, `--wav FILE`)
