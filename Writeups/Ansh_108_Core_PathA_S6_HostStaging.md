# Ansh-108 Core — Path A, Session S6: host staging agent (parser / slicer / assembler)

### The front chamber's data path — a chant `.txt` becomes the exact packet stream the core eats

*Path-A Phase-3 deliverable (plan §3 Phase 3 / §5 row S6). The first **host-side**
session — an independent track from the chip (S1–S5), built in pure Python and
cross-checked against S1's `golden_model.py` (the source of truth). No Verilog, no
FPGA tooling touched. Created 2026-06-28. Tools: Python 3.14. Artifacts in
`Ansh_108_Core_Artifacts/`.*

---

## What was built

| File | Role |
|---|---|
| `host_staging.py` | parser + slicer + assembler + CLI (the staging agent's data path) |
| `test_host_staging.py` | unit tests + golden cross-checks + software loopback |
| `sample_chant.txt` | a demo chant for the CLI |

**1. parser** — `parse_text` / `parse_file`: map `a..z → 0` (laghu), `A..Z → 1`
(guru), strip everything else (digits, spaces, punctuation, comments). Mirrors the
locked `a→0 / A→1` rule.

**2. slicer** — `slice_feet`: pack the bitstream **MSB-first** into 28-bit feet (the
packet data field); the **final foot is left-aligned and zUnya-padded** (zeros on
the right) so the chant's tail still folds. Returns a `SliceResult` carrying the
feet, the zUnya `pad_bits`, the true `n_bits`, and the `final_index` (so the host
knows the real length even though the chip only sees padded feet). Empty input → a
single all-zUnya foot.

**3. assembler** — `pkt_fast` (fast lane `data = Y<<14 | X`), `pkt_data` (flexible
28-bit lane), `assemble_fold` (FOLD stream + appended **bindu exit** = RESET op 15),
and a general `assemble(ops)` that builds any opcode with the right hybrid layout and
injects the bindu unless the program already ends in RESET.

**Pipeline + contract** — `text_to_fold_packets` (parse→slice→assemble FOLD+bindu)
and `fold_fingerprint` (the Horner `h←(h·108+foot) mod 12289`, seed 1, that the host
expects the core's FOLD stream to produce, read **before** the bindu reseeds).

**CLI** — `python host_staging.py <chant.txt>` prints the packet stream + the
fingerprint. On `sample_chant.txt`: 126 laghu/guru bits (99 laghu / 27 guru) → 5
feet (final foot zUnya-padded 14 bits) → **6 packets** (5 FOLD + 1 bindu RESET) →
fold fingerprint **9033 (0x2349)**.

---

## Verification — ALL PASS (`test_host_staging.py`, 17 checks)

This is a **software** phase, so the gate is unit tests + golden cross-check +
software loopback (not the 5-leg silicon gate). The **hardware** co-sim that drives
the real `core_top` RTL is Phase 5 / S9 — explicitly out of scope here.

| Group | Check | Result |
|---|---|---|
| parser | case-map + strip; empty cases; **== golden `text_to_bits` over 5000 random strings** | PASS |
| slicer | zUnya-pad directed vectors; empty→[0]; exact-multiple→0 pad; **== golden `slice_bits_to_feet` over 5000 random lengths**; pad accounting `28·nfeet == nbits + pad` | PASS |
| assembler | `pkt_fast/pkt_data == golden encode_* (20k)`; fast-lane **round-trips through golden `decode_packet` (20k)**; FOLD-stream + single bindu structure; general `assemble` round-trip + bindu injection (and no double-bindu) | PASS |
| **loopback** | **host stream → executed by golden core == `fold_text(text)` == `fold_fingerprint` over 3012 chants**; every stream ends in the bindu exit; order-sensitive (`aA≠Aa`); deterministic | PASS |

**The headline (loopback) contract holds:** for 3012 chants (incl. corners — empty,
single bit, exact-28, 29, 56+1, real mantra text), the packet stream the host emits,
when run through the known-good golden core, reproduces the golden fingerprint
exactly, and always terminates in the bindu. The host turns a `.txt` into precisely
the stream a known-good core consumes — the S6 done-criterion.

---

## Honesty ledger

1. **Software loopback only — hardware co-sim is S9.** S6 proves the host stream is
   correct against the *software* golden model, not yet against the *RTL* `core_top`.
   That hardware drive (host → iverilog `core_top` → result) is Phase 5 / S9 by plan;
   not claimed here. (The golden model is itself RTL-validated in S4's 6000-op replay,
   so the chain is sound — but the literal host↔RTL link is still owed.)
2. **Fingerprint is read before the bindu.** The trailing RESET (bindu) reseeds the
   fold accumulator, so the fingerprint must be captured from the last FOLD result
   *before* RESET — the loopback test does exactly that, and this is the contract the
   S7 `usb_stream`/result-reader must honor.
3. **Constants imported, algorithms independent.** `host_staging.py` pulls the locked
   constants (opcodes, field widths, Q, B, seed) from `golden_model.py` (one source
   of truth) but implements parse/slice/assemble independently; the tests prove the
   independent algorithms equal golden's reference helpers. Not a copy.
4. **Padding is part of the fingerprint, by design.** The zUnya pad on the final foot
   is folded in (matching `fold_text`), so two chants differing only in trailing
   length can still collide if they share padded feet — acceptable for a chant
   fingerprint; `n_bits`/`pad_bits` are retained if a length-exact scheme is wanted later.

---

## Reproducibility
```
# tests:  python test_host_staging.py        -> ALL PASS (17 checks, incl. 3012-chant loopback)
# CLI:    python host_staging.py sample_chant.txt
```

### Cross-references
- Plan: `Ansh_108_Core_PathA_Build_Plan.md` (§3 Phase 3, §5 row S6)
- Source of truth: `golden_model.py` (S1) — host-side helpers `text_to_bits`,
  `slice_bits_to_feet`, `encode_*`, `decode_packet`, `fold_text` (cross-check targets)
- Consumes the packet format proven in S4 (`core_top` / `opcode_decode`).
- **Next: S7** — the rest of the staging agent: clock/LED state machine
  (Laghu/Guru ISI timing), `usb_stream` (whole-packet send + result-mode reader),
  and `host_ops` (the positional fallbacks: shift/rotate/reverse aSTa-dik, bitwise,
  magnitude-compare). Then **S8** (A0S grammar) and **S9** (host↔RTL co-sim).
