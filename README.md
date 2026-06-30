# A0S — Ansh-108 Core (AS108)

A small, deterministic **residue / modular-arithmetic chip** and a set of host-side
applications built on top of it. The chip is a measured, place-and-routed design
(not a paper idea); the applications run **in pure Python with no FPGA board** and
are validated against the proven chip model — one of them all the way down to the
real RTL, and one all the way out to the **official NIST Falcon-512 test vectors**.

> Honesty first: every claim here is measured or proven, negative results are kept,
> and no number is a hope. The "what it is NOT" lists below are deliberate.

---

## What the chip is

A fixed-function modular-arithmetic engine over **Z/12289** (and an identity lane
over Z/108 = Z/4 × Z/27). Measured at Phase 4 (real Vivado P&R, xc7a35t):

| Spec | Measured |
|---|---|
| Core multiply `ntt_mul12289` | `(x·y) mod 12289`, Barrett, 4-stage, **bitwuzla full-correctness proof**, routed **109.3 MHz**, 178 LUT / 2 DSP |
| Identity lane `rns108` | `(x·y) mod 108`, CRT branch-free, routed **157.9 MHz**, 51 LUT / 0 DSP |
| Free-running clock | carry-free RNS {256,27,625}, monotonic + write-protected (no setter) |

**What it is NOT:** a general CPU, a float unit, or keyed crypto. Its edge is
*parallel, constant-time, zero-jitter modular arithmetic*, not single-thread speed.

---

## Headline result

The chip's 12289 lane is the NTT prime of **Falcon (NIST FN-DSA)**. The host-side
verifier built here, using the chip's NTT for the heavy polynomial multiply,
**accepts all 100 official Falcon-512 NIST KAT signatures and rejects tampering** —
a fully independent, externally-verifiable interop result. (Note: 12289 is the
Falcon/NewHope prime, *not* Kyber's 3329 or Dilithium's 8380417.)

---

## Run the demos

**Prerequisites:** Python 3.8+ (the core model, all applications, and all gates use
the **standard library only** — no `pip install` needed). One optional extra: the
hardware co-sim needs [Icarus Verilog](http://iverilog.icarus.com/).

All commands are run from the repository root.

### 1. The chip model (start here)
```sh
cd Core_Artifacts
python golden_model.py          # proven chip semantics — self-test, expect ALL PASS
```

### 2. Applications (pure Python, no board)
```sh
# A-TS — tamper-evident timestamped notarizer (proof-of-order)
python ats_notarizer.py             # gate (11/11)
python ats_notarizer.py --demo      # notarize a log, then catch a tamper
python ats_notarizer.py --measure   # measured collision + order-sensitivity

# A-FP — content fingerprinting / dedup
python afp_fingerprint.py           # gate (6/6)
python afp_fingerprint.py --demo    # dedup over a real corpus
python afp_fingerprint.py --measure # collision curve vs chain count

# A-AC — acoustic / rhythm fingerprinting (chant domain)
python aac_acoustic.py              # gate (synthesized audio, no files needed)
python aac_acoustic.py --demo       # exact-rhythm clustering + the honest limit
python aac_acoustic.py --wav FILE   # fingerprint a real local WAV (stays local)

# A-PQC — Falcon post-quantum signature verification on the chip's NTT
python apqc_ntt.py                  # negacyclic NTT gate (8/8)
python apqc_ntt.py --measure        # op-count benchmark + honest verdict
python apqc_falcon_verify.py        # Falcon-512 verify gate (9/9)
python apqc_falcon_verify.py --demo # accept + reject cases, with norms
python apqc_falcon_codec.py         # Falcon wire-format codec (8/8)
python apqc_interop_vector.py       # interop vs a genuine reference signature (5/5)
python apqc_kat_check.py            # *** 100/100 official NIST KAT vectors ***
```

### 3. Hardware co-simulation (optional — needs Icarus Verilog)
Proves the real integrated `core_top` RTL reproduces the A-TS stamps bit-for-bit.
On Windows the toolchain typically lives at `C:\iverilog\bin` (or oss-cad-suite).
```sh
cd Core_Artifacts
python cosim_ats.py                 # Leg 1: notarizer -> RTL vectors + golden
"C:\iverilog\bin\iverilog" -g2012 -o tb_cosim_ats.vvp core_top.v opcode_decode.v \
  result_mode.v rns_reduce.v tick_counter.v ntt_mul12289.v rns_add.v rns_sub.v \
  rns_verify.v fold_hash.v tb_cosim_ats.v
"C:\iverilog\bin\vvp" tb_cosim_ats.vvp
python check_cosim_ats.py           # gate: routed core_top == chain-0 stamp (5/5)
```

A fuller run/status index is in [`Core_Artifacts/README_ANSH_Apps.md`](Core_Artifacts/README_ANSH_Apps.md).

---

## Results at a glance

| Demo | Command | Gate |
|---|---|---|
| Chip model | `python golden_model.py` | ALL PASS |
| A-TS notarizer | `python ats_notarizer.py` | 11/11 |
| A-TS on real RTL | `check_cosim_ats.py` | 5/5 |
| A-FP fingerprinting | `python afp_fingerprint.py` | 6/6 |
| A-AC acoustic/rhythm | `python aac_acoustic.py` | ALL PASS |
| A-PQC Falcon NTT | `python apqc_ntt.py` | 8/8 |
| A-PQC Falcon verify | `python apqc_falcon_verify.py` | 9/9 |
| A-PQC Falcon codec | `python apqc_falcon_codec.py` | 8/8 |
| **NIST KAT cross-check** | `python apqc_kat_check.py` | **100/100** |

---

## Repository layout

```
Core_Artifacts/      RTL (.v), the chip model (golden_model.py), the apps, gates,
                     co-sim, and the NIST KAT vector. README_ANSH_Apps.md indexes it.
Science_Background/  Per-topic writeups (each Ansh_108_Core_*.md): the measured
                     baseline, formal proofs, the applications, and honesty ledgers.
Plans/               Build + applications plans.
Writeups/            Path-A build-arc session writeups (S2..S9).
```

---

## Honesty firewall (applies throughout)

- **Fingerprint, not keyed crypto.** A-TS / A-FP give integrity, proof-of-order, and
  dedup — *not* unforgeable signatures against a key-holding adversary.
- **A-PQC is a verifier, not a signer.** Signing (NTRU trapdoor + Gaussian sampler)
  and unforgeability are out of scope; the chip owns the NTT multiply, while hashing
  and the norm/compare stay host-side (the project's "Path A" division of labor).
- **Not a per-op CPU-beater.** The chip ~ties a CPU per operation; its wins are
  constant-time determinism (no timing side-channel), perf/watt, and replication.
  Constant-time covers timing channels only — power/EM are out of scope.
- A fuller benchmark + limitations live in `Science_Background/`.

---

*A0S Technologies — hardware. (Project Ansh, the music/Sanskrit work, is a separate
effort and is not in this repository.)*
