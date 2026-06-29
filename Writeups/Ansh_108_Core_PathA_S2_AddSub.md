# Ansh-108 Core — Path A, Session S2: rns_add / rns_sub (5-leg verified)

### Two new residue-native ops on the primary lane, every leg green

*Path-A Phase-1 deliverable (plan §3 / §5 row S2). Builds on S1's
`golden_model.py` (17/17) and the already-verified cores `ntt_mul12289.v`,
`rns108.v` — those were NOT rebuilt. Created 2026-06-28. Tools: Python 3.14,
Icarus Verilog (C:\iverilog), oss-cad-suite 2026-06-28 (Yosys 0.66, SymbiYosys,
boolector 3.2.4), Vivado 2026.1 (E:\AMD\2026.1). All artifacts in
`Ansh_108_Core_Artifacts/`.*

---

## What was built

Two branch-free modular ALU ops on the **primary mod-12289 lane** (the same
14-bit operand lane as `ntt_mul12289`), matching the locked §2 packet layout and
the `ADD`/`SUB` semantics in `golden_model.py`:

| Module | Function | Construction | Latency |
|---|---|---|---|
| `rns_add.v` | `out = (x + y) mod 12289` | 15-bit sum, **one** conditional `−q` (x+y < 2q) | 2 cycles |
| `rns_sub.v` | `out = (x − y) mod 12289` | 15-bit subtract, borrow bit drives **one** conditional `+q` | 2 cycles |

Both are **constant-time**: the single correction is a 2:1 mux selected by one
carry/borrow bit — no divider, no data-dependent loop, no branch. Throughput =
1 result/cycle. The valid pipeline is exactly as deep as the datapath (2 stages),
so `out_valid` stays aligned with `out` (see the latency-bug note below).

---

## The 5-leg verification gate — ALL GREEN (both modules)

| Leg | Tool | rns_add | rns_sub |
|---|---|---|---|
| 1 · Python | `verify_rns_addsub.py` vs `golden_model.py` | **PASS** | **PASS** |
| 2 · Sim | Icarus Verilog, ≥300k random pairs + corners | **0 mismatch**, lat 2 | **0 mismatch**, lat 2 |
| 3 · Formal | SymbiYosys + boolector, BMC depth 12 | **PASS** (P1·P2·P3) | **PASS** (P1·P2·P3) |
| 4 · Synth | Yosys `synth_xilinx -family xc7` | 37 LUT / 31 FF / 0 DSP* | 17 LUT / 31 FF / 0 DSP* |
| 5 · P&R | Vivado 2026.1, `xc7a35tcsg324-1`, routed | **242.2 MHz** | **261.3 MHz** |

\* Synth leg cell counts and the P&R footprint below differ because Vivado
optimises harder; both are reported honestly.

### Leg 1 — Python (exhaustive + cross-check)
A bit-exact model of each RTL reducer is verified **exhaustively over its entire
reachable domain** — every sum `[0, 2q−2]` (add) and every signed difference
`[−(q−1), q−1]` (sub), 24,577 values each, a *complete* proof of the reduction
logic — then cross-checked `RTL-model == golden_model == true mod q` over
**2,000,000 random pairs**, plus directed corners (incl. the sub borrow path).
`ALL PASS`.

### Leg 2 — Icarus Verilog
Self-checking TBs (`tb_rns_add.v`, `tb_rns_sub.v`) stream 300,008 / 300,009
pairs against true modulo: **0 mismatches**, measured **latency = 2 cycles**.
Corners include the overflow boundary (add) and `x<y` borrow (sub).

### Leg 3 — Formal (SymbiYosys / boolector)
Three properties proven by SMT over **all** inputs (free `x,y,in_valid,rst`;
domain assumed `<12289`), BMC depth 12 — complete for a feedback-free 2-stage
pipeline:
- **P1 range:** every valid `out < 12289`.
- **P2 latency:** `out_valid` is exactly 2 cycles behind `in_valid`, for any
  reset/valid sequence.
- **P3 functional correctness:** `out == (x±y) mod 12289`, shadowed through the
  2-stage delay — the **full** correctness theorem (no wide multiply here, so
  unlike `ntt_mul12289` this did not need to be offloaded to an exhaustive C
  check; boolector closes it directly in <1 s).

### Leg 4 — Yosys synth_xilinx (resource estimate)
`rns_add`: 132 cells (31 FDRE, 9 CARRY4, 34 LUT, +I/O buffers); LTP length 12.
`rns_sub`: 117 cells (31 FDRE, 8 CARRY4, 28 LUT, +I/O buffers); LTP length 12.
The 31 flip-flops confirm the register count by construction (add: 15-bit `s1`
+ 14-bit `out` + `v1` + `out_valid`; sub: 15-bit `d1` + 14-bit `out` + 2 valid).

### Leg 5 — Vivado P&R (measured routed fmax)
Same flow/part as `ntt_mul12289_pnr.tcl` (synth → opt → place → route, core
reg-to-reg worst-slack against a 4.0 ns probe):

```
                 rns_add              rns_sub
ROUTED FMAX      242.2 MHz            261.3 MHz
achieved period  4.129 ns             3.827 ns
WNS (core)       -0.129 ns            +0.173 ns
post-route       37 LUT / 31 FF       17 LUT / 31 FF
DSP              0                    0
opt_design       applied              SKIPPED (flake, see ledger)
```

Both land **far above** the heavier lanes on the same part (ntt_mul12289
109.3 MHz, rns108 157.9 MHz) — exactly as expected: a branch-free add/sub is a
single carry chain + one correction, an order of magnitude shorter than Barrett
reduction. (Same I/O transparency note as Phase 4: I/O delay was constrained to
0.0, so the *overall* design WNS is artificially tight; the honest figure is the
**core reg-to-reg** fmax reported here.)

---

## Honesty ledger (negative results & toolchain stay in)

1. **Latency bug, caught and fixed (not by the sim).** First cut gave the valid
   chain 3 registers (`v1,v2,out_valid`) while the datapath had only 2 stages —
   so `out_valid` lagged `out` by one cycle. The functional sim still reported
   **0 mismatches** because it only checks `out` *gated on* `out_valid`, and in
   steady-state streaming the data was aligned; a valid/data skew is invisible to
   it. The bug surfaced as **iverilog latency reading 4, not 2**, and would have
   been caught by formal P2. Fixed by making the valid chain exactly datapath-deep
   (2). Re-sim: latency 2, 0 mismatch; formal P2 then passes. *Lesson logged: the
   functional TB cannot police valid-vs-data alignment — only P2 (or a matched
   latency assertion) can.*

2. **Formal P3 first FAILED on rns_add — but the bug was in the *gold model*, not
   the DUT.** The harness reference computed `(xx+yy) % 14'd12289` with 14-bit
   operands, so `xx+yy` wrapped mod 2¹⁴ *before* the modulo (e.g. 12288+12288 →
   8192 instead of 24576). boolector produced a real counterexample at step 4.
   The DUT was already proven correct by legs 1+2; rns_sub's gold (which used a
   32-bit `integer` intermediate) passed for the same reason. Fixed the add gold
   to accumulate in a 32-bit integer first; re-proof PASSES. *This is the
   empirical-honesty rule working as intended — the solver caught my reference
   error, and the negative result stays recorded.*

3. **oss-cad-suite was not installed at session start.** Legs 3+4 require it
   (yosys/sby/solvers); it was absent on all mounted drives though prior sessions
   used it. Installed fresh: release **2026-06-28** self-extractor →
   `C:\oss-cad-suite`.

4. **Windows `yosys-smtbmc` packaging quirk.** The console-script launcher ships
   double-named `yosys-smtbmc.exe.exe` (+ `yosys-smtbmc.exe-script.py`), so the
   bare `yosys-smtbmc` that sby invokes via cmd doesn't resolve and sby errored
   `COMMAND NOT FOUND`. Fixed with a PATHEXT shim `C:\oss-cad-suite\bin\
   yosys-smtbmc.bat` forwarding to the real launcher (which keeps its own
   `-script.py` lookup intact). *New toolchain quirk for the ledger.*

5. **Vivado 2026.1 `opt_design` flaked on rns_sub** (the known free-mode flake;
   wrapped in `catch`). rns_sub routed on the post-synth netlist — a conservative
   number, and it still beat target and rns_add. Logged as `opt_design = SKIPPED`.

---

## Reproducibility
```
# Leg 1 (Python):
.venv/Scripts/python verify_rns_addsub.py            # -> ALL PASS

# Leg 2 (sim), from Ansh_108_Core_Artifacts with C:\iverilog\bin on PATH:
iverilog -g2012 -o tb_rns_add.vvp rns_add.v tb_rns_add.v && vvp tb_rns_add.vvp
iverilog -g2012 -o tb_rns_sub.vvp rns_sub.v tb_rns_sub.v && vvp tb_rns_sub.vvp

# Legs 3+4 (formal + synth):  run_formal_synth_s2.bat   (sources oss-cad-suite)
#   sby -f rns_add.sby / rns_sub.sby     -> DONE (PASS)
#   yosys synth_rns_add.ys / synth_rns_sub.ys
# (requires the yosys-smtbmc.bat shim above)

# Leg 5 (P&R):  run_pnr_s2.bat            (sources Vivado 2026.1)
#   -> rns_add_out/fmax.txt, rns_sub_out/fmax.txt + utilization/timing rpts
```

### Cross-references
- Plan: `Ansh_108_Core_PathA_Build_Plan.md` (§3 Phase 1, §5 row S2)
- Source of truth: `Ansh_108_Core_Artifacts/golden_model.py` (S1, 17/17)
- Reused cores (not rebuilt): `ntt_mul12289.v` (MUL), `rns108.v` (identity lane)
- Next (S3): `rns_verify.v` + `fold_hash.v`, same 5-leg gate.
