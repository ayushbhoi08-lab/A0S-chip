# Ansh-108 Core — Path A Build Plan (Pure Residue Chip + ASTa-Dik as Grammar Layer)

**Status:** PLAN ONLY — nothing built. Created for multi-session execution.
**v2 (this revision):** adds a continuous free-running **time counter** (the
"never-stopping Yuga clock" idea) — see **§8 Amendment**. It is additive and does
NOT change the Path-A fence.
**Decision locked:** Path A = pure residue datapath on silicon; positional ops
(shift / bitwise / magnitude-compare) live on the host or in the assembly-grammar
geometry layer, never welded onto the residue datapath.
**Standing rule (per [[feedback_empirical_verification]]):** every claim is
measured or proven, negative results reported honestly, no number is a hope.

---

## 0. What Path A IS (scope fence)

**On the chip (back chamber, FPGA) — RESIDUE-NATIVE ONLY:**
- `× mod q`  (the proven heartbeat)
- `+ mod q`, `− mod q`  (branch-free in RNS)
- `mod-reduce`  (the core's own reduction)
- `VERIFY` = equality test `a == b`  (cheap in residue form: equal iff all dials equal)
- `FOLD` = whole-pattern fingerprint via polynomial/Horner hash (uses native × and +)
- Control/plumbing: `FLUSH`, `RESET` (no arithmetic)

**OFF the chip (host / staging agent), because they need positional binary form:**
- Shifts, rotations, bit-reversal, swaps (the aSTa-dik)
- Bitwise AND / OR / XOR
- Magnitude compare (`a > b?` — needs full CRT reconstruction = the branch we kill)

**The aSTa-dik survives as a naming + geometry layer in the A0S assembly grammar**
(how data is addressed/arranged), mirroring the project's locked principle:
*Sanskrit is the soul, the silicon body stays universal.*

---

## 1. What ALREADY EXISTS (do NOT rebuild — verified in the arc)

| Artifact | What it is | Verified status |
|---|---|---|
| `ntt_mul12289.v` | `(x·y) mod 12289`, Barrett, 14-bit operands, 4-stage | sim 3M pairs 0-miss; **bitwuzla full-correctness proof**; routed **109.3 MHz**, 178 LUT/2 DSP |
| `rns108.v` | `(x·y) mod 108` = Z/4×Z/27, CRT branch-free | sim 11,664/0; SMT 3 theorems; routed **157.9 MHz**, 51 cells |
| `rns41580.v` (+`p`,`g`) | 5-dial Z/41580 scaling | sim 300k/0; boolector formal; routed 118.7 / 153.6 MHz |
| `gen_rns.py` | generator for d2..d5 cores | curve measured |
| `cpu_bench.c`, `barrett_check.c`, `verify_crt*.py` | CPU baseline + exhaustive checks | measured |

**Consequence:** Phase 1 below *extends* this proven base; it does not start from zero.

---

## 2. DECISIONS TO LOCK before any code (my recommended defaults in **bold**)

These are the only things that can stall a session mid-build. Read and confirm/override.

1. **✅ LOCKED (2026-06-28): Primary execution/data lane = the `mod 12289` core.**
   Rationale: strongest proof (bitwuzla full correctness), 14-bit values give
   *meaningful* fingerprints, and it is the real crypto primitive (Kyber/Dilithium
   NTT). `rns108` stays as the **namesake/identity demonstrator** lane.
   Consequence: packet fast-lane fields are sized for 14-bit operands (`[13:0] X |
   [27:14] Y`), and the FOLD fingerprint is computed mod 12289.

2. **Packet = 32-bit pAda, `[31:28]` opcode + `[27:0]` data.**
   - Fast lane (arith): `[13:0] X | [27:14] Y` — exact fit for q=12289.
   - 108 lane reuses the same field (values just occupy 7 of 14 bits).

3. **✅ LOCKED (2026-06-28): FOLD = Horner/polynomial hash** `h ← (h·B + pAda) mod 12289`.
   Uses native × **and** +, residue-pure, no zero-collapse.
   - **Base `B` = 108** (coprime to 12289; the chip's own number).
   - **Seed `h₀` = 1** (blank-wax start; Horner form can't collapse to zero).
   - **Width = single chain (0–12288, ~14-bit) for Phase 1**, but `fold_hash.v` is
     **parameterized** so N parallel chains (distinct B, h₀) can be instantiated later
     for a longer fingerprint without redesign.

4. **✅ LOCKED (2026-06-28): on-chip opcode set** (integrates the counter ops from §8):
   `0 MUL · 1 ADD · 2 SUB · 3 REDUCE · 4 FOLD(hash) · 5 VERIFY(eq) ·
   6 READ_TICK · 7 SEED_FROM_TICK (optional, off by default) · 8 FLUSH · 15 RESET`.
   Slot **9 (magnitude-compare)** and **10–14 (bitwise/shift)** are **host-side in
   Path A** and left reserved on-chip. Load/store deferred (no on-chip memory in Path A).

5. **Scope of this session-arc = full simulation + synth + P&R + formal.**
   Physical FPGA bring-up is Phase 7, aligned to the January board timeline — it is
   the honest frontier and is planned but gated separately.

---

## 3. BUILD PHASES (each phase = deliverables → verification gate → done-criteria)

### Phase 1 — Residue datapath extensions (FPGA back chamber)
Build the missing native ops on top of the proven cores.

**Deliverables (Verilog):**
- `rns_add.v`, `rns_sub.v` — per-dial add/sub then mod, branch-free.
- `rns_verify.v` — per-dial equality → AND-reduce → 1-bit equal flag.
- `fold_hash.v` — Horner fold `h ← (h·B + x) mod q`, registered accumulator, seed load.
- Reuse `ntt_mul12289.v` (MUL), `rns108.v` (identity lane).

**Verification gate (the standing 5 legs, per op):**
1. Python exhaustive/large cross-check (`verify_*.py`).
2. iverilog sim, ≥200k random pairs, 0 mismatch, latency asserted.
3. SymbiYosys formal — P1 range, P2 latency, P3 per-dial correctness; **bitwuzla**
   for any wide-multiply spec (it cleared the 14×14 wall boolector couldn't).
4. Yosys `synth_xilinx xc7` resource estimate.
5. Vivado P&R on `xc7a35tcsg324-1`, opt-applied, routed fmax recorded.

**Done when:** every op has all 5 legs green, numbers logged in a results table,
caveats written.

---

### Phase 2 — On-chip front-end (decoder + result FSM)
Wrap the datapath so it speaks the packet protocol.

**Deliverables:**
- `opcode_decode.v` — `[31:28]` → op select; hybrid unpack (fast lane fixed
  two-halves; flexible lane opcode-dependent — but in Path A only FOLD/VERIFY/FLUSH
  use flexible, so this stays small).
- `result_mode.v` — adaptable result FSM (reduced):
  - Critical (MUL/ADD/SUB/REDUCE): hold result, valid flag set, await read.
  - Stream (FOLD): push result on completion.
  - Verify (VERIFY): hold 1-bit pass/fail, await query.
  - Fire-and-forget (FLUSH/RESET): no result.
- `bindu_exit.v` (or handled in FSM) — recognize the bindu control packet
  (opcode 15 / zero data) → "sequence complete, apply final result policy."
- `core_top.v` — integrates decode + datapath + result FSM; single clock domain.

**Verification gate:** sim with directed packet streams (each opcode, plus a
multi-pAda sequence ending in bindu); formal on the FSM (valid-output range gated on
`out_valid`; latency exactness; bindu triggers exactly once). Synth + P&R of
`core_top`.

**Done when:** `core_top` passes directed + randomized packet streams, formal FSM
properties hold, routed fmax of the *integrated* core recorded (expect a small drop
vs bare datapath — log it honestly).

---

### Phase 3 — Staging agent (host PC software, the front chamber)
The FPGA is "blind"; the host owns timing, LEDs, files, and positional ops.

**Deliverables (host, language TBD — recommend Python first, then C for the USB path):**
- `parser` — read `.txt` of `a/A`, strip non-`a/A`, map `a→0 / A→1`.
- `slicer` — pack bitstream into 32-bit pAdas; zero-pad final pAda with zUnya;
  set final-pAda flag.
- `assembler` — build packets: opcode + hybrid data layout; inject bindu exit.
- `clock/led` — 50 ms (Laghu) / 100 ms (Guru) forward-modeled ISI; HOLD/COMPILE/
  3 s-warning/EXECUTE/FLUSH/ERROR state + LED color map (locked table).
- `usb_stream` — send complete packets only (packet buffering = collision-proof);
  read results per result-mode contract.
- `host_ops` — the **positional fallbacks**: shift/rotate/reverse (aSTa-dik),
  AND/OR/XOR, magnitude-compare — done in software, results optionally re-fed to chip.

**Verification gate:** unit tests on parser/slicer/assembler (golden vectors);
loopback test against the Phase 5 co-sim (below) before any real USB.

**Done when:** host can turn a `.txt` file into the exact packet stream a known-good
core consumes, and correctly interprets every result mode, in pure software loopback.

---

### Phase 4 — A0S Assembly grammar + ASTa-Dik geometry layer
The human-facing language; cosmology lives here, not in silicon.

**Deliverables:**
- `A0S_Assembly_Spec.md` — formal syntax for `.txt` programs: `a/A` data, `.`
  terminate, `..` early bindu, `Enter` hold, digit (1–9) Sanskrit control layer
  (eka…nava), comments, file structure.
- **ASTa-dik layer:** the 8 directions defined as *addressing / arrangement*
  operators in the grammar (how a block is laid out / traversed), each mapped to a
  host-side transform — NOT an on-chip opcode. Document the 8 names + meanings +
  the host transform each invokes. Correct the Sanskrit (per the audit:
  XOR→bheda, shift-L→vAma, shift-R→dakSiNa, etc.).
- Reference grammar test programs (small `.txt` files exercising each construct).

**Verification gate:** the Phase 3 parser accepts every reference program and emits
the expected packet/host-op stream; grammar is unambiguous (no construct parses two ways).

**Done when:** spec is complete, reference programs round-trip through the host
parser, Sanskrit names are verified correct.

---

### Phase 5 — End-to-end integration (simulation)
Tie host ↔ core without hardware.

**Deliverables:**
- Co-sim harness: host emits packet stream → drives `core_top` testbench → captures
  results → host verifies against a pure-software golden model of the whole pipeline.
- Golden reference model (Python) of the entire Path-A semantics (incl. fold hash,
  verify, host positional ops).

**Verification gate:** a battery of full programs (live-mode and file-mode, single-
and multi-pAda, every opcode, bindu and `..` early-exit) all match the golden model,
0 mismatch.

**Done when:** the whole chain — file → parse → slice → packet → core → result →
host interpretation — is bit-exact against the golden model across the test battery.

---

### Phase 6 — Full-core synthesis / P&R / formal (honest silicon numbers)
Characterize the integrated Path-A core as a real chip target.

**Deliverables:** Yosys synth + Vivado P&R of `core_top` on `xc7a35t`; replication
estimate (cores per device, DSP/LUT-bound); SymbiYosys formal pass on the integrated
control + datapath; consolidated results table; honesty ledger.

**Verification gate:** routed fmax, footprint, latency, throughput, replication count
all recorded; formal properties green; every limitation written down.

**Done when:** there is a single results doc with measured numbers + proofs + caveats,
in the same format as the rest of the arc.

---

### Phase 7 — Physical FPGA bring-up (the frontier; January-aligned)
The first time it leaves simulation. Planned, gated separately.

**Deliverables:** target board (Cmod A7 / Arty A7 / equiv), constraints/pinout (`.xdc`),
USB bridge bring-up (UART/FTDI first; FT2232H/FX3 only if memory-mapped is needed),
LED wiring, on-board smoke test (known vectors), then the host staging agent over real USB.

**Verification gate:** on-hardware results match the golden model on the test battery;
LED states observed; timing closure on the real part.

**Done when:** a real board runs a real `.txt` program end-to-end and matches sim.
*(Honest note: this is the current frontier — everything before it is pre-silicon
validation, exactly how chips are signed off before fab.)*

---

## 4. Cross-cutting standards (apply to every phase)

- **5-leg verification** (Python check · iverilog · SymbiYosys/bitwuzla · Yosys ·
  Vivado P&R) for anything that becomes hardware.
- **Honesty ledger** per phase: what passed, what was skipped, what flaked, what's
  estimated vs measured. Negative results stay in.
- **Artifact home:** all source + outputs persisted into `Ansh_108_Core_Artifacts/`;
  each phase gets a `Ansh_108_Core_*.md` writeup like the existing arc.
- **Toolchain quirks already known:** Vivado free-mode + `.bat` needs `call` in loops
  (keep `XILINXD_LICENSE_FILE` UNSET for WebPACK); oss-cad-suite PATH (now reinstalled at
  `C:\oss-cad-suite`, 2026-06-28 build, source `environment.bat`); `sby` reports
  status-not-narrative; **bitwuzla > boolector on multipliers** (boolector is fine/fast
  for non-multiply ops like add/sub/verify). **NEW (S2):** on Windows, sby's `yosys-smtbmc`
  ships double-named `yosys-smtbmc.exe.exe` (+`.exe-script.py`) → bare command unresolved →
  add shim `C:\oss-cad-suite\bin\yosys-smtbmc.bat` forwarding to it. Also: the functional
  TB cannot police valid-vs-data alignment — rely on formal **P2 latency** for that.
  **NEW (S3):** (a) a `% q` modulo-REFERENCE in a formal gold over free wide data is an
  SMT wall (stalls boolector AND bitwuzla, induction or BMC) — prove full numeric
  correctness EXHAUSTIVELY (Python/C) per the ntt precedent; keep formal for
  range/latency/control. (b) Always drive `sby`/`yosys` via `call environment.bat`
  (bash-PATH-only crashes yosys: STATUS_DLL_NOT_FOUND). (c) Kill stale oss-cad procs
  BY PATH `C:\oss-cad-suite\*`, not by name — TaskStop orphans children that hold the
  sby workdir (`Device or resource busy`).
  **NEW (S4):** (a) multi-property formal is cleanest as several tiny formal TOP modules
  in one `_formal.v` selected by sby `[tasks]` + per-task `prep -top ctf_<name>` (no
  parameters/generate needed); all 5 boolector tasks finish in seconds since they are
  control-plane only (no modulo reference). (b) Yosys `synth_xilinx` prints benign
  "Detected loop … tick_counter" notes from its alumacc/abc loop-detector on the RNS
  wrap-compare+increment — NOT a real comb loop (purely registered); confirmed by the
  0-error sim tick-monitor, the formal write-protect proof, and a clean Vivado route.
  (c) Integrated `core_top` routed fmax is bounded by the **fold_hash Horner feedback**
  (the S3 limiter), not the new front-end — pipelining fold is the Phase-6 lever.
  **NEW (S5):** (a) the "tiny formal top per property" pattern scales — 8 more tops in a
  SEPARATE `core_top_s5_formal.v` (S4's file left untouched) + a second `.sby`, all
  boolector BMC, finish in ~4–5 s. (b) For latency-exactness over a busy-gated op, the
  S4 `ctf_latmul` trick generalizes to any latency L: a length-L accept-shift register
  + `assert(out_valid==a_L)` works because `accept = in_valid & ~busy` is self-spacing
  (busy masks re-accept during the op). (c) Single-in-flight is provable with ONE 2-bit
  shadow counter (+1 accept / −1 out_valid, `assert ≤1`): the same assertion catches a
  spurious result via 2-bit underflow wrapping to 3 — no separate "no-spurious" property
  needed. (d) `mode prove` (unbounded k-induction) is NOT usable for these: 1-induction
  picks unreachable start states (e.g. `busy=1` under reserved opcodes) and fails — the
  classic induction CTI limitation, not a bug; BMC at op-covering depth is the honest gate
  (and matches the whole arc). Driver: `run_formal_s5.bat`.
  **NEW (S7, host-side / pure-Python):** (a) the plan's "locked LED colour map" had
  never actually been written — **S7 locks it** (HOLD=BLUE, COMPILE=AMBER,
  WARNING_3S=ORANGE, EXECUTE=GREEN, FLUSH=WHITE, ERROR=RED) in `clock_led.py`; it is an
  engineering decision, not a measurement. (b) The aSTa-dik direction NAMES in
  `host_ops.ASHTA_DIK` are PROVISIONAL — only vAma/dakSiNa/bheda are audit-confirmed
  (plan §4); **S8 finalizes the Sanskrit**, host_ops only owns the transforms. (c)
  `SpiralHeightTracker` (residue-stream → absolute linear count) has a **Nyquist bound**:
  it only catches a wrap if successive samples are < one period `M` apart — a full-period
  jump is invisible (tested + documented). (d) READ_TICK keeps the Path-A fence: the
  core returns RAW residues, the HOST reconstructs (CRT == Garner mixed-radix == Python).
  (e) The read-before-bindu rule is made REAL in the loopback model (the fold mirror
  reseeds on FLUSH/RESET exactly like `fold_hash`), so reading the fingerprint late
  yields the seed — a negative result the test asserts. Gate: `test_s7_staging_agent.py`.
  **NEW (S8, host-side / grammar — no FPGA):** (a) UNAMBIGUITY is cheapest to both
  guarantee AND prove when the lexer is driven by **disjoint leading-character
  classes** (letters / `.` / `0` / `1-9` / `@` / `^` / newline / ws / `#`) — the
  first char fixes the token kind, so the only proof obligations are the two
  maximal-munch tokens (dot-run, sigil+digit); the gate confirms it with a
  **canonical re-lex fixed point** (serialize tokens → re-tokenize == identity).
  (b) The true aSTa-dik is the **8 compass directions as 2-D grid permutations**, NOT
  the 1-D bitwise/shift ops S7 provisionally named `ASHTA_DIK` (now `POSITIONAL_OPS`);
  `dakSiNa`=South is a grid roll, not shift-right. (c) `gcd(9,12)=3` means a +1+1
  diagonal *roll* splits into 3 loops — so diagonals use the **zig-zag SCAN** (proven
  a full 108-permutation) for corner-to-corner coverage; the ROLL itself stays a clean
  toroidal shift (still reversible). (d) "8 distinct fingerprints" is a **measured**
  claim: asymmetric/random patterns hit 8/8, but symmetric patterns collide along
  their symmetry axis (uniform 1/8, col-stripes 2/8 ROLL — logged, never assumed).
  (e) Keep the geometry STRICTLY ADDITIVE: a maNDala with no `@`/`^` folds the raw
  bitstream byte-identically to S6, so the 5016-chant equivalence still holds and the
  fence is provable, not asserted. Gate: `test_s8_a0s_grammar.py`.
  **NEW (S9, host↔RTL co-sim — iverilog, no FPGA):** (a) the cleanest co-sim split
  is a tiny **3-file** seam: a Python driver emits a flat `<pid> <rec> <pkt_hex>`
  vector file + a golden sidecar, a `-g2012` TB reads it and drives the real
  `core_top`, a Python comparator diffs RTL-out vs golden — the driver/comparator
  *import* the proven host modules (assert `__module__`, never copy). (b) The TB
  emits a program's per-op `O` lines as they run but its `P` summary at program
  CLOSE, so `O` precedes `P` → the comparator's RTL parser must be order-tolerant
  (`setdefault`/merge, never overwrite). (c) Read-before-bindu is realized robustly
  by capturing all FOLD `out_valid`s BEFORE firing the segment's RESET — and it is
  *safe* because `fold_hash` gates `out_valid <= fold_en & ~flush`, so a RESET one
  cycle after the last FOLD reseeds `h` but cannot clobber the already-registered
  result. (d) A free-running clock has no host-predictable absolute value: prove
  READ_TICK by the continuous monitor (`tick==cyc%m_i`) for correctness +
  write-protect, and check the READ_TICK *path* by range + host-CRT reconstruction
  (host_ops==golden CRT==Garner) + monotonic advance — never a baked constant.
  (e) Multi-maNDala fingerprint = the **last committed** maNDala's pre-bindu fold
  (aborted `..` contribute only a bindu); apply the identical rule in BOTH the RTL
  TB and the golden walk so they agree. Driver: `run_cosim_s9.bat`.

---

## 5. Session sequencing (suggested, with dependencies)

| Session | Focus | Depends on | Exit artifact |
|---|---|---|---|
| ✅ S1 | **Lock §2 decisions** + write golden Python model skeleton | — | **DONE 2026-06-28:** §2 locked; `Ansh_108_Core_Artifacts/golden_model.py` — 17/17 self-tests PASS (incl. exhaustive CRT bijection over all 4,320,000 counter states + all 11,664 rns108 pairs) |
| ✅ S2 | Phase 1: `rns_add`/`rns_sub` + 5-leg | S1 | **DONE 2026-06-28:** `rns_add.v`/`rns_sub.v` — all 5 legs green (Python exhaustive+2M vs golden; iverilog 300k/0, lat 2; SymbiYosys/boolector BMC-12 P1·P2·P3 PASS; Yosys synth 37/17 LUT, 31 FF, 0 DSP; Vivado routed **242.2 / 261.3 MHz**). Writeup: `Ansh_108_Core_PathA_S2_AddSub.md` |
| ✅ S3 | Phase 1: `rns_verify` + `fold_hash` + 5-leg | S2 | **DONE 2026-06-28:** `rns_verify.v` (x==y flag, lat 1) + `fold_hash.v` (Horner h←(h·108+data) mod q, lat 1, two-Barrett reduce) — all 5 legs green (Python incl. **exhaustive 2²⁸ Barrett** + 2M vs golden; iverilog 0-mismatch; boolector formal range/latency/reseed/eq; Yosys 45-cell / 257-cell+6 DSP; Vivado verify 5 LUT/2 FF, fold routed **41.2 MHz**). Formal full-correctness of fold hit the modulo-reference SMT wall → owned by exhaustive Python (arc precedent). REDUCE = the proven `barrett28`, thin wrapper deferred to Phase 2. Writeup: `Ansh_108_Core_PathA_S3_VerifyFold.md` |
| ✅ S4 | Phase 2: `opcode_decode` + `result_mode` + `core_top` | S3 | **DONE 2026-06-28:** `opcode_decode.v` (hybrid unpack + one-hot selects + result-mode class + bindu) · `rns_reduce.v` (REDUCE = thin wrapper on the S3-proven `barrett28`) · `tick_counter.v` (carry-free RNS {256,27,625} Maha-Yuga clock, no opcode port → write-protected) · `result_mode.v` (busy-interlock result FSM, registered hold/strobe, 1-cycle bindu) · `core_top.v` (decode + REUSED datapath ntt/add/sub/verify/fold + tick + FSM, single clock). Core latency = datapath+1 (MUL 5, ADD/SUB 3, REDUCE/VERIFY/READ_TICK 2, FOLD 2 @1/cyc). ALL 5 legs green: Python incl. **exhaustive 2²⁸ REDUCE** + 6000-op golden program; iverilog **6000-op golden replay 0-mismatch** + per-op latency/value + FOLD 1/cycle burst + bindu-once + tick monitor; SymbiYosys/boolector **5/5** (quiet valid-gating · bindu-once · tick write-protect · MUL & FOLD latency exactness); Yosys 877 cell/13 DSP/238 FF; Vivado routed **42.1 MHz** (853 LUT/190 FF/8 DSP/301 slice), critical path = the fold_hash Horner feedback (S3 limiter; integration adds ~nothing). Writeup: `Ansh_108_Core_PathA_S4_FrontEnd.md` |
| ✅ S5 | Phase 2: formal + P&R of `core_top` | S4 | **DONE 2026-06-28: Phase 2 SIGNED OFF.** Deeper formal CLOSES the gate — `core_top_s5_formal.v` adds **8** new control-plane boolector tasks (all `PASS 0 0`): `latadd/latsub/latred/latver/lattick` (every remaining gated-op latency now exact: ADD/SUB 3, REDUCE/VERIFY/READ_TICK 2 — joining S4's MUL 5 + FOLD 2), `interlock` (single-in-flight, outstanding≤1, also catches spurious results via 2-bit underflow), `ready` (await-read contract: `result_ready` holds until `read_ack`/new-accept), `reserved` (opcodes 9–14 inert). **13 formal properties total** on `core_top`. Consolidated synth (877 cell/13 DSP/238 FF, hierarchy intact) + routed P&R (**42.1 MHz**, 853 LUT/190 FF/8 DSP/301 slice, critical path = fold_hash Horner feedback) from the S4 run, re-confirmed on disk; S4 fast legs (Python+iverilog) re-run live and re-passed. Formal stays BMC (bounded) + numeric correctness owned by exhaustive Python — per the arc, stated honestly. Writeup: `Ansh_108_Core_PathA_S5_Phase2_Signoff.md` |
| ✅ S6 | Phase 3: parser/slicer/assembler + unit tests | S1 (parallel ok) | **DONE 2026-06-28:** `host_staging.py` (parser `a→0/A→1`+strip · slicer 28-bit MSB-first feet w/ zUnya-pad of final foot · assembler `pkt_fast`/`pkt_data` + `assemble_fold` w/ bindu=RESET exit + general `assemble`) + CLI. Verified `test_host_staging.py` **ALL PASS (17 checks)**: parser/slicer/assembler each cross-checked vs `golden_model` helpers over 5k–20k random cases; **software loopback over 3012 chants** (host stream → golden core == `fold_text` == `fold_fingerprint`, every stream ends in bindu). Software phase (no 5-leg silicon gate; hardware host↔RTL co-sim is S9). Writeup `Ansh_108_Core_PathA_S6_HostStaging.md`. Next host step: S7. |
| ✅ S7 | Phase 3: clock/led/usb_stream + host_ops | S6 | **DONE 2026-06-28:** the rest of the staging agent — `host_ops.py` (Path-A positional fence: bitwise AND/OR/XOR, shift/rotate/bit-reverse aSTa-dik, **SPIRAL** magnitude-compare = unroll `height·M + CRT(residues)` then compare, `SpiralHeightTracker` stream→absolute, CRT==Garner mixed-radix cross-check) + `transport.py` (whole-packet `PacketFramer` = collision-proof "complete pAdas only"; `LoopbackTransport` over `golden_model`; `UsbTransport` Phase-7 seam = NotImplementedError) + `result_reader.py` (the 4 contracts critical/stream/handshake/fire-forget; **read FOLD fingerprint BEFORE bindu reseed**; READ_TICK host-CRT reconstruct) + `clock_led.py` (deterministic Laghu 50ms/Guru 100ms ISI + 3s-warning FSM HOLD/COMPILE/WARNING_3S/EXECUTE/FLUSH/ERROR + **locked LED colour map** HOLD=BLUE/COMPILE=AMBER/WARN=ORANGE/EXEC=GREEN/FLUSH=WHITE/ERROR=RED) + `staging_agent.py` (driver+CLI: .txt→packets→loopback→fingerprint→human-readable, verified inline vs host+golden). **S7 GATE ALL PASS** (`test_s7_staging_agent.py`): every module's unit tests + **END-TO-END loopback over 5016 chants + 3000 programs, 0 mismatch** (agent fp == golden `fold_text` == host `fold_fingerprint`), host_ops==Python ints (30k), clock_led timing exact. HONESTY: host↔software-golden (NOT host↔RTL=S9; no real USB=Phase 7). Writeup `Ansh_108_Core_PathA_S7_StagingAgent.md`. |
| ✅ S8 | Phase 4: A0S grammar spec + aSTa-dik layer + ref programs | S6 | **DONE 2026-06-28:** the human-facing language + 8-direction host geometry (pure Python/grammar, ZERO silicon change — the Path-A fence). `A0S_Assembly_Spec.md` (unambiguous `.txt` grammar: `a/A` data · `.` bindu · `..` early-bindu/abort · Enter=HOLD · `1`–`9` eka…nava control-repeat · `0` zUnya-clear · `@d`/`^d` aSTa-dik roll/scan · `#` comments) + `ashta_dik.py` (locked **9×12=108** toroidal grid; 8 dirs = 4 dizA PUrva/DakSiNa/Pazcima/Uttara + 4 koNa Agneya/NairRta/VAyavya/IzAna; each = a reversible ROLL [reuses `host_ops` 1-D rotate for cardinals] + a corner-to-corner zig-zag SCAN [beats the gcd(9,12)=3 loop-split, full-108]) + `a0s_parser.py` (extends S6 `parse_text` → tokens → packets+geometry; plain maNDalas byte-identical to S6) + `a0s_programs/*.txt` (10 refs, every construct + all 8 dirs). **Sanskrit/op CORRECTION:** S7's `host_ops.ASHTA_DIK` conflated direction-names with bitwise/shift OPS → renamed `POSITIONAL_OPS` (alias kept); true aSTa-dik = compass directions (geometry), `dakSiNa`=South not shift-right, `bheda`=XOR confirmed. **S8 GATE ALL PASS** (`test_s8_a0s_grammar.py`): [A] grammar unambiguous (disjoint leading-char classes + canonical re-lex fixed point over 3000+ programs + golden token vectors; malformed rejected); [B] every ROLL/SCAN reversible + cross-checked vs brute-force double-loop AND numpy (0 mismatch, 5k×8); [C] **8-fingerprint MEASURED** — asymmetric/random = 8/8 distinct, symmetric COLLIDE honestly (uniform 1/8, row-stripes 3/8, col-stripes 2/8 ROLL — logged, not assumed); [D] round-trip compile→packets→S6/S7 loopback→fingerprint == compile == independent golden (4k directional + 4k plain byte-identical + 2k multi-segment + all 10 refs, 0 mismatch). Writeup `Ansh_108_Core_PathA_S8_AshtaDik.md`. HONESTY: host↔software-golden (host↔RTL=S9; USB=Phase 7); zero silicon change. |
| ✅ S9 | Phase 5: co-sim, full test battery vs golden | S5,S7,S8 | **DONE 2026-06-29: the software↔RTL capstone — the chant drove the ACTUAL RTL, in simulation.** Closes the gap every prior ledger owed (host stream proven only vs the software golden, never vs RTL `core_top`). Three artifacts, ZERO edits to any proven module: `cosim_s9.py` (Leg-1 driver — REAL host path `text_to_fold_packets`/`a0s_parser.compile_file`/`assemble`, asserted imports-not-copies; 4-way golden cross-check `fold_fingerprint==fold_text==S7-loopback==last_committed_fp`; emits `cosim_vectors.txt`+`cosim_golden.txt`), `tb_cosim_s9.v` (Leg-2 Icarus TB — drives the locked protocol into the real `core_top`+9 submodules: FOLD 1/cycle, **last FOLD captured before the bindu RESET reseeds**, gated ops single-in-flight, RESET→one bindu, continuous tick monitor `tick==cyc%m_i`; writes `cosim_rtl_out.txt`), `check_cosim_s9.py` (the integration gate). **iverilog -g2012, vvp: 29/29 programs match, 137 packets, 0 mismatch, 0 gaps, tick monitor 0 errors.** Battery = 7 corners (empty/1-bit/exact-28/29/56+1/long mantra) + order pair (aA≠Aa on RTL) + 6 real chant .txt (sample + cosim_chants/ gAyatrI/mahAmRtyuMjaya/zAnti/asato_mA/gaNeza) + all 10 S8 A0S programs (incl. multi-maNDala bindu=2) + 4 op programs. All 4 required checks green: (a) RTL fp==golden every program; (b) bindu-terminated, one pulse/RESET, 0 spurious; (c) order fp(aA)=11032≠fp(Aa)=9667 on RTL; (d) VERIFY/REDUCE/arith==golden exact, READ_TICK residues in-range + host-CRT reconstruct self-consistent (host_ops==golden CRT==Garner) + monotonic [647,657]. No regression (S1/S6/S7/S8 + S4 6000-op TB re-green). Writeup `Ansh_108_Core_PathA_S9_CoSim.md`. HONESTY: host→RTL in SIMULATION (Icarus), NOT silicon; physical FPGA board (Phase 7) is the ONLY unclosed frontier — everything below physical hardware is now closed. Driver `run_cosim_s9.bat` |
| S10 | Phase 6: full-core synth/P&R/formal + results doc | S9 | consolidated results md |
| S11+ | Phase 7: physical board (January) | S10 + hardware | on-HW match |

*S2/S3 (cores) and S6/S7 (host) are independent tracks — can interleave.*

---

## 6. Definition of DONE (whole Path-A arc, pre-hardware)

1. Every native op (MUL/ADD/SUB/REDUCE/VERIFY/FOLD) verified by all 5 legs.
2. `core_top` integrated, formally proven, routed on `xc7a35t` with logged numbers.
3. Staging agent turns any `.txt` program into the correct packet/host-op stream
   and interprets every result mode.
4. A0S assembly grammar specified, unambiguous, Sanskrit verified; aSTa-dik lives as
   grammar/geometry with host transforms.
5. End-to-end co-sim is bit-exact vs a pure-software golden model across the battery.
6. One consolidated results doc with measured numbers, proofs, and an honest caveat
   ledger — matching the rest of the arc.
7. Phase 7 (physical) staged and ready, gated to the January board.

---

## 7. Open items still flagged for your call (don't need them to start, do need them by the phase noted)

- ~~**§2.1** primary lane~~ — ✅ **LOCKED: 12289** (2026-06-28).
- ~~**§2.3** fold B / h₀ / width~~ — ✅ **LOCKED: B=108, h₀=1, single chain (parameterized for N)**.
- ~~**§2.4** opcode set~~ — ✅ **LOCKED: 0-8 + 15 as listed; 9–14 host/reserved**.
- ~~**§2.6/2.7/2.8** counter~~ — ✅ **LOCKED: RNS carry-free / Maha-Yuga {256,27,625} / SEED_FROM_TICK optional-off**.
- ~~Host language~~ — ✅ **LOCKED: Python-first (golden model + staging agent), then C for the real USB path**.
- **Target board model** — still open; needed only before Phase 7 (January).

**§2 is fully locked. Ready for S1.**

---

## 8. AMENDMENT v2 — Continuous Time Counter (the "never-stopping Yuga clock")

**Origin:** a separate design dream — a chip that counts continuously, a clock that
"can't lie," with the 108 core as co-processor that logs/seeds from it.

### 8.1 The buildable kernel (fluff stripped, per the standing rule)
- A **free-running counter (FRC):** increments every master-clock cycle, never stops,
  wraps at its period (overflow = reset / "Pralaya").
- **Read-only to the outside:** host can READ the tick; no packet/opcode can write it
  → **monotonic, unspoofable**. This is the real meaning of "the device can't lie."
- The tick can **seed the fold/crypto** → timestamped fingerprints.
- Excluded as philosophy (not silicon): DNA-as-cosmic-archive, time-travel proofs,
  Casio go-to-market, "world is vibration," etc.

### 8.2 Does Path A change? Yes — additively, and it FITS
- The counter is **control-plane plumbing** (like FLUSH/RESET), not data arithmetic,
  so it does NOT breach the pure-residue fence.
- Build it **carry-free in the chip's own idiom:** an RNS/mixed-radix counter, each
  dial `cᵢ ← (cᵢ+1) mod mᵢ`, no carry between dials. Period = product of coprime
  moduli; wrap = natural CRT roll-over.

### 8.3 Concrete construction — the Maha Yuga counter
- 3 pairwise-coprime dials **{256, 27, 625} = {2⁸, 3³, 5⁴}**.
- Period = 256 × 27 × 625 = **4,320,000 ticks = exactly one Maha Yuga**, carry-free by
  construction; wrap = Pralaya.
- Existing `Ansh_108_Core_Yuga_Mapping_LUT.md` = the host-side lookup turning the raw
  tick into yuga/epoch position. Cosmology stays in the grammar/host layer; datapath
  stays pure.

### 8.4 New modules / opcodes
- `tick_counter.v` — always-on FRC (recommend RNS carry-free; optional plain-binary
  baseline for comparison).
- `READ_TICK` (flexible-lane opcode) — return current tick (value or residues).
- *(optional)* `SEED_FROM_TICK` — load current tick as the fold seed (ties §2.3 seed
  to the live clock → timestamped hashes).

### 8.5 New formal properties (the "can't lie" guarantee — provable)
- **Monotonic:** tick only ever +1/cycle, never decreases except the defined wrap.
- **Write-protected:** no packet/opcode can set or alter the tick.
- **Deterministic period:** wraps exactly at the modulus product.

### 8.6 New decisions to lock (append to §2) — ✅ ALL LOCKED (2026-06-28)
- **2.6 Counter style:** ✅ **RNS carry-free** (on-brand; keeps the no-carry identity).
- **2.7 Period/width:** ✅ **{256, 27, 625} = 2⁸·3³·5⁴ = 4,320,000 = one Maha Yuga**
  (cascade additional coprime dials later for longer horizons).
- **2.8 Tick auto-seeds the fold?** ✅ **Optional via `SEED_FROM_TICK` (opcode 7),
  OFF by default.**

### 8.7 Phase deltas
- **Phase 1:** add `tick_counter.v` + 5-leg verification (period/wrap checked
  exhaustively; monotonicity formal).
- **Phase 2:** wire counter always-on, read-only; add `READ_TICK` (+ optional
  `SEED_FROM_TICK`); add monotonic + write-protect formal properties.
- **Phase 3 (host):** "read timestamp" command + Yuga-LUT interpretation.
- **Phase 4 (grammar):** tick/timestamp + yuga-reporting constructs (host-side).
- **Phase 6:** characterize counter fmax impact (wide incrementer / wrap-compare can
  land on the critical path — measure honestly; per-dial RNS wrap keeps it short).

### 8.8 Honesty firewall (carry forward)
- The chip is a perfect **cycle** counter. Cycles → calendar time needs a *known
  oscillator frequency*. "Never drifts / space-grade accuracy" is NOT free — it needs
  a disciplined reference (TCXO/OCXO, or GPS/atomic discipline) at board level. The
  core guarantees monotonic, unspoofable *cycles*, not absolute *seconds*.
- **"Can't lie" = monotonic + write-protected, proven.** It does NOT mean the absolute
  time is correct — only that the count cannot be rewound or forged.
- µW "coin-cell watch" + space survival need the **ASIC + rad-hard track**
  (post-Phase-7), exactly as the dream's own later messages concede. FPGA proves the
  logic, not the microwatts.

### 8.9 New future track (post-arc)
ASIC tape-out with rad-hard standard cells (RHBD / DICE flip-flops) for the actual
space-grade low-power watch. Planned; explicitly **out of** the pre-silicon arc.

### 8.10 Identity upgrade
With the counter, the chip is no longer only "data-sealing + crypto accelerator" — it
is also a **trusted monotonic time base**. The combination = **timestamped,
tamper-proof fingerprints** (fold seeded by an unspoofable tick). Coherent, buildable,
and genuinely novel.
