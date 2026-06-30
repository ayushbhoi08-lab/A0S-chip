# ANSH-108 Core — A-TS host↔RTL Co-sim: the routed chip echoes the notarizer

### Closes the loop from the Track-A application down to the MEASURED silicon

*Drives the A-TS notarizer's timestamped stamps through the real integrated
`core_top` RTL (Icarus), isolated from the proven S9 battery. Created 2026-06-30.
Standing rule honored. Code: `cosim_ats.py`, `tb_cosim_ats.v`, `check_cosim_ats.py`.*

---

## 1. What this proves (and the honest scope)

The A-TS app produces an 8-chain ≈108-bit fingerprint. **Chain 0 (B=108, seed=1)
is the chain the chip itself runs** — it is byte-for-byte the proven golden FOLD.
Chains 1–7 are *host-side replication* of the same primitive with different
constants (the documented "wins via replication" story). So the meaningful
hardware claim is: **the routed `core_top` reproduces chain 0's stamps exactly.**
This co-sim proves it on the actual RTL, not just the software model.

This is the genuinely novel A-TS combination demonstrated end-to-end on silicon:
a content fingerprint bound to a monotonic, write-protected tick, recomputed by
the chip design itself.

---

## 2. Pipeline (isolated from S9 — proven artifacts untouched)

```
A-TS notarized log (tick + event bytes per event, one continuous FOLD chain)
  -> chain-0's exact 28-bit foot sequence  (tick foot, then bytes_to_feet(event))
  -> FOLD packets + terminal RESET (bindu commits the maNDala)
  -> cosim_ats_vectors.txt
  -> tb_cosim_ats.v  drives Icarus-simulated core_top  -> cosim_ats_out.txt
  -> check_cosim_ats.py : RTL fingerprint == chain-0 stamp, per program
```

`tb_cosim_ats.v` is the proven `tb_cosim_s9.v` with only its two I/O filenames
redirected (`cosim_ats_vectors.txt` / `cosim_ats_out.txt`), so the S9 battery and
its artifacts are never modified.

**Two host cross-checks run before any RTL** (in `cosim_ats.py`): each chain-0
stamp is asserted equal to (a) a real 8-chain `Notarizer`'s chain 0 over the same
events, and (b) the proven S7 loopback host path (`last_committed_fp`).

---

## 3. Result — ALL PASS (5/5 gate legs)

Build: `iverilog -g2012 core_top.v + 9 submodules + tb_cosim_ats.v` → `vvp`.
RTL ran 4 A-TS programs, 163 packets, **tick monitor 0 errors**.

| Program | Golden chain-0 stamp | RTL `core_top` | Echo |
|---|---|---|---|
| `ats_single` (1 event) | 0x0ccb | 0x0ccb | ✓ |
| `ats_demo` (5 events) | 0x2947 | 0x2947 | ✓ |
| `ats_demo_swap` (#1,#2 reordered) | 0x105a | 0x105a | ✓ |
| `ats_chant_gayatri` (chant bytes) | 0x1378 | 0x1378 | ✓ |

Gate legs: RTL == chain-0 stamp for all 4 (0 mismatch) · **order sensitivity on
the RTL** (0x2947 ≠ 0x105a) · tick monitor clean · program count matches · golden
reproducible from the real notarizer path. `0x2947 = 10567` also matches the
notarizer demo's final `root[0]`.

---

## 4. Honesty ledger

- ✅ Drives the **real integrated `core_top`** (the same RTL routed at 42.1 MHz in
  S4/S5), not a toy — via the proven S9 testbench, only I/O-redirected.
- ✅ Claim scoped to **chain 0** (what the chip runs); chains 1–7 are explicitly
  host-side replication, stated as such — no overclaim that the chip runs 8 chains.
- ✅ Stamps cross-checked against a real `Notarizer` and the proven loopback host
  path *before* the RTL run, so a green RTL can't hide a host-side error.
- ⚠️ Functional co-sim (Icarus) — proves logic equivalence, not timing/power; those
  remain the Phase-7 board frontier.
- ⚠️ "Cannot be forged" still depends on the §5 deployment anchor from the A-TS
  writeup (external append-only sink) + the oscillator — not proven by this co-sim.

---

## 5. Reproduce

```
cd D:\Project_Ansh_Data\01_CHIP_A0S\Core_Artifacts
python cosim_ats.py                      # Leg 1: notarizer -> vectors + golden
C:\iverilog\bin\iverilog -g2012 -o tb_cosim_ats.vvp core_top.v opcode_decode.v \
  result_mode.v rns_reduce.v tick_counter.v ntt_mul12289.v rns_add.v rns_sub.v \
  rns_verify.v fold_hash.v tb_cosim_ats.v
C:\iverilog\bin\vvp tb_cosim_ats.vvp     # Leg 2: drive RTL -> cosim_ats_out.txt
python check_cosim_ats.py                # gate: RTL == chain-0 stamp
```

### Cross-references
- App: `Ansh_108_Core_ATS_Notarizer.md` (the notarizer + threat model)
- Pattern reused: `Ansh_108_Core_PathA_S9_CoSim.md` (the S9 host↔RTL co-sim)
- Code: `../Core_Artifacts/{cosim_ats.py, tb_cosim_ats.v, check_cosim_ats.py}`
