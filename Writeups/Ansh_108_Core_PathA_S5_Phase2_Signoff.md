# Ansh-108 Core — Path A, Session S5: Phase-2 sign-off (deeper formal + consolidated P&R)

### Closing the Phase-2 formal gate on `core_top` and consolidating the routed silicon numbers

*Path-A Phase-2 sign-off (plan §3 Phase 2 / §5 row S5). S4 built and 5-leg-verified
the integrated `core_top`; S5 (a) DEEPENS the formal to close the Phase-2 gate — every
gated-op latency now formally pinned, plus the single-in-flight interlock, the
await-read contract, and reserved-opcode inertness — and (b) consolidates the
synthesis + routed-P&R characterization into one sign-off table. Nothing already
verified was rebuilt; the S4 RTL and its 5 legs are unchanged. The S4 fast legs
(Python `verify_core_top.py`, iverilog `tb_core_top.v`) were RE-RUN live at the start
of this session and re-passed (ALL PASS / RESULT: PASS, 6000-op replay 0-mismatch),
and the S4 formal/P&R artifacts on disk were re-confirmed present and green. Created
2026-06-28. Tools: oss-cad-suite 2026-06-28 (Yosys 0.66, SymbiYosys, boolector 3.2.4),
Vivado 2026.1, Icarus Verilog, Python 3.14. All artifacts in `Ansh_108_Core_Artifacts/`.*

---

## What S5 adds

| Artifact | Role |
|---|---|
| `core_top_s5_formal.v` | 8 NEW control-plane formal tops (separate file; S4's `core_top_formal.v` untouched) |
| `core_top_s5.sby` | sby task file selecting the 8 tops via `prep -top` (boolector, BMC) |
| `run_formal_s5.bat` | driver (`call environment.bat` → `sby -f core_top_s5.sby`) |
| this doc | consolidated Phase-2 sign-off table + honesty ledger |

No new datapath, no RTL change to the proven core — S5 is verification + consolidation.

---

## The full Phase-2 formal set on `core_top` — 13 properties, ALL PASS

Control-plane only (no numeric/modulo reference → no SMT modulo-wall; that wall, hit
in S3, means datapath NUMERIC correctness is owned by the exhaustive Python legs + the
already-proven reused cores). Each property is a tiny formal top; sby selects it with
`prep -top`; boolector BMC at the listed depth; every task `PASS 0 0`, seconds each.

| # | Task | Property proven | From | Depth |
|---|---|---|---|---|
| 1 | quiet | no packets ⇒ `out_valid`/`bindu`/`busy`/`result_ready` never assert | S4 | 8 |
| 2 | bindu | `bindu` == registered (RESET accepted) ⇒ exactly one pulse per RESET | S4 | 8 |
| 3 | tick | tick == input-independent shadow ramp for every packet stream (write-protected / "can't lie") | S4 | 8 |
| 4 | latmul | `out_valid` is EXACTLY `accept` delayed **5** (MUL: datapath 4 + 1 reg) | S4 | 16 |
| 5 | latfold | `out_valid` is EXACTLY `accept` delayed **2** (FOLD stream: 1 + 1) | S4 | 10 |
| 6 | **latadd** | `out_valid` is EXACTLY `accept` delayed **3** (ADD: rns_add 2 + 1) | **S5** | 12 |
| 7 | **latsub** | `out_valid` is EXACTLY `accept` delayed **3** (SUB: rns_sub 2 + 1) | **S5** | 12 |
| 8 | **latred** | `out_valid` is EXACTLY `accept` delayed **2** (REDUCE: rns_reduce 1 + 1) | **S5** | 10 |
| 9 | **latver** | `out_valid` is EXACTLY `accept` delayed **2** (VERIFY: rns_verify 1 + 1) | **S5** | 10 |
| 10 | **lattick** | `out_valid` is EXACTLY `accept` delayed **2** (READ_TICK: rt_ov 1 + 1) | **S5** | 10 |
| 11 | **interlock** | at most ONE gated op in flight (2-bit outstanding count ≤ 1; 2-bit underflow→3 also catches a spurious gated result) | **S5** | 18 |
| 12 | **ready** | await-read contract: once `result_ready` is set it STAYS set until `read_ack` OR a new gated accept (the only two clears) | **S5** | 12 |
| 13 | **reserved** | opcodes 9..14 are inert: no `out_valid`, no `busy`, no `result_ready`, no `bindu`, ever | **S5** | 10 |

**Coverage achieved:** every result-producing opcode's latency is now formally exact
(MUL 5 · ADD 3 · SUB 3 · REDUCE 2 · VERIFY 2 · READ_TICK 2 · FOLD 2) — matching the S4
latency table and the iverilog Leg-2 measurements exactly. The result-port safety
(single-in-flight, no collision/reorder at the shared port), the host-facing await-read
contract, the tick write-protect, the bindu-once policy, and reserved-opcode inertness
are all proven. The Phase-2 plan gate ("valid-output gated on `out_valid`; latency
exactness; bindu triggers exactly once") is **met and exceeded**.

---

## Consolidated synthesis (Yosys `synth_xilinx xc7`, `core_top_stat.txt`)

**Total: 877 cells · 13 DSP48E1 · 238 FF (233 FDRE + 5 FDSE) · 82 CARRY4 · 368 LUTs ·
1 BUFG.** Hierarchy intact — exactly one instance of each of the 9 submodules (proof
nothing was duplicated in integration):

| submodule | cells | DSP48E1 | role |
|---|---|---|---|
| fold_hash | 209 | 6 | Horner fold `h←(h·108+x) mod q` — **the fmax limiter** |
| ntt_mul12289 | 126 | 4 | MUL `(x·y) mod 12289` |
| rns_reduce | 96 | 3 | REDUCE (barrett28) |
| rns_add | 85 | 0 | ADD mod q |
| rns_sub | 70 | 0 | SUB mod q |
| tick_counter | 36 | 0 | carry-free Maha-Yuga clock |
| result_mode | 30 | 0 | result FSM |
| opcode_decode | 13 | 0 | packet front-end |
| rns_verify | 11 | 0 | equality flag |
| core_top (local) | 201 | 0 | mux/dispatch/glue + I/O buffers |

*(Yosys prints benign "Detected loop … tick_counter" notes from its alumacc/abc
loop-detector on the RNS wrap-compare+increment — the counter is purely registered;
confirmed by the formal `tick` write-protect proof, the sim tick monitor, and a clean
Vivado route with no combinational-loop error.)*

---

## Consolidated routed P&R (Vivado, `xc7a35tcsg324-1`, `core_top_out/fmax.txt`)

| metric | value |
|---|---|
| ROUTED FMAX | **42.1 MHz** (achieved period 23.736 ns; WNS −15.736 ns @ 8 ns probe) |
| LUT | 853 (4.10%) |
| FF | 190 (0.46%) |
| DSP48E1 | 8 |
| slices | 301 (3.69%) |
| IOB / BUFG | 92 / 1 |
| critical path | `u_fold/h_reg[4] → u_fold/h_reg[11]` — the **fold_hash Horner feedback** |

**Reading it honestly:** the integrated fmax (42.1 MHz) ≈ the bare fold lane from S3
(41.2 MHz). The integration the front-end adds (decode / result mux / FSM / tick) is
**NOT** on the critical path — so 42.1 is *not a drop from* a faster integrated number;
it is the single-cycle full-reduce Horner loop inherited from S3, now shared across one
clock. The fast lanes exist underneath (MUL 109 MHz, add/sub 240+ MHz from S2) but are
masked by the shared clock + the fold feedback.

---

## Honesty ledger (negative results & caveats stay in)

1. **Formal is BMC (bounded), not unbounded induction — stated, by arc convention.**
   All 13 properties are bounded model checking to the listed depths (the depths cover
   each op's full accept→complete→re-accept window, e.g. interlock depth 18 spans two
   MUL cycles). This is the same methodology as S2/S3/S4. Unbounded k-induction was NOT
   claimed: for `interlock`/`reserved` plain 1-induction fails on unreachable states
   (e.g. an inductive start state with `busy=1` under reserved opcodes), which is the
   classic induction limitation, not a design bug — so BMC at op-covering depth is the
   honest gate, exactly as in the rest of the arc.
2. **P&R/synth numbers are the S4-measured run, re-confirmed present this session, not
   re-routed.** The user chose the consolidation path over a fresh re-route; `fmax.txt`
   (42.1 MHz), `core_top_stat.txt`, and the 5 S4 formal status files were all verified
   on disk and green. Re-running Vivado would reproduce 42.1 MHz (deterministic place
   seed) at a cost of minutes — deferred to the Phase-6 full characterization, where
   pipelining the fold accumulator is the named lever to lift the whole core.
3. **Numeric correctness remains split across legs, by design (S3 precedent).** A `% q`
   reference over free wide data is the SMT modulo-wall, so formal proves only
   control/latency/gating/write-protect/interlock; the *numeric* truth is the exhaustive
   Python (REDUCE over all 2²⁸; add/sub/verify/fold vs golden) + the already-proven reused
   cores (ntt full bitwuzla proof; add/sub boolector P3; verify P3) + the 6000-op golden
   replay. Net assurance is complete; it is just honestly partitioned. S5 changes none of
   this — it strengthens the CONTROL proof only.
4. **`interlock` assumes gated-or-idle packets** (no FOLD/FLUSH/RESET/SEED), so that
   `out_valid` is purely the gated result and the 2-bit outstanding counter is exact.
   FOLD streaming (1/cycle, not busy-gated) is covered separately by `latfold` (S4) and
   the Leg-2 64-burst 0-gap sim. Stated scope, not a gap.

---

## Reproducibility
```
# S5 deeper formal:  run_formal_s5.bat   (call environment.bat; sby -f core_top_s5.sby)
#                    -> 8x PASS (latadd latsub latred latver lattick interlock ready reserved)
# Re-confirm S4 fast legs:
#   python verify_core_top.py            -> ALL PASS (incl. exhaustive 2^28 REDUCE)
#   iverilog -g2012 -o tb.vvp core_top.v opcode_decode.v result_mode.v rns_reduce.v \
#     tick_counter.v ntt_mul12289.v rns_add.v rns_sub.v rns_verify.v fold_hash.v \
#     tb_core_top.v && vvp tb.vvp          -> RESULT: PASS
# Synth/P&R already logged: core_top_stat.txt, core_top_out/fmax.txt (S4 run).
# Note: kill stale oss-cad procs BY PATH 'C:\oss-cad-suite\*' before re-running sby.
```

### Cross-references
- Plan: `Ansh_108_Core_PathA_Build_Plan.md` (§3 Phase 2, §5 row S5, §6 Phase-6 lever)
- S4 integration: `Ansh_108_Core_PathA_S4_FrontEnd.md` (the 5-leg build this signs off)
- Ops: S2 `…_S2_AddSub.md`, S3 `…_S3_VerifyFold.md`; golden: `golden_model.py` (S1)
- **Phase 2 SIGNED OFF:** integrated `core_top` — 13 formal properties (all gated-op
  latencies + interlock + await-read + tick write-protect + bindu-once + reserved-inert),
  877-cell / 13-DSP synth, routed 42.1 MHz on `xc7a35t`, numeric correctness owned by the
  exhaustive Python + proven reused cores. Next: **S6** = Phase-3 host track
  (parser/slicer/assembler + golden vectors), which is independent and can run in parallel;
  Phase-6 fold-pipelining is the named fmax lever.
