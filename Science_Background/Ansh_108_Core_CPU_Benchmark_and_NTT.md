# Ansh-N Core vs a normal CPU — measured, on a real crypto operation (NTT modular multiply)

**Status:** measured end-to-end, 2026-06-25. Answers two questions head-on:
*(1) how does the chip actually compare to a normal CPU, in real numbers?* and
*(2) is there a real job where its carry-free / divider-free style is the right
tool?* — using the same primitive for both: **modular multiply `(x·y) mod q`**,
the inner loop of lattice cryptography (Kyber/Dilithium-class) and homomorphic
encryption.

## The honest one-paragraph verdict

For a **single** modular multiply a normal CPU is **~10× faster** than this chip
(3.3 ns vs 36.6 ns) and ~10× faster **per core/unit**. The chip only competes by
**replication** — many constant-time cores in parallel — and even then a small
$130 FPGA roughly **ties** an 8-thread laptop CPU on aggregate throughput; it
needs a bigger FPGA/ASIC to pull clearly ahead. The chip's genuine, unconditional
edges are **constant-time determinism** (side-channel resistance — a real reason
crypto accelerators exist) and **performance-per-watt**, not raw speed. It is a
specialized accelerator/building-block, **not a CPU replacement**, and a GPU would
beat all of these on raw throughput.

## The CPU side (measured)

`cpu_bench.c`, gcc 16.1 `-O3 -march=native -fopenmp`, on **Intel i5-9300H**
(4 cores / 8 threads, 2.4 GHz, ~45 W). Constant `q` compiles the `%` into a
Barrett multiply-shift — the fair optimized path (no runtime divide). Clean
idle-machine run (the first attempt was discarded — it was contaminated by Vivado
P&R running concurrently; honest-measurement hygiene per
[[feedback_empirical_verification]]):

| q | single-op latency | 1-core throughput | 8-thread throughput |
|---|---|---|---|
| 41580 (the chip's modulus) | 3.3 ns | ~1,160 M/s | ~4,250 M/s |
| 12289 (NTT crypto prime) | 3.3 ns | ~1,155 M/s | ~4,260 M/s |

(The CPU is modulus-agnostic — same cost either way.)

## The chip side — a real NTT prime (measured)

`ntt_mul12289.v`: `(x·y) mod 12289`, q=12289 a real NTT-friendly prime
(12288 = 2¹²·3, supports radix-2 NTT to N=4096). **Barrett reduction**,
divider-free, constants fixed by an **exhaustive C check over all 12289² pairs**
(`barrett_check.c`: mu=21843, K=28, one conditional subtract — 0 mismatches).
3 multiplies → DSP-mapped, 4-stage pipeline, 1 op/cycle.

Verified **four** independent ways:
- **Exhaustive C** (`barrett_check.c`): all ~151M input pairs, 0 mismatch — a
  complete proof of the algorithm.
- **RTL sim** (iverilog): 3,000,008 pairs, 0 mismatch, latency 4 cycles.
- **Formal range+latency** (SymbiYosys+boolector): P1 `out<q` (valid), P2 exact
  4-cycle latency, over all inputs.
- **Formal FULL correctness** (SymbiYosys+**bitwuzla**): `out == (x·y) mod q`
  proven over all inputs in **89 s**. *Methodology note:* this is the 14×14
  multiplier-equivalence that **boolector could not** solve in Phase 5 at 16×16
  — **bitwuzla solves it**. So the multiplier wall is solver-specific, not
  fundamental; the Phase-5 strong spec is likely bitwuzla-provable too.

Routed (Vivado 2026.1, opt-applied, `xc7a35tcsg324-1`):

| | value |
|---|---|
| Routed fmax | **109.3 MHz** (WNS −5.146 ns @ 4 ns probe, 9.146 ns achieved) |
| Latency | 4 cycles = 36.58 ns |
| Footprint | **178 LUT / 61 FF / 2 DSP** (Vivado packed the 3 mults into 2 DSP48E1) |

## Head-to-head on the NTT prime

Replication is DSP-limited (2 DSP/core): xc7a35t has 90 DSP → **~45 cores**;
xc7a200t (740 DSP) → ~370 cores. (The composite-modulus 41580 core is *LUT*-based,
0 DSP, so it replicates further — ~91 cores on xc7a35t — see below.)

| Metric | CPU i5-9300H (~45 W) | 1 NTT chip core | full xc7a35t (~$130) | full xc7a200t |
|---|---|---|---|---|
| single-op latency | **3.3 ns** | 36.6 ns | — | — |
| throughput / unit | **1,155 M/s** /core | 109 M/s | — | — |
| device throughput | 4,260 M/s (8 thr) | — | ~45 cores → **~4,900 M/s** | ~370 cores → **~40,000 M/s** |
| timing | data-dependent | **constant-time** | **constant-time** | **constant-time** |
| relative power | high | very low | low | low |

**Reading it honestly:**
- **Latency:** CPU wins by ~11×. No contest for one operation.
- **Per core/unit throughput:** CPU wins by ~10×.
- **Whole small $130 FPGA vs 8-thread CPU:** ~4.9 G/s vs ~4.3 G/s — a **tie**.
- **Bigger FPGA (~$300–1000):** ~40 G/s — ~**9×** the laptop CPU.
- **A GPU** would beat all of these on raw throughput; the chip is not aimed there.

## Why the composite (LUT) core replicates better than the NTT (DSP) core

The 41580 RNS core uses **LUTs, 0 DSP** (153.6 MHz pipelined, 227 LUT) → ~91 cores
on xc7a35t → **~14 G/s** aggregate (~3× the CPU). The NTT core is **DSP-bound**
(2 DSP/core → 45 cores → ~4.9 G/s). So the carry-free LUT style actually scales
*further* on a small FPGA; the Barrett/DSP style is more area-efficient per op but
hits the DSP wall sooner. Honest trade, measured both ways.

## So — is it significant, and can it be its own chip?

- **As a CPU replacement: no.** Slower per operation, and only ties a laptop CPU
  on aggregate on cheap silicon.
- **As a deterministic, low-power, massively-replicable building block for
  constant-time modular arithmetic (PQC / FHE / NTT): yes, credibly.** That is
  exactly what real crypto accelerators are, and this is a verified, routed,
  formally-proven instance of the core primitive. On a large FPGA or an ASIC the
  replication story turns into a real multiple-× over a CPU, *with* constant-time
  guarantees a CPU struggles to give.
- It would be a **co-processor** (plug beside a CPU), never a standalone computer
  — no control, memory, or program execution.

**Honest caveats:** perf-per-watt is argued qualitatively (FPGA fabric vs a 45 W
CPU), **not** measured here — no power instrumentation. fmax is the core
reg-to-reg path, same metric as the rest of the arc. No physical chip — routed
FPGA implementation only. The NTT core is a single modular-multiply (the butterfly
*twiddle* step); a full NTT also needs add/sub-mod and address/twiddle control,
not built here. Replication counts are resource-limit ceilings; real designs lose
some to routing/fanout.

**Sources** (in `Ansh_108_Core_Artifacts/`): `cpu_bench.c` (+ `cpu_bench_result.txt`),
`barrett_check.c`, `ntt_mul12289.v`, `tb_ntt_mul12289.v`, `ntt_mul12289_formal.v`
(range+latency), `ntt_mul12289_corr.v` (bitwuzla full correctness), `*.sby`,
`synth_ntt_mul12289.ys`, `ntt_mul12289_pnr.tcl`, `ntt12289_out/`.
