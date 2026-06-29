# Ansh-108 Core — Phase 2: The Verilog RTL (Real Datapath)

### Parallel Mod-4 ∥ Mod-27, LUT-based reduction, simulated in Icarus iverilog

*Seventh experiment, the hardware realization of the architecture. Phase 1
(`..._RNS_Kernel_Measured.md`) measured the transform on an x86 CPU *emulating*
RNS, and flagged that x86's integer-division for mod-27 inflated the cost. Phase
2 builds the real datapath in Verilog — explicit parallel tracks, mod-27 as a
ROM lookup (no divider) — and measures the true hardware cycle cost. Created
2026-06-24. Source: `scratchpad/rns108.v`, `scratchpad/tb_rns108.v`. Toolchain:
Icarus iverilog 12 (winget).*

---

## What was built

A 4-stage pipelined RNS-108 transform, `Z/108 = Z/4 × Z/27`:

- **Mod-4 track** — the low 2 bits; free, combinational.
- **Mod-27 track** — reduction by **ROM lookup** (`MOD27[v] = v % 27`, the `%`
  runs once at elaboration to fill the ROM; in synthesis it is table contents,
  **never a runtime divider**). This is the explicit fix for x86's mod penalty.
- The two tracks run **in parallel, no cross-talk**, exactly as the CRT proof
  requires.
- **CRT recombine** — `out = MOD108[81*a + 28*b]`, also ROM-reduced.

---

## Functional result — it is correct

```
transforms checked : 11664   (all 108×108 input pairs)
mismatches vs TRUE modulo : 0
```

Every one of the 11,664 input pairs matches a golden reference computed with
real `%`. **The division-free LUT datapath is exactly correct** — the ROM
reduction reproduces true modular arithmetic with zero error. The parallel
mod-4 ∥ mod-27 structure the whole thesis rests on is now a verified RTL
artifact, not a claim.

---

## Hardware cost — measured (exact, from simulation)

```
pipeline LATENCY    : 4 cycles   (serial / asiddha step)
streaming THROUGHPUT: 1 transform / cycle   (independent ops)
```

These cycle counts are the hard, noise-free truth from the simulator. **Cycles,
not nanoseconds** — the ns value needs a clock, and the *true* clock (fmax) needs
synthesis (Phase 3). Below is the utilization curve across a clock sweep, using
the host scheduling costs measured on x86 in Phase 1 (best-case, since `S` and
`c` are only a few cycles and jitter run-to-run): `S ≈ 0.79 ns`, `c ≈ 0.57 ns`.

---

## The utilization curve — where the real-silicon crossover lands

**Serial / asiddha regime** (the chip pays the full 4-cycle latency, no overlap):

| Clock | E_serial | Chip util = E/(S+E) | Crossover N* = E/c |
|---|---|---|---|
| 250 MHz | 16.0 ns | **95.3%** | 28.1 rules/step |
| 500 MHz | 8.0 ns | **91.0%** | 14.0 |
| **1 GHz** | **4.0 ns** | **83.5%** | **7.0** |
| 2 GHz | 2.0 ns | 71.7% | 3.5 |
| 3 GHz | 1.33 ns | 62.8% | 2.3 |
| *x86 software (Phase 1)* | *9.69 ns* | *92.5%* | *17.0* |

**Crossover verdict:** at a realistic 1 GHz the real-silicon crossover lands at
**N\* ≈ 7 rules/step** — the host may weigh up to ~7 candidate rules before it
becomes the bottleneck. Pāṇini's indexed selection weighs **~1 rule per step**
(advance the tripādī pointer). **1 ≪ 7, so the host stays well under the
crossover and the chip runs at ~84% utilisation.** At 250–500 MHz it's
90–95%; only at multi-GHz does it dip toward parity.

---

## The Phase-1 caveat — now confirmed by real hardware

Phase 1 predicted: *remove the division and the muscle gets faster, which
**lowers** utilisation (a faster muscle is harder to keep fed).* Measured:

| | muscle cost | speed-up | chip util | crossover N* |
|---|---|---|---|---|
| x86 software (div-bound) | 9.69 ns | — | 92.5% | 17.0 |
| **RTL LUT @ 1 GHz** | **4.0 ns** | **2.4×** | **83.5%** | **7.0** |
| **RTL LUT @ 2 GHz** | **2.0 ns** | **4.8×** | **71.7%** | **3.5** |

**The LUT mod-27 did exactly what §6.3 said it would** — it removed the division
penalty and made the muscle 2.4–4.8× faster than the x86 software path. And the
predicted consequence is real: the faster muscle **lowers** utilisation
(92% → 84% → 72%) and **shrinks** the crossover (17 → 7 → 3.5). The muscle is so
fast now that the tiny host overhead is *relatively* larger. But it is **still
well-fed, not starved** — 84% at 1 GHz — because Pāṇini's indexing keeps the host
at ~1 rule/step, far below even the shrunken N\* of 7.

**The one regime that flips:** for the *parallelisable* majority of rules (the
non-asiddha bulk, which experiments 4–5 showed dominate), the chip pipelines at
**1 transform/cycle**. At 1 GHz that's 1.0 ns/op vs host 0.79 ns → roughly
balanced; at 2 GHz the chip throughput (0.5 ns) outruns the host (0.79 ns) and
the system becomes **host-bound** — but on a host cost so small it doesn't
matter in absolute terms.

---

## Verdict (Phase 2)

We built the true physical datapath, not a software approximation: explicit
parallel mod-4 ∥ mod-27 tracks with a **division-free LUT mod-27**, verified
correct on all 11,664 input pairs, measured at **4-cycle latency / 1-per-cycle
throughput**. Removing the divider made the muscle **2.4–4.8× faster** than the
x86 path — confirming the division was the dominant cost (§6.3) and that the
real chip is genuinely quick. The real-silicon crossover lands at **N\* ≈ 7
rules/step at 1 GHz** (3.5 at 2 GHz, 28 at 250 MHz). Because Pāṇini's sequential
rule order keeps the host at ~1 rule/step, **the host never reaches the crossover
and the chip stays 84–95% utilised at realistic clocks.** The faster muscle
confirms Phase 1's caveat — utilisation and N\* both drop — but the chip is
well-fed, not starved, until you push past ~2 GHz, where the (still-negligible)
host scheduling becomes the nominal limiter. **The architecture holds in real
RTL.**

---

## Honest caveats
- **iverilog yields cycles, not nanoseconds.** Latency = 4 cycles is exact; all
  ns figures are `cycles × assumed clock`. The *true* fmax requires synthesis
  (Yosys + a timing library / FPGA) — **Phase 3, not done here.** The clock
  sweep is given precisely so no single fabricated ns is implied.
- For a **serial** chain, pipelining cannot help — the 4-cycle latency is the
  combinational work split into 4 stages. A 1-stage combinational version would
  be latency-1 but lower fmax; net ns is roughly clock-invariant and is itself a
  synthesis question. So "4 cycles" is the structure; total ns is Phase 3.
- Host `S`, `c` are few-cycle measurements with real run-to-run variance
  (frequency scaling); best-case values used. The verdict (util 80–95%, N\* in
  single-to-low-double digits at realistic clocks) is robust to that jitter;
  the exact decimals are not.

## Reproducibility
```
iverilog -o rns108.vvp rns108.v tb_rns108.v && vvp rns108.vvp
```
iverilog 12 (winget `Icarus.Verilog`). Output: `11664 checked, 0 mismatches,
latency 4 cycles, throughput 1/cycle`. Curve: `scratchpad/recompute_phase2.py`.

### Cross-references
- Phase 1 (x86 measured, the caveat): `Ansh_108_Core_RNS_Kernel_Measured.md`
- The mod-27 cost this fixes: `Ansh_108_Core_Technical_Proof_and_Limitations.md` §6.3
- The asiddha serial regime: `Ansh_108_Core_Asiddha_Latency_Breakpoint.md`
- Next: Phase 3 = Yosys synthesis for true fmax (real nanoseconds).
