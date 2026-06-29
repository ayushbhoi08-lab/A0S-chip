# A0S Assembly Specification (Ansh-108 Core, Path A — Phase 4 / S8)

**Status:** LOCKED 2026-06-28. Reference implementation: `a0s_parser.py` (lexer +
compiler) and `ashta_dik.py` (the geometry layer). Verified by
`test_s8_a0s_grammar.py` (ALL PASS). This document is the human-facing language;
**all cosmology lives here, not in silicon** — the A0S program is reordered and
folded entirely on the host, and the residue chip's math is untouched (the Path-A
fence). *Sanskrit is the soul; the silicon body stays universal.*

---

## 0. What A0S is

A `.txt` program describes a **chant** as a stream of *laghu* (short) and *guru*
(long) syllables, optional **maNDala geometry** (the aSTa-dik 8 directions), and a
terminating **bindu**. The host (S6/S7 staging agent) compiles it into the exact
32-bit packet stream `core_top` consumes (`FOLD` feet + a `RESET` bindu), applying
all positional/geometry work **before** the bits ever reach the chip.

A0S **extends** the S6 chant parser (`host_staging.parse_text`, which only mapped
`a/A` and stripped the rest). A maNDala with **no** direction operator folds the raw
bitstream **byte-identically to S6/S7** — the geometry layer is strictly additive.

---

## 1. Lexical tokens (the alphabet)

The lexer is a single pass driven by **disjoint leading-character classes** — the
first character at any position fixes the token kind, so **no input parses two
ways** (see §4). The classes:

| Source | Token | Meaning |
|---|---|---|
| `a`–`z` | **DATA 0** | a *laghu* (short) syllable → bit `0` |
| `A`–`Z` | **DATA 1** | a *guru* (long) syllable → bit `1` |
| `.` (a run of exactly **1** dot) | **BINDU** | terminate + execute the maNDala |
| `..` (a run of **≥ 2** dots) | **EARLY BINDU** | abort: void this maNDala **without** folding |
| Enter (`\n` / `\r`) | **HOLD** | host clock/LED pause; folds nothing, emits no packet |
| `0` | **zUNYA** | clear the current maNDala buffer (the void) |
| `1`–`9` | **CONTROL** (eka…nava) | repeat the next repeatable token N times |
| `@d` (`d` = `1`–`8`) | **ROLL** | roll the maNDala one step toward diz `d` |
| `^d` (`d` = `1`–`8`) | **SCAN** | set the readout traversal to diz `d` |
| `#` … end-of-line | *comment* | dropped (may carry Sanskrit/diacritics) |
| space, tab, **any other char** | *separator* | ignored |

**Maximal munch, two cases only:** (i) a run of dots is consumed whole (length 1 ⇒
BINDU, length ≥ 2 ⇒ EARLY BINDU); (ii) a sigil (`@`/`^`) consumes **exactly** the
one following character as its direction selector, which **must** be `1`–`8`
(immediately, no space). Every other token is a single character. Both multi-char
forms are deterministic.

The Sanskrit control numerals: `1` eka · `2` dvi · `3` tri · `4` catur · `5` paJca ·
`6` SaS · `7` sapta · `8` aSTa · `9` nava.

---

## 2. The aSTa-dik (8 directions) — the geometry layer

The grid is **LOCKED**: **9 rows × 12 cols = 108**, row-major fill (each row is a
12-syllable pAda line; columns align syllable positions across the 9 lines). Short
patterns are **zUnya-padded** with zeros to 108. The grid is **toroidal** (every
ROLL wraps → every ROLL is reversible). `row 0 = North` (top, increasing south);
`col 0 = West` (left, increasing east).

| `d` | Sanskrit | Compass | Kind | ROLL vector (Δrow, Δcol) |
|---|---|---|---|---|
| 1 | PUrva | E | dizA (cardinal) | (0, +1) |
| 2 | Agneya | SE | koNa (diagonal) | (+1, +1) |
| 3 | DakSiNa | S | dizA | (+1, 0) |
| 4 | NairRta | SW | koNa | (+1, −1) |
| 5 | Pazcima | W | dizA | (0, −1) |
| 6 | VAyavya | NW | koNa | (−1, −1) |
| 7 | Uttara | N | dizA | (−1, 0) |
| 8 | IzAna | NE | koNa | (−1, +1) |

Each direction provides two facets:

- **ROLL (`@d`)** — shift the whole grid one step toward `d` (a diagonal koNa steps
  in **both** axes at once). Toroidal, hence reversible: `roll(roll(x, d),
  opposite(d)) == x` where opposite pairs are E↔W, S↔N, SE↔NW, SW↔NE. Cardinal rolls
  reuse the S7 `host_ops` 1-D rotate (rows for E/W, columns for N/S); diagonals
  compose a row-roll and a column-roll.
- **SCAN (`^d`)** — the **readout/traversal order** when the maNDala is folded.
  Cardinal scans flow straight (row-major for E/W, column-major for N/S); diagonal
  scans are the **corner-to-corner zig-zag** (JPEG-style boustrophedon over the
  diagonals). The zig-zag matters: `gcd(9, 12) = 3`, so a naive +1+1 diagonal *walk*
  would split into 3 disjoint loops and miss cells; the zig-zag SCAN covers **all
  108** in one sweep. Each SCAN is a bijection over the 108 cells → reversible.

**Naming correction (supersedes the provisional S7 `host_ops.ASHTA_DIK`):** S7
conflated direction-names with the bitwise/shift *operation* vocabulary
(`vAma`=shift-left, `dakSiNa`=shift-right, `bheda`=XOR…). S8 separates the two: the
aSTa-dik = the 8 **compass directions** (2-D grid geometry, `ashta_dik.py`); the
bitwise/shift ops keep their own names in `host_ops.POSITIONAL_OPS` (`bheda`=XOR
confirmed). Note **dakSiNa is properly South** (a grid roll), not "shift-right".

---

## 3. Semantics (how a program executes on the host)

A program is a sequence of **maNDalas** (segments) separated by bindus.

Within the current maNDala the compiler keeps: a **bit pattern** (appended by DATA),
an ordered list of **rolls**, and a single **scan** (default **PUrva** = row-major;
a later `^d` overrides). A maNDala becomes **directional** the moment any `@`/`^`
appears.

- **DATA** appends a bit. **CONTROL `N`** repeats the next repeatable token (DATA /
  `@` / `^`) N times; if the next token is not repeatable (or absent), it is a
  **syntax error**.
- **zUNYA `0`** clears the buffer (pattern, rolls, scan reset) — the void.
- **HOLD** (Enter) is a host clock/LED pause only: it folds nothing and does **not**
  split feet, so multiple pAda lines fold as one stream.
- **BINDU `.`** finalizes:
  - *directional:* lay the pattern into the 9×12 grid (zUnya-padded), apply each
    ROLL in textual order, read out in the SCAN order → 108 bits.
  - *plain:* fold the raw bitstream exactly as S6 (no forced 108-pad).
  - then slice into 28-bit feet (MSB-first, final foot zUnya-padded), emit one
    `FOLD` packet per foot, then the `RESET` **bindu** packet.
- **EARLY BINDU `..`** aborts: the maNDala is **voided without folding** — only the
  `RESET` bindu packet is emitted, so the fingerprint read before the bindu is the
  seed. (At the packet level the chip has a single bindu = `RESET`; `.` commits,
  `..` discards — a host-side distinction.)
- **EOF** closes any open maNDala with an **implicit bindu** (the chant's natural
  close). A program of only comments/HOLDs emits nothing.

The **fold fingerprint** = Horner hash `h ← (h·108 + foot) mod 12289`, seed `h₀ = 1`
(the locked §2.3 FOLD), read from the FOLD stream **before** the trailing bindu
reseeds the accumulator (the S6/S7 read-before-bindu contract).

---

## 4. Unambiguity (the grammar guarantee)

Proven in `test_s8_a0s_grammar.py`:

1. **Disjoint, total leading-char classes** — every character maps to exactly one
   token-starting rule; the kind is fixed by the first character alone.
2. **Canonical re-lex fixed point** — serializing any token list back to source and
   re-tokenizing yields the **same** tokens (verified over 3000+ programs). Two
   adjacent BINDUs can never arise (a 2-dot run is one EARLY BINDU), so no
   serialization aliases.
3. **Golden token vectors** — every construct tokenizes to one form (e.g. `a..A` and
   `a...A` both → DATA, EARLY BINDU, DATA).

Malformed programs are **rejected** with `A0SSyntaxError`: a sigil with no `1`–`8`
selector (`@`, `@9`, `@0`, `^ 1`), or a control numeral with nothing repeatable
after it (`a3` at EOF, `3.`, `30`).

---

## 5. File structure & grammar (EBNF-ish)

```
program     = { token | comment | separator } ;
token       = data | bindu | early_bindu | hold | sunya | control | roll | scan ;
data        = "a".."z" | "A".."Z" ;          (* laghu=0 / guru=1 *)
bindu       = "." ;                            (* a maximal dot-run of length 1 *)
early_bindu = "..", { "." } ;                  (* a maximal dot-run of length >= 2 *)
hold        = "\n" | "\r" ;
sunya       = "0" ;
control     = "1".."9" ;                       (* applies to the next repeatable token *)
roll        = "@", dir ;
scan        = "^", dir ;
dir         = "1".."8" ;                        (* aSTa-dik index, clockwise from East *)
comment     = "#", { any-char-except-newline } ;
separator   = " " | "\t" | any-other-char ;    (* ignored *)
```

Conventions: program files use the `.txt` extension; one chant/program per file;
comments and HOLDs are free. Reference programs live in `a0s_programs/` (one per
construct, plus `10_full_mandala.txt` exercising everything).

---

## 6. Worked examples

| Program | Result |
|---|---|
| `aA.` | plain maNDala, bits `01`, 1 foot, fingerprint of `[01…]` |
| `1A 2A 3A … 9A.` | control numerals → 45 guru bits (1+2+…+9), plain |
| `AAAA 0 bbbb .` | zUnya erases `AAAA`; only `bbbb` (=0000) folds |
| `aAAa .. bbAA .` | first maNDala **aborted** (seed fp); second committed |
| `…108 bits… @1 .` | directional: grid rolled East, read row-major, folded |
| `…grid… @2 @8 2@4 ^8 .` | rolled SE, NE, SW×2; read out on the IzAna (NE) zig-zag |

---

## 7. Honesty ledger

- The aSTa-dik is a **host-side reordering only** — zero silicon change; the chip's
  residue math is untouched (the Path-A fence).
- "**8 distinct fingerprints**" is a **measured** claim: on rich/asymmetric patterns
  all 8 directions give distinct stamps (8/8), but **symmetric patterns collide**
  (uniform → 1/8; row-stripes → 3/8 ROLL; col-stripes → 2/8 ROLL) — collisions are
  reported, never assumed away (`test_s8_a0s_grammar.py` §C).
- This layer is validated **host ↔ software-golden** (same standing as S6/S7).
  host ↔ RTL co-sim is **S9**; real USB is **Phase 7**.
- Multi-maNDala tiling (segments > 108 bits with a direction operator) is **not** in
  S8 — a directional segment is one 108-cell maNDala; oversize raises an error.
