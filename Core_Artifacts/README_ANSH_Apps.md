# ANSH-108 Core — Track-A Applications (host-side, no FPGA board)

These are **software applications built on the proven chip model** — they run today
against `golden_model.py` (the source-of-truth) with **no FPGA board required**. A
board is only Phase-7 (drift/power); it adds nothing to proving the logic. One app
(A-TS) is additionally **echoed bit-for-bit on the real `core_top` RTL** via Icarus.

All numbers are measured or proven; negative results are kept; no number is a hope
(per the project's empirical-honesty rule).

---

## Status

| App | What it is | Status | Gate | Writeup |
|---|---|---|---|---|
| **A-TS** | Tamper-evident timestamped notarizer (proof-of-order) | DONE + **RTL echo** | 11/11 + co-sim 5/5 | `Ansh_108_Core_ATS_Notarizer.md`, `..._ATS_CoSim.md` |
| **A-FP** | Content fingerprinting / dedup (wide multi-chain hash) | DONE | 6/6 | `Ansh_108_Core_AFP_Fingerprint.md` |
| **A-PQC** | Falcon negacyclic NTT on the 12289 lane | DONE | 8/8 | `Ansh_108_Core_APQC_FalconNTT.md` |
| **A-PQC** | Falcon-512 **verify** harness (chip NTT in the loop) | DONE | 9/9 | `Ansh_108_Core_APQC_FalconVerify.md` |
| **A-PQC** | Falcon wire-format **codec** + real-signature **interop** | DONE | 8/8 + 5/5 | `Ansh_108_Core_APQC_FalconInterop.md` |

Writeups live in `../Science_Background/`. The application directory + class
firewall is `../Science_Background/Ansh_108_Core_Applications_Directory.md`.

---

## Run it

```sh
cd D:\Project_Ansh_Data\01_CHIP_A0S\Core_Artifacts

# A-TS — tamper-evident notarizer
python ats_notarizer.py            # self-test gate (11/11)
python ats_notarizer.py --demo     # notarize a log, then catch a tamper
python ats_notarizer.py --measure  # collision + order-sensitivity (measured)

# A-TS host<->RTL co-sim (needs iverilog: C:\iverilog\bin or /c/oss-cad-suite/bin)
python cosim_ats.py                # Leg 1: notarizer -> vectors + golden
C:\iverilog\bin\iverilog -g2012 -o tb_cosim_ats.vvp core_top.v opcode_decode.v \
  result_mode.v rns_reduce.v tick_counter.v ntt_mul12289.v rns_add.v rns_sub.v \
  rns_verify.v fold_hash.v tb_cosim_ats.v
C:\iverilog\bin\vvp tb_cosim_ats.vvp
python check_cosim_ats.py          # gate: routed core_top == chain-0 stamp (5/5)

# A-FP — content fingerprinting / dedup
python afp_fingerprint.py          # self-test gate (6/6)
python afp_fingerprint.py --measure  # collision curve vs chain count (measured)
python afp_fingerprint.py --demo   # dedup over the real chant + program corpus

# A-PQC — Falcon NTT on the 12289 lane
python apqc_ntt.py                 # self-test gate (8/8)
python apqc_ntt.py --measure       # op-count benchmark + honest verdict
python apqc_falcon_verify.py       # Falcon-512 verify harness gate (9/9)
python apqc_falcon_verify.py --demo  # accept + reject cases with norms
python apqc_falcon_codec.py        # Falcon wire-format codec self-test (8/8)
python apqc_interop_vector.py      # interop vs a GENUINE reference signature (5/5)
```

---

## How they fit together (reuse, not reinvention)

```
golden_model.py  (proven source-of-truth: FOLD, RNS counter, slicer, CRT)
   └─ ats_notarizer.py    MultiChainFold (chain 0 == golden FOLD, asserted)
        ├─ afp_fingerprint.py   reuses MultiChainFold for content-ID / dedup
        └─ cosim_ats.py + tb_cosim_ats.v + check_cosim_ats.py
              drives the REAL core_top RTL; proves it echoes chain-0 stamps
   └─ apqc_ntt.py         every butterfly multiply = the proven ntt_mul12289 op
```

The A-TS co-sim is **isolated** from the S9 battery: it uses `cosim_ats_*` files and
a redirected copy of the proven testbench, so `cosim_vectors.txt` / `cosim_golden.txt`
/ `cosim_rtl_out.txt` are never touched.

---

## Honesty firewall (carry-forward, applies to all three)

- **Fingerprint, not keyed crypto.** Z/12289 is unkeyed — A-TS/A-FP give integrity,
  proof-of-order, and dedup, *not* unforgeable signatures against a key-holding adversary.
- **8 chains ≈ 108-bit fingerprint, ~54-bit collision resistance** — *projected* from a
  measured 1–2-chain birthday curve, **not** a 2⁵⁴ search. Base 108 alone is weak
  (order 3072, not primitive); strength chains use primitive roots.
- **A-TS "can't lie"** = tamper-EVIDENCE + proof-of-order. Tamper-PROOF additionally
  needs an external append-only anchor (not built) and a disciplined oscillator for
  absolute time.
- **A-PQC = Falcon, not Kyber/Dilithium.** 12289 is the Falcon/NewHope prime;
  Kyber (3329) / Dilithium (8380417) need a different datapath. Benchmark is a
  multiply-bound model on one core; the chip is **not** a per-op CPU-beater (wins on
  constant-time determinism + perf/watt + replication). Constant-time covers timing
  side-channels only — power/EM out of scope.
- **Path B** (general-purpose RNS processor) is deliberately deferred, not dead.
