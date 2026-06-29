# Ansh-N Core — N-Dial Scaling (Phase 5): does carry-free RNS scale, and what does width cost?

**Status:** measured end-to-end (math → sim → formal → synth → routed silicon),
2026-06-25. Tenth/eleventh build experiment in the Ansh-108 hardware arc; the
first that leaves Z/108 and asks the *scaling* question.

## The question

The whole 108-core arc fixed one transform: Z/108 = Z/4 × Z/27, **two** coprime
dials, made branch-free by CRT (see Phase 2–4). Phase 5 asks the obvious next
thing: **add more dials.** Does the carry-free / no-cross-talk property survive
to a wider residue number system, and — the headline — does the wider CRT
*reconstruction* cost clock speed at the same pipeline depth?

Test article: **Ansh-N Core over Z/41580 = Z/4 × Z/27 × Z/5 × Z/7 × Z/11** —
**five** coprime dials, 41,580 states (385× the 108-core's range), same 4-stage
pipeline, same Artix-7 part (`xc7a35tcsg324-1`), same P&R flow as Phase 4. So
any fmax difference is attributable to *width*, not methodology.

## Result (one line)

**Carry-free scaling holds — formally, over all inputs — but width costs fmax:
157.9 MHz (2 dials) → 118.7 MHz (5 dials), a −24.8 % clock penalty for a 385×
larger state space, at identical 4-cycle latency.**

## The five legs (all executed, nothing modeled)

| Leg | Tool | Result |
|---|---|---|
| (1) Math | Python `verify_crt_5mod.py` | moduli {4,27,5,7,11} pairwise coprime; **CRT bijection PASS over all 41,580 states** (exhaustive); idempotents `e=[31185,1540,8316,11880,30240]`; branch-free ×/+ PASS (3,000,000+6 / 500,000 pairs) |
| (2) RTL + sim | iverilog 12 (`rns41580.v`, `tb_rns41580.v`) | **300,008 random product pairs, 0 mismatch vs true modulo, latency 4 cycles, 1 transform/cycle** |
| (3) Formal | SymbiYosys + boolector (`rns41580.sby`) | **PASS, depth-12 BMC, over ALL residue inputs** — P1 `out<41580`; P2 `out_valid` exactly 4 cycles behind `in_valid`; P3 per-track correctness (see "Formal note") |
| (4) Synth | Yosys 0.66 `synth_xilinx xc7` | 331 LUT / 80 FF / 2 DSP48E1 / 21 CARRY4 / 71 MUXF7 (pre-P&R estimate; Vivado folds this far smaller) |
| (5) P&R | Vivado 2026.1, WebPACK mode, `xc7a35tcsg324-1` | **ROUTED CORE FMAX = 118.7 MHz** (reg-to-reg, achieved 8.425 ns, WNS −4.425 ns vs 4 ns probe) → 4-cycle latency = **33.70 ns**. Post-route footprint: **227 LUT / 70 FF / 0.5 BRAM / 0 DSP / 27 CARRY4 / 4 F7 mux** |

## Head-to-head vs the 108-core (Phase 4, same flow/part)

| Metric | 108-core (Z/108, 2 dials) | **41580-core (Z/41580, 5 dials)** | ratio |
|---|---|---|---|
| States | 108 | 41,580 | ×385 |
| Coprime dials | 2 | 5 | — |
| Routed core fmax | 157.9 MHz | **118.7 MHz** | ×0.752 (−24.8 %) |
| Achieved period | 6.334 ns | 8.425 ns | ×1.330 |
| 4-cycle latency | 25.34 ns | 33.70 ns | ×1.330 |
| Slice LUTs (routed) | 51 | 227 | ×4.45 |
| Flip-flops (routed) | 22 | 70 | ×3.18 |
| BRAM / DSP | 0 / 0 | 0.5 / 0 | — |

## What the numbers say

- **The carry-free property scales cleanly.** No cross-talk between dials; the
  five tracks multiply and LUT-reduce fully in parallel, divider-free, and the
  formal proof confirms correctness for *every* input — not a sample. Going from
  2 to 5 dials did not break the model.
- **Width costs fmax, and the cost lands in the recombine, not the tracks.** The
  per-dial track products (≤26×26) stay tiny; the penalty is the **stage-4 final
  reduction**. The 108-core finished with a single bounded output ROM
  (`MOD108[81a+28b]`, ~free). The 5-dial core must sum five weighted terms
  (18-bit) and reduce mod 41580 with a compare-ladder + `s − q·M` subtract — and
  *that* path is critical (+2.09 ns; corroborated by Yosys's longest topological
  path, which runs through `sum_3 → q → s−q·M`).
- **The trade is favorable in state-space terms.** 385× the range for a 1.33×
  longer clock period and ~4.4× the LUTs. The recombine cost scales with the
  *number of dials* (sum width / ladder depth), while the state space scales with
  the *product* of the moduli — so adding dials buys range far faster than it
  costs speed. (Stated across **two** design points only; a 3- and 4-dial point
  would be needed before calling this a scaling *law* — see [[feedback_empirical_verification]].)

## Formal note — why P3 was reformulated (and why it is still complete)

The naive correctness spec `out == (rx*ry) % 41580` makes the SMT solver
bit-blast a **16×16 variable multiply + 32-bit modulo** — the multiplier-
equivalence wall. boolector did **not** converge on it (a first attempt was
killed at the 10-minute solver-timeout mid-query). It was reformulated using CRT:
since Z/41580 ≅ ∏ Z/mᵢ is a **bijection**, two values in [0,41580) are equal iff
equal modulo each dial, and `(rx·ry mod M) mod mᵢ = (xᵢ·yᵢ) mod mᵢ`. So the
strong spec is *equivalent* to **P1 (`out<41580`) + P3 (`out ≡ xᵢ·yᵢ (mod mᵢ)`
for all 5 dials)** — every check small-modulus, no wide multiply. boolector then
proves it over all inputs in **2 m 25 s**. The final `out == (rx·ry) mod M`
equality follows from CRT *uniqueness*, which is proven **exhaustively over all
41,580 states** in `verify_crt_5mod.py`.

**Honest scope:** this is a complete proof of the hardware against small-modulus
arithmetic + an exhaustive offline bijection proof — a *layered* proof. It does
**not** bit-level-verify a 16×16 multiplier in SMT (no engine here does). The
end-to-end product is additionally covered by the 300,008-pair iverilog sim and
the 3,000,000-pair Python cross-check, both 0-mismatch.

## Honest caveats (per the standing empirical-verification rule)

- **fmax is the core reg-to-reg path**, derived from
  `get_timing_paths -from all_registers -to all_registers` WNS (−4.425 ns) —
  identical metric to Phase 4. The *global* worst path (−5.479 ns) is an
  FF→output-pin I/O path, an artifact of the 0-delay I/O constraints, and is
  correctly excluded (outputs are unregistered; off-chip timing is out of scope).
- **opt_design flaked once.** The first Phase-5 P&R aborted in `opt_design` with
  a blank `[Synth 20-411]` *after* DRC passed (0 errors). A re-run of the
  identical flow (wrapped in `catch`) had **`opt_design completed successfully`**
  — a Vivado 2026.1 internal flake, not a design defect. The 118.7 MHz figure is
  from the clean **opt-applied** run, so it stays apples-to-apples with Phase 4.
- **No physical chip.** Sim + synth + routed P&R on Artix-7 only, as with the
  whole arc.
- **`verify_crt_5mod.py` line ~99** prints "max weighted sum 540539 (20-bit)" for
  the *un-pre-reduced* sum; the RTL pre-reduces each term in its W-ROM so the
  hardware `sum_3` is correctly 18-bit (< 5·M). Not a bug; formal P1 confirms
  `out < 41580` regardless.

## Phase 5b — pipelining the glue (the fix, measured)

Phase 5 localized the whole −24.8 % to the stage-4 recombine. So the obvious
test: split that one fat cycle into several smaller ones and see if the clock
comes back. **`rns41580p`** is the same transform, same divider-free ROMs, but
the glue is spread over four stages instead of two — **6-stage pipeline** total:
S1 track products · S2 LUT reduce · S3 W-ROM weighted terms · **S4 5-way sum ·
S5 quotient ladder · S6 final subtract**. The two heavy blocks of the flat core
(the 5-way add, and the ladder+subtract) each get their own cycle.

| 5-dial core | Routed fmax | Period | Latency | Throughput | LUT / FF |
|---|---|---|---|---|---|
| Flat (4-stage) | 118.7 MHz | 8.425 ns | 33.70 ns (4 cyc) | 118.7 M/s | 227 / 70 |
| **Pipelined (6-stage)** | **153.6 MHz** | 6.510 ns | 39.06 ns (6 cyc) | **153.6 M/s** | 294 / 144 |
| 108-core (reference) | 157.9 MHz | 6.334 ns | 25.34 ns (4 cyc) | 157.9 M/s | 51 / 22 |

**Pipelining recovered the clock: 118.7 → 153.6 MHz (+29.4 %), closing ~89 % of
the gap to the 2-dial 108-core — now within 2.7 % (153.6 vs 157.9).** The width
penalty is *recoverable engineering, not a wall.* The cost is the standard
pipelining bargain: **+2 cycles of latency** (33.70 → 39.06 ns end-to-end) and
more flip-flops (70 → 144). For this accelerator — built for streaming and
~hundreds of replicated cores — **throughput is the figure of merit**, and it
rose to essentially match the 2-dial core while keeping 385× the range.

All five legs re-run on the pipelined core:
- **Sim** (iverilog, `tb_rns41580p.v`): 300,008 pairs, **0 mismatch**, latency 6.
- **Formal** (SymbiYosys+boolector, `rns41580p.sby`): **PASS, depth-16 BMC over
  ALL inputs, 3 m 10 s** — P1 (valid `out<41580`), P2 (`out_valid` exactly 6
  cycles behind `in_valid`), P3 (per-track residue correctness).
- **Synth** (Yosys): 294 LUT / 144 FF / 2 DSP48E1 / 21 CARRY4.
- **P&R** (Vivado 2026.1, opt applied, route clean): 153.6 MHz as above.

*Formal honesty:* P1 here is gated on `out_valid`. Splitting the reduce across a
register boundary means `sum` and the quotient `q` live in separate registers, so
the flat core's *unconditional* "out<M even on power-on garbage" no longer holds
for don't-care cycles — only the meaningful guarantee (**valid** outputs are in
range) does, and it is proven. The proof in fact **caught my first (ungated)
harness assertion** as a spurious step-2 power-on counterexample; gating on
validity is the correct property and it then passed clean.

## Phase 5c — the fmax-vs-dials curve (4 points, measured)

Phases 5/5b gave two points (2 and 5 dials). To see the *shape* of the cost, a
generator **`gen_rns.py`** emits architecturally-identical flat cores for any
prefix of the coprime moduli {4,27,5,7,11}: it exhaustively checks the CRT
bijection, computes the idempotents, and writes core + tb + formal harness + sby
+ synth + P&R. Generated, verified and routed **d2..d5** — every point with the
*same* arithmetic recombine, so the only variable is the number of dials. Each
point: exhaustive CRT bijection PASS, 200k-pair sim 0-mismatch, boolector formal
PASS over all inputs, opt-applied routed P&R on the same `xc7a35t`.

| dials | moduli | M (states) | routed fmax | period | latency (4 cyc) | LUT | FF |
|---|---|---|---|---|---|---|---|
| 2 | 4·27 | 108 | 243.5 MHz | 4.107 ns | 16.43 ns | 41 | 23 |
| 3 | 4·27·5 | 540 | 197.4 MHz | 5.065 ns | 20.26 ns | 76 | 37 |
| 4 | 4·27·5·7 | 3,780 | 134.0 MHz | 7.460 ns | 29.84 ns | 131 | 51 |
| 5 | 4·27·5·7·11 | 41,580 | 118.7 MHz | 8.425 ns | 33.70 ns | 227 | 70 |

Reading the curve:
- **Monotonic** fmax decrease 243.5 → 197.4 → 134.0 → 118.7 MHz as dials go 2→5.
- **Range multiplicative, cost additive.** Each added dial multiplies the state
  space (×5, ×7, ×11 → ×385 total, 108→41,580) while the critical-path *period*
  grows only ~linearly (+0.96, +2.40, +0.97 ns; ≈1.4 ns/dial avg) and LUTs grow
  ~linearly (≈+62/dial). **Exponential number-range for linear clock-and-area
  cost** — the core quantitative result of the whole N-dial study.
- The widening lives entirely in the recombine (sum width + ladder rungs + final
  subtract); the parallel tracks stay cheap. Steepest step is d3→d4 (+2.40 ns), a
  datapath-width crossing (sum 11→14 bit, out 10→12 bit) — single sample, not
  separately isolated from P&R placement variance.

Two architecture-variant reference points (deliberately *not* on the uniform
curve):
- **2-dial ROM-reduce** = the canonical 108-core, **157.9 MHz** — *slower* than
  the 2-dial arithmetic core (243.5 MHz). Honest correction: at small M the
  1024-deep distributed-ROM final reduce is worse than a 2-rung compare-ladder;
  the ROM framing read as "free" but cost ~35 % fmax in routed silicon. The
  arithmetic-reduce family is the better architecture across the board.
- **5-dial pipelined** (Phase 5b) = **153.6 MHz** — deepening the pipeline lifts
  the d5 point back up into the d3 neighborhood / near the d2 ROM-core.

## Where this sits

The N-dial study is now a measured **curve**, not an anecdote: the branch-free RNS
datapath generalizes from 2 to 5 dials with every point formally correct over all
inputs, and its cost is a smooth, recombine-bound, ~linear-in-dials clock/area
penalty set against a multiplicative range gain — and even that penalty is
recoverable by pipelining (d5: 118.7→153.6 MHz). No structural break anywhere on
the scaling axis. Open ends: pipelined variants of d2–d4 for a second curve; a
latency-optimal middle pipeline depth if latency (not throughput) ever binds; and
dials beyond 5 (add 13, 17, …) to test how far the linear-cost trend holds.

**Sources:** `scratchpad/rns41580.v`, `tb_rns41580.v`, `rns41580_formal.v`,
`rns41580.sby`, `verify_crt_5mod.py`, `synth_rns41580.ys`, `phase5_pnr.tcl`
(+ robust `phase5_pnr_v2.tcl`); outputs in `phase5_out/` (`fmax.txt`,
`timing_summary.rpt`, `utilization.rpt`, `worst_path.rpt`). **Phase 5b
(pipelined):** `rns41580p.v`, `tb_rns41580p.v`, `rns41580p_formal.v`,
`rns41580p.sby`, `synth_rns41580p.ys`, `phase5p_pnr.tcl`; outputs in
`phase5p_out/`. **Phase 5c (curve):** generator `gen_rns.py` (+ generated cores
`rns108a.v`, `rns540.v`, `rns3780.v`, and cross-check `rns41580g.v`); routed
results in `phase5c_curve_out/` (`rns108a/rns540/rns3780_fmax.txt` +
`_utilization.rpt`). All persisted into `Ansh_108_Core_Artifacts/`.
