# Ansh-108 Core — Weighing the Brain: the Rule-Selection Layer

### How much does the Ubuntu "brain" actually carry, vs the 108-chip "muscle"?

*Third experiment in the series, following `..._Panini_Tensor_Experiment.md`.
That file found the split: the rules' **transformations** are clean arithmetic
(muscle), but **choosing** which rule fires is a comparison the residue chip
can't do (brain). This file measures the brain's load directly. Created
2026-06-24. Script: `scratchpad/panini_selection.py`; numbers are measured.*

---

## The question, made concrete

For the brain/muscle architecture, the worry is a **meta-rule bottleneck**: if
selecting the rule is heavy, the Ubuntu brain becomes the limiting factor and
the fast 108-chip starves. So: build the real rule-selection function over
every vowel junction and measure how heavy it actually is.

I enumerated all **144** ordered vowel-pair junctions (12 × 12 vowels) and, for
each, computed which sandhi rule Pāṇini fires — savarṇa-dīrgha (6.1.101),
guṇa (6.1.87), vṛddhi (6.1.88), yaṇ (6.1.77), or ayādi (6.1.78).

---

## Result 1 — the selection is low-entropy

```
Junctions: 144
Rules fired:  yaṇ 60 · ayādi 48 · savarṇa 16 · guṇa 12 · vṛddhi 8
Rule-choice entropy: 1.937 bits   (information floor for 5 rules = 2.322 bits)
```

The decision carries under 2 bits. It is not a hard classification problem.

---

## Result 2 — 8 of the 9 routing cells are unary (no comparison at all)

Route every junction by just the **class** of each vowel — `a` (a/ā),
`ik` (simple non-a), `ec` (compound) — a 3×3 table:

```
        R=a       R=ik              R=ec
L=a     savarṇa   guṇa              vṛddhi
L=ik    yaṇ       MIXED(savarṇa/yaṇ) yaṇ
L=ec    ayādi     ayādi             ayādi
```

**Eight of the nine cells are pure** — decided by class alone, which is a
*unary lookup on one symbol* (cheap; the muscle's own input encoding could
carry it). Only **one cell — `ik + ik` — is mixed**, and that is the *entire*
irreducible relational content of vowel-sandhi selection.

---

## Result 3 — only 25% of junctions need a genuine comparison

```
Junctions needing a real L–R comparison:  36 / 144  =  25%
Average relational comparisons per junction:  0.250
```

The other **75% are decided with zero relational branching.** And the one
comparison that the `ik+ik` cell needs is exactly `place(L) == place(R)`
(homorganic? → savarṇa-dīrgha; else → yaṇ).

**This is the punchline:** the brain's only irreducible job is a single
**equality test** — and that is *precisely* the magnitude/comparison operation
the proof file's §6.2 showed a residue machine over `Z/108Z` cannot do for
free. The brain and the muscle partition the work **exactly along the RNS
capability line**:

- **Muscle (108-chip):** the ring operations `+ − ×` → the rule *transforms*.
- **Brain (Ubuntu):** equality/comparison → the rule *selection*.

Nothing is wasted and nothing overlaps. The split the firmware note proposed is
not just convenient — it is the *natural* fault line of the mathematics.

---

## Result 4 — the whole selector compresses to a comparator + a tiny table

```
Factored model = 9-cell routing table + 1 place-equality predicate
Reproduces all 144 junctions:  0 mismatches
```

The full 144-entry selection table collapses, **losslessly**, to a **9-cell
lookup plus one comparator**. That is the entire weight the Ubuntu brain has to
carry for vowel sandhi: ~10 numbers and a single `==`. The feared bottleneck,
for this subsystem, is almost nothing — the brain is featherweight and the
muscle does the real work.

---

## The honest caveat (don't over-read this)

Vowel sandhi is the **most regular** corner of the *Aṣṭādhyāyī*. These numbers —
0.25 comparisons per junction, a 9-cell table — are a measured **floor on the
easy subsystem**, not a verdict on the whole grammar. The brain's weight grows
once you add:

- **Consonant sandhi** (jaśtva, ṣṭutva, visarga-sandhi) — more context, longer
  conditioning windows.
- **Rule conflict** (`vipratiṣedha`, 1.4.2) — when two rules both apply and the
  grammar must pick by ordering/specificity.
- **Asiddhatva** (8.2.1) — rules that are deliberately "invisible" to later
  rules, a non-local ordering constraint.

Those meta-rules (the `paribhāṣā` layer) exist *precisely because* selection is
not always as trivial as it is here. So the right reading is: **for the regular
core, the brain is nearly free; the open question is how fast its weight climbs
as the conflict structure thickens.** That is the next thing to measure.

---

## Verdict for the firmware note

> **The meta-rule bottleneck is real but, for the regular core, tiny.**
> The Ubuntu brain carries a 9-cell routing table and exactly one equality
> comparator (`place(L)==place(R)`), fired on only 25% of junctions. The
> 108-chip muscle carries every transform. The division of labour falls exactly
> on the RNS line — ring-ops to the muscle, comparison to the brain — so the
> architecture is not a compromise but the mathematically natural partition.
> **Weight on the brain (this subsystem): ~10 numbers + 1 compare. Verdict: the
> muscle is not starved.**

---

## Reproducibility
`scratchpad/panini_selection.py` — no libraries. Measured output:
`144 junctions · entropy 1.937 bits · 1 mixed class-cell (ik+ik) · 36/144=25%
relational · factored model 0 mismatches · 0.250 comparisons/junction`.

### Cross-references
- The split this measures: `Ansh_108_Core_Panini_Tensor_Experiment.md`
- Why comparison is the hard op: `Ansh_108_Core_Technical_Proof_and_Limitations.md` §6.2
- Narrative: `Ansh_108_Core_Master_Document.md`
