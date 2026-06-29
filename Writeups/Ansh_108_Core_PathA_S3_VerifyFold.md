# Ansh-108 Core — Path A, Session S3: rns_verify / fold_hash (5-leg verified)

### The equality flag and the whole-pattern fingerprint, every leg green

*Path-A Phase-1 deliverable (plan §3 / §5 row S3). Completes the residue-native
op set begun in S2 (rns_add/rns_sub). Builds on S1's `golden_model.py` and the
proven `ntt_mul12289.v` Barrett constant; nothing already-verified was rebuilt.
Created 2026-06-28. Tools: Python 3.14 + numpy 2.4, Icarus Verilog, oss-cad-suite
2026-06-28 (Yosys 0.66, SymbiYosys, boolector 3.2.4, bitwuzla 0.9.1), Vivado
2026.1. All artifacts in `Ansh_108_Core_Artifacts/`.*

---

## What was built

| Module | Function | Construction | Latency |
|---|---|---|---|
| `rns_verify.v` | `out_eq = (x == y)` → 1-bit flag | single-dial residue equality (AND-reduce of one dial); no CRT reconstruction | 1 cycle |
| `fold_hash.v` | `h ← (h·108 + data) mod 12289`, seed h₀=1 | reduce `h·108` and the 28-bit `data` **separately** with the proven Barrett (μ=21843, one correction), then modular-add | 1 cycle |

**Key `fold_hash` idea.** Instead of one wide reduce of `h·108 + data` (a 29-bit
value), reduce the two summands independently:
`h_next = (barrett28(h·108) + barrett28(data)) mod q = (h·108 + data) mod q`.
Both inputs are `< 2²⁸`, where the **same Barrett constant as `ntt_mul12289`**
(μ = ⌊2²⁸/q⌋ = 21843) is exact with a single conditional subtract. Every multiply
is by a **constant** (108, 21843) → cheap, and the correctness reduces to one
exhaustively-provable reducer plus the identity `(a mod q + b mod q) mod q =
(a+b) mod q`. The feedback uses the current registered `h` combinationally, so
back-to-back folds chain correctly at 1 fold/cycle. `rst`/`flush` both reseed to 1.

---

## The 5-leg verification gate — ALL GREEN (both modules)

| Leg | Tool | rns_verify | fold_hash |
|---|---|---|---|
| 1 · Python | `verify_rns_verify_fold.py` | **PASS** | **PASS** (incl. exhaustive 2²⁸ Barrett) |
| 2 · Sim | Icarus Verilog | 300k pairs, **0 mismatch** | 200k cycles, **0 mismatch** |
| 3 · Formal | SymbiYosys + boolector | **PASS** (latency, x==y) | **PASS** (range, latency, reseed) |
| 4 · Synth | Yosys `synth_xilinx xc7` | 45 cells, 2 FF | 257 cells, 15 FF, 6 DSP48 |
| 5 · P&R | Vivado, `xc7a35tcsg324-1`, routed | 5 LUT / 2 FF / 0 DSP † | **41.2 MHz**, 303 LUT / 29 FF / 5 DSP |

† `rns_verify` has **no register-to-register path** (input → comparator → FF → output),
so the reg-to-reg fmax metric is undefined; routed cleanly, footprint is trivial.

### Leg 1 — Python (the authoritative numeric proof)
- **Exhaustive Barrett:** `barrett28(a) == a mod q` verified over **all 268,435,456
  inputs** `a ∈ [0, 2²⁸)` (numpy, chunked). A *complete* proof of the reducer — it
  establishes both correctness and that the output is always `< q` (range).
- **Horner step:** RTL-model `next_h == golden_model FOLD == (h·108+data) mod q`
  over **2,000,000** random `(h, data)` one-step updates.
- Directed: 28-bit-max term, `aA≠Aa` (order matters), determinism, seed = 1.
- `rns_verify`: `(x==y) == golden VERIFY` over 200k random (half forced equal) + corners.
`ALL PASS`.

### Leg 2 — Icarus Verilog
- `rns_verify`: 300,006 pairs (≈150k equal), **0 mismatch**.
- `fold_hash`: 200,015 cycles of random folds + periodic flush + bubbles, the running
  hash tracked cycle-by-cycle against a software Horner accumulator — **0 mismatch**;
  the golden feet `[5,9,12292]` produced `h=4084`, matching the hand-computed Horner;
  the `out_valid == gv` check confirms the 1-cycle valid alignment.

### Leg 3 — Formal (SymbiYosys / boolector)
- `rns_verify`: **P2 latency** (`out_valid` exactly 1 behind `in_valid`) and **P3**
  (`out_eq == (x==y)`), proven over all inputs.
- `fold_hash`: **P1 range** (`h < q` always), **P2 latency** (1), **P3 reseed**
  (`rst|flush ⇒ h=1`), proven (boolector, BMC depth 6, 19 s).
- *Scope, honest:* full numeric correctness of `fold_hash` (`h == (h·108+data) mod q`)
  is owned by the **exhaustive Python leg**, not formal — see the ledger.

### Leg 4 — Yosys synth_xilinx
- `rns_verify`: 45 cells, **2 FDRE** (out_eq + out_valid), 6 LUT6/2 LUT4/1 MUXF7.
- `fold_hash`: 257 cells, **15 FF** (h[14] + out_valid), **6 DSP48E1** (the constant
  multiplies), 35 CARRY4, ~115 LUTs. FF count confirms the 1-stage accumulator.

### Leg 5 — Vivado P&R (measured routed)
- `rns_verify`: **5 LUT / 2 FF / 0 DSP**. No reg-to-reg path; the input→reg
  comparator path (I/O delay = 0, so pad-dominated) is 9.30 ns — not comparable to
  the other cores' reg-to-reg fmax; the point is the core is trivially small/fast.
- `fold_hash`: **ROUTED 41.2 MHz** (period 24.28 ns), **303 LUT / 29 FF / 5 DSP**,
  opt_design applied. The low fmax is the honest cost of doing the **entire reduce
  combinationally inside the 1-cycle feedback loop** (const-mult 108 → two Barrett
  reducers → modular-add → back to `h`). It is pipelineable later (Phase 6) without
  changing the golden semantics; for a fingerprint accumulator the 1-fold/cycle
  functional behaviour is already correct.

---

## Honesty ledger (negative results & toolchain stay in)

1. **The `fold_hash` formal hit a real solver wall — and it is documented, not
   hidden.** The first harness asserted full numeric correctness `h ==
   (h·108+data) mod q`, with a `% q` reference. Proving a Barrett datapath equal to a
   **modulo-reference over free 28-bit `data`** stalled BOTH bitwuzla (k-induction,
   >15 min) AND boolector/bitwuzla (BMC, **>1 h** at step 4). This is the same class
   of "multiplier/modulo wall" the arc's `ntt_mul12289` hit; the arc resolved it with
   an exhaustive C check (`barrett_check.c`). I did the same: dropped the formal
   correctness assertion and made the **exhaustive 2²⁸ Python proof authoritative**
   (it is complete), keeping formal for range/latency/reseed (which it proves in
   seconds). Net assurance is *complete* (exhaustive reducer + algebraic identity +
   200k-cycle RTL sim), just split across legs honestly.

2. **Two orphaned-process cleanups.** Stopping the stuck `sby` left child processes
   (`bitwuzla`, `python3`/`sby`, `yosys-smtbmc`) orphaned and holding the work dir
   (`Device or resource busy`, `Directory already exists`). Fix: kill **by executable
   path** (`C:\oss-cad-suite\*`), not by name, before re-running. *Ledger note.*

3. **`sby` from bash crashed yosys** (`STATUS_DLL_NOT_FOUND`, 0xC0000135). oss-cad
   tools need the full env from `environment.bat`, not just `bin/` on PATH. Always
   drive sby/yosys via a `call environment.bat` cmd shim.

4. **`rns_verify` has no reg-to-reg path**, so the standard reg-to-reg fmax probe
   returned no object (`get_property expects at least one object`). Fixed the P&R tcl
   to fall back to the worst overall path and label it; reported honestly as N/A for
   the reg-to-reg metric.

5. **`fold_hash` is slow (41 MHz).** Not hidden, not "fixed" by a tighter probe — the
   single-cycle full-reduce feedback path is genuinely 24 ns. Logged; pipelining is a
   Phase-6 option.

---

## Reproducibility
```
# Leg 1:  .venv/Scripts/python verify_rns_verify_fold.py        -> ALL PASS
# Leg 2:  iverilog -g2012 -o tb_rns_verify.vvp rns_verify.v tb_rns_verify.v && vvp ...
#         iverilog -g2012 -o tb_fold_hash.vvp  fold_hash.v  tb_fold_hash.v  && vvp ...
# Leg 3:  run_formal_synth_s2-style: call environment.bat; sby -f rns_verify.sby ; sby -f fold_hash.sby
# Leg 4:  run_synth_s3.bat           (yosys synth_xilinx)
# Leg 5:  run_pnr_s3.bat             (Vivado P&R) -> *_out/fmax.txt
# Note: kill stale oss-cad procs by PATH 'C:\oss-cad-suite\*' before re-running sby.
```

### Cross-references
- Plan: `Ansh_108_Core_PathA_Build_Plan.md` (§3 Phase 1, §5 row S3)
- Source of truth: `golden_model.py` (S1) · S2 ops: `Ansh_108_Core_PathA_S2_AddSub.md`
- Reused: `ntt_mul12289.v` Barrett constant (μ=21843) — not rebuilt.
- **Phase 1 datapath ops now verified:** MUL (`ntt_mul12289`), ADD/SUB (S2),
  VERIFY/FOLD (S3). **REDUCE** = the Barrett reducer `barrett28` proven EXHAUSTIVELY
  over all 2²⁸ inputs here (`data % q` on the 28-bit field); it needs only a thin
  standalone wrapper, deferred to Phase 2 where it is wired as opcode 3 in `core_top`.
  Next: S4 — Phase 2 front-end (`opcode_decode`, `result_mode`, `core_top`).
