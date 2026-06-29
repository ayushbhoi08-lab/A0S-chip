# Ansh-108 Core — Path A, Session S4: Phase-2 front-end + integrated `core_top` (5-leg verified)

### The packet decoder, the result FSM, REDUCE, and the whole core wired together — every leg green

*Path-A Phase-2 deliverable (plan §3 Phase 2 / §5 row S4). Wraps the residue
datapath proven in S2/S3 (rns_add/sub, rns_verify, fold_hash) and the already-proven
reused cores (ntt_mul12289 = MUL, rns108 identity lane) behind the 32-bit packet
protocol, and adds the free-running tick counter from the plan's v2 amendment.
Built on S1's `golden_model.py` (source of truth); nothing already-verified was
rebuilt. Created 2026-06-28. Tools: Python 3.14 + numpy 2.4.4, Icarus Verilog,
oss-cad-suite 2026-06-28 (Yosys 0.66, SymbiYosys, boolector 3.2.4), Vivado 2026.1.
All artifacts in `Ansh_108_Core_Artifacts/`.*

---

## What was built

| Module | Role | Construction | Latency |
|---|---|---|---|
| `opcode_decode.v` | packet front-end | `[31:28]`→opcode; hybrid unpack (fast lane `X=data[13:0]`,`Y=data[27:14]`; flexible lane `data[27:0]`); one-hot selects + result-mode class + bindu (op 15) | comb |
| `rns_reduce.v` | REDUCE (op 3) | thin wrapper on the S3-proven `barrett28` (μ=21843, one correction) over the 28-bit foot | 1 cyc |
| `tick_counter.v` | the "Yuga clock" | carry-free RNS counter {256,27,625}=2⁸·3³·5⁴, per-dial inc, period = 4,320,000 = one Maha Yuga; **no data/opcode port** (write-protected by construction) | — |
| `result_mode.v` | adaptable result FSM | busy interlock (single in-flight gated op) + registered hold/strobe + sticky `result_ready` + 1-cycle `bindu` | +1 cyc |
| `core_top.v` | integration | decode + reused datapath + REDUCE + tick + FSM; single clock domain | per-op |

**Protocol.** Assert `in_valid` with a 32-bit pAda. Gated ops
(MUL/ADD/SUB/REDUCE/VERIFY/READ_TICK) are accepted only when `~busy` (single
in-flight; the host awaits `out_valid`/`result_ready` before the next gated op);
FOLD streams 1/cycle (not gated); FLUSH/RESET reseed the fold accumulator (fire-
and-forget), RESET also raises the bindu. The output stage is registered, so each
op's **core latency = its datapath latency + 1**:

| op | MUL | ADD | SUB | REDUCE | VERIFY | READ_TICK | FOLD |
|---|---|---|---|---|---|---|---|
| core latency (cyc) | 5 | 3 | 3 | 2 | 2 | 2 | 2 (throughput 1/cyc) |

**Result bus** `out[22:0]`: arithmetic/REDUCE in `[13:0]`; VERIFY equality in
`bit[0]`; READ_TICK returns the **packed tick residues** `{c0[7:0],c1[4:0],c2[9:0]}`
— the host CRT-recombines them (reconstruction is a positional/magnitude op and
stays host-side, honoring the Path-A fence). The tick residues are also exposed
directly. SEED_FROM_TICK (op 7, "off by default") and reserved opcodes 9–14
(host-side cmp/bitwise) decode to no datapath effect.

---

## The 5-leg verification gate — ALL GREEN

| Leg | Tool | Result |
|---|---|---|
| 1 · Python | `verify_core_top.py` | **ALL PASS** — incl. exhaustive 2²⁸ REDUCE proof + golden program |
| 2 · Sim | Icarus Verilog (`tb_core_top.v`) | **RESULT: PASS**, 0 errors across 5 phases |
| 3 · Formal | SymbiYosys + boolector (`core_top.sby`, 5 tasks) | **5/5 PASS** |
| 4 · Synth | Yosys `synth_xilinx xc7` | 877 cells, 13 DSP48E1, 238 FF, 82 CARRY4, ~368 LUT |
| 5 · P&R | Vivado, `xc7a35tcsg324-1`, routed | **42.1 MHz**, 853 LUT / 190 FF / 8 DSP / 301 slice |

### Leg 1 — Python (golden_model authoritative)
- **REDUCE complete:** `barrett28(a) == a mod q` re-proven EXHAUSTIVELY over all
  **268,435,456** inputs `a∈[0,2²⁸)` (numpy, chunked) — REDUCE (op 3) is that exact
  reducer on the 28-bit field, so its numeric correctness is complete.
- **Golden program:** emitted `core_top_program.txt` = **6000** random packets
  (MUL/ADD/SUB/REDUCE/VERIFY/FOLD), each with its expected result computed by
  `golden_model.execute()`; confirmed stored expected == golden == independent
  arithmetic. (The TB replays this exact file → the RTL is checked against
  `golden_model.py` directly.)
- **Tick:** on-chip residues `(N%256,N%27,N%625)` → host CRT == golden `RnsCounter`
  value across the Maha-Yuga wrap (and a contiguous 0..1999 ramp).
- **FOLD:** burst final hash == golden Horner chain; order-sensitive; deterministic.

### Leg 2 — Icarus Verilog (`tb_core_top.v`, 5 phases, 0 errors)
1. **Per-op latency + value:** MUL=5 (val ✓), ADD=3, SUB=3, REDUCE=2, VERIFY 1/0=2,
   FOLD=2 — every latency and value exact.
2. **READ_TICK:** latency 2; residues in-range and advancing; plus a **continuous
   tick monitor** asserting `t == cyc mod mᵢ` every cycle (tick correct *and*
   write-protected in sim — it never deviates while packets fly).
3. **Golden-program replay:** all **6000** ops issued in order, DUT vs the
   golden-model expected — **0 mismatch**.
4. **FOLD streaming burst:** 64 back-to-back folds → 64 results, **0 gaps (true
   1/cycle)**, final hash == in-TB Horner.
5. **FLUSH/RESET/bindu/no-op:** RESET reseeds the fold accumulator (next fold starts
   from seed); **bindu fires exactly once** per RESET packet; SEED/reserved opcodes
   produce no result.

### Leg 3 — Formal (SymbiYosys / boolector, 5 tasks all PASS)
Control-plane only (no numeric/modulo reference → no solver wall):
- **quiet** — valid-output gating: with no packets, `out_valid`/`bindu`/`busy`/
  `result_ready` never assert (no spurious results).
- **bindu** — `bindu` equals a registered "RESET-packet accepted" → exactly one
  pulse per RESET.
- **tick** — the tick equals an input-independent shadow ramp for **every** packet
  stream → write-protected / "can't lie" (monotonic *cycles*, unspoofable).
- **latmul** — latency exactness for the longest op: `out_valid` is EXACTLY `accept`
  delayed **5** (datapath 4 + 1 output reg), and only then.
- **latfold** — latency exactness for the stream op: `out_valid` is EXACTLY `accept`
  delayed **2**.

### Leg 4 — Yosys `synth_xilinx`
`core_top` incl. submodules: **877 cells**, **13 DSP48E1** (the constant multiplies
in MUL/REDUCE/FOLD), **238 FF** (233 FDRE + 5 FDSE), 82 CARRY4, ~368 LUT, 1 BUFG.
Hierarchy intact (one instance each of the 9 submodules — proof nothing was
duplicated). *(Yosys prints benign "Detected loop … tick_counter" notes from its
alumacc/abc loop-detector on the wrap-compare+increment; the counter is purely
registered — confirmed by the 0-error sim monitor, the formal tick proof, and a
clean Vivado route with no combinational-loop error.)*

### Leg 5 — Vivado P&R (measured routed)
- **ROUTED FMAX = 42.1 MHz** (period 23.736 ns, WNS −15.736 @ 8 ns probe),
  opt_design applied.
- **853 LUT (4.10%) / 190 FF (0.46%) / 8 DSP48E1 / 301 slices (3.69%) / 92 IOB / 1 BUFG.**
- **Critical path = `u_fold/h_reg[4] → u_fold/h_reg[11]`** — i.e. the **fold_hash
  Horner feedback loop**, the *exact* S3 limiter (41.2 MHz). The integration around
  it (decode/mux/control/tick) is **not** on the critical path: the integrated fmax
  (42.1) essentially equals the bare fold lane, NOT a drop. The fast lanes (MUL
  109 MHz, add/sub 240+ MHz) are masked by the single shared clock + the fold
  feedback; pipelining fold (Phase 6) is the path to lift the whole core.

---

## Honesty ledger (negative results & caveats stay in)

1. **fmax is the fold feedback, openly.** 42.1 MHz is the integrated number and it
   is bounded by the single-cycle full-reduce Horner loop inherited from S3, *not*
   by the new front-end. Reported as measured; not massaged by a tighter probe.
   Faster lanes exist but share one clock — the honest integrated figure is the
   slowest reg-to-reg path. Pipelining the fold accumulator is the named Phase-6
   lever; it does not change the golden semantics.
2. **Routed FF (190) < synth FF estimate (238) and DSP (8) < estimate (13).**
   Vivado packs constant multiplies/pipeline regs into the DSP48 slices and trims,
   so the routed footprint is smaller than the Yosys cell estimate. Routed numbers
   are the authoritative ones; the Yosys count is the pre-map estimate.
3. **Full numeric correctness is split across legs, by design** (the S3 precedent):
   a `% q` reference over free wide data is the SMT modulo-wall, so formal here
   proves only control/latency/gating/write-protect; the *numeric* truth is the
   exhaustive Python (REDUCE over all 2²⁸) + the already-proven reused cores
   (ntt full bitwuzla proof; add/sub boolector P3; verify P3) + the 6000-op golden
   replay. Net assurance is complete; it is just honestly partitioned.
4. **READ_TICK is latency/range/monotonic-checked, not absolute-value-replayed.**
   Its value is cycle-dependent, so it is excluded from the offline golden replay;
   its correctness is the continuous `t==cyc mod mᵢ` monitor + the Leg-1 golden CRT
   cross-check + the formal write-protect proof. Honest scope note.
5. **SEED_FROM_TICK is decoded but inert on chip** (the lock says "off by default";
   arbitrary seed-load would require editing the proven fold_hash, which was *not*
   rebuilt). It is reserved-on, no datapath effect — and therefore not exercised
   against golden (which *does* model it). Stated, not hidden.

---

## Reproducibility
```
# Leg 1:  python verify_core_top.py                 -> ALL PASS (+ writes program/burst)
# Leg 2:  iverilog -g2012 -o tb_core_top.vvp core_top.v opcode_decode.v result_mode.v \
#             rns_reduce.v tick_counter.v ntt_mul12289.v rns_add.v rns_sub.v \
#             rns_verify.v fold_hash.v tb_core_top.v && vvp tb_core_top.vvp   -> RESULT: PASS
# Leg 3:  run_formal_s4.bat   (call environment.bat; sby -f core_top.sby)     -> 5x PASS
# Leg 4:  run_synth_s4.bat    (yosys synth_xilinx)   -> core_top_stat.txt
# Leg 5:  run_pnr_s4.bat      (Vivado P&R)           -> core_top_out/fmax.txt
# Note: kill stale oss-cad procs BY PATH 'C:\oss-cad-suite\*' before re-running sby.
```

### Cross-references
- Plan: `Ansh_108_Core_PathA_Build_Plan.md` (§3 Phase 2, §5 row S4, §8 tick amendment)
- Source of truth: `golden_model.py` (S1) · ops: S2 `…_S2_AddSub.md`, S3 `…_S3_VerifyFold.md`
- Reused un-rebuilt: `ntt_mul12289.v` (MUL), `rns_add/sub.v`, `rns_verify.v`,
  `fold_hash.v`, `rns108.v` (identity lane). REDUCE = the S3 `barrett28` reducer.
- **Phase 2 DONE:** decode + result FSM + REDUCE wrapper + integrated `core_top`,
  all 5 legs green, routed on `xc7a35t`. Next: **S5** = focused formal + P&R
  characterization sign-off of `core_top` (plan row S5), then the host track
  (S6 parser/slicer/assembler) which is independent and can run in parallel.
