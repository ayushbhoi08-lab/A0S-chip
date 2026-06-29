# Ansh-108 Core — Path A, Session S7: the rest of the staging agent

### The front chamber comes alive — host ops, result reader, transport, clock/LED, and the driver that ties them to the S6 data path

*Path-A Phase-3 deliverable (plan §3 Phase 3 / §5 row S7). Builds on S6's
`host_staging.py` (parse/slice/assemble) and the verified cores (S1 `golden_model`,
S2–S5 RTL) — none of which were rebuilt. Pure Python (project `.venv`, Python 3.14,
numpy present but unused here), no Verilog/FPGA tooling touched, so it ran safely
alongside any FPGA session. Created 2026-06-28. Artifacts in `Ansh_108_Core_Artifacts/`.*

---

## What was built (5 new modules + a master gate)

| File | Role |
|---|---|
| `host_ops.py` | the **Path-A positional fence** — everything the residue chip is forbidden to do |
| `transport.py` | whole-packet **packet streamer** + the **software-loopback** transport + USB seam |
| `result_reader.py` | the **four result-mode contracts** + the read-before-bindu fingerprint |
| `clock_led.py` | the **clock/LED state machine** (Laghu/Guru ISI timing + the locked colour map) |
| `staging_agent.py` | the **driver**: `.txt → packets → loopback → fingerprint → human-readable` + CLI |
| `test_s7_staging_agent.py` | the **S7 verification gate** (mirrors S6): all module tests + end-to-end loopback |

### 1. `host_ops.py` — the positional fence (host-side; the chip refuses these)
- **Bitwise** `band`/`bor`/`bxor` (XOR = *bheda*, the cut, plan §4).
- **Shift** `shl`/`shr` (*vAma*/*dakSiNa*), **rotate** `rotl`/`rotr`, **bit-reversal**
  `bit_reverse` (the aSTa-dik mirror). An `ASHTA_DIK` registry maps the 8 directions
  to these host transforms — **provisional names**, finalized by the S8 grammar layer.
- **Magnitude compare = the SPIRAL.** A residue value lives on a circle of
  circumference `M`; to compare two you must *unroll the spiral* first:
  `spiral_value = height·M + reconstruct(residues)`, then compare absolute linear
  magnitudes (`spiral_compare` → −1/0/+1). This is exactly the branch the residue
  datapath kills — so it lives host-side.
- **`SpiralHeightTracker`** turns a *stream* of circular-core residues (e.g. the
  free-running Yuga tick, which wraps every Maha Yuga) into an absolute, ever-rising
  linear count by detecting wraps (a value drop = a Pralaya → height++).
- **Two independent reconstructions** kept and cross-checked: the CRT idempotent path
  (imported from `golden_model`, the source of truth) and **mixed-radix / Garner**
  (implemented here, positional). They agree exhaustively on the 108-state demo lane
  and over 50k random Maha-Yuga states — and both equal plain Python ints.

### 2. `transport.py` — send COMPLETE packets only
- `PacketFramer` accumulates a raw **byte** stream and releases only whole 4-byte
  (32-bit) pAdas; a partial tail is buffered until completed — **collision-proof**, so
  the core never sees half a packet aliasing into a wrong opcode.
- `LoopbackTransport` drives `golden_model.AnshCoreGolden` and returns a `CoreEvent`
  per packet (opcode, result-mode class, value, the bindu pulse, and — for READ_TICK —
  the **raw tick residues** for the host to recombine). It advances the write-protected
  Yuga tick once per packet (a deterministic stand-in for the per-clock hardware
  advance) and **reseeds the fold mirror on FLUSH/RESET exactly like `fold_hash`**, so
  the read-before-bindu contract is real, not decorative.
- `UsbTransport` is a **declared-but-unimplemented Phase-7 seam** (`open()` raises
  `NotImplementedError`) — it shares the framer + the `CoreEvent` protocol, so the real
  UART/FTDI bridge drops in later without touching the rest.

### 3. `result_reader.py` — the four contracts
- **CRITICAL** (MUL/ADD/SUB/REDUCE): await `out_valid`, read the held word.
- **STREAM** (FOLD): collect each push; the fingerprint is the **last push BEFORE the
  bindu** (`fold_fingerprint` / `StreamCollector`). `interpret()` seals exactly one
  fingerprint Reading per chant, captured before the reseed.
- **HANDSHAKE**: VERIFY → 1-bit pass/fail; **READ_TICK → the host CRT-recombines** the
  raw residues via `host_ops` (Path-A fence), with a Garner cross-check assertion, into
  a within-period tick; absolute-across-Pralayas comes from feeding a stream into
  `SpiralHeightTracker`.
- **FIRE-FORGET** (FLUSH/RESET): no result; RESET raises the bindu pulse.

### 4. `clock_led.py` — the front face (pure deterministic model, no real LEDs)
- Forward-modeled ISI: **laghu (bit 0) = 50 ms**, **guru (bit 1) = 100 ms**; a **3-second
  warning** (abort window) before EXECUTE; one laghu pulse to reseed on FLUSH.
- States **HOLD / COMPILE / WARNING_3S / EXECUTE / FLUSH / ERROR** with a **LOCKED transition
  table** (illegal transitions raise) and the **LOCKED LED colour map** (locked here in S7 —
  the plan referenced a "locked table" that had not yet been written down):

  | State | Colour | Meaning |
  |---|---|---|
  | HOLD | **BLUE** | idle / waiting (the "Enter" hold) |
  | COMPILE | **AMBER** | host parsing / slicing / assembling |
  | WARNING_3S | **ORANGE** | 3 s countdown before execution (abort still possible) |
  | EXECUTE | **GREEN** | streaming pAdas to the core (per-syllable ISI timing) |
  | FLUSH | **WHITE** | reseed / bindu / zUnya (resonates with the canon "white") |
  | ERROR | **RED** | parse or runtime fault |

  Engineering-locked; the cosmology behind the colours (Agni-triangle, five elements)
  stays in the story canon + the S8 grammar, not in this model.

### 5. `staging_agent.py` — the driver + CLI
`.txt → parse/slice/assemble (S6) → clock/LED timing → loopback transport → result
reader → human-readable report`, with the fingerprint **read before the bindu** and
**verified** in-line against both `host_staging.fold_fingerprint` and
`golden_model.fold_text`. Also runs general A0S programs (arith/verify/read-tick) and
routes every result mode. CLI:
```
python staging_agent.py sample_chant.txt
```
On `sample_chant.txt`: 126 bits (99 laghu/27 guru) → 5 feet → 6 packets (5 FOLD +
bindu) → fingerprint **9033 (0x2349)** [VERIFIED] → session time **10700 ms**
(3000 warning + 7650 ISI + 50 flush). The fingerprint matches S6 exactly.

---

## Verification — S7 GATE: ALL PASS (`test_s7_staging_agent.py`)

This is a **software** phase, so the gate is unit tests + golden cross-check + an
end-to-end software loopback (not the 5-leg silicon gate).

| Group | Check | Result |
|---|---|---|
| **A** module unit tests | `host_ops` (14) · `transport` (9) · `result_reader` (8) · `clock_led` (14) · `staging_agent` (8) — each `_selftest()` ALL PASS | PASS |
| **B** end-to-end chants | **staging_agent fingerprint == golden `fold_text` == host `fold_fingerprint` over 5016 chants, 0 mismatch**; every stream ends in the bindu; order-sensitive; deterministic | PASS |
| **B'** end-to-end programs | CRITICAL readings == a fresh golden core over **3000 random A0S programs** | PASS |
| **C** host_ops vs Python | AND/OR/XOR/shift/rotate/bit-reverse == Python ints (30k); **SPIRAL magnitude compare == Python int compare (30k)** | PASS |
| **D** clock_led | transitions exact; timing == `3000 + 50·laghu + 100·guru + 50` | PASS |

Headline contracts proven:
- **Whole-packet framing is collision-proof:** feeding the byte stream **one byte at a
  time** still delivers exactly the whole packets, in order, with nothing partial.
- **Read-before-bindu is real:** the live fold accumulator is **reseeded to the seed
  AFTER the bindu** — so the fingerprint *must* be taken from the stream first; the
  reader does, and the loopback confirms it equals the golden fold over thousands of chants.
- **READ_TICK honors the Path-A fence:** the core hands back raw residues; the **host**
  reconstructs (CRT == Garner == Python), and a `SpiralHeightTracker` recovers the
  absolute tick across a Pralaya.

---

## Honesty ledger

1. **Host ↔ software-golden loopback only — NOT host ↔ RTL.** S7 drives
   `golden_model`, the source of truth, which is itself RTL-validated by S4's 6000-op
   replay — so the chain is sound — but the literal host↔`core_top` RTL co-sim is **S9
   (Phase 5)** and is not claimed here.
2. **No real USB yet.** `UsbTransport` is a Phase-7 seam that raises
   `NotImplementedError`; there is no board and no `pyserial` dependency in the
   pre-silicon arc. The real UART/FTDI bridge is **Phase 7 (January)**.
3. **The LED colour map is engineering-locked in S7, not earlier.** The plan referenced
   a "locked table" that had never been written; this session writes and locks it. It is
   a model decision, defensible but not a measurement.
4. **Tick timing is cycles, not seconds.** The loopback advances the Yuga tick once per
   packet as a deterministic model. Cycles → calendar seconds still needs a disciplined
   oscillator at board level (plan §8.8) — unchanged.
5. **`SpiralHeightTracker` has a Nyquist bound.** It only tracks wraps if successive
   samples are < one full period `M` apart; a full-period jump is invisible. This is
   tested and documented (sample the tick often enough).
6. **Constants imported, algorithms independent.** Every module pulls the locked
   constants from `golden_model`/`host_staging` but implements its own logic; the tests
   prove the independent logic equals the source of truth. Not a copy.

---

## Reproducibility
```
# the S7 gate (all modules + end-to-end):
python test_s7_staging_agent.py        -> S7 GATE: ALL PASS

# individual module self-tests:
python host_ops.py        # positional fence vs Python ints (14)
python transport.py       # whole-packet framing + loopback (9)
python result_reader.py   # four result contracts (8)
python clock_led.py       # clock/LED FSM + ISI timing (14)
python staging_agent.py --selftest   # end-to-end (8)

# the driver CLI:
python staging_agent.py sample_chant.txt
```

### Cross-references
- Plan: `Ansh_108_Core_PathA_Build_Plan.md` (§3 Phase 3, §5 row S7).
- Builds on: S6 `host_staging.py` (parse/slice/assemble), S1 `golden_model.py` (source
  of truth), S4 `core_top` result-mode contracts (`opcode_decode.result_mode`,
  `result_mode.v`, `tick_counter.v`).
- **Next: S8** — the A0S assembly grammar + the aSTa-dik geometry layer (finalizes the
  provisional `ASHTA_DIK` names + Sanskrit audit) + reference programs. Then **S9**
  (Phase 5) — the literal host↔RTL co-sim that closes the honesty gap above.
- Phase-6 fold-pipelining remains the named fmax lever (do AFTER end-to-end).
