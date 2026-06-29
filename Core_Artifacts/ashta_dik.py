#!/usr/bin/env python3
"""
Ansh-108 Core -- Path A, Phase 4 / S8: ASTA-DIK (the 8-direction geometry layer).
=================================================================================
The true aSTa-dik: the 8 compass directions of the VAstu maNDala, here realized as
2-D *host-side* permutations of a fixed 9×12 = 108 grid. This is the Path-A FENCE:
the residue chip's math is untouched -- every direction is a pure reordering of
bits the host performs *before* it folds them. ZERO silicon change.

    GRID (locked 2026-06-28): 9 rows × 12 cols = 108, row-major fill.
      - each ROW = one 12-syllable pAda line; columns align syllable positions
        across the 9 lines (the meter-meaningful orientation).
      - short patterns are zUnya-padded (zeros) up to 108.
      - the grid is TOROIDAL: every ROLL wraps, so every ROLL is reversible
        (its inverse is the opposite diz).

The 8 directions (canonical clockwise order, starting due East):

      idx  Sanskrit   compass  kind       roll vector (drow, dcol)
      ---  ---------  -------  ---------   -----------------------
       1   PUrva       E       dizA        ( 0, +1)
       2   Agneya      SE      koNa        (+1, +1)
       3   DakSiNa     S       dizA        (+1,  0)
       4   NairRta     SW      koNa        (+1, -1)
       5   Pazcima     W       dizA        ( 0, -1)
       6   VAyavya     NW      koNa        (-1, -1)
       7   Uttara      N       dizA        (-1,  0)
       8   IzAna       NE      koNa        (-1, +1)

  (row 0 = North/top, row increases southward; col 0 = West/left, col increases
   eastward -- the standard screen/matrix convention.)

Each direction provides:
  (a) ROLL -- shift the whole grid one step toward that direction (toroidal; a
      diagonal koNa steps in BOTH axes at once). Reversible: roll(roll(x,d), opp(d)) == x.
  (b) SCAN -- a readout/traversal ORDER (a permutation of the 108 cells). Cardinal
      scans flow straight (row- or column-major in that sense); diagonal scans are
      the corner-to-corner ZIG-ZAG (JPEG-style boustrophedon over the diagonals),
      which covers ALL 108 cells in one sweep -- important because gcd(9,12)=3, so a
      naive +1+1 diagonal *step* would split into 3 disjoint loops and miss cells.

NAME / OP CORRECTION (supersedes the provisional S7 `host_ops.ASHTA_DIK`):
  S7 conflated direction-NAMES with the bitwise/shift OPERATION vocabulary
  (vAma=shift-left, dakSiNa=shift-right, bheda=XOR, ...). That was provisional.
  S8 separates the two concerns cleanly:
    * The aSTa-dik = the 8 COMPASS DIRECTIONS above (2-D grid geometry, THIS file).
    * The positional bitwise/shift ops keep their own (corrected) operation names in
      host_ops (now also exposed as `host_ops.POSITIONAL_OPS`). Note dakSiNa is
      properly *South* (a grid roll), not "shift-right"; the S7 reuse of the word
      for shift-right was the conflation this correction fixes.

Reuses host_ops.rotl/rotr for the cardinal rolls (1-D toroidal rotate lifted to
rows/columns); a pure-Python double-loop reference and a NumPy reference are kept
and cross-checked against it (brute-force grid model, 0 mismatch).

Python 3.8+; NumPy used only as an independent cross-check reference. UTF-8 prints.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Sequence, Tuple
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import host_ops                                                        # noqa: E402

# --------------------------------------------------------------------------- #
# Locked grid
# --------------------------------------------------------------------------- #
ROWS = 9
COLS = 12
NCELLS = ROWS * COLS            # 108 -- the maNDala

# direction indices
PURVA, AGNEYA, DAKSHINA, NAIRRTA = 1, 2, 3, 4
PASCIMA, VAYAVYA, UTTARA, ISHANA = 5, 6, 7, 8


@dataclass(frozen=True)
class Dik:
    idx: int
    sanskrit: str        # with diacritics (the soul)
    ascii: str           # ascii spelling (for grep / non-utf8 contexts)
    compass: str         # E / SE / S / SW / W / NW / N / NE
    kind: str            # "disa" (cardinal) | "kona" (diagonal)
    roll_vec: Tuple[int, int]    # (drow, dcol) -- content moves by this each ROLL


# canonical clockwise order, due East first
DIRECTIONS: Dict[int, Dik] = {
    PURVA:    Dik(PURVA,    "PUrva",   "Purva",   "E",  "disa", (0,  +1)),
    AGNEYA:   Dik(AGNEYA,   "Agneya",  "Agneya",  "SE", "kona", (+1, +1)),
    DAKSHINA: Dik(DAKSHINA, "DakSiNa", "Dakshina","S",  "disa", (+1,  0)),
    NAIRRTA:  Dik(NAIRRTA,  "NairRta", "Nairrta", "SW", "kona", (+1, -1)),
    PASCIMA:  Dik(PASCIMA,  "Pazcima", "Pascima", "W",  "disa", (0,  -1)),
    VAYAVYA:  Dik(VAYAVYA,  "VAyavya", "Vayavya", "NW", "kona", (-1, -1)),
    UTTARA:   Dik(UTTARA,   "Uttara",  "Uttara",  "N",  "disa", (-1,  0)),
    ISHANA:   Dik(ISHANA,   "IzAna",   "Ishana",  "NE", "kona", (-1, +1)),
}

DISA = (PURVA, DAKSHINA, PASCIMA, UTTARA)        # 4 cardinal
KONA = (AGNEYA, NAIRRTA, VAYAVYA, ISHANA)        # 4 diagonal


def opposite(d: int) -> int:
    """The diametrically opposite diz (its ROLL is the inverse roll)."""
    return ((d - 1 + 4) % 8) + 1                  # +4 places around the 8-wheel


# --------------------------------------------------------------------------- #
# grid <-> flat helpers
# --------------------------------------------------------------------------- #
def pad108(bits: Sequence[int]) -> List[int]:
    """Lay a bit pattern row-major into the 108-cell grid, zUnya-padded with zeros.
    A pattern longer than one maNDala is rejected (multi-maNDala is a future item)."""
    b = [int(x) & 1 for x in bits]
    if len(b) > NCELLS:
        raise ValueError(f"directional segment has {len(b)} bits > one {NCELLS}-cell "
                         f"maNDala (multi-maNDala tiling is not in S8)")
    return b + [0] * (NCELLS - len(b))


def _rows_of(g: Sequence[int]) -> List[List[int]]:
    return [list(g[r * COLS:(r + 1) * COLS]) for r in range(ROWS)]


def _flat(rows: Sequence[Sequence[int]]) -> Tuple[int, ...]:
    return tuple(rows[r][c] for r in range(ROWS) for c in range(COLS))


# --------------------------------------------------------------------------- #
# 1. ROLL -- toroidal shift of grid CONTENTS toward a direction
# --------------------------------------------------------------------------- #
def roll(bits: Sequence[int], d: int) -> Tuple[int, ...]:
    """Roll the grid one step toward diz `d` (toroidal). Cardinal dizA reuse the
    S7 host_ops 1-D rotate (rows for E/W, columns for N/S); diagonal koNa compose
    a row-roll and a column-roll. Returns the 108-cell flat grid."""
    g = pad108(bits)
    drow, dcol = DIRECTIONS[d].roll_vec
    if dcol != 0:                                 # horizontal component: roll rows
        g = _roll_rows(g, dcol)
    if drow != 0:                                 # vertical component: roll columns
        g = _roll_cols(g, drow)
    return tuple(g)


def _roll_rows(g: Sequence[int], dcol: int) -> List[int]:
    """Roll every row by dcol (+1 = East) using host_ops 1-D rotate.
    Row word encodes col 0 as MSB (bit COLS-1); East (col c -> c+1) is rotate-RIGHT."""
    rows = _rows_of(g)
    for r in range(ROWS):
        w = _word(rows[r], COLS)
        w = host_ops.rotr(w, 1, COLS) if dcol > 0 else host_ops.rotl(w, 1, COLS)
        rows[r] = _bits(w, COLS)
    return [rows[r][c] for r in range(ROWS) for c in range(COLS)]


def _roll_cols(g: Sequence[int], drow: int) -> List[int]:
    """Roll every column by drow (+1 = South) using host_ops 1-D rotate.
    Column word encodes row 0 as MSB (bit ROWS-1); South (row r -> r+1) is rotate-RIGHT."""
    rows = _rows_of(g)
    cols = [[rows[r][c] for r in range(ROWS)] for c in range(COLS)]
    for c in range(COLS):
        w = _word(cols[c], ROWS)
        w = host_ops.rotr(w, 1, ROWS) if drow > 0 else host_ops.rotl(w, 1, ROWS)
        cols[c] = _bits(w, ROWS)
    return [cols[c][r] for r in range(ROWS) for c in range(COLS)]


def _word(line: Sequence[int], width: int) -> int:
    """Pack a bit line into an integer with index 0 as the MSB (bit width-1)."""
    w = 0
    for i in range(width):
        w |= (line[i] & 1) << (width - 1 - i)
    return w


def _bits(word: int, width: int) -> List[int]:
    return [(word >> (width - 1 - i)) & 1 for i in range(width)]


# -- independent references for the cross-check (brute-force grid models) ----- #
def roll_ref(bits: Sequence[int], d: int) -> Tuple[int, ...]:
    """Pure double-loop reference: content at (r,c) moves to (r+drow, c+dcol) mod grid."""
    g = pad108(bits)
    drow, dcol = DIRECTIONS[d].roll_vec
    out = [0] * NCELLS
    for r in range(ROWS):
        for c in range(COLS):
            nr, nc = (r + drow) % ROWS, (c + dcol) % COLS
            out[nr * COLS + nc] = g[r * COLS + c]
    return tuple(out)


def roll_numpy(bits: Sequence[int], d: int) -> Tuple[int, ...]:
    """NumPy reference via np.roll (independent of the host_ops path)."""
    import numpy as np
    drow, dcol = DIRECTIONS[d].roll_vec
    grid = np.array(pad108(bits), dtype=np.int8).reshape(ROWS, COLS)
    rolled = np.roll(grid, shift=(drow, dcol), axis=(0, 1))
    return tuple(int(x) for x in rolled.reshape(-1))


# --------------------------------------------------------------------------- #
# 2. SCAN -- a readout/traversal ORDER (permutation of the 108 cells)
# --------------------------------------------------------------------------- #
def _antidiag_zigzag() -> List[int]:
    """Zig-zag over anti-diagonals (r+c = s) -- the NE<->SW family. Covers all 108."""
    order: List[int] = []
    for s in range(ROWS + COLS - 1):
        diag = [(r, s - r) for r in range(ROWS) if 0 <= s - r < COLS]
        if s % 2 == 0:
            diag.reverse()
        order += [r * COLS + c for (r, c) in diag]
    return order


def _maindiag_zigzag() -> List[int]:
    """Zig-zag over main diagonals (r-c = k) -- the NW<->SE family. Covers all 108."""
    order: List[int] = []
    for k in range(-(COLS - 1), ROWS):
        diag = [(r, r - k) for r in range(ROWS) if 0 <= r - k < COLS]
        if k % 2 == 0:
            diag.reverse()
        order += [r * COLS + c for (r, c) in diag]
    return order


def scan_order(d: int) -> List[int]:
    """The readout order (list of 108 flat indices) for diz `d`. Each is a bijection
    over the 108 cells -> every SCAN is reversible (apply then inverse == identity)."""
    if d == PURVA:        # E: row-major, West->East, North->South (the natural read)
        return [r * COLS + c for r in range(ROWS) for c in range(COLS)]
    if d == PASCIMA:      # W: row-major, East->West
        return [r * COLS + (COLS - 1 - c) for r in range(ROWS) for c in range(COLS)]
    if d == DAKSHINA:     # S: column-major, North->South, columns West->East
        return [r * COLS + c for c in range(COLS) for r in range(ROWS)]
    if d == UTTARA:       # N: column-major, South->North
        return [(ROWS - 1 - r) * COLS + c for c in range(COLS) for r in range(ROWS)]
    if d == AGNEYA:       # SE: main-diagonal zig-zag (NW -> SE)
        return _maindiag_zigzag()
    if d == VAYAVYA:      # NW: reverse of SE
        return list(reversed(_maindiag_zigzag()))
    if d == ISHANA:       # NE: anti-diagonal zig-zag
        return _antidiag_zigzag()
    if d == NAIRRTA:      # SW: reverse of NE
        return list(reversed(_antidiag_zigzag()))
    raise ValueError(f"unknown direction index {d}")


def apply_scan(bits: Sequence[int], d: int) -> Tuple[int, ...]:
    """Read the 108-cell grid in diz `d`'s traversal order -> a reordered 108-bit
    sequence."""
    g = pad108(bits)
    return tuple(g[i] for i in scan_order(d))


def invert_scan(scanned: Sequence[int], d: int) -> Tuple[int, ...]:
    """Inverse of apply_scan: place a scanned sequence back into grid order."""
    if len(scanned) != NCELLS:
        raise ValueError(f"scanned sequence must be {NCELLS} bits")
    order = scan_order(d)
    out = [0] * NCELLS
    for i, idx in enumerate(order):
        out[idx] = scanned[i] & 1
    return tuple(out)


# --------------------------------------------------------------------------- #
# 3. The grammar's readout: lay pattern -> apply rolls (in order) -> scan
# --------------------------------------------------------------------------- #
def grid_readout(bits: Sequence[int], rolls: Sequence[int] = (),
                 scan: int = PURVA) -> Tuple[int, ...]:
    """The maNDala operation invoked at a directional bindu: lay the pattern into
    the 108 grid, apply each ROLL in textual order, then read it out in the SCAN
    traversal. Returns 108 bits ready to slice into FOLD feet."""
    g: Tuple[int, ...] = tuple(pad108(bits))
    for d in rolls:
        g = roll(g, d)
    return apply_scan(g, scan)


# --------------------------------------------------------------------------- #
# Self-test (reversibility + brute-force cross-check + 8-fingerprint measurement)
# --------------------------------------------------------------------------- #
def _selftest() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    import random
    from golden_model import FOLD_SEED, FOLD_B, Q, slice_bits_to_feet
    random.seed(108)
    fails = 0

    def check(name, cond):
        nonlocal fails
        print(f"  [{'PASS' if cond else 'FAIL'}] {name}")
        if not cond:
            fails += 1

    print("Ansh-108 S8 -- ashta_dik (8-direction grid geometry) self-test")

    # ---- registry sanity ----------------------------------------------------- #
    check("8 directions, 4 dizA + 4 koNa, distinct compass points",
          len(DIRECTIONS) == 8 and len(DISA) == 4 and len(KONA) == 4
          and len({d.compass for d in DIRECTIONS.values()}) == 8)
    check("opposite() pairs E<->W, S<->N, SE<->NW, SW<->NE",
          opposite(PURVA) == PASCIMA and opposite(DAKSHINA) == UTTARA
          and opposite(AGNEYA) == VAYAVYA and opposite(NAIRRTA) == ISHANA
          and all(opposite(opposite(d)) == d for d in DIRECTIONS))

    def rand_pattern():
        n = random.randint(0, NCELLS)
        return [random.randint(0, 1) for _ in range(n)]

    # ---- ROLL: host_ops path == pure-python ref == numpy ref (brute force) --- #
    roll_xc = True
    for _ in range(4000):
        p = rand_pattern()
        for d in DIRECTIONS:
            r1 = roll(p, d)            # host_ops 1-D rotate path
            r2 = roll_ref(p, d)        # pure double-loop brute force
            r3 = roll_numpy(p, d)      # numpy np.roll
            roll_xc &= (r1 == r2 == r3)
        if not roll_xc:
            break
    check("ROLL host_ops == double-loop == numpy over 4k patterns x 8 dirs (brute force)",
          roll_xc)

    # ---- ROLL reversibility: roll then opposite-roll == identity ------------- #
    roll_rev = True
    for _ in range(4000):
        p = rand_pattern()
        padded = tuple(pad108(p))
        for d in DIRECTIONS:
            roll_rev &= (roll(roll(p, d), opposite(d)) == padded)
        if not roll_rev:
            break
    check("ROLL reversible: roll(roll(x,d), opp(d)) == x over 4k x 8 dirs", roll_rev)

    # ROLL is a bijection (permutation) of the 108 cells -> never loses a cell.
    perm_ok = True
    for d in DIRECTIONS:
        # roll a grid of distinct labels 0..107; result must be a permutation
        labels = list(range(NCELLS))
        # emulate the permutation by rolling each one-hot... cheaper: ref on indices
        drow, dcol = DIRECTIONS[d].roll_vec
        moved = [0] * NCELLS
        for r in range(ROWS):
            for c in range(COLS):
                moved[((r + drow) % ROWS) * COLS + (c + dcol) % COLS] = labels[r * COLS + c]
        perm_ok &= (sorted(moved) == labels)
    check("each ROLL is a permutation of all 108 cells (no cell lost)", perm_ok)

    # ---- SCAN: each order is a permutation; covers all 108 (gcd-loop-proof) --- #
    scan_perm = all(sorted(scan_order(d)) == list(range(NCELLS)) for d in DIRECTIONS)
    check("each SCAN order is a full permutation of 108 cells (diagonal zig-zag "
          "beats the gcd(9,12)=3 loop split)", scan_perm)

    # ---- SCAN reversibility -------------------------------------------------- #
    scan_rev = True
    for _ in range(4000):
        p = rand_pattern()
        padded = tuple(pad108(p))
        for d in DIRECTIONS:
            scan_rev &= (invert_scan(apply_scan(p, d), d) == padded)
        if not scan_rev:
            break
    check("SCAN reversible: invert_scan(apply_scan(x,d), d) == x over 4k x 8 dirs",
          scan_rev)

    # ---- diagonal SCAN is corner-to-corner ---------------------------------- #
    se = scan_order(AGNEYA)
    ne = scan_order(ISHANA)
    check("diagonal SCAN runs corner-to-corner (SE starts at a corner, ends at a corner)",
          se[0] in (0, COLS - 1, (ROWS - 1) * COLS, NCELLS - 1)
          and se[-1] in (0, COLS - 1, (ROWS - 1) * COLS, NCELLS - 1)
          and ne[0] in (0, COLS - 1, (ROWS - 1) * COLS, NCELLS - 1))

    # ---- THE 8-FINGERPRINT MEASUREMENT (honest: count distinct, log collisions) #
    def fold_bits(bits108):
        h = FOLD_SEED
        for foot in slice_bits_to_feet(list(bits108)):
            h = (h * FOLD_B + foot) % Q
        return h

    # a structured, asymmetric test pattern (first 108 bits of a deterministic chant)
    test_pattern = [(i * 37 + (i // 5)) % 2 for i in range(NCELLS)]
    roll_fps = {d: fold_bits(roll(test_pattern, d)) for d in DIRECTIONS}
    scan_fps = {d: fold_bits(apply_scan(test_pattern, d)) for d in DIRECTIONS}
    base_fp = fold_bits(test_pattern)
    n_roll = len(set(roll_fps.values()))
    n_scan = len(set(scan_fps.values()))
    n_union = len(set(roll_fps.values()) | set(scan_fps.values()))
    print(f"    [MEASURED] base fingerprint           = {base_fp} (0x{base_fp:04x})")
    print(f"    [MEASURED] distinct ROLL fingerprints = {n_roll}/8  "
          f"{{ {', '.join(f'{DIRECTIONS[d].ascii}:{v}' for d, v in roll_fps.items())} }}")
    print(f"    [MEASURED] distinct SCAN fingerprints = {n_scan}/8  "
          f"{{ {', '.join(f'{DIRECTIONS[d].ascii}:{v}' for d, v in scan_fps.items())} }}")
    print(f"    [MEASURED] distinct over ROLL+SCAN (16 transforms) = {n_union}/16")
    # honest claim: report, do NOT assert all 8 differ. We only assert the geometry
    # is non-trivial (at least the majority of directions yield distinct stamps).
    check("ROLL fingerprints are non-trivial (>=6/8 distinct on this pattern, "
          "collisions logged honestly)", n_roll >= 6)
    check("SCAN fingerprints are non-trivial (>=6/8 distinct on this pattern)",
          n_scan >= 6)

    # ---- grid_readout matches an independent brute-force readout -------------- #
    gr_ok = True
    for _ in range(2000):
        p = rand_pattern()
        ndir = random.randint(0, 3)
        rolls = [random.randint(1, 8) for _ in range(ndir)]
        sc = random.randint(1, 8)
        got = grid_readout(p, rolls, sc)
        # brute-force independent: ref rolls + ref scan
        g = tuple(pad108(p))
        for d in rolls:
            g = roll_ref(g, d)
        ref = tuple(g[i] for i in scan_order(sc))
        gr_ok &= (got == ref)
        if not gr_ok:
            break
    check("grid_readout == brute-force (roll_ref + scan) over 2k random programs", gr_ok)

    print(f"\n{'ALL PASS' if fails == 0 else str(fails) + ' FAILURE(S)'}")
    return fails


if __name__ == "__main__":
    raise SystemExit(_selftest())
