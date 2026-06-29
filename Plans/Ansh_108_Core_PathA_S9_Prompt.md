# Ansh-108 Core — Path A, Session S9 prompt (paste into a fresh session)

Continue the Ansh-108 Path A build (master plan: `Ansh_108_Core_PathA_Build_Plan.md`, §3 / §5 row S9). All artifacts live in `...\02_WORLD_BIBLE\Science_Background\Ansh_108_Core_Artifacts\`.

**Do S9 = host<->RTL co-simulation — close the last open gap.** Every prior ledger says the same owed item: the host packet stream is proven only against the *software* golden model, never against the *RTL* `core_top`. S9 drives the **real RTL** with the **real host pipeline** and proves they agree end to end: a chant `.txt` -> `host_staging` / `staging_agent` packet stream -> Icarus-simulated `core_top.v` -> fingerprint read back == golden `fold_text` fingerprint. After S9 you can honestly say "the chant drove the actual chip design," verified in simulation.

**Reuse, do NOT rebuild.** `core_top.v` + all 9 submodules are S4-proven (5 legs green). `host_staging.py` (S6) and `staging_agent.py` / `result_reader.py` (S7) are test-proven. `golden_model.py` (S1) is the source of truth. S9 adds ONLY the co-sim harness + comparator; it must NOT edit any proven module.

**Build (all in `Ansh_108_Core_Artifacts/`):**
1. `cosim_s9.py` — the driver. For each input (a battery of real chant `.txt` files + the S8 `a0s_programs/*.txt` directional programs + corner cases: empty, 1 bit, exact-28, 29, 56+1, a long mantra), call the **real host path** (`text_to_fold_packets` / the staging agent) to get the exact 32-bit packet stream, compute the **expected** fingerprint from `golden_model.fold_text` / `fold_fingerprint`, and emit a vectors file (`cosim_vectors.txt`: one hex packet per line, with a sidecar of expected results). Keep the host path the literal S6/S7 code — no re-implementation.
2. `tb_cosim_s9.v` — an Icarus testbench that reads `cosim_vectors.txt`, drives `core_top` with the exact protocol (assert `in_valid`; honor `busy` for gated ops; stream FOLD 1/cycle; capture the last FOLD result **before** the bindu RESET; also exercise a few VERIFY / READ_TICK / REDUCE packets so non-FOLD opcodes are co-sim'd too) and writes RTL results to `cosim_rtl_out.txt`.
3. `check_cosim_s9.py` — compares `cosim_rtl_out.txt` vs the golden expected file; asserts (a) RTL fingerprint == golden fingerprint for every program, (b) every stream terminates in exactly one bindu, (c) order-sensitivity holds (`aA` != `Aa`) on the RTL, (d) any VERIFY / REDUCE / READ_TICK packets match golden. Print a per-program PASS table + an ALL PASS / FAIL summary.

**Verification gate (this is the integration leg):**
- Leg 1 · Python: golden expected computed; the host path is the real S6/S7 code (assert imports, not copies).
- Leg 2 · RTL co-sim: `iverilog -g2012` build of `core_top.v` + all 9 submodules + `tb_cosim_s9.v`; `vvp` run; **RTL result == golden across the whole battery, 0 mismatches**, bindu-terminated, order-sensitive.
- Report the battery size (N programs, total packets). Keep it honest.

**Rules (unchanged, enforced):**
- Empirical-honesty rule: no faked legs; negative results stay in the ledger. If any program mismatches, report it — do not hide or massage it.
- Strict Harvard-Kyoto ASCII in ALL new code / comments / strings / docstrings (zUnya, aSTa-dik, pAda, bindu, Maha-Yuga, etc.) — no diacritics, per the locked constraint.
- iverilog `-g2012`. If you touch formal (not required for S9), kill stale oss-cad procs by path `C:\oss-cad-suite\*` before `sby`.
- S4 latency facts still hold (core latency = datapath + 1; FOLD throughput 1/cycle; fingerprint read before the bindu reseed) — the TB must respect them.

**On done:** write `Ansh_108_Core_PathA_S9_CoSim.md` (what was built, the co-sim gate with the per-program table, an honesty ledger — including that this proves the host->RTL link **in simulation**; the physical FPGA board remains the only unclosed frontier). Update the plan's S9 row and the `project_ansh108_pathA_build` memory.

**Honest scope:** S9 is the software<->RTL capstone, NOT silicon. Do not claim a board bring-up. State plainly that everything below physical hardware is now closed and the board is the next / last rung.
