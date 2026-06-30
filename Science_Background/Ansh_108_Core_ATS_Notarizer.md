# ANSH-108 Core — A-TS: Tamper-evident Timestamped Notarizer

### Track-A application #1, built on the MEASURED golden model — no FPGA board

*Implements the three A-TS deliverables from `Ansh_108_Watch_and_Applications_Plan.md`
on top of the proven `golden_model.py`. The silicon does not change; this is a
host-side wrapper and is exactly the logic a later S9 host↔RTL co-sim would drive.
Created 2026-06-30. Standing rule honored: every claim here is measured or proven,
negative results kept, no number is a hope. Code: `Core_Artifacts/ats_notarizer.py`.*

---

## 1. Why this is the right first app (and why it needs no board)

The chip's genuine edge is **parallel, deterministic, zero-jitter modular arithmetic**
with a **monotonic, write-protected counter** (no setter exists — proven in S4). That
combination is exactly a *proof-of-order timestamp*: a value that **cannot be rewound or
forged**, fused to a **content fingerprint**. A normal CPU does the hashing faster, but it
does **not** give you a tick that is monotonic *by construction*.

No hardware is required to build or measure this. The whole stack runs against
`golden_model.py` (the software source-of-truth every later RTL artifact is checked
against). A board would only let us measure real-world *drift/power* later (Phase 7); it
adds nothing to proving the logic or shipping the app.

---

## 2. What was built (`ats_notarizer.py`)

| Piece | What it is | Reuse anchor |
|---|---|---|
| `MultiChainFold` | N parallel Horner hashes `h_i ← (h_i·B_i + foot) mod 12289` | step is **identical** to golden FOLD (line 199); chain 0 (B=108, seed=1) reproduces it byte-for-byte |
| `Notarizer` | append-only log; each event bound to a fresh monotonic tick, then FOLDed | proven `RnsCounter` (monotonic, no setter) + proven `slice_bits_to_feet` |
| `verify()` | independent replay: tick-monotonicity + per-entry snapshot + final root | — |

**Base selection (honest design choice).** Q = 12289 is prime, Q−1 = 12288 = 2¹²·3.
Chain 0 keeps the canonical base **108** so it equals the proven core. Strength chains
1…7 use **primitive roots** (multiplicative order = Q−1 = 12288) for maximal diffusion.
The "108-bit fingerprint" target falls out of the chip's own number: log₂(12289) = 13.585,
and **8 × 13.585 ≈ 108.7 bits**.

---

## 3. Verification gate — ALL PASS (11/11)

`python ats_notarizer.py`

- **chain 0 == proven golden FOLD** over the same feet — reuse, not reinvention ✓
- 8 distinct bases; chain 0 = 108; strength chains are primitive roots (order 12288) ✓
- clean log VERIFIES ✓
- **content edit → TAMPER DETECTED** ✓
- **reorder → TAMPER DETECTED**, and specifically breaks tick monotonicity ✓
- **deletion → TAMPER DETECTED** ✓
- multi-chain FOLD is order-sensitive (ab ≠ ba) ✓
- tick cannot be rewound (monotonic, no setter) ✓

---

## 4. Measured numbers (firewall: MEASURE collisions, don't assume)

`python ats_notarizer.py --measure` (reproducible, seed = 108)

**Per-chain birthday collision — matches the √(πQ/2) prediction:**

| Configuration | State space | Birthday prediction | **Measured** mean first collision |
|---|---|---|---|
| 1 chain, B = 108 | Q = 12289 | ~139 msgs | **133.4** (40 trials) |
| 1 chain, B = 11 (primitive) | Q = 12289 | ~139 msgs | **139.7** (40 trials) |
| 2 chains (108 + 11) | Q² = 1.51×10⁸ | ~15,402 msgs | **14,344** (8 trials) |

**Honest negative finding:** base **108 is *not* a primitive root** mod 12289 — its order
is only **3072** (= Q−1 ÷ 4). Single-chain birthday is still ~Q because input entropy
dominates, but this is exactly **why 108 is never used as a lone fingerprint** and why the
strength chains use primitive roots.

**Scaling (extrapolated honestly — NOT a 2⁵⁴ search):** each added chain multiplies the
state space by Q, so collision resistance ≈ Q^(N/2):

| Chains | Fingerprint width | Collision resistance |
|---|---|---|
| 1 | 13.6 bit | 6.8 bit |
| 2 | 27.2 bit | 13.6 bit |
| 4 | 54.3 bit | 27.2 bit |
| **8** | **108.7 bit** | **~54 bit** |

The two-chain point (predicted 13.6-bit ≈ 15.4k msgs, **measured 14.3k**) confirms the
per-chain ×Q scaling; the 8-chain figure is *projected from that confirmed scaling*, not
brute-forced.

**Order-sensitivity:** 5000 random permutations of a fixed 12-event multiset →
**5000 distinct roots, 0 cross-order collisions.** Any reorder changes the root.

---

## 5. Threat model — what "can't lie" does and does NOT cover (A-TS-3)

**Covered (provable from this build):**
- **Tamper-evidence of a held log:** any edit, reorder, or deletion fails `verify()` —
  caught by ≥1 of {tick-monotonicity, per-entry snapshot, final-root recomputation}.
- **Proof-of-order:** events are bound to a strictly increasing tick; you cannot present
  a reordered log whose ticks still increase *and* whose root recomputes.
- **Determinism / reproducibility:** same inputs → same root, bit-exact, zero-jitter.

**NOT covered (must be stated to every customer):**
- **Absolute time** is only as good as the **oscillator** (Phase-7 / W4 budget). "Monotonic
  + write-protected" ≠ "the wall-clock is correct." Needs a disciplined reference (TCXO/GPS).
- **Adversary who controls the host and rewrites the *entire* log** can recompute a fresh
  consistent root. Defeating that needs an **external anchor** the attacker can't rewrite —
  publish/notarize the root to an append-only/third-party log (the real-world deployment step).
- **Not keyed crypto.** Z/12289 is unkeyed; this is integrity/order, not unforgeable
  signatures against a key-holding adversary. For that, this is the zero-jitter datapath
  *under* a real keyed construction — a separate design.
- **Side channels:** constant-time math defeats **timing** channels only — not power/EM, and
  only if the whole host datapath stays constant-time.

---

## 6. Honesty ledger

- ✅ Reuses the proven golden FOLD/counter/slicer; chain 0 == golden FOLD asserted in the gate.
- ✅ Collision + order claims are **measured**; scaling is extrapolated from a *confirmed*
  two-chain point, explicitly not a 2⁵⁴ search.
- ⚠️ Negative result kept: base 108 has order 3072 (not primitive) → never used alone.
- ⚠️ "~54-bit collision resistance" is a *projection*; the deployment anchor (§5) is the part
  that makes it tamper-*proof* rather than tamper-*evident*, and that is not in this code yet.
- ⛔ No keyed/adversarial-crypto claim. No absolute-time claim without an oscillator budget.

---

## 7. Next steps (optional)

- **A-FP** reuses `MultiChainFold` directly for content dedup/content-ID over a real corpus
  (e.g. the SHOALKS chant assets) — the collision curve is already measured here.
- **External anchor** (§5): emit the root to an append-only sink to upgrade evidence → proof.
- **S9 hardware echo:** drive the same events through host↔RTL co-sim so a routed FOLD chain
  reproduces chain 0's stamps — closes the loop from this host app to the measured silicon.

### Cross-references
- Plan: `../Plans/Ansh_108_Watch_and_Applications_Plan.md` (A-TS-1/2/3)
- Reused (not rebuilt): `../Core_Artifacts/golden_model.py`
- Directory & firewall: `Ansh_108_Core_Applications_Directory.md`
- Code: `../Core_Artifacts/ats_notarizer.py` (`--measure`, `--demo`)
