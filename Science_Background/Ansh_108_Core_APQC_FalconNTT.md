# ANSH-108 Core — A-PQC: Post-Quantum (Falcon) NTT accelerator

### Track-A application #3, built on the proven 12289 lane — no FPGA board

*Implements the three A-PQC deliverables. Maps the negacyclic NTT of lattice
signatures onto the chip's measured `ntt_mul12289` op. Created 2026-06-30.
Standing rule honored. Code: `Core_Artifacts/apqc_ntt.py`.*

---

## 1. HONESTY CORRECTION to the plan (the headline)

The Watch & Applications Plan states *"12289 is the Kyber/ML-KEM & Dilithium NTT
prime."* **That is wrong, and it changes the whole pitch:**

| Scheme | NTT prime q |
|---|---|
| Kyber / ML-KEM (FIPS 203) | **3329** |
| Dilithium / ML-DSA (FIPS 204) | **8380417** |
| **Falcon / FN-DSA (FIPS 206)** | **12289** ← the chip's prime |
| NewHope (deprecated) | 12289 |

So the 12289 lane **natively accelerates Falcon / NewHope, not Kyber/Dilithium.**
Kyber and Dilithium use a *different* modulus → a *different* datapath (Class B),
not this core. `q − 1 = 12288 = 2¹²·3`, so 12289 supports a negacyclic NTT up to
**n = 2048**; Falcon uses **n = 512 and n = 1024**. This correction is logged per
[[feedback_empirical_verification]] — better an accurate Falcon story than a false
Kyber one.

---

## 2. What was built

Forward + inverse **negacyclic NTT** over Z₁₂₂₈₉[x]/(xⁿ+1) via ψ pre/post-scaling
(ψ = primitive 2n-th root, ω = ψ²). **Every multiply is routed through `chip_mul`
= `(x·y) mod 12289` — the proven `ntt_mul12289` op** (Barrett, 4-stage, routed
**109.3 MHz**, 178 LUT/2 DSP, **bitwuzla full-correctness proof**); every add/sub
is `(x ± y) mod 12289`. Validated against a schoolbook negacyclic reference.

---

## 3. A-PQC-1 — verification gate, ALL PASS (8/8)

`python apqc_ntt.py`

- n = 256 / 512 / 1024: **INTT(NTT(a)) == a** (roundtrip) ✓
- n = 256 / 512 / 1024: **NTT mult == schoolbook negacyclic** (5 random pairs each) ✓
- **constant-time:** op counts identical for all-zero vs random input ✓
- `chip_mul == (x·y) mod 12289` — the multiply literally is the proven chip op ✓

**The multiply needs no fresh RTL echo:** `ntt_mul12289` carries a *full-correctness*
proof (bitwuzla, all 12289² inputs), so **every butterfly multiply in this NTT is
already proven on the routed core** — a stronger statement than sampling pairs in sim.

---

## 4. A-PQC-2 — constant-time / side-channel scope

- The butterfly network is **data-independent control flow** — the op count depends
  only on n, never on the coefficients (asserted in the gate). That defeats **timing**
  side-channels, *provided the whole host datapath stays constant-time too*.
- **Out of scope:** power and EM side-channels — not addressed by constant-time math;
  they need separate countermeasures (masking, hiding). Stated plainly, not hidden.

---

## 5. A-PQC-3 — benchmark + honest verdict

`python apqc_ntt.py --measure`

| n | fwd-NTT muls | 1× neg-mul muls | mul-bound cycles | @109.3 MHz |
|---|---|---|---|---|
| 512 | 4,608 | 16,384 | 16,384 | **149.9 µs** |
| 1024 | 10,240 | 35,840 | 35,840 | **327.9 µs** |

**Honest reading of these numbers:**
- "cycles" counts **multiplies only**, on a *single* pipelined `ntt_mul` core
  (1 result/cycle). Adds/subs, host orchestration, and memory traffic are **not**
  counted → the µs figure is a multiply-bound **lower bound**, not a wall-clock.
- **Not a per-op CPU-beater:** a modern CPU does one 12289-multiply about as fast.
  The chip's real wins are: **constant-time determinism** (no data-dependent branch →
  no timing channel), **perf/watt**, and **replication** (many `ntt_mul` cores running
  independent butterflies in lockstep — the documented architecture advantage).

---

## 6. Honesty ledger

- ✅ Corrected the plan's prime error: 12289 = **Falcon**, not Kyber/Dilithium.
- ✅ Multiply is the proven chip op; correctness is the existing bitwuzla full proof,
  not a hand-wave or a weaker sampled sim.
- ✅ NTT validated against an independent schoolbook reference at all Falcon sizes.
- ⚠️ Benchmark is a multiply-bound model on a single core, explicitly labelled — no
  end-to-end wall-clock or speedup is claimed.
- ⚠️ Constant-time covers timing only; power/EM out of scope.
- ⛔ This is the NTT inner engine, **not** a full Falcon signer (Gaussian samplers,
  FFT over the reals, key handling are separate and not built here).

---

## 7. Next steps

- A real Falcon-512 sign/verify harness that calls this NTT for the polynomial
  products, benchmarked against a reference Falcon (e.g. PQClean) — host-side.
- A **Class-B** sketch for Kyber (q=3329) / Dilithium (q=8380417): what a configurable-
  modulus datapath would cost, since this lane cannot do them.
- Optional: a replication study — N `ntt_mul` cores vs the LUT budget (reuse the
  `gen_rns` fmax-vs-width curve lessons).

### Cross-references
- Plan: `../Plans/Ansh_108_Watch_and_Applications_Plan.md` (A-PQC-1/2/3)
- Proven multiply: `Ansh_108_Core_Verilog_RTL_Phase2.md` (ntt_mul12289 + bitwuzla)
- Code: `../Core_Artifacts/apqc_ntt.py` (`--measure`)
