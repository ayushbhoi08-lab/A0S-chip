# Ansh-108 Core — Pāṇini-as-Tensor: First Experiment

### Testing limitation §6.6(1): can a real Pāṇini rule be a linear map over Z/108Z?

*Empirical companion to `Ansh_108_Core_Technical_Proof_and_Limitations.md`.
Limitation §6.6(1) said: "no one has shown Pāṇini's rule operators can be
represented as linear maps / tensors whose entries live in Z/108Z." This file
is a first, honest attempt to do exactly that — with a principled encoding and
a real chance of failing. Result: it **partially succeeds, informatively**.
Created 2026-06-24. Script: `scratchpad/panini_tensor.py`, all numbers below
are measured, not asserted.*

---

## Method (and the one guard that keeps it honest)

I used real vowel-sandhi rules — the cleanest deterministic transformations in
the *Aṣṭādhyāyī*:

- **6.1.101 savarṇa-dīrgha** — vowel + homogeneous vowel → its long form
  (`i + i → ī`).
- **6.1.87 guṇa** — `a/ā + i/ī → e`, `a/ā + u/ū → o`.
- **6.1.88 vṛddhi** — `a/ā + e/ai → ai`, `a/ā + o/au → au`.

Each vowel was given a **feature code fixed in advance** from standard
articulation — *not* reverse-engineered from the answers:

```
place  : guttural=0, palatal=1, labial=2, retroflex=3   (4 values)
grade  : zero=0, guṇa=1, vṛddhi=2                        (base-3)
length : short=0, long=1
```

**The guard:** if you let yourself pick codes *after* seeing the outputs, you
can always make a rule "linear" — but that is just a lookup table wearing a
matrix costume. Fixing the codes from independent phonetic features first is
what makes a positive result mean something.

The codes were then packed into `Z/108Z` using the **same CRT idempotents from
the proof file**: `x ≡ 81·(place) + 28·(grade + 3·length) (mod 108)` — i.e.
place rides the mod-4 track, grade/length ride the mod-27 track.

---

## Result A — guṇa + vṛddhi IS arithmetic (the surprise)

> **`grade := min(R.grade + 1, 2)`, copy R's place, force length = long**
> reproduces **16 / 16** guṇa + vṛddhi cases exactly.

A single affine law — *increment the grade coordinate* — covers **two
different sūtras** (6.1.87 and 6.1.88) with no exceptions. And it is not a
coincidence of encoding: guṇa and vṛddhi are *defined* in Sanskrit grammar as
successive **strengthening grades** of a vowel. The feature code just makes
that explicit, and the arithmetic falls out:

```
a + i (grade 0) → e  (grade 1)      a + e  (grade 1) → ai (grade 2)
a + u (grade 0) → o  (grade 1)      a + o  (grade 1) → au (grade 2)
```

So limitation §6.6(1) is **not** a brick wall. A real Pāṇini operation can be a
genuine affine map over the feature space — the "grammar is arithmetic"
intuition has real content here, not just metaphor.

---

## Result B — but ONE global linear map cannot be "sandhi" (the catch)

> Best single affine map `α·L + β·R + γ (mod 108)` over **all** sandhi
> (guṇa + vṛddhi + savarṇa): **16 / 32** — exactly half.

The search even told us *why*: the best map it found was `out ≡ 9·R + 84
(mod 108)`, with `α = 0` — **it threw the left vowel away entirely**. It could
fit the one rule-family whose output depends only on the right vowel
(guṇa/vṛddhi, 16 cases) and necessarily missed every savarṇa-dīrgha case
(where the output depends on the left–right *relationship*).

You cannot have a single flat tensor that *is* "sandhi." You need to first
**select which rule fires** — and that selection is the part that does not
linearize.

---

## Result C — the branching didn't vanish; it moved to rule-selection

Hold the left vowel fixed at `a` and the output still changes shape:

```
a + a  → ā    (savarṇa-dīrgha)
a + i  → e    (guṇa)
a + e  → ai   (vṛddhi)
```

Choosing among these requires asking *relational* questions about the pair —
"is R homogeneous with L?" (i.e. **place(L) == place(R)**) and "what grade is
R?" An equality test on the two place-codes is precisely a **magnitude /
comparison operation** — the exact thing the proof file's §6.2 showed a residue
system over `Z/108Z` is *bad* at and cannot do without reconstruction.

So the irreducible `IF/THEN` of Sanskrit grammar does not live inside the
rules' transformations (those are clean affine maps). It lives in
**rule-selection** — Pāṇini's own ordering, `vipratiṣedha`, and `paribhāṣā`
meta-rules. That is where the branch is, and a flat 108-state tensor cannot
absorb it.

---

## Result D — how well does 108 itself fit? (partial)

Real structural alignment, with honest cracks:

- ✅ The **4 articulation places** map *exactly* onto the mod-4 (`2²`) track.
- ✅ **Grade** is a base-3 digit, sitting naturally in the mod-27 (`3³`) track.
- ❌ Add the 5th vocalic place (`ḷ`) and you have 5 places — and **5 does not
  divide 108**, breaking the clean mod-4 fit.
- ❌ The grade increment must be **capped at 2** and length **forced to 1** —
  `min()` and constant-assignment are not ring operations; they are the
  non-linear residue.

108 accommodates the *regular* part of the structure beautifully and the
*irregular* part not at all — which is exactly the honest shape of the whole
project claim.

---

## Verdict on §6.6(1)

| Sub-claim | Finding |
|---|---|
| A Pāṇini rule's *operation* can be a linear/affine map over Z/108Z | **Yes** — guṇa+vṛddhi = grade increment, 16/16, principled encoding |
| A single global tensor can represent *sandhi as a whole* | **No** — 16/32; needs rule-selection |
| The eliminated `IF/THEN` truly disappears | **No** — it relocates to rule-selection, which is relational/comparison = the RNS-hard operation (§6.2) |
| 108's CRT structure fits the linguistic features | **Partially** — places→mod-4, grade→mod-27 fit; 5th place and the caps break it |

**Bottom line.** The hypothesis "gets off the ground" — and lands somewhere
genuinely useful. The *transformations* of Sanskrit grammar can be real
arithmetic over `Z/108Z`; what cannot be made branch-free is the *selection*
among them, because selection is comparison, and comparison is exactly what a
residue machine cannot do for free. This both **validates** a real piece of the
Project ANSH thesis and **sharpens** its central limitation into one precise
sentence: *the rules are tensors; the meta-rules are the branch.*

---

## Reproducibility
`scratchpad/panini_tensor.py` — no external libraries. Defines the feature
codes, the three sandhi tables, and runs Tests A–D. Measured output:
`A: 16/16 · B: 16/32 (coeffs 0,9,84) · C: a→{ā,e,ai} · D: as above`.

### Cross-references
- Proof + limitations: `Ansh_108_Core_Technical_Proof_and_Limitations.md` (§6.6, §6.2)
- Narrative: `Ansh_108_Core_Master_Document.md`
- Pāṇini–Backus grounding: `Acoustic_Firewall_PaniniBackus_BinaryMatrix.md`
