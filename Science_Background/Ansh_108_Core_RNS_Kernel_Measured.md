# Ansh-108 Core — The RNS Kernel, Measured on Real Silicon

### Replacing the modeled cycle costs with rdtsc measurements — and how the verdict changed

*Sixth experiment, the empirical anchor for `..._Asiddha_Latency_Breakpoint.md`.
That file used a transparent cost MODEL (E=10, c=5, S=20 ns assumed). Here we
compiled a real RNS kernel in C (gcc 16.1.0, `-O2 -march=native`), measured the
actual costs with `__rdtsc()` calibrated to ns, and re-derived everything from
measured numbers. Created 2026-06-24. Source: `scratchpad/rns_kernel.c`. CPU:
TSC 2.400 GHz.*

---

## What was measured

A real kernel, serial data dependencies forcing true latency (the asiddha case),
results summed into volatile sinks so nothing is optimized away:

- **E** — one RNS transform over Z/108Z: decompose to (mod 4, mod 27), multiply
  on each track, recombine with `81a + 28b mod 108`.
- **c** — one rule-domain predicate (three feature comparisons).
- **S** — indexed selection: pointer advance + one domain check.

---

## Measured numbers (2.400 GHz, 1 tick = 0.417 ns)

| Quantity | Modeled (assumed) | **MEASURED** |
|---|---|---|
| E — RNS transform | 10 ns | **10.83 ns** (26.5 ticks) |
| c — one domain check | 5 ns | **0.417 ns** (1.9 ticks) |
| S — indexed select | 20 ns | **1.25 ns** (3.7 ticks) |
| **Crossover N\* = E/c** | 2 rules/step | **13.8 rules/step** |
| **Chip util (indexed) = E/(S+E)** | 33% | **87.9%** |

---

## The verdict changed — and that is the whole point of measuring

The model said the chip was **starved at 33% utilisation**, host-bound from step
one, crossover at just 2 rules. **Real silicon says the opposite: the chip runs
at 87.9% utilisation under indexed selection, and the host can weigh ~14 rules
per step before it becomes the bottleneck.**

Why the flip? The model guessed **S = 20 ns** for indexed selection. The real
cost is **1.25 ns** — 16× cheaper. A pointer-advance-plus-one-check is nearly
free; the model badly over-charged the brain. Meanwhile the transform costs
~10.8 ns, so the **muscle dominates the timeline and stays busy 88% of the
time.** The Ubuntu host is not the long pole after all — once the rules are
indexed, the 108-chip is well-fed.

**This is exactly why simulated numbers are a shadow.** The *structure* of the
model held perfectly — `util = E/(S+E)`, `N* = E/c`, the scan cliff, depth
irrelevance all reproduced. But the *constants* were wrong enough to invert the
headline conclusion, from "starved" to "well-fed." Only the silicon settled it.

---

## The scan cliff: confirmed, and sharper

Full O(N) scan of the rule base, measured per junction:

| Rules scanned | Per-junction latency | Chip utilisation |
|---|---|---|
| 16 | 15.3 ns | 42.0% |
| 256 | 159 ns | 6.5% |
| 4096 (full grammar) | **2 066 ns** | **0.53%** |

The cliff is real: scanning 4096 rules collapses the chip to **0.53%
utilisation** and inflates each junction to **2 microseconds**. A depth-5
asiddha chain under full scan measures **16.4 µs**; the same chain **indexed
measures 63 ns** — a **260× difference**, decided entirely by whether the host
scans or indexes. Pāṇini's tripādī ordering *is* that index. The measured cost
of not having it is three orders of magnitude.

---

## The honest caveat (this is the most important paragraph)

The measured **E = 10.8 ns is inflated because x86 has no native mod-27.** The
`% 27` and `% 108` compile to integer-division instructions (~26 cycles total) —
this is **limitation §6.3 ("the mod-27 reduction is not free") showing up as
literal silicon cost.** On a *real* RNS chip, mod-27 would be a small lookup
table (~1 cycle), dropping E to perhaps 1–2 ns.

That cuts both ways and must be said plainly:
- **On this CPU emulating RNS:** transform is div-bound (10.8 ns), so the chip
  looks well-fed at 88% and the crossover is a comfortable ~14 rules.
- **On true RNS hardware (LUT mod):** the transform would shrink to ~1–2 ns,
  pushing utilisation back *down* and the crossover back toward ~2–3 rules —
  closer to the pessimistic model. A faster muscle is *harder* to keep fed.

So the favourable 88% is partly an artifact of running RNS on a non-RNS CPU. The
**substrate-independent** results — the ones that survive either way — are:
1. the formulas `util = E/(S+E)` and `N* = E/c` (measured, exact);
2. the scan cliff (260× indexed-vs-scan, measured);
3. depth is never the limiter;
4. **indexing the rules is the one decision that matters**, on any substrate.

---

## Bottom line, plain English

We built the real kernel. On measured 2.4 GHz silicon the 108-chip is **not
starved — it runs at 88% utilisation** once the rules are indexed, and the host
can consider ~14 candidate rules per step before it becomes the bottleneck (the
model's "2" was pessimistic by 7×, because it over-charged indexed selection by
16×). The only thing that genuinely starves the chip is a brute-force O(N) scan
of the grammar — measured at 0.53% utilisation and 2 µs per junction for 4096
rules — and the fix is free: use Pāṇini's sequential rule order as the index, as
the firmware note put it, *he solved the O(N) scan 2,500 years ago.* The
measurement confirms the shape of that claim and corrects its magnitude: **index
the rules and the muscle stays ~88% busy; the real ceiling is the cost of the
modular reduction itself (§6.3), not the scheduler.**

---

## Reproducibility
- Compiler: `gcc 16.1.0` (WinLibs UCRT, installed via `winget` user-scope).
- Build: `gcc -O2 -march=native -o rns_kernel.exe rns_kernel.c`
- Gotchas hit & fixed: `OUT` is a reserved SAL macro in `windows.h` (renamed to
  `OUTER`); TSC calibrated against `QueryPerformanceCounter` over 0.25 s.
- Caveat: `__rdtsc()` counts a fixed-rate *reference* clock, not core cycles —
  fine for the ratios E:c:S and ns conversion, which is all we use.
- Measured: `E=10.83 ns · c=0.417 ns · S=1.25 ns · N*=13.8 · util=87.9% · scan-
  4096=2066 ns/0.53% · depth-5 indexed 63 ns vs scan 16.4 µs`.

### Cross-references
- The model this anchors: `Ansh_108_Core_Asiddha_Latency_Breakpoint.md`
- The mod-27 cost predicted here: `Ansh_108_Core_Technical_Proof_and_Limitations.md` §6.3
- The CRT recombine being timed: same proof file, §4
