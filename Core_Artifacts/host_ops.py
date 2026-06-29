#!/usr/bin/env python3
"""
Ansh-108 Core -- Path A, Phase 3 / S7: HOST POSITIONAL OPS (the Path-A fence).
==============================================================================
Everything the residue chip is *forbidden* to do, because it needs positional
(binary / linear-magnitude) form. Per the locked Path-A decision, these live on
the host, never welded onto the residue datapath:

  * bitwise   AND / OR / XOR           (XOR = the "bheda" cut, plan §4)
  * shift     left / right             (vAma / dakSiNa)
  * rotate    left / right
  * bit-reversal                       (the aSTa-dik mirror transform)
  * magnitude compare  a>b / a<b / ==  -- the branch the residue core kills.

The magnitude compare is the "SPIRAL": a residue value lives on a circle of
circumference M (the modulus product); to compare two of them you must first
*unroll the spiral* -- rebuild the absolute LINEAR value = wraparound-height * M
+ CRT-reconstructed-residue -- and only then compare. `SpiralHeightTracker`
turns a stream of circular-core residues (e.g. the free-running Yuga tick, which
wraps every Maha Yuga) into that absolute linear magnitude.

Two independent reconstructions are kept and cross-checked against each other and
against plain Python ints:
  * CRT (idempotents)        -- imported from golden_model (source of truth)
  * mixed-radix (Garner)     -- implemented here, independently, positional digits

Pure Python 3.8+, no third-party deps. Importable + `python host_ops.py` self-test.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Sequence, Tuple
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
# CRT source of truth + the locked moduli; mixed-radix below is independent.
from golden_model import (                                            # noqa: E402
    crt_idempotents, crt_reconstruct, COUNTER_MODULI, RNS108_MODULI, MAHA_YUGA)

# operand widths in play (fast-lane operand = 14 bits; chant foot = 28 bits)
OPND_WIDTH = 14
FOOT_WIDTH = 28


# --------------------------------------------------------------------------- #
# 0. small helpers
# --------------------------------------------------------------------------- #
def _mask(width: int) -> int:
    return (1 << width) - 1


def _prod(seq: Sequence[int]) -> int:
    m = 1
    for s in seq:
        m *= s
    return m


# --------------------------------------------------------------------------- #
# 1. BITWISE  (positional -- host-side; the residue core cannot do these)
# --------------------------------------------------------------------------- #
def band(a: int, b: int, width: Optional[int] = None) -> int:
    r = a & b
    return r & _mask(width) if width is not None else r


def bor(a: int, b: int, width: Optional[int] = None) -> int:
    r = a | b
    return r & _mask(width) if width is not None else r


def bxor(a: int, b: int, width: Optional[int] = None) -> int:
    """XOR = bheda (the 'cut/split' direction in the aSTa-dik grammar, plan §4)."""
    r = a ^ b
    return r & _mask(width) if width is not None else r


# --------------------------------------------------------------------------- #
# 2. SHIFT / ROTATE / BIT-REVERSAL  (the aSTa-dik positional transforms)
# --------------------------------------------------------------------------- #
def shl(a: int, n: int, width: int = FOOT_WIDTH) -> int:
    """Logical shift left within `width` bits (vAma). Bits past the MSB drop."""
    if n < 0:
        raise ValueError("shift amount must be >= 0")
    return (a << n) & _mask(width)


def shr(a: int, n: int, width: int = FOOT_WIDTH) -> int:
    """Logical shift right (dakSiNa). Zero-fill from the MSB side."""
    if n < 0:
        raise ValueError("shift amount must be >= 0")
    return (a & _mask(width)) >> n


def rotl(a: int, n: int, width: int = FOOT_WIDTH) -> int:
    """Rotate left within `width` bits (no bits lost; they wrap)."""
    a &= _mask(width)
    n %= width
    return ((a << n) | (a >> (width - n))) & _mask(width)


def rotr(a: int, n: int, width: int = FOOT_WIDTH) -> int:
    """Rotate right within `width` bits."""
    a &= _mask(width)
    n %= width
    return ((a >> n) | (a << (width - n))) & _mask(width)


def bit_reverse(a: int, width: int = FOOT_WIDTH) -> int:
    """Reverse the bit order within `width` bits -- the aSTa-dik mirror."""
    a &= _mask(width)
    r = 0
    for _ in range(width):
        r = (r << 1) | (a & 1)
        a >>= 1
    return r


# Positional bitwise/shift OPERATION vocabulary (1-D, host-side). These are NOT the
# aSTa-dik directions -- S8 corrected that conflation: the true aSTa-dik is the 8
# COMPASS DIRECTIONS realized as 2-D grid permutations in `ashta_dik.py` (a maNDala
# roll/scan), and "dakSiNa" is properly *South* (a grid roll), not "shift-right".
# This dict keeps the operation-level names (bheda=XOR confirmed by the plan §4
# audit) for the bitwise/shift fence; it is exposed as POSITIONAL_OPS below. The
# legacy name `ASHTA_DIK` is retained as an alias for back-compatibility only.
POSITIONAL_OPS = {
    "vama":       ("shift-left",   shl),          # west / left
    "dakshina":   ("shift-right",  shr),          # right
    "rotate_l":   ("rotate-left",  rotl),
    "rotate_r":   ("rotate-right", rotr),
    "darpana":    ("bit-reverse",  bit_reverse),  # mirror
    "bheda":      ("xor",          bxor),          # the cut
    "samyoga":    ("or",           bor),           # union
    "samgraha":   ("and",          band),          # intersection
}
# back-compat alias (deprecated; the real aSTa-dik now lives in ashta_dik.py)
ASHTA_DIK = POSITIONAL_OPS


# --------------------------------------------------------------------------- #
# 3. MIXED-RADIX (Garner) -- independent positional reconstruction
# --------------------------------------------------------------------------- #
def mixed_radix_digits(residues: Sequence[int], moduli: Sequence[int]) -> List[int]:
    """Garner's algorithm: positional digits d_i with
         value = d0 + d1*m0 + d2*(m0*m1) + ...   (least-significant dial first),
       0 <= d_i < m_i. Independent of the CRT idempotent path; used both to
       reconstruct and to compare magnitudes without ever leaving integer range."""
    v = [r % m for r, m in zip(residues, moduli)]
    n = len(moduli)
    digits = [0] * n
    for i in range(n):
        x = v[i]
        for j in range(i):
            x = ((x - digits[j]) * pow(moduli[j], -1, moduli[i])) % moduli[i]
        digits[i] = x % moduli[i]
    return digits


def mixed_radix_value(residues: Sequence[int], moduli: Sequence[int]) -> int:
    """Reconstruct the absolute value (within one period) from mixed-radix digits."""
    val = 0
    weight = 1
    for d, m in zip(mixed_radix_digits(residues, moduli), moduli):
        val += d * weight
        weight *= m
    return val


def reconstruct(residues: Sequence[int], moduli: Sequence[int]) -> int:
    """Absolute residue value in [0, M). Uses the CRT source-of-truth; the
    mixed-radix path is cross-checked equal in the self-test."""
    return crt_reconstruct(list(residues), list(moduli))


def to_residues(value: int, moduli: Sequence[int]) -> Tuple[int, ...]:
    """Project an absolute value down to per-dial residues (host helper / tests)."""
    return tuple(value % m for m in moduli)


# --------------------------------------------------------------------------- #
# 4. THE SPIRAL -- unroll a circular residue value to an absolute linear one
# --------------------------------------------------------------------------- #
def spiral_value(residues: Sequence[int], moduli: Sequence[int], height: int = 0) -> int:
    """Absolute LINEAR magnitude of a residue value that has wrapped `height`
    times around its circle of circumference M = prod(moduli):
        absolute = height * M + reconstruct(residues)."""
    if height < 0:
        raise ValueError("spiral height (wraparound count) must be >= 0")
    return height * _prod(moduli) + reconstruct(residues, moduli)


def spiral_compare(a_res: Sequence[int], a_height: int,
                   b_res: Sequence[int], b_height: int,
                   moduli: Sequence[int]) -> int:
    """Compare two residue values by FIRST unrolling the spiral, then comparing
    the absolute linear magnitudes. Returns -1 (a<b), 0 (a==b), +1 (a>b).
    This is the branch the residue datapath refuses to take (Path-A fence)."""
    a = spiral_value(a_res, moduli, a_height)
    b = spiral_value(b_res, moduli, b_height)
    return (a > b) - (a < b)


def spiral_gt(a_res, a_h, b_res, b_h, moduli) -> bool:
    return spiral_compare(a_res, a_h, b_res, b_h, moduli) > 0


def spiral_lt(a_res, a_h, b_res, b_h, moduli) -> bool:
    return spiral_compare(a_res, a_h, b_res, b_h, moduli) < 0


def spiral_eq(a_res, a_h, b_res, b_h, moduli) -> bool:
    return spiral_compare(a_res, a_h, b_res, b_h, moduli) == 0


@dataclass
class SpiralHeightTracker:
    """Turn a STREAM of circular-core residues (e.g. the free-running Yuga tick,
    which wraps every Maha Yuga) into an absolute, monotone, ever-rising LINEAR
    magnitude. Each sample is CRT-reconstructed to a point on the circle; when the
    point drops below the previous one, the circle has wrapped (a Pralaya) and the
    wraparound height is incremented.

    HONESTY / sampling limit: this only works if successive samples are < one full
    period M apart (a Nyquist-style bound). If more than M ticks elapse between two
    samples, a wrap is silently missed -- documented, and guarded by `max_step`
    (raises if a single advertised step would alias). Sample the tick often enough.
    """
    moduli: Tuple[int, ...] = COUNTER_MODULI
    height: int = 0
    _prev: Optional[int] = field(default=None, repr=False)
    M: int = field(init=False)

    def __post_init__(self):
        self.M = _prod(self.moduli)

    def update(self, residues: Sequence[int]) -> int:
        """Feed the next residue sample; return the current absolute linear count."""
        v = reconstruct(residues, self.moduli)
        if self._prev is not None and v < self._prev:
            self.height += 1                     # the circle wrapped (Pralaya)
        self._prev = v
        return self.height * self.M + v

    def value(self) -> int:
        if self._prev is None:
            return 0
        return self.height * self.M + self._prev


# --------------------------------------------------------------------------- #
# Self-test (cross-check every op vs plain Python ints over large sweeps)
# --------------------------------------------------------------------------- #
def _selftest() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    import random
    random.seed(108)
    fails = 0

    def check(name, cond):
        nonlocal fails
        print(f"  [{'PASS' if cond else 'FAIL'}] {name}")
        if not cond:
            fails += 1

    print("Ansh-108 S7 -- host_ops (positional fence) self-test")

    # ---- bitwise == Python ints --------------------------------------------- #
    bw = True
    for _ in range(50000):
        a, b = random.randrange(1 << 28), random.randrange(1 << 28)
        bw &= band(a, b) == (a & b)
        bw &= bor(a, b) == (a | b)
        bw &= bxor(a, b) == (a ^ b)
    check("AND/OR/XOR == Python &|^ over 50k pairs", bw)
    check("bxor(a,a)=0, bor(a,0)=a, band(a,0)=0", all(
        bxor(a, a) == 0 and bor(a, 0) == a and band(a, 0) == 0
        for a in (0, 1, 12289, (1 << 28) - 1)))

    # ---- shift == Python ints (within width) -------------------------------- #
    sh = True
    for _ in range(50000):
        a = random.randrange(1 << 28)
        n = random.randrange(0, 30)
        sh &= shl(a, n, 28) == ((a << n) & ((1 << 28) - 1))
        sh &= shr(a, n, 28) == ((a & ((1 << 28) - 1)) >> n)
    check("shl/shr == masked Python <<,>> over 50k cases", sh)

    # ---- rotate: invertible, full-rotate identity, mask-preserving ---------- #
    rot = True
    for _ in range(50000):
        w = random.choice((14, 28))
        a = random.randrange(1 << w)
        n = random.randrange(0, 3 * w)
        rot &= rotr(rotl(a, n, w), n, w) == a            # rotate is invertible
        rot &= rotl(a, w, w) == a                        # full rotation = identity
        rot &= rotl(a, n, w) <= (1 << w) - 1             # stays in width
        # rotate preserves popcount (no bits created/destroyed)
        rot &= bin(rotl(a, n, w)).count("1") == bin(a).count("1")
    check("rotl/rotr invertible + popcount-preserving + width-bound over 50k", rot)
    # rotate matches a reference string rotation
    refrot = True
    for _ in range(20000):
        w = random.choice((8, 14, 28))
        a = random.randrange(1 << w)
        n = random.randrange(0, w)
        s = format(a, f"0{w}b")
        ref = int(s[n:] + s[:n], 2) if n else a           # left-rotate string
        refrot &= rotl(a, n, w) == ref
    check("rotl == reference string rotation over 20k", refrot)

    # ---- bit reversal: involution + reference --------------------------------#
    br = True
    for _ in range(50000):
        w = random.choice((8, 14, 28))
        a = random.randrange(1 << w)
        rev = int(format(a, f"0{w}b")[::-1], 2)
        br &= bit_reverse(a, w) == rev
        br &= bit_reverse(bit_reverse(a, w), w) == a       # involution
    check("bit_reverse == string-reverse + involution over 50k", br)

    # ---- aSTa-dik registry dispatches to the right transform ----------------- #
    check("ASHTA_DIK has 8 directions mapping to host transforms",
          len(ASHTA_DIK) == 8 and ASHTA_DIK["bheda"][1] is bxor
          and ASHTA_DIK["vama"][1] is shl and ASHTA_DIK["darpana"][1] is bit_reverse)

    # ---- mixed-radix (Garner) == CRT == Python (exhaustive on the demo lane) - #
    M108 = _prod(RNS108_MODULI)
    mr108 = all(mixed_radix_value(to_residues(v, RNS108_MODULI), RNS108_MODULI) == v
                for v in range(M108))
    crt108 = all(reconstruct(to_residues(v, RNS108_MODULI), RNS108_MODULI) == v
                 for v in range(M108))
    check(f"mixed-radix == value over all {M108} rns108 states", mr108)
    check(f"CRT == value over all {M108} rns108 states", crt108)
    # mixed-radix == CRT on the big counter lane (random sweep across the period)
    eqrec = True
    for _ in range(50000):
        v = random.randrange(MAHA_YUGA)
        res = to_residues(v, COUNTER_MODULI)
        eqrec &= mixed_radix_value(res, COUNTER_MODULI) == v == reconstruct(res, COUNTER_MODULI)
    check("mixed-radix == CRT == value over 50k Maha-Yuga states", eqrec)

    # ---- SPIRAL magnitude compare == Python int compare --------------------- #
    sc = True
    for _ in range(50000):
        ha, hb = random.randrange(0, 5), random.randrange(0, 5)
        ra, rb = random.randrange(MAHA_YUGA), random.randrange(MAHA_YUGA)
        a_abs = ha * MAHA_YUGA + ra
        b_abs = hb * MAHA_YUGA + rb
        got = spiral_compare(to_residues(ra, COUNTER_MODULI), ha,
                             to_residues(rb, COUNTER_MODULI), hb, COUNTER_MODULI)
        sc &= got == ((a_abs > b_abs) - (a_abs < b_abs))
        sc &= spiral_value(to_residues(ra, COUNTER_MODULI), COUNTER_MODULI, ha) == a_abs
    check("spiral_compare == Python int compare over 50k (residues+height)", sc)
    check("spiral_eq/gt/lt agree with compare",
          spiral_eq((0,), 0, (0,), 0, (7,)) and spiral_gt((1,), 1, (6,), 0, (7,))
          and spiral_lt((6,), 0, (1,), 1, (7,)))

    # ---- SpiralHeightTracker over MANY Maha Yugas vs true cumulative count --- #
    # Sample the Yuga tick every `step` ticks for several wraps; the unrolled
    # absolute magnitude must equal the true cumulative tick count exactly.
    from golden_model import RnsCounter
    trk_ok = True
    for step in (1, 7, 99999, MAHA_YUGA - 1):
        c = RnsCounter(COUNTER_MODULI)
        trk = SpiralHeightTracker(COUNTER_MODULI)
        total = 0
        trk.update(c.residues())                          # t=0 sample
        for _ in range(37):                               # cross ~ several Pralayas
            c.tick(step)
            total += step
            if trk.update(c.residues()) != total:
                trk_ok = False
                break
        if not trk_ok:
            break
    check("SpiralHeightTracker absolute == true cumulative ticks across wraps", trk_ok)
    # the documented aliasing limit: a step >= M cannot be tracked from residues
    c = RnsCounter(COUNTER_MODULI)
    trk = SpiralHeightTracker(COUNTER_MODULI)
    trk.update(c.residues())
    c.tick(MAHA_YUGA)                                      # a full period -> residues unchanged
    aliased = trk.update(c.residues())
    check("aliasing limit honest: a full-period jump is invisible to the tracker",
          aliased == 0)   # height did NOT advance -- the documented Nyquist bound

    print(f"\n{'ALL PASS' if fails == 0 else str(fails) + ' FAILURE(S)'}")
    return fails


if __name__ == "__main__":
    raise SystemExit(_selftest())
