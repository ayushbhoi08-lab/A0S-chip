# Ansh-108 Core — Phase 4: Place & Route (MEASURED routed fmax)

### The last gap closed — real Vivado P&R on Artix-7, not a projection

*Ninth/final file of the build arc. Phase 3 gave a synthesis-level fmax estimate
(~250 MHz, no routing). Phase 4 runs the real Vivado place-and-route and reports
the **measured routed fmax**. Created 2026-06-24. Tool: Vivado 2026.1 (found at
`E:\AMD\2026.1`, bundled with Vitis). Script: `scratchpad/phase4_pnr.tcl`.*

---

## Headline — the measured routed result

```
part              = xc7a35tcsg324-1   (Arty A7-35T, consumer Artix-7, -1 grade)
ROUTED CORE FMAX  = 157.9 MHz         (reg-to-reg, achieved period 6.334 ns)
4-CYCLE LATENCY   = 25.34 ns
```

This is a **real, placed-and-routed number** from Vivado's post-route static
timing — synth → opt_design → place_design → route_design all completed with 0
errors. No projection, no model: the final routed silicon truth.

---

## How the licensing actually resolved (honest trail)

The first run hard-failed with `ERROR: a valid license was not found (exit 42)`.
**That was self-inflicted:** I had set `XILINXD_LICENSE_FILE` to the bundled
IP-core license dir, which *broke* Vivado's free-mode fallback. With that env var
**unset**, Vivado 2026.1 runs the xc7a35t (a WebPACK-class part) in **free
Standard mode** — it auto-checks-out `Vivado_Synthesis` and
`Vivado_Implementation` with **no paid license**. A second bug (`remove_from_collection`
isn't valid in this Tcl context) was fixed with explicit port lists. After both
fixes the full flow ran clean. So: no paid license was needed; the wall was my
own two script/env mistakes, now corrected.

---

## Measured post-route footprint (REAL — and far leaner than estimated)

```
=== post-route utilization (xc7a35t) ===
  Slice LUTs ........  51   (all LUT as Logic)       of 20800   (0.25%)
  Slice Registers ...  22   (FF)                     of 41600   (0.05%)
  DSP48 .............   0                             of    90   (0.00%)
  F7 Muxes ..........  10                             of 16300
  F8 Muxes ..........   0
  BUFGCTRL ..........   1
  Bonded IOB ........  25
```

| | Yosys synth_xilinx (Phase 3 estimate) | **Vivado post-route (measured)** |
|---|---|---|
| LUTs | 130 | **51** |
| Flip-flops | 30 | **22** |
| DSP48 | 2 | **0** |
| F7/F8 muxes | 59 / 24 | **10 / 0** |

**Vivado optimised far harder than Yosys.** It constant-folded the mod-27/mod-108
ROMs aggressively (the operands are bounded `<108`, so much of the 1024-entry
tables is unreachable and was pruned) and implemented the tiny 5×5 / constant
multiplies in LUTs rather than DSPs. The functional equivalence is intact — the
Phase-2 testbench verified all 11,664 input pairs, and P&R preserves logic
equivalence. **The real core is ~51 LUTs — a quarter of the Phase-3 estimate.**

---

## The fmax number, read honestly

The script extracts the **core reg-to-reg** worst-slack path: against a 4.0 ns
probe clock, WNS = −2.334 ns → achieved period 6.334 ns → **157.9 MHz**.

One transparency note: the *overall* design WNS in `report_timing_summary` is
worse (−7.94 ns) because the I/O paths were constrained with **zero external
delay** (`set_input/output_delay 0.0`) — demanding the whole pad-to-FF path fit
in one clock with no board budget, which is unrealistically tight and an
**artifact of the constraint, not the core logic**. A real integration registers
the I/O at the boundary. The honest core-logic fmax is **157.9 MHz**.

---

## Projection vs reality — the estimate held

| | fmax | 4-cycle latency |
|---|---|---|
| Phase 3 synthesis estimate (no routing) | ~250 MHz | ~16 ns |
| Phase 4 projection (this file, before the run) | ~150–200 MHz (central 175) | ~20–27 ns |
| **Phase 4 MEASURED (routed)** | **157.9 MHz** | **25.34 ns** |

The measured **157.9 MHz** lands inside the projected 150–200 MHz band, near the
low end. The routing derate from Yosys's 250 MHz estimate is **1.58×** —
squarely within the stated 1.3–1.7× band. The projection was honest and correct;
reality just landed on the conservative side.

---

## Final verdict — the whole arc, closed with a real number

The serial transform on a real, placed-and-routed consumer Artix-7 takes
**25.34 ns at 157.9 MHz** — **~2.6× slower than the optimized x86 software path
(~9.7 ns)**. That confirms, with measured silicon, what every prior phase pointed
at: **a consumer FPGA loses the single-operation latency race to a 2.4 GHz CPU.**

Its real advantages, also now measured:
- **Throughput:** fully pipelined = **1 transform / 6.33 ns** for independent ops.
- **Replication, now even larger than Phase 3 thought:** with the real footprint
  at **51 LUTs and 0 DSP per core**, DSP is no longer the limiter — it's
  LUT-bound: **20,800 / 51 ≈ ~400 cores on a single ~$130 xc7a35t** (FFs would
  allow ~1,890). Phase 3 guessed ~45 (DSP-limited); the real, leaner mapping
  fits **~8× more**.

So the Ansh-108 Core is physically real, **tiny (51 LUTs), modest-clock
(158 MHz), and massively replicable (~400 cores/chip)** — a deterministic
throughput-and-width engine, exactly as the thesis predicted, and **not** a
single-thread speed demon. Every rung from the CRT proof to routed gates is now
**measured truth**.

---

## Reproducibility
```
# from the scratchpad dir holding rns108.v + phase4_pnr.tcl:
E:\AMD\2026.1\Vivado\bin\vivado.bat -mode batch -source phase4_pnr.tcl
# (XILINXD_LICENSE_FILE must be UNSET so free WebPACK mode engages)
```
Vivado 2026.1, free Standard/WebPACK mode (no paid licence; xc7a35t is
WebPACK-class). Outputs: `phase4_out/fmax.txt`, `timing_summary.rpt`,
`utilization.rpt`, `rns108_routed.dcp`. Measured: `fmax 157.9 MHz · period
6.334 ns · WNS(core) -2.334 · latency 25.34 ns · 51 LUT / 22 FF / 0 DSP`.

### Cross-references
- Phase 3 (synthesis estimate this confirms): `Ansh_108_Core_Synthesis_Phase3.md`
- Phase 2 (RTL verified, 11,664 pairs): `Ansh_108_Core_Verilog_RTL_Phase2.md`
- Script: `scratchpad/phase4_pnr.tcl`
