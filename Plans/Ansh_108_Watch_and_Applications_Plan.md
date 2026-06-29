# Ansh-108 — Watch & Applications Plan (companion to the Path-A Build Plan)

**Status:** PLAN ONLY — nothing built. Multi-session, persists across sessions.
**Standing rule (per [[feedback_empirical_verification]]):** every claim measured or
proven; negative results kept; no number is a hope; claims sized to the evidence.
**Companion to:** `Ansh_108_Core_PathA_Build_Plan.md` (the chip arc, S1–S11). This doc
adds two NEW, independent tracks that sit ON TOP of the already-proven Path-A core:
**Track W** (the standalone Yuga-clock watch) and **Track A** (applications). It does
NOT change the Path-A fence or re-plan the chip.

---

## 0. Relationship to the main arc (what these tracks assume)

Both tracks are *consumers* of work already done — they do **NOT rebuild it**:

- **Proven datapath:** `ntt_mul12289.v` (MUL), `rns_add/sub.v`, `rns_verify.v`,
  `fold_hash.v`, `rns108.v` — all 5-leg verified (S2/S3).
- **Integrated core:** `core_top.v` + `opcode_decode/result_mode/rns_reduce` (S4/S5),
  routed 42.1 MHz, 13 formal properties. Exposes `FOLD`, `VERIFY`, `READ_TICK`,
  `SEED_FROM_TICK`.
- **The time counter:** `tick_counter.v` — carry-free RNS {256,27,625}, period
  4,320,000, **write-protected by construction**, verified inside S4. *The watch's
  core already exists.*
- **Host data path:** `host_staging.py` (S6) parser/slicer/assembler; soon S7's
  `host_ops`/`transport`/`result_reader`.
- **Reference + mapping:** `golden_model.py` (CRT/bijection helpers), `yuga_lut.*`
  (tick → yuga/epoch), and the measured **NTT crypto core + CPU benchmark** from the
  Ansh-108 Core series ([[project_ansh108_core_series]]).

**Two integration postures for the watch (both valid):**
1. **Programmable WITH the chip** — already exists: `READ_TICK`/`SEED_FROM_TICK` on
   `core_top` give timestamped fingerprints today. No new silicon needed.
2. **Completely separate module** — a self-contained watch as its own FPGA top. *This
   is the new thing Track W builds.*

---

## 1. HONESTY FIREWALL (applies to every session below — carry forward verbatim)

**Watch:**
- The chip is a perfect **cycle / enable counter**. Cycles → calendar *seconds* is only
  as accurate as the **oscillator** feeding it. "Never drifts / space-grade" needs a
  disciplined reference (TCXO/OCXO, or GPS/atomic discipline) at board level.
- **"Can't lie" = monotonic + write-protected, PROVEN.** It does NOT mean absolute time
  is correct — only that the count cannot be rewound or forged.
- µW "coin-cell watch" + space survival need the **ASIC + rad-hard track** (post-Phase-7).
  FPGA proves the *logic*, not the microwatts.

**Applications:**
- Constant-time math defeats **timing** side-channels only — not power/EM, and only if
  the whole datapath (incl. host) stays constant-time.
- A **single 14-bit FOLD chain is NOT collision-resistant**; cryptographic strength needs
  **N parallel chains** (distinct B, h₀) — measure the collision rate, don't assume it.
- "Tamper-proof / impossible to fake" depends on key management + the oscillator + board
  security — never claim it from the math alone.
- Every app is tagged **Class A** (directly enabled, defensible), **Class B** (plausible,
  needs design work), or **Class C** (speculative / story-layer — firewalled, unvalidated).

---

## 2. TRACK W — the standalone Yuga-clock watch

**Scope fence:** a self-contained, free-running, carry-free, write-protected time base as
its own FPGA top, separate from `core_top`. Human units & calendar are a **host-side
mapping** (positional/division = host, per the Path-A fence). Counter moduli stay
**coprime** — that is what makes it carry-free (the chip's identity). Pretty units
(60/60/24) are NOT coprime → they live only in the host mapping, never on-chip.

### Decisions to lock before W-code (defaults in **bold**)
- **W.1 moduli** = **keep {256, 27, 625} = 2⁸·3³·5⁴ (one Maha Yuga = 4,320,000
  enable-ticks)**; cascade more coprime dials later (W5) for longer horizons.
- **W.2 base resolution** = **1 enable / second** (parameterized; sub-second later).
- **W.3 reference oscillator** = **modeled as `param FREQ_HZ`** until a board is chosen
  (Phase 7); accuracy = the chosen XO's spec.
- **W.4 epoch anchor** = **host-side metadata** (the chip never gets a "set time"
  command; staying write-protected is the whole point).
- **W.5 readout** = **residues out + a read strobe**; display/UART is a later session.

### Sessions

**W1 — BASE (the "just the base" build).** *Depends on: existing counter pattern + golden.*
- Deliverables: `clk_divider.v` (param `FREQ_HZ` → 1 tick-enable/sec, the explicit
  cycles→seconds bridge); `tick_counter_ce.v` (the carry-free RNS counter WITH a
  clock-ENABLE — advance only on the 1 Hz enable; single clock domain, NOT a gated
  divided clock; do **not** edit the proven `tick_counter.v`); `yuga_watch_top.v`
  (standalone top: divider → counter → read-only residues + read strobe);
  `watch_readout.py` (host: CRT-reconstruct residues → absolute tick).
- Gate (full 5-leg — it becomes hardware): Python model + exhaustive period/wrap (reuse
  golden bijection) → iverilog (divider emits exactly 1 enable per `FREQ_HZ` cycles;
  counter advances once/enable; wraps at period) → SymbiYosys/boolector formal
  (**monotonic**, **write-protected**, **deterministic period**, enable-correctness —
  control only, no modulo reference → no SMT wall) → Yosys synth → Vivado P&R
  (fmax/footprint; expect tiny + fast).
- Done: standalone watch counts/reads/wraps; logic proven; numbers + caveats logged;
  writeup `Ansh_108_Core_PathA_W1_Watch.md`.

**W2 — Time & calendar mapping (host).** *Depends on: W1.*
- Deliverables: host tick → {sec, min, hr, day} and → yuga/epoch position (reuse
  `yuga_lut`); display format; leap/anchor handling — all host-side.
- Gate: golden vectors over the **full period incl. the Maha-Yuga wrap**, 0 mismatch.
- Done: any tick value maps to a correct, human-readable time/yuga string vs golden.

**W3 — Readout & display I/O.** *Depends on: W1.*
- Deliverables: a latch-and-read protocol; an optional on-chip readout module (BCD /
  seven-seg driver, or a UART time emitter). 5-leg for any new RTL.
- Done: time is observable off-chip (serial/LED), proven.

**W4 — Oscillator discipline & accuracy budget.** *Depends on: W1.*
- Deliverables: an error-budget model (ppm → drift/day); a host **calibration** routine
  (measure actual XO vs a reference, store the correction host-side); a TCXO/OCXO plan.
- Gate: the stated accuracy matches the modeled XO spec; calibration reduces modeled
  drift as predicted.
- Done: an honest accuracy statement ("±X s/day with a Y-ppm XO; correctable to Z").

**W5 — Multi-horizon cascade.** *Depends on: W1.*
- Deliverables: extend the coprime dial set (more dials) for year/decade horizons while
  staying carry-free; characterize the fmax/footprint cost (reuse the `gen_rns` N-dial
  curve lessons — [[project_ansh108_core_series]]).
- Done: a longer-period watch with the cost curve logged honestly.

**W6 — Power & always-on analysis.** *Depends on: W1 (+ W5).*
- Deliverables: FPGA dynamic/static power estimate (honest: an FPGA is NOT µW); scope the
  **ASIC + rad-hard** path (DICE/RHBD flip-flops) for the real low-power/space watch.
- Done: a power ledger + a clear "FPGA proves logic; µW/space = ASIC track, post-Phase-7".

**W7 — Physical bring-up (frontier; aligned to the main Jan board).** *Depends on:
W1–W4 + hardware.*
- Deliverables: real XO wired to the divider; time over UART/LED; **measured drift** vs a
  GPS/NTP reference over hours/days.
- Done: a real board keeps time, and the drift matches the W4 budget.

**W8 — (Optional) FUSION with the chip.** *Depends on: W1 + core_top (exists).*
- Deliverables: standalone watch ↔ `core_top` link = **timestamped FOLD** via
  `SEED_FROM_TICK` (the "trusted monotonic time base + tamper-evident fingerprint"
  identity). Integration partly exists via `READ_TICK`; this hardens/demos it.
- Done: a fingerprint provably stamped by an unspoofable tick (feeds Track A-TS).

---

## 3. TRACK A — Applications (host-side wrappers on the proven core)

Each application is a **software project on the already-proven engine** (the silicon does
not change). Most can be prototyped against `golden_model.py` now; a real *hardware* demo
depends on **S9** (host↔RTL co-sim) from the main plan. Any app that grows new RTL (e.g.
a crypto NTT network) takes the full 5-leg gate.

### A-PQC — Post-Quantum Crypto accelerator  **(Class A — strongest)**
*Why real: 12289 is the actual Kyber/ML-KEM & Dilithium NTT prime; the inner loop is
exactly your constant-time `×/＋ mod q`.*
- A-PQC-1: map the ML-KEM/Kyber forward+inverse **NTT** onto the 12289 lane — BUILD ON the
  existing measured NTT core ([[project_ansh108_core_series]]); do NOT rebuild it. Host
  orchestration of the butterfly network.
- A-PQC-2: constant-time / side-channel **scope doc** (timing-channel argument; honest
  about power/EM out of scope).
- A-PQC-3: benchmark vs a reference Kyber implementation; report **perf/watt + determinism**,
  and the honest verdict ("not a per-op CPU-beater; wins on constant-time + perf/watt +
  replication").
- Gate: golden cross-check of the NTT vs a reference; 5-leg for any new RTL; measured
  numbers + honesty ledger.

### A-TS — Tamper-evident timestamped fingerprint / proof-of-order  **(Class A)**
*Ties Track W + FOLD. The genuinely novel combination.*
- A-TS-1: `SEED_FROM_TICK` timestamped FOLD; **multi-chain** FOLD for collision strength
  (measure the collision rate — firewall item).
- A-TS-2: a stream/log **notarizer** — ingest events, emit a timeline hash; prove
  order-sensitivity end-to-end.
- A-TS-3: a verifier tool + an explicit **threat model** (what the keys/oscillator/board
  must guarantee; what "can't lie" does and does NOT cover).
- Gate: golden cross-check; collision-rate measured for N chains; threat model written.

### A-FP — Stream integrity / content fingerprinting  **(Class A− / B)**
- A-FP-1: multi-chain FOLD → a **wide** fingerprint; **measure** the collision rate vs
  chain count (don't assume).
- A-FP-2: a dedup / content-ID demo over a real corpus; honest collision math.
- Gate: measured collision curve; demo vs golden.

### A-AC — Acoustic / rhythm fingerprinting (your chant domain)  **(Class B)**
- A-AC-1: extract audio/chant features on the host → FOLD via `host_staging`; cluster/dedup.
- Honest scope: this is **modular fingerprinting of extracted features**, NOT a general
  audio-DSP/FFT engine (that's floating-point; this is modular). State it plainly.
- Gate: cluster/dedup quality measured on a labeled set; golden cross-check of the hashes.

### A-CH — Chess / AI  **(Class B / C — low priority)**
- Transposition-table hashing via FOLD (a CPU does Zobrist trivially → low added value);
  RNS-native NN eval only if the network is *designed* for RNS (not drop-in NNUE). Keep
  modest; do not oversell.

---

## 4. Dependencies, sequencing, and the parallelism rule

- **Track W is independent of the host S7/S8.** W1 needs only the existing counter
  pattern + golden. W2/W3 build on W1. W7 needs hardware.
- **Track A** mostly needs the golden model now; *hardware* demos need **S9**.
- **Parallelism rule (hard):** FPGA-tool sessions (W1/W3/W5/W7, any A-PQC RTL) run
  iverilog/sby/yosys/Vivado and use the "kill stale oss-cad procs by path" step — so **no
  two FPGA-tool sessions at once** (they'd kill each other / fight the Vivado flow).
  Python-only sessions (W2/W4 host parts, all early A-* prototyping, the main S7) are safe
  to run alongside ONE FPGA session.
- **Suggested order:** **W1 (base)** → **A-TS** (high value, uses watch+FOLD, mostly host)
  → **A-PQC** (build on the existing NTT) → **W2/W3** → the rest as interest dictates.

---

## 5. Cross-cutting standards (same as the main arc)

- **5-leg verification** for anything that becomes hardware (Python · iverilog ·
  SymbiYosys/boolector · Yosys · Vivado P&R). Keep formal to range/latency/control — a
  `% q` modulo-reference over free wide data is the SMT wall (S3 precedent); numeric
  correctness is owned by exhaustive Python + the proven reused cores.
- **Per-session honesty ledger**; negative results stay in.
- **Artifacts** into `Ansh_108_Core_Artifacts/`; each session gets an `Ansh_108_Core_*.md`
  writeup. Toolchain quirks carry forward (call `environment.bat`; kill oss-cad by path;
  Vivado `XILINXD_LICENSE_FILE` unset; Windows `sys.stdout.reconfigure(encoding="utf-8")`).

---

## 6. Definition of DONE (per track)

- **Watch:** standalone module 5-leg proven (monotonic + write-protected + period); time
  mapping correct vs golden over the full period incl. wrap; accuracy budget stated
  honestly; Phase-7 board staged; (optional) fusion timestamped-FOLD demoed.
- **Applications:** each **Class-A** app has a golden-validated prototype + a **measured**
  benchmark + an honest claim sheet (incl. collision rates, side-channel scope); Class B/C
  clearly labeled and firewalled, never sold as proven.

---

## 7. Open calls (needed by the session noted, not to start)

- W.1 moduli set for longer horizons (by W5) · reference board + XO (by W7) ·
  display/readout form — LED/UART/segment (by W3).
- A-PQC: which scheme first — ML-KEM (Kyber) vs ML-DSA (Dilithium) (by A-PQC-1).
- A-TS: number of FOLD chains for the target collision bound (by A-TS-1).
- App hardware demos are gated on **S9** (host↔RTL co-sim) from the main plan.

---

### Cross-references
- Main arc: `Ansh_108_Core_PathA_Build_Plan.md` · source of truth `golden_model.py`
- Reused (do NOT rebuild): `tick_counter.v`, `core_top.v`, the proven datapath cores,
  `yuga_lut.*`, the Ansh-108 Core series NTT/CPU benchmark ([[project_ansh108_core_series]]).
- Memory: [[project_ansh108_pathA_build]], [[project_aos_branding_entities]] (A0S vs
  Project Ansh firewall — the chip is hardware; keep app claims honest).
