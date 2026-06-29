# Ansh-108 Core — The Breaking Point: Consonant Sandhi + Conflicts

### Does the brain's comparison load spike when the grammar gets hard?

*Fourth experiment, following `..._RuleSelection_Weight.md` (which measured the
easy vowel subsystem at 0.25 comparisons/junction). Here we push to the harder
case — consonant sandhi with real rule overlap (vipratiṣedha / asiddha
ordering) — using the **same metric**, to see whether the Ubuntu brain
bottlenecks. Created 2026-06-24. Script: `scratchpad/panini_consonant.py`.
Numbers measured over 160 junctions.*

---

## What was encoded

A representative, correctly-sourced slice of external consonant sandhi — 11
rules with their actual Aṣṭādhyāyī sūtra numbers:

khari-ca (8.4.55) · jaśtva (8.2.39) · ścutva (8.4.40) · ṣṭutva (8.4.41) ·
anusvāra (8.3.23) · m→parasavarṇa (8.4.58) · nasal-assimilation (8.4.45) ·
savarṇa-degemination (8.4.65) · the visarga cluster (8.3.34, 8.3.36).

Junction space: **8 realistic word-final sounds × 20 following sounds = 160
junctions.** For each, the brain finds every rule whose domain matches; where
two match, it must order them (vipratiṣedha 1.4.2 / asiddhatva 8.2.1). Same
metric as before: a **relational comparison** = comparing a feature across both
operands, or comparing two rules' priority. Unary lookups (is R voiced?) are
not counted.

---

## The hard numbers, in plain English

| Metric | Vowel sandhi | Consonant sandhi | Change |
|---|---|---|---|
| **Relational comparisons per junction** | 0.250 | **0.419** | ↑ 1.7× |
| Junctions needing *any* comparison | 25% | **36%** | ↑ |
| Junctions decided by pure lookup (no comparison) | 75% | **64%** | — |
| **True conflicts** (two rules fight over the *same* feature) | 0 | **0** | none |
| Junctions needing 2 rules applied *in order* (asiddha) | 0% | **19%** | NEW |
| Junctions needing a context window wider than 2 sounds | 0% | **8%** | NEW |
| Rules firing per junction | 1 | 0→34, 1→95, **2→31** | — |

---

## What this means

**1. The comparison count does NOT spike. It rises gently.** From 0.25 to 0.42
relational comparisons per junction — still **less than one comparison per
junction.** Going from the easiest subsystem to a genuinely hard one (with
overlap and ordering) moved the needle by a modest 1.7×, not by an order of
magnitude. **The brain does not bottleneck on branching.** On the exact metric
you asked about, the main computer stays cheap.

**2. The reason it stays cheap is structural — and beautiful.** There were
**zero true conflicts**: in all 31 junctions where two rules fire, they modify
**different features** (one changes voicing, the other changes place) and simply
**stack**. They never fight over the same feature, so the brain almost never has
to *arbitrate a value* — it just applies both. Pāṇini's system is engineered to
be near-conflict-free; the famous vipratiṣedha machinery exists for the rare
residue, not the common case. **The meta-rule layer is light because the rules
were designed not to collide.**

**3. Two genuinely new costs appear — but neither is branching.**
- **Ordered application (asiddha):** 19% of junctions fire two rules that must
  be applied in a fixed sūtra sequence. That is a *scheduling* cost, not a
  comparison — the brain sequences, it doesn't branch.
- **Wider context:** 8% of junctions (the visarga cases) need to look back past
  the immediate neighbour — visarga's output depends on the **vowel before it**,
  a 3-sound window. The brain's *input* gets wider; its *decision* does not get
  harder.

---

## The breaking point — where it actually is

You asked for the breaking point. It is **not** the comparison count. That stays
bounded and cheap (< 1 per junction) even under conflict, because the grammar
avoids same-feature collisions by design.

The thing that grows — the real watch-item — is **the depth of ordered rule
chains (asiddha sequencing).** Here the maximum was 2 rules per junction. In the
full *tripādī* (the asiddha section of Book 8), chains can run longer, and the
brain must apply them strictly in order, each step potentially hiding the next
rule's trigger. **If anything bottlenecks the main computer, it will be
sequence-length, not branch-count** — a pipeline-depth problem, not a
combinatorial-explosion problem. That is the difference between *manageable*
(linear in chain depth) and *catastrophic* (exponential in choices). We are in
the manageable regime.

**Verdict for the architecture:** the 108-chip muscle is not starved and the
Ubuntu brain is not choked. Branching stays under one comparison per junction
from the easiest subsystem to a hard one. The cost that scales is rule-ordering
depth and context width — both linear, both bounded, both cheap to buffer. **No
spike. The split holds.**

---

## Honest caveats

- This is a **representative encoded subset** (~11 rules), not a complete sandhi
  engine. The *methodology* (count relational comparisons per junction) is the
  deliverable; the exact 0.419 will shift as more rules are added, but the
  qualitative finding — comparisons stay sub-1, sequencing is the growth term —
  is robust.
- "Zero true conflicts" is for this subset; the full grammar has a handful of
  genuine vipratiṣedha arbitrations. The point is their **rarity**, which is the
  standard understanding of why Pāṇini's system is computationally clean.
- One metric was uninformative and is excluded: at full feature granularity
  every junction is its own routing cell (160/160), so "table compression" can't
  be read off it the way the vowel system's clean 9-cell table could — the
  comparison/sequencing/window numbers are the load-bearing ones.

---

## Reproducibility
`scratchpad/panini_consonant.py` — no libraries. **Note:** printing Sanskrit
glyphs (ṣ, ś) crashes under Windows' default cp1252 console; run with
`PYTHONIOENCODING=utf-8` (the known platform encoding gotcha). Measured output:
`160 junctions · 0.419 comparisons/junction · 36% need a comparison · 0 true
conflicts · 19% need ordered application · 8% need a >2-sound window · rules-per-
junction {0:34, 1:95, 2:31}`.

### Cross-references
- Easy-subsystem baseline: `Ansh_108_Core_RuleSelection_Weight.md` (0.25/junction)
- Why comparison is the hard op: `Ansh_108_Core_Technical_Proof_and_Limitations.md` §6.2
- The split being stress-tested: `Ansh_108_Core_Panini_Tensor_Experiment.md`
