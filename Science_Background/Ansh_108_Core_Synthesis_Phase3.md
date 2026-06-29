# Ansh-108 Core — Phase 3: Hardware Synthesis (Artix-7)

### Yosys synthesis to real FPGA primitives — footprint, gate count, and fmax

*Eighth experiment and the end of the build arc. Phase 2 verified the RTL in
simulation (4-cycle latency, 0 errors). Phase 3 runs it through Yosys
`synth_xilinx` targeting Xilinx Artix-7 (xc7) to extract the physical footprint
and a timing estimate. Created 2026-06-24. Source: `scratchpad/rns108.v`,
`scratchpad/synth.ys`. Tool: Yosys 0.66 (OSS CAD Suite 2026-06-24).*

---

## The honesty boundary up front

- **Footprint (LUTs / FFs / DSP / gate count) = hard synthesis truth.** Yosys
  mapped the RTL to actual Artix-7 cells. These numbers are real.
- **fmax = a synthesis-level ESTIMATE, not P&R-closed.** True fmax needs
  place-and-route timing (Vivado, or `nextpnr-xilinx`). This OSS CAD Suite build
  ships `nextpnr-ecp5` but **not** `nextpnr-xilinx`, and Vivado isn't present, so
  no routed timing was run. The fmax below is derived from the critical-path
  structure + published Artix-7 (-1) cell delays, and **excludes routing** —
  real P&R would pull it toward the low end.

---

## Physical footprint — Artix-7 (xc7), measured

```
=== rns108 (synth_xilinx -family xc7) ===
  LUTs total ........ 130   (114x LUT6, 2x LUT5, 3x LUT4, 4x LUT3, 7x LUT2)
  Flip-flops ........  30   (FDRE)
  DSP48E1 ...........   2   (the two multipliers: b1*b2 and 81*a+28*b)
  CARRY4 ............   2
  MUXF7 / MUXF8 .....  59 / 24   (wide-mux fabric building the ROMs)
  BUFG ..............   1   (clock buffer)
  I/O buffers .......  25   (17 IBUF + 8 OBUF)
  total cells .......  273
```

**ASIC-equivalent gate count** (generic AND-inverter mapping):

```
  ~2,846 logic gates   (1,608 AND + 1,238 INV)  +  44 flip-flops
```

**Where the area goes:** the two **1024-entry mod-27 / mod-108 ROMs** dominate.
Yosys built them as **distributed LUT-ROM** (that's the 114 LUT6 + 59 MUXF7 + 24
MUXF8 cascades), not BRAM. The division-free LUT approach trades arithmetic
logic for ROM fabric — and you can see the exact price: ~130 LUTs, most of it
ROM. The two multiplies dropped neatly into **2 hardened DSP48E1** slices.

---

## Timing estimate — fmax

The per-stage critical path (from the longest-path analysis) is a **combinational
DSP48E1 multiply** and/or a **1024-deep distributed LUT-ROM read**
(LUT6 → MUXF7 → MUXF8) in series with a CARRY4 add. On Artix-7 (-1 speed grade),
using published cell delays + modest routing:

| Critical element | est. delay |
|---|---|
| DSP48E1 multiply, combinational (no internal pipe regs) | ~2.8–3.3 ns |
| 1024-deep distributed ROM read (LUT6+MUXF7+MUXF8 + nets) | ~1.5–2.5 ns |
| CARRY4 add + clk-to-Q + setup + routing | ~1–2 ns |

> **Estimated fmax ≈ 250 MHz** (defensible band **200–350 MHz**). The DSP used
> combinationally and the deep distributed ROMs are the limiters. P&R routing
> would likely push toward the **low** end (~200–250 MHz); enabling the DSP's
> internal pipeline registers and moving the ROMs to BRAM would push the **high**
> end (400 MHz+). This is an estimate, not timing closure.

---

## The 4-cycle latency in hard nanoseconds

| fmax | clock period | 4-cycle serial latency |
|---|---|---|
| 200 MHz | 5.0 ns | 20.0 ns |
| **250 MHz** | **4.0 ns** | **16.0 ns** |
| 300 MHz | 3.33 ns | 13.3 ns |

So a single serial (asiddha) transform on a real consumer Artix-7 takes
**~13–20 ns**, central **~16 ns**.

---

## The raw silicon truth — and it's a reality check

**The serial transform on a real consumer FPGA (~16 ns) is NOT faster than the
optimized x86 software path (~9.7 ns). It's slightly slower.** That is the
honest, slightly humbling result of going all the way to gates:

- A naive RTL on a ~250 MHz consumer FPGA cannot beat a 2.4 GHz CPU on a
  **single dependent operation** — the CPU's raw clock wins a latency race.
- The FPGA's real advantages are the two things the CPU can't do:
  1. **Throughput** — fully pipelined, **1 transform/cycle = ~4 ns/op** at
     250 MHz for *independent* operations (the parallelisable bulk from
     experiments 4–5).
  2. **Replication** — at **130 LUTs + 2 DSP + 30 FF per core**, the core is
     tiny. The DSPs are the limiter (2/core): a small **xc7a35t** (90 DSPs) fits
     **~45 parallel cores**; an **xc7a200t** (740 DSPs) fits **~370 cores** —
     each running its own rule stream deterministically. Drop the DSPs (do the
     small multiplies in LUTs) and hundreds more fit.

So the Ansh-108 isn't a single-thread speed demon; it's a **tiny, deterministic,
massively-replicable throughput engine.** Its win over the CPU is *width and
determinism*, not single-op latency.

---

## Utilisation at the REAL clock

At the estimated ~250 MHz, the serial transform E ≈ 16 ns. Against the host
costs (S ≈ 0.79 ns, c ≈ 0.57 ns):

```
chip util = E/(S+E) = 16/(0.79+16) = 95.3%
crossover N* = E/c   = 16/0.57      = 28 rules/step
```

Because the real FPGA muscle is *modest-speed* (16 ns, not the hypothetical
1–2 ns), it is trivially easy to keep fed: **95% utilisation, host could weigh
28 rules per step.** The "faster muscle is harder to feed" worry from Phases 1–2
**does not bite at real Artix-7 speeds** — it would only matter on a multi-GHz
ASIC. On consumer silicon, the host is never close to the bottleneck.

---

## Verdict (Phase 3 / end of build)

We took the architecture all the way to gates on a real, consumer-grade Artix-7:
**130 LUTs, 30 FFs, 2 DSP48E1, ~2,850 ASIC-equivalent gates per core**,
estimated **~250 MHz** (200–350 MHz band; P&R needed to close it), giving a
**~16 ns** 4-cycle serial latency. The raw truth: on consumer silicon the core
is **not** a single-op speed demon — it's *slightly slower than optimized x86
for one dependent transform* — but it is **tiny, fully pipelined (4 ns/op
throughput), and massively replicable (~45–370 cores per chip).** Its real
advantage is exactly what the whole thesis pointed at: not brute speed, but
**parallel, deterministic width** — many small Pāṇini-fed cores running in
lock-step. The architecture is physically real, physically small, and physically
modest in clock — and that is the honest silicon truth.

---

## Honest caveats
- **No P&R / no routed timing.** fmax is a structure-based estimate (cell delays
  + light routing), not Vivado/nextpnr closure. `nextpnr-xilinx` was not in the
  installed suite. Treat fmax as ±30%.
- The ROMs mapped to **distributed LUT** here; forcing BRAM (`-nobram` off /
  attributes) would cut LUTs sharply and change fmax — a real design knob not
  explored.
- The DSP used combinationally is the likely timing limiter; pipelining it would
  raise fmax at the cost of +1–2 latency cycles.
- Core-count-per-chip figures assume DSP is the binding resource (2/core) and
  ignore I/O, clocking, and interconnect overhead — first-order, not a floorplan.

## Reproducibility
```
yosys -s synth.ys -l synth.log         # synth_xilinx -family xc7 ; stat ; ltp
yosys -s synth_generic.ys              # generic AIG gate count
```
Yosys 0.66 (OSS CAD Suite 2026-06-24, winget download). Footprint numbers are
from `stat.txt`; gate count from `stat_gates.txt`.

### Cross-references
- Phase 2 (RTL verified in sim): `Ansh_108_Core_Verilog_RTL_Phase2.md`
- Phase 1 (x86 measured): `Ansh_108_Core_RNS_Kernel_Measured.md`
- The "faster muscle, lower util" prediction tested here: same Phase-2 file
