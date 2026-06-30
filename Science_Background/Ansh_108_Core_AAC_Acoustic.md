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

**Two feature front-ends, one chip backend:** (a) a built-in **stdlib RMS rhythm
proxy** (runs anywhere, no deps), and (b) the project's **validated Laghu/Guru
engine** (`fold_lg_sequence` over the ChandasTokenizer output — §4). Both end in the
same proven multi-chain FOLD; the chip's job is identical either way.

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

## 4. Validated Laghu/Guru extractor (chandas) — wired in

The RMS rhythm code is a stdlib proxy. The project's **validated** Laghu/Guru engine
is the `ChandasTokenizer` in `03_RESEARCH_RHYTHM/` (librosa spectral-flux onsets →
syllable durations → L/G by duration vs the adaptive median → Anuṣṭubh pādas). A-AC
now fingerprints **that** real analysis:

- `fold_lg_sequence("LGGLL…")` — the **chip's job**: FOLD a Laghu/Guru sequence
  (G→1, L→0) into the ~108-bit fingerprint. Pure, stdlib, committed, and tested
  (determinism, sensitivity, order, chain 0 == golden FOLD).
- `python aac_acoustic.py --chandas FILE.wav [--backend DIR]` — runs the validated
  tokenizer (lazy import by path; needs `numpy/librosa/scipy`, **not** bundled here)
  and FOLDs its L/G output. The tokenizer and any audio stay **outside** this repo.

**Validated end-to-end (this session, local):** a real Gītā recitation →
ChandasTokenizer → **64 L / 26 G / 116 mātrās** → a stable 108-bit fingerprint
(`b0debe54…`). The bridge runs the *actual* validated engine; only its L/G string
crosses into the chip. (Onset detection is tuning-sensitive: smooth isolated-vocal
takes can yield few/no onsets at the default threshold — a property of the tokenizer,
not the fingerprint; pass a lower `threshold` for sustained vocals.)

So the fingerprint is now over the **real rhythm analysis**, not the RMS proxy —
while the committed gate stays stdlib-only (it tests `fold_lg_sequence` on synthetic
L/G strings, so a fresh clone needs no `pip install`).

---

## 5. Honesty ledger

- ✅ Reuses the proven multi-chain FOLD (chain 0 == golden FOLD); stdlib-only (`wave`),
  runs on a fresh clone with no `pip install`.
- ✅ The non-perceptual, noise-sensitive nature is **measured and stated**, not hidden.
- ✅ The **validated** Laghu/Guru analysis (ChandasTokenizer) is now the real feature
  front-end (§4); the chip fingerprints its L/G output, not just the RMS proxy.
- ⚠️ Two front-ends, both honest: the stdlib RMS proxy (a coarse stress feature, not a
  rhythm-science claim) and the validated chandas engine (the real analysis, needs
  librosa). Either way FOLD stays an **exact** hash — making it perceptual/robust would
  require a similarity-preserving hash (LSH), which FOLD is not.
- ⚠️ Chandas onset detection is tuning-sensitive (threshold per recording); a 0-syllable
  result is a tokenizer property, not a fingerprint failure.
- ⛔ Not speaker/chant recognition, not similarity search, not transcription.

---

## 6. Where it goes next

- For *grouping by similarity*, add a similarity-preserving front end (quantized onset
  histogram or an LSH over MFCCs), then FOLD the LSH bucket id — FOLD alone stays exact.
- Provenance use: stamp a reciter's certified rendition's L/G fingerprint with A-TS
  (timestamped, tamper-evident) for a verifiable "this is the reference recitation."

### Cross-references
- FOLD source: `Ansh_108_Core_ATS_Notarizer.md` (multi-chain FOLD), `golden_model.py`
- Validated extractor: `03_RESEARCH_RHYTHM/Backend/chandas_tokenizer_phase1.py`
- Sibling: `Ansh_108_Core_AFP_Fingerprint.md` (byte-stream fingerprinting)
- Code: `../Core_Artifacts/aac_acoustic.py` (`--demo`, `--wav FILE`, `--chandas FILE`)
