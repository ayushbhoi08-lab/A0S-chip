# Ansh-108 Core — Path A, S9: Host ↔ RTL Co-Simulation (Phase 5)

**Status: DONE (2026-06-29). The software↔RTL capstone.** The chant drove the
*actual chip design* — verified in simulation. This closes the last pre-silicon
gap every prior ledger admitted: the host packet stream was proven only against the
**software** golden model, never against the **RTL** `core_top`. S9 drives the real
RTL with the real host pipeline and proves they agree end to end.

> **Honest scope.** S9 is the software↔RTL capstone, **NOT silicon.** It is a
> host→RTL co-simulation in Icarus Verilog. No board bring-up is claimed. Everything
> *below physical hardware* is now closed; the **physical FPGA board (Phase 7) is the
> only unclosed frontier** — the last rung of the ladder.

---

## 1. What S9 adds (and what it must NOT touch)

S9 adds **only** the co-sim harness + comparator. It does **not** edit any proven
module. `core_top.v` + its 9 submodules are S4/S5-proven (13 formal properties +
6000-op replay); `host_staging.py` (S6), `staging_agent.py`/`transport.py`/
`result_reader.py` (S7), `a0s_parser.py`/`ashta_dik.py` (S8), and `golden_model.py`
(S1) are test-proven. S9 *imports* them — asserted, not copied (see §3, Leg 1).

New artifacts (all in `Ansh_108_Core_Artifacts/`):

| File | Role |
|---|---|
| `cosim_s9.py` | **Leg 1 driver.** Builds the battery with the REAL host path, computes the golden fingerprints, emits `cosim_vectors.txt` (the packet stream) + `cosim_golden.txt` (the expected sidecar). |
| `tb_cosim_s9.v` | **Leg 2 testbench.** Reads the vectors, drives the REAL `core_top` with the locked protocol, writes `cosim_rtl_out.txt`. |
| `check_cosim_s9.py` | **The integration gate.** Compares RTL vs golden; asserts (a) fp==golden, (b) bindu-terminated, (c) order-sensitive, (d) VERIFY/REDUCE/READ_TICK match. |
| `cosim_chants/*.txt` | 5 real chant `.txt` (gAyatrI, mahAmRtyuMjaya, zAnti, asato mA, gaNeza), Harvard-Kyoto ASCII. |
| `run_cosim_s9.bat` | One-shot 2-leg driver. |

---

## 2. The battery — 29 programs, 137 packets

| Class | Count | Members |
|---|---|---|
| **Corners** | 7 | `empty` (→ single zUnya foot), `one_laghu` (1 bit), `one_guru` (1 bit, MSB), `exact_28` (one full foot), `twentynine` (1 over → 2 feet), `fiftysix_plus1` (2 full + 1 → 3 feet), `long_mantra` (23 feet) |
| **Order pair** | 2 | `order_aA`, `order_Aa` (checked distinct on the RTL) |
| **Real chant `.txt`** | 6 | `sample_chant` (Rgveda 1.1.1) + `cosim_chants/` gAyatrI · mahAmRtyuMjaya · zAnti · asato_mA · gaNeza |
| **A0S programs** | 10 | every `a0s_programs/*.txt` (S8) — incl. early-bindu abort, sunya-clear, control digits, all 8 directions, multi-maNDala |
| **Op programs** | 4 | `op_verify` (5), `op_reduce` (5), `op_arith` (MUL/ADD/SUB, 5), `op_readtick` (2 reads) |

The packet streams are produced **literally** by the real host code:
`host_staging.text_to_fold_packets` (chants/corners), `a0s_parser.compile_file`
(A0S), `host_staging.assemble` (op programs). No re-implementation.

---

## 3. Verification gate — both legs green

### Leg 1 · Python (golden = the real host path)
`cosim_s9.py` asserts at import time that the host functions live in their proven
modules (`__module__ == "host_staging" / "a0s_parser" / "golden_model" /
"result_reader"`) — imports, not copies. For every chant it cross-checks **four**
independent golden routes agree before emitting:

```
host_staging.fold_fingerprint(text)
  == golden_model.fold_text(text)
  == result_reader.fold_fingerprint(LoopbackTransport().send(packets))   # S7 loopback
  == last_committed_fp(packets)                                          # multi-maNDala rule
```

For A0S it uses `a0s_parser.CompileResult.fingerprint` (last committed maNDala) and
asserts it equals the same loopback `last_committed_fp`. Op-program expected values
come from `golden_model.AnshCoreGolden.execute`.

### Leg 2 · RTL co-sim (the real `core_top`)
```
iverilog -g2012 -o tb_cosim_s9.vvp \
    core_top.v opcode_decode.v result_mode.v rns_reduce.v tick_counter.v \
    ntt_mul12289.v rns_add.v rns_sub.v rns_verify.v fold_hash.v tb_cosim_s9.v
vvp tb_cosim_s9.vvp        # -> cosim_rtl_out.txt
```
The TB drives the locked protocol: FOLD streamed 1/cycle, the **last FOLD result is
captured before the bindu RESET** (read-before-reseed, the S6 contract), gated ops
(VERIFY/REDUCE/READ_TICK/MUL/ADD/SUB) issued single-in-flight and awaited, RESET
fires and its single bindu pulse is counted. A **continuous tick monitor**
(`tick == cyc mod m_i` every cycle while real packets fly) re-proves the
free-running, write-protected Maha-Yuga clock across the whole run.

**Result: 29/29 programs match, 137 packets driven, 0 mismatches, 0 mid-stream
gaps, tick monitor clean (0 errors).**

```
    pid program                kind   golden     rtl  bindu  feet  ops  result
      0 empty                  chant     108     108      1     1    0  PASS
      1 one_laghu              chant     108     108      1     1    0  PASS
      2 one_guru               chant    9667    9667      1     1    0  PASS
      3 exact_28               chant     108     108      1     1    0  PASS
      4 twentynine             chant   11664   11664      1     2    0  PASS
      5 fiftysix_plus1         chant    3101    3101      1     3    0  PASS
      6 long_mantra            chant    2032    2032      1    23    0  PASS
      7 order_aA               chant   11032   11032      1     1    0  PASS
      8 order_Aa               chant    9667    9667      1     1    0  PASS
      9 sample_chant           chant    9033    9033      1     5    0  PASS
     10 chant_asato_mA         chant    4956    4956      1     4    0  PASS
     11 chant_gAyatrI          chant    2680    2680      1     6    0  PASS
     12 chant_gaNeza           chant   11507   11507      1     2    0  PASS
     13 chant_mahAmRtyuMjaya   chant    8678    8678      1     5    0  PASS
     14 chant_zAnti            chant    4585    4585      1     6    0  PASS
     15 a0s_01_basics          a0s      8984    8984      1     1    0  PASS
     16 a0s_02_early_bindu     a0s      8301    8301      2     1    0  PASS
     17 a0s_03_hold            a0s      2193    2193      1     2    0  PASS
     18 a0s_04_control_digits  a0s      4240    4240      1     2    0  PASS
     19 a0s_05_sunya           a0s       108     108      1     1    0  PASS
     20 a0s_06_comments        a0s      1474    1474      1     1    0  PASS
     21 a0s_07_cardinal        a0s      2399    2399      1     4    0  PASS
     22 a0s_08_diagonal        a0s     11070   11070      1     4    0  PASS
     23 a0s_09_scan            a0s      3316    3316      1     4    0  PASS
     24 a0s_10_full_mandala    a0s     11604   11604      2     4    0  PASS
     25 op_verify              op          1       1      1     0    5  PASS
     26 op_reduce              op          1       1      1     0    5  PASS
     27 op_arith               op          1       1      1     0    5  PASS
     28 op_readtick            op          1       1      1     0    2  PASS

  gate legs:
    [PASS] golden sidecar reproducible from the real host path (cosim_s9.build_battery)
    [PASS] every program: RTL fingerprint == golden, bindu-terminated, ops match (29 programs, 0 mismatch)
    [PASS] order sensitivity on RTL: fp(aA)=11032 != fp(Aa)=9667
    [PASS] READ_TICK monotonic across reads (advancing clock): [647, 657]
    [PASS] TB tick monitor clean over the whole battery (tick_errors=0)
    [PASS] TB program count == battery size
  ALL PASS
```

The four required comparator checks, all green:
- **(a) RTL fingerprint == golden** for every program (incl. multi-maNDala A0S, where
  `bindu=2` for `a0s_02_early_bindu` and `a0s_10_full_mandala`).
- **(b) bindu-terminated**: `bindu_count == reset_count == golden #maNDalas`, 0 gaps —
  every RESET fires exactly one bindu pulse, no spurious.
- **(c) order sensitivity on the RTL**: `fp("aA")=11032 ≠ fp("Aa")=9667`.
- **(d) VERIFY/REDUCE/arith == golden exactly**; **READ_TICK** residues in range, host
  CRT reconstruction self-consistent (`host_ops.reconstruct == golden crt_reconstruct
  == Garner mixed_radix`), within one Maha-Yuga, and **monotonic** across reads
  (`[647, 657]` — the write-protected clock advanced).

No regression: S1/S6/S7/S8 gates and the S4 `tb_core_top` (6000-op replay) all re-run
green on the reused, unmodified RTL.

---

## 4. Honesty ledger

- **What this proves:** the *host → RTL* link, in **simulation** (Icarus). The exact
  packet stream the real staging agent emits, executed by the real `core_top` Verilog,
  produces the same fingerprints / op results as the software golden — across chants,
  every A0S construct, corners, and the op contracts. "The chant drove the actual chip
  design" is now true (in sim).
- **Why the chain is sound:** the golden is itself **S4-RTL-validated** (the 6000-op
  golden replay 0-mismatch against `core_top`), so golden ≈ RTL was already strong;
  S9 makes it a *direct* host→RTL equality across a fresh battery.
- **READ_TICK is honest about a free-running clock:** the tick's *absolute* value is
  hardware-cycle determined, not host-predictable. The continuous monitor proves
  `tick == cyc mod m_i` every cycle (correct + write-protected); the host-meaningful
  golden for READ_TICK is the **CRT reconstruction + range + monotonicity** (the
  Path-A fence: chip returns residues, host recombines), all verified — not a single
  host-baked constant.
- **Read-before-bindu is real:** the TB captures the last FOLD result *before* issuing
  each RESET; the RESET then reseeds `fold_hash` (confirmed because every subsequent
  maNDala folds from the seed, and multi-maNDala A0S streams resolve to the
  last-committed fingerprint). `fold_hash` suppresses `out_valid` on flush, so even a
  back-to-back RESET cannot clobber the captured fingerprint.
- **Multi-maNDala rule:** the program fingerprint is the **last committed maNDala's**
  pre-bindu fold (aborted `..` maNDalas contribute only a bindu); both the RTL TB and
  the golden `last_committed_fp` apply this identical rule — they agree.
- **The only unclosed frontier:** the **physical FPGA board (Phase 7)**. Everything
  below physical hardware — datapath, integrated core, formal, synth/P&R, host
  pipeline, grammar/geometry, and now the host↔RTL co-sim — is closed. This is exactly
  how a chip is signed off before fab.

---

## 5. Toolchain notes (new this stage)

- **`-g2012` Icarus**, same 10-file source list as the S4 synth (`core_top` + 9
  submodules). The vector/result files are plain ASCII, read/written with
  `$fscanf`/`$fdisplay` from the artifacts dir.
- The TB writes a program's `O` (op) lines as it runs but its `P` (summary) line at
  **program close** — so `O` lines precede their `P`. The comparator's RTL parser is
  therefore order-tolerant (`setdefault`/merge, never overwrite the ops list).
- **`fold_hash` flush suppresses `out_valid`** (`out_valid <= fold_en & ~flush`), which
  is why the last FOLD result survives a RESET issued one cycle later — the basis for a
  robust read-before-bindu capture.
- Decoupled fold-burst capture (collect all FOLD `out_valid`s *before* firing the
  segment's RESET) is the simplest faithful realization of the read-before-reseed
  contract; it also yields the 0-gap (1/cycle) throughput check for free.

---

## 6. Reproduce

```
run_cosim_s9.bat
# or, from the artifacts dir:
python cosim_s9.py
iverilog -g2012 -o tb_cosim_s9.vvp core_top.v opcode_decode.v result_mode.v \
    rns_reduce.v tick_counter.v ntt_mul12289.v rns_add.v rns_sub.v rns_verify.v \
    fold_hash.v tb_cosim_s9.v
vvp tb_cosim_s9.vvp
python check_cosim_s9.py        # ALL PASS, exit 0
```
