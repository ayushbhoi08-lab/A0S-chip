# Ansh-108 Core — Path A, S8: A0S Grammar + ASTa-Dik Geometry Layer

**Phase 4 (the human-facing language). Pure Python / grammar — NO FPGA tools, NO
silicon change.** The aSTa-dik is a host-side permutation: the Path-A fence holds,
the residue chip's proven math is untouched. Built on S6/S7; no verified core or
host module rebuilt. Date: 2026-06-28.

---

## 1. What S8 delivers

| Artifact | What it is |
|---|---|
| `A0S_Assembly_Spec.md` | The formal, **unambiguous** `.txt` grammar: `a/A` data, `.` bindu, `..` early bindu, Enter = HOLD, `1`–`9` Sanskrit control numerals (eka…nava), `0` zUnya (clear), `@d`/`^d` aSTa-dik roll/scan, `#` comments, file structure. |
| `ashta_dik.py` | The 8 directions as 2-D host transforms on the **locked 9×12 = 108** grid: a toroidal **ROLL** + a corner-to-corner zig-zag **SCAN** per direction. Reuses `host_ops` 1-D rotate for the cardinal rolls; brute-force + NumPy cross-checks. |
| `a0s_parser.py` | The parser/compiler that **extends** S6's `host_staging.parse_text` into the full grammar and emits the exact S6/S7 packet stream + host geometry. |
| `a0s_programs/*.txt` | 10 reference programs exercising **every** construct (data, bindu, early-bindu, hold, each digit, each of the 8 directions, zUnya, comments). |
| `test_s8_a0s_grammar.py` | The S8 verification gate (**ALL PASS**). |
| `host_ops.py` (edit) | Additive: the provisional `ASHTA_DIK` op-table is renamed `POSITIONAL_OPS` (alias kept) — the Sanskrit/op correction (below). |

---

## 2. The locked grid and the 8 directions

**Grid (locked 2026-06-28):** 9 rows × 12 cols = 108, row-major fill (each row = a
12-syllable pAda line; columns align syllable positions across the 9 lines). Short
patterns zUnya-padded to 108. **Toroidal** (every ROLL wraps → reversible).
`row 0 = North`, `col 0 = West`.

| `d` | Sanskrit | Compass | Kind | ROLL (Δrow,Δcol) |
|---|---|---|---|---|
| 1 | PUrva | E | dizA | (0,+1) |
| 2 | Agneya | SE | koNa | (+1,+1) |
| 3 | DakSiNa | S | dizA | (+1,0) |
| 4 | NairRta | SW | koNa | (+1,−1) |
| 5 | Pazcima | W | dizA | (0,−1) |
| 6 | VAyavya | NW | koNa | (−1,−1) |
| 7 | Uttara | N | dizA | (−1,0) |
| 8 | IzAna | NE | koNa | (−1,+1) |

- **ROLL** = shift the grid one step toward the direction (diagonal = both axes).
  Cardinal rolls **reuse `host_ops.rotl/rotr`** (rows for E/W, columns for N/S);
  diagonals compose a row-roll and a column-roll. Inverse = opposite diz.
- **SCAN** = readout order. Cardinal = straight (row/column-major); diagonal =
  corner-to-corner **zig-zag**. Because `gcd(9,12)=3`, a naive +1+1 diagonal *walk*
  splits into 3 loops and loses cells; the zig-zag SCAN covers **all 108** in one
  sweep (verified: every SCAN is a full 108-permutation).

### Sanskrit / op correction (resolves the S7 provisional flag)
S7's `host_ops.ASHTA_DIK` conflated direction-names with the **bitwise/shift
operation** vocabulary (`vAma`=shift-left, `dakSiNa`=shift-right, `bheda`=XOR…). S8
separates the two cleanly:
- the **aSTa-dik** = the 8 **compass directions** = 2-D grid geometry (`ashta_dik.py`);
- the bitwise/shift ops keep their own names in `host_ops.POSITIONAL_OPS`
  (`bheda`=XOR confirmed by the plan §4 audit).
- **`dakSiNa` is properly South** (a grid roll), not "shift-right" — that was the
  conflation. (`ASHTA_DIK` retained as a deprecated alias so the S7 gate stays green.)

---

## 3. The grammar (unambiguous by construction)

The lexer is a single pass over **disjoint, total leading-character classes** — the
first character at any position fixes the token kind. The only multi-character tokens
are deterministic maximal munches: a dot-run (len 1 = bindu, len ≥ 2 = early bindu)
and a sigil + one `1`–`8` selector.

Semantics: DATA appends a bit; CONTROL `N` repeats the next repeatable token;
zUNYA clears the buffer; HOLD is a clock/LED pause (no fold, no foot split); BINDU
folds the maNDala (directional ⇒ lay into 108-grid, roll, scan-readout; plain ⇒ raw
bitstream **exactly as S6**) and emits `FOLD` feet + `RESET`; EARLY BINDU aborts
(voids the maNDala, `RESET` only); EOF closes an open maNDala with an implicit bindu.

**Strictly additive:** a maNDala with no `@`/`^` folds the raw bitstream
byte-identically to the S6/S7 pipeline (proven in the gate, §D2).

---

## 4. Verification gate — `test_s8_a0s_grammar.py` (ALL PASS)

Mirrors the S6/S7 software gates; **host ↔ software-golden** (golden is itself
S4-RTL-validated, so the chain is sound).

**[A] Grammar.**
- Golden token vectors: every construct tokenizes to exactly one form (incl. `a..A`
  and `a...A` both → DATA, EARLY-BINDU, DATA).
- Unambiguity #1: leading-char classes disjoint & total (one rule per char).
- Unambiguity #2: canonical **re-lex fixed point** over 3000+ programs (serialize →
  re-tokenize == identity ⇒ no input parses two ways).
- Accepts all **10** reference programs; the set exercises **every** construct and
  **all 8** directions. Known structures checked (ref04 → 45 guru bits; ref05 zUnya
  leaves 4 bits; ref02 first maNDala aborted = seed fp).
- Malformed programs rejected with `A0SSyntaxError` (`@`, `@9`, `@0`, `^ 1`, `a3`,
  `3.`, `30`).

**[B] ASTa-dik reversibility + brute-force cross-check (0 mismatch).**
- `roll()` (host_ops path) == double-loop reference == NumPy `np.roll`, over 5k
  patterns × 8 directions.
- ROLL reversible: `roll(roll(x,d), opp(d)) == x`. SCAN reversible:
  `invert_scan(apply_scan(x,d), d) == x`. Every SCAN is a full 108-permutation.

**[C] 8 fingerprints — MEASURED, collisions reported honestly.** Over a battery of
patterns we count distinct fold fingerprints across the 8 directions:

| pattern | distinct ROLL | distinct SCAN |
|---|---|---|
| all-zUnya (0) | 1/8 | 1/8 |
| all-guru (1) | 1/8 | 1/8 |
| checkerboard | 5/8 | 5/8 |
| row-stripes | 3/8 | 4/8 |
| col-stripes | 2/8 | 5/8 |
| asymmetric | **8/8** | **8/8** |
| random ×4 | **8/8** | **8/8** |

Honest reading: **rich/asymmetric patterns give a full 8/8** (the geometry is
order-sensitive under the FOLD), but **symmetric patterns collide** — uniform → 1/8,
and stripe patterns collapse along their axis of symmetry (e.g. col-stripes are
invariant under N/S rolls → only 2 distinct ROLLs). We do **not** assume all 8
differ; the gate asserts (a) at least one pattern hits 8/8 and (b) collisions occur
and are logged.

**[D] Round-trip through the S6/S7 host pipeline (0 mismatch).**
- Directional programs (4k random): `compile → packets → LoopbackTransport →
  result_reader.fold_fingerprint` == compile fingerprint == an **independent**
  brute-force golden (`roll_ref` + `scan_order` + golden fold). 0 mismatch.
- Plain (letter-only) programs (4k): fingerprint == S6 `host_staging.fold_fingerprint`
  == golden `fold_text`; and the **packet stream is byte-identical** to S6
  `text_to_fold_packets` (the additive guarantee).
- Multi-segment programs (2k): the sealed FOLD fingerprints == the committed
  maNDalas, in order (aborted maNDalas correctly seal nothing).
- All 10 reference programs round-trip through the loopback (every stream ends in the
  bindu/`RESET`).

---

## 5. Honesty ledger

- **Zero silicon change.** The aSTa-dik is a host-side reordering of bits before they
  fold; `core_top` and all proven cores are untouched. This is the Path-A fence.
- **"8 distinct fingerprints" is measured, not assumed.** Symmetric patterns collide
  (table §4C); the claim holds for rich patterns and is reported honestly for the
  rest.
- **Validation standing = S6/S7:** host ↔ software-golden. The literal host ↔ RTL
  co-sim is **S9**; real USB is **Phase 7**. Both gaps are explicit.
- **Scope limit:** a directional segment is exactly one 108-cell maNDala; >108 bits
  with a direction operator raises an error (multi-maNDala tiling is future work).
- **`..` vs `.`:** at the packet level the chip has a single bindu (`RESET`); `.`
  commits (folds), `..` aborts (no fold) — a host-side distinction, documented.

---

## 6. Status

**Phase 4 COMPLETE.** A0S grammar specified + proven unambiguous; aSTa-dik lives as
the host geometry layer with reversible roll/scan transforms; Sanskrit names
corrected; reference programs round-trip bit-exact through the S6/S7 pipeline.

**Next:** S9 (Phase 5) — the literal host ↔ `core_top` RTL co-sim closing the S7/S8
honesty gap, with the full test battery against the golden model. Phase-6 fold
pipelining remains the named fmax lever (after end-to-end).
