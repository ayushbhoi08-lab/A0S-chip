# ANSH-108 Core — Master Applications Directory

### Strategic vertical directory, built on the MEASURED silicon (Phases 1–4)

*Tenth file. Layers an application/strategy directory on top of the nine-file
build arc. Every capability claim here is anchored to a measured number, not an
aspiration. Created 2026-06-24. Lead Systems Architect record. Query protocol at
the bottom: ask about one vertical → full pipeline, I/O, and Artix-7 limits.*

---

## 1. The measured silicon baseline (what the core actually IS)

From Phase 4 (real Vivado P&R, xc7a35t, free WebPACK mode):

| Spec | Measured value |
|---|---|
| Function | a **fixed** transform over Z/108 = Z/4 × Z/27 (mod-4 ‖ mod-27 tracks, CRT recombine) |
| Footprint | **51 LUTs, 22 FFs, 0 DSP** per core |
| Clock | **157.9 MHz** routed (6.33 ns period) |
| Latency | **4 cycles ≈ 25 ns** serial; throughput **1 result / 6.33 ns** pipelined |
| Replication | **~400 cores / xc7a35t** (LUT-limited at 20,800/51) |

**What it IS:** a tiny, deterministic, massively-replicable **fixed-function
modular-arithmetic engine**. Its edge is *parallel deterministic width + bit-exact
zero-jitter timing*, never single-thread speed (measured ~2.6× slower than x86 on
one op — constraint #1 holds, with numbers).

**What it is NOT (and this gates every vertical below):**
- Not a general processor, string matcher, sorter, or float unit.
- Not an arbitrary-modulus engine — the moduli are **hardwired 4 and 27**.
  Anything needing a *different* or *configurable* modulus is a **new datapath**,
  not this core.
- Not a cryptographic primitive (see §2).

---

## 2. Two corrections before we scale (so the strategy stays honest)

**(A) "108-bit" ≠ what the core emits.** One transform outputs a value in
**[0, 108) — about 6.75 bits**, not 108 bits. A 108-bit `ansh_signature` is
*achievable* but only as a **construction on top of the core**: chain ~16
transforms in a sponge/feedback mode and concatenate the states. Feasible, but
it is a mode we build, not a single-cycle output. The directory must say
"108-bit fingerprint via N chained 108-state rounds," not "108-bit output."

**(B) "Cryptographic" ≠ what mod-108 provides.** Z/108 is algebraically trivial
(smooth modulus, 72 of 108 elements non-invertible, no key, no trapdoor). The
core gives a **deterministic, zero-jitter content FINGERPRINT / integrity hash** —
excellent for *provenance and bit-exact reproducibility* ("this asset is
identical to the certified original, verifiable by recomputation"). It does **not**
give *unforgeability against an adversary*. Call it a **deterministic provenance
hash**, not a signature/crypto, in anything customer-facing. (If true crypto is
needed, the core can be the zero-jitter datapath *under* a real keyed
construction — a separate design.)

These two corrections don't kill any vertical; they keep the claims defensible.

---

## 3. Capability classes (how each vertical relates to the real core)

- **Class A — Native:** runs the actual RNS-108 transform as-is. (Verticals 1, 6)
- **Class B — Architecture reuse:** keeps the *principle* (parallel deterministic
  modulo lanes, FPGA determinism) but needs a **new datapath**, not this core.
  (Verticals 3, 4, 5)
- **Class C — Structural / creative:** the modulo math models a structure;
  "hardware" is conceptual, not a workload. (Vertical 2)

Being explicit about the class is the whole point — it tells us where the
measured 51-LUT/158-MHz core literally drops in (A), where we reuse only the
pattern (B), and where it's a metaphor (C).

---

## 4. The vertical directory (summary; deep-dive on query)

**1. Project Ansh — Provenance Audio · Class A.**
Deterministic 108-bit provenance hash (16 chained rounds) over the 737
Sanskrit/vocal assets (the SHOALKS/BG_ corpus). Pipeline: asset bytes →
streaming chained RNS-108 → `ansh_signature` register. Win: bit-exact, zero-jitter,
recomputable provenance for studios. #1 limit: it's integrity/provenance, **not
adversarial crypto** (§2B); throughput bound by asset-streaming I/O, not the core.

**2. ANSH Chronicles — Literary Physics · Class C.**
The 54→108→432 cycle and mod-27 tracks as a narrative-structure
generator/validator (already real as `ansh_janayu_telemetry.py`). The hardware is
a *model* of the structure, not a renderer. #1 limit: honest framing — the chip
doesn't "run the novel"; the cyclic math hard-codes the scaffold. Respects
constraint #2 (the cyclic loop) by construction.

**3. Hardware-Accelerated Genomics · Class B.**
A/C/G/T → 2-bit fits the **mod-4 lane natively** — the one place Base-4 maps
perfectly. But matching is a **comparator/aligner datapath**, not the RNS
transform. #1 limit: xc7a35t is far too small to hold a reference genome on-chip →
needs streaming + external DRAM and a bigger part; sequencing I/O bandwidth is the
real wall, not compute.

**4. Acoustic Beamforming · Class B.**
FPGA determinism is a genuinely strong fit (no OS jitter). New datapath:
per-channel fractional delay + sum. #1 limit: **I/O-pin count** — xc7a35t has ~210
IOB, capping array channels; fractional delay needs more than mod-4/27; the
**0-DSP** mapping means MAC sums compete for LUTs.

**5. Radio Astronomy — Epoch Folding / FRB · Class B (closest cousin).**
Pulsar epoch folding *is* modulo-binning — conceptually the nearest to the core.
#1 limit: real pulsar periods are arbitrary, but the core's modulus is
**hardwired 108** → needs **configurable moduli** (a generalization that must
still respect constraint #2); de-dispersion needs frequency-dependent delays
(non-modular); sample rates exceed a 35t → bigger part + DRAM.

**6. Zero-Power IoT Edge Hashing · Class A.**
The measured **51-LUT / 0-DSP** footprint is the headline — a real fit for tiny
edge integrity hashing. #1 limit: an Artix-7's **static power (~tens of mW idle)
is too high for ambient-RF/solar** — true "zero-power" needs an ASIC or a
flash-based nano-FPGA port of the 51-LUT core; and §2B applies (fingerprint, not
crypto).

---

## 5. Query protocol

Ask about **one vertical** and you get: (a) the exact data pipeline stage-by-stage,
(b) hardware I/O requirements (pins, bandwidth, memory, clocking), and (c) the
specific Artix-7 limitation that bounds it — each tied to the measured baseline in
§1. Constraints honored throughout: never a sequential CPU (it's parallel
deterministic width), and every expansion respects the cyclic-loop math (§2,
flagged explicitly where a vertical strains it — e.g. vertical 5's arbitrary
moduli).

### Cross-references
- Measured baseline: `Ansh_108_Core_PnR_Phase4.md`, `..._Synthesis_Phase3.md`
- The transform itself: `Ansh_108_Core_Verilog_RTL_Phase2.md`
- Provenance corpus (vertical 1): recording-provenance notes; backend rhythm pipeline
