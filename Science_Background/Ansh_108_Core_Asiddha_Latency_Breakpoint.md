# Ansh-108 Core — The Asiddha Latency Breakpoint

### Exactly when does the Ubuntu host's scheduling starve the 108-chip?

*Fifth and deepest experiment, following `..._Consonant_Conflict_Breakpoint.md`
(which found the growth term is asiddha sequencing, not branching). Here we
build a deep serial asiddha chain and find the precise crossover where host
scheduling overtakes chip execution. Created 2026-06-24. Script:
`scratchpad/panini_asiddha.py`. The cycle costs are a transparent MODEL (not
measured silicon); the load-bearing results are the **relationships and
crossover points**, which hold for any constants.*

---

## The setup, and the one fact that decides everything

`asiddhatva` (8.2.1, *pūrvatrāsiddham*): the rules of the tripādī apply in
**strict textual order**, and each rule's trigger is **created by the previous
rule's output**. That single fact has two hard consequences for the
architecture:

1. **No reordering** — the chain is serial; you cannot parallelise it.
2. **No host/chip overlap** — the host cannot schedule step *k+1* until the
   chip has finished step *k*, because step *k+1*'s trigger doesn't exist until
   then. The data dependency **forbids pipelining** the brain and the muscle.

So chain latency is forced to be `Σ (host_select + chip_execute)` over the
steps — the brain and the muscle take turns, never overlapping. That is the
worst case for a fast accelerator, and it is exactly what asiddha imposes.

We ran a **depth-5 chain** (jaśtva → n-lopa → ścutva → ṣṭutva → parasavarṇa),
each step firing only on the prior step's result.

**Model costs:** chip transform `E = 10 ns` (one CRT recombine + residue ops),
host domain-check `c = 5 ns/rule`, indexed select `S = 20 ns`, clock 1 GHz.

---

## Hard numbers

**Depth-5 chain, three ways the host can find each rule:**

| Host strategy | Host time | Chip time | Total | Chip utilisation |
|---|---|---|---|---|
| **Indexed** (tripādī pointer, O(1)) | 100 ns | 50 ns | **150 ns** | **33.3%** |
| **Scan** N=200 rules | 5 000 ns | 50 ns | 5 050 ns | 0.99% |
| **Scan** N=4000 (full grammar) | 100 000 ns | 50 ns | **100 050 ns** | **0.05%** |

**The crossover — the exact mathematical point you asked for:**

> The host starves the chip the moment **per-step selection cost `S` exceeds the
> per-step transform cost `E`**. With the chip at 10 ns, that crossover is
> `N* = E / c = 10/5 = `**`2 candidate rules per step.`**

If the host weighs **more than ~2 rules** to pick the next one, it is already
the bottleneck. And it always does: even the cheapest indexed selection
(`S = 20 ns`) is **twice** the transform (`E = 10 ns`), so the chip is pinned at
**33% utilisation from depth 1.**

---

## The three findings, in plain English

**1. The 108-chip is never the bottleneck — it's the fast part.** A transform is
~10 ns; the host needs ~20 ns just to pick the next rule with perfect indexing,
and 20 *microseconds* if it scans the full grammar. **The muscle finishes
instantly and waits; the brain is the long pole from the very first step.** The
chip is not "starved" by being slow — it's so fast that *any* real scheduling
out-weighs it.

**2. Depth is NOT the breaking point.** This is the key result and it's clean:

```
chip utilisation along an asiddha chain = E / (S + E)   — CONSTANT in depth.
```

At depths 1, 5, 10, 100 the utilisation is **flat at 33.3%**; only absolute
latency grows, and only **linearly** — 30 ns per step. A depth-100 chain is
3 µs. Against a generous 10 ms real-time budget the depth ceiling is **333,000
steps** (indexed). Real asiddha chains are depth **2–7**. **Depth never breaks
it — not even close.** There is no combinatorial explosion; serial depth is
linear and cheap.

**3. The real cliff is the rule SCAN, not the chain.** The thing that actually
starves the chip is the host doing an **O(N) scan** of the rule base per step.
Scanning 4000 rules collapses chip utilisation to **0.05%** and drops the depth
ceiling from 333,000 to **499**. The fix is purely architectural: index the
rules (the tripādī's fixed order already *is* an index — advance a pointer,
don't scan). **Indexing vs scanning moves utilisation from 0.05% to 33% — a
650× swing.** That single design choice, not chain depth, is the breakpoint
knob.

---

## The asiddha-specific tax

The cost that asiddha imposes *beyond* an ordinary parallelisable rule set is the
serial host time that **cannot be hidden** behind chip execution:

```
asiddha tax = (D − 1) · S
```

For depth 5 indexed, that's `4 × 20 = 80 ns` of pure scheduling that a
pipelinable system could have overlapped away but asiddha forbids. It grows
**linearly** with depth — annoying, bounded, never catastrophic.

---

## Verdict, in one paragraph

There is no point at which chain depth makes the 108-chip too slow — its
utilisation is **constant in depth (≈33%)** and absolute latency is **linear and
tiny** (30 ns/step indexed; depth-100 = 3 µs vs a 10 ms budget). The host does
"starve" the chip in the *utilisation* sense — but only because the chip is so
fast that a ≥20 ns scheduler outweighs a 10 ns transform, crossing over at just
**2 candidate rules per step**. That is not a performance crisis: at 33%
utilisation the system is still blazing (150 ns for a 5-rule cascade). **The
single thing that turns low-utilisation into an actual latency cliff is a naive
O(N) rule scan** — fixable for free by using the tripādī's own fixed order as an
index. **Breaking point: not depth, not branching — unindexed rule selection.
Index the rules and the host keeps the chip fed at its structural ceiling
forever.**

---

## Honest caveats
- Cycle costs (E=10, c=5, S=20 ns) are a **transparent model**, not silicon.
  The robust outputs are the **forms**: `util = E/(S+E)` (flat in depth),
  crossover `N* = E/c`, tax `(D−1)·S`. Change the constants and the *numbers*
  move; the *structure and the conclusion* do not.
- The depth-5 chain is representative of tripādī serial dependency; it is not a
  claim that this exact 5-rule sequence is attested verbatim. The measured
  quantity (serial latency under a forced no-overlap dependency) is the point.
- "Utilisation" ≠ "too slow." We separated the two deliberately: the chip idles,
  but absolute latency stays negligible until the O(N) scan inflates it. Don't
  read 33% utilisation as a failure — read it as headroom.

## Reproducibility
`scratchpad/panini_asiddha.py` (run with `PYTHONIOENCODING=utf-8` on Windows).
Output: `depth-5 indexed 150 ns / 33.3% util · scan-4000 100 µs / 0.05% · cross-
over N*=2 rules/step · util flat in depth · D_max: 333k indexed vs 499 scan`.

### Cross-references
- Growth term identified here: `Ansh_108_Core_Consonant_Conflict_Breakpoint.md`
- The brain/muscle split: `Ansh_108_Core_Panini_Tensor_Experiment.md`
- Why comparison is the host's job: `Ansh_108_Core_Technical_Proof_and_Limitations.md` §6.2
