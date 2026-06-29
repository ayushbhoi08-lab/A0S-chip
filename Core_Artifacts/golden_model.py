#!/usr/bin/env python3
"""
Ansh-108 Core — Path A GOLDEN MODEL (S1 skeleton)
=================================================
The single software source-of-truth for Path-A semantics. Every later artifact
(Verilog sim, formal harness, host staging agent) is checked against THIS.

Built directly from the locked §2 decisions in
    Ansh_108_Core_PathA_Build_Plan.md  (2026-06-28, all of §2 locked)

Locked decisions encoded here:
  - Primary execution/data lane = modular arithmetic mod q, q = 12289.
  - Packet = 32-bit: opcode = bits[31:28], data = bits[27:0];
    fast lane operands X = data[13:0], Y = data[27:14].
  - FOLD = Horner hash  h <- (h*B + pada) mod q,  B = 108, seed h0 = 1,
    single chain (parameterized so N chains can be added later).
  - Opcodes: 0 MUL 1 ADD 2 SUB 3 REDUCE 4 FOLD 5 VERIFY
             6 READ_TICK 7 SEED_FROM_TICK(optional) 8 FLUSH 15 RESET
             (9 magnitude-compare and 10-14 bitwise/shift are HOST-side in Path A).
  - Time counter = carry-free RNS, moduli {256, 27, 625} = 2^8 * 3^3 * 5^4,
    period = 4,320,000 = one Maha Yuga; tick is monotonic + write-protected
    (RESET/FLUSH do NOT touch it); SEED_FROM_TICK off by default.
  - rns108 lane (M = 108 = 4*27) kept as the namesake/identity demo lane.

S1 design choices (flagged for review — easy to change before RTL):
  * REDUCE(out) = the 28-bit concatenation {Y,X} reduced mod q  (a "wide reduce").
  * FOLD term  = the full 28-bit data field of the packet (the chant "foot").
  * The hardware tick free-runs at the clock; in this functional model the tick is
    advanced explicitly via .tick(n) so tests are deterministic.

No third-party deps. Python 3.8+ (uses pow(a,-1,m)).
"""

from dataclasses import dataclass, field
from typing import Optional, List, Dict

# --------------------------------------------------------------------------- #
# Locked constants
# --------------------------------------------------------------------------- #
Q = 12289                      # primary lane prime modulus (NTT-friendly: 12288 = 2^12 * 3)
FOLD_B = 108                   # Horner base (the chip's own number; coprime to Q)
FOLD_SEED = 1                  # h0

RNS108_MODULI = (4, 27)        # identity / namesake demo lane, M = 108
COUNTER_MODULI = (256, 27, 625)  # carry-free Maha-Yuga counter, M = 4_320_000
MAHA_YUGA = 4_320_000

DATA_BITS = 28
OPND_BITS = 14
DATA_MASK = (1 << DATA_BITS) - 1
OPND_MASK = (1 << OPND_BITS) - 1

# Opcodes
MUL, ADD, SUB, REDUCE, FOLD, VERIFY = 0, 1, 2, 3, 4, 5
READ_TICK, SEED_FROM_TICK, FLUSH = 6, 7, 8
RESET = 15

OPNAME = {MUL: "MUL", ADD: "ADD", SUB: "SUB", REDUCE: "REDUCE", FOLD: "FOLD",
          VERIFY: "VERIFY", READ_TICK: "READ_TICK", SEED_FROM_TICK: "SEED_FROM_TICK",
          FLUSH: "FLUSH", RESET: "RESET"}

# Adaptable result mode (for the FSM/host; informational in the golden model)
CRITICAL, STREAM, HANDSHAKE, FIRE_FORGET = "critical", "stream", "handshake", "fire_forget"
RESULT_MODE = {
    MUL: CRITICAL, ADD: CRITICAL, SUB: CRITICAL, REDUCE: CRITICAL,
    FOLD: STREAM, VERIFY: HANDSHAKE, READ_TICK: HANDSHAKE,
    SEED_FROM_TICK: FIRE_FORGET, FLUSH: FIRE_FORGET, RESET: FIRE_FORGET,
}


# --------------------------------------------------------------------------- #
# CRT helpers (the carry-free recombine, used by the counter and rns108 lane)
# --------------------------------------------------------------------------- #
def crt_idempotents(moduli):
    """Return (M, [e_i]) where value = sum(r_i * e_i) mod M reconstructs from residues."""
    M = 1
    for m in moduli:
        M *= m
    e = []
    for m in moduli:
        Mi = M // m
        yi = pow(Mi, -1, m)        # Mi^{-1} mod m
        e.append((Mi * yi) % M)
    return M, e


def crt_reconstruct(residues, moduli, M=None, e=None):
    if e is None:
        M, e = crt_idempotents(moduli)
    return sum((r % m) * ei for r, m, ei in zip(residues, moduli, e)) % M


def check_crt_bijection(moduli):
    """Exhaustively confirm residues<->value is a bijection over all M states.

    Round-trip argument (no O(M) memory): if reconstruct(residues(v)) == v for
    every v in [0,M), then v->residues has a left inverse, hence is injective;
    domain and codomain both have size M, so it is a bijection.
    """
    M, e = crt_idempotents(moduli)
    for v in range(M):
        res = [v % m for m in moduli]
        if crt_reconstruct(res, moduli, M, e) != v:
            return False, f"reconstruct mismatch at {v}"
    return True, f"{M}/{M} round-trip exact"


# --------------------------------------------------------------------------- #
# Carry-free RNS free-running counter  (the "Yuga clock")
# --------------------------------------------------------------------------- #
class RnsCounter:
    """
    Each dial increments mod its modulus, no carry between dials. The combined
    value (via CRT) is monotonic over one period then wraps (= Pralaya).
    'Can't lie' property modeled: only tick() advances it; there is NO setter.
    """
    def __init__(self, moduli=COUNTER_MODULI):
        self.moduli = tuple(moduli)
        self.M, self._e = crt_idempotents(self.moduli)
        self._res = [0] * len(self.moduli)

    def tick(self, n: int = 1):
        if n < 0:
            raise ValueError("counter is monotonic: n must be >= 0")  # can't rewind
        for i, m in enumerate(self.moduli):
            self._res[i] = (self._res[i] + n) % m
        return self.value()

    def value(self) -> int:
        return crt_reconstruct(self._res, self.moduli, self.M, self._e)

    def residues(self):
        return tuple(self._res)


# --------------------------------------------------------------------------- #
# rns108 identity-lane multiply (demo; primary lane is plain mod-Q arithmetic)
# --------------------------------------------------------------------------- #
def rns108_mul(x, y, moduli=RNS108_MODULI):
    """Branch-free (x*y) mod 108 via per-dial multiply + CRT recombine."""
    M, e = crt_idempotents(moduli)
    res = [((x % m) * (y % m)) % m for m in moduli]
    return crt_reconstruct(res, moduli, M, e)


# --------------------------------------------------------------------------- #
# Packet encode / decode
# --------------------------------------------------------------------------- #
def encode_packet(opcode: int, x: int = 0, y: int = 0) -> int:
    data = ((y & OPND_MASK) << OPND_BITS) | (x & OPND_MASK)
    return ((opcode & 0xF) << DATA_BITS) | (data & DATA_MASK)

def encode_data_packet(opcode: int, data28: int) -> int:
    return ((opcode & 0xF) << DATA_BITS) | (data28 & DATA_MASK)

def decode_packet(packet: int) -> Dict[str, int]:
    opcode = (packet >> DATA_BITS) & 0xF
    data = packet & DATA_MASK
    return {"opcode": opcode, "data": data,
            "x": data & OPND_MASK, "y": (data >> OPND_BITS) & OPND_MASK}


# --------------------------------------------------------------------------- #
# The core
# --------------------------------------------------------------------------- #
@dataclass
class ExecResult:
    opcode: int
    result_mode: str
    value: Optional[int]      # None for fire-and-forget ops with no result


@dataclass
class AnshCoreGolden:
    q: int = Q
    fold_b: int = FOLD_B
    fold_seed: int = FOLD_SEED
    h: int = field(init=False)             # fold accumulator (single chain)
    counter: RnsCounter = field(default_factory=RnsCounter)

    def __post_init__(self):
        self.h = self.fold_seed

    # -- one packet through the core ---------------------------------------- #
    def execute(self, packet: int) -> ExecResult:
        d = decode_packet(packet)
        op, data, x, y = d["opcode"], d["data"], d["x"], d["y"]
        xr, yr = x % self.q, y % self.q   # valid operands are [0,q); reduce defensively

        if op == MUL:
            return ExecResult(op, CRITICAL, (xr * yr) % self.q)
        if op == ADD:
            return ExecResult(op, CRITICAL, (xr + yr) % self.q)
        if op == SUB:
            return ExecResult(op, CRITICAL, (xr - yr) % self.q)
        if op == REDUCE:
            return ExecResult(op, CRITICAL, data % self.q)          # wide reduce of {Y,X}
        if op == FOLD:
            self.h = (self.h * self.fold_b + data) % self.q
            return ExecResult(op, STREAM, self.h)
        if op == VERIFY:
            return ExecResult(op, HANDSHAKE, 1 if x == y else 0)    # residue-cheap equality
        if op == READ_TICK:
            return ExecResult(op, HANDSHAKE, self.counter.value())
        if op == SEED_FROM_TICK:                                    # optional, off by default
            self.h = self.counter.value() % self.q
            return ExecResult(op, FIRE_FORGET, None)
        if op == FLUSH:
            self.h = self.fold_seed                                 # does NOT touch the tick
            return ExecResult(op, FIRE_FORGET, None)
        if op == RESET:
            self.h = self.fold_seed                                 # datapath reset only;
            return ExecResult(op, FIRE_FORGET, None)                # tick is write-protected
        raise ValueError(f"opcode {op} reserved/host-side in Path A (9 cmp, 10-14 bitwise/shift)")

    # -- convenience: advance the free-running clock ------------------------ #
    def tick(self, n: int = 1):
        return self.counter.tick(n)


# --------------------------------------------------------------------------- #
# Host-side reference helpers (the staging-agent slicer, for cross-checking)
# --------------------------------------------------------------------------- #
def text_to_bits(text: str) -> List[int]:
    """a-z -> 0 (laghu), A-Z -> 1 (guru); all else ignored. Mirrors the host parser."""
    out = []
    for ch in text:
        if "a" <= ch <= "z":
            out.append(0)
        elif "A" <= ch <= "Z":
            out.append(1)
    return out

def slice_bits_to_feet(bits: List[int], width: int = DATA_BITS) -> List[int]:
    """Pack bits MSB-first into 'feet' of `width`; final foot sunya-padded with 0s."""
    feet = []
    for i in range(0, len(bits), width):
        chunk = bits[i:i + width]
        v = 0
        for b in chunk:
            v = (v << 1) | b
        v <<= (width - len(chunk))        # sunya pad on the right
        feet.append(v)
    return feet or [0]

def fold_text(text: str, core: Optional[AnshCoreGolden] = None) -> int:
    """Reference whole-pattern fingerprint: parse -> slice -> FOLD each foot."""
    core = core or AnshCoreGolden()
    core.h = core.fold_seed
    for foot in slice_bits_to_feet(text_to_bits(text)):
        core.execute(encode_data_packet(FOLD, foot))
    return core.h


# --------------------------------------------------------------------------- #
# Self-tests (the S1 verification gate for the golden model itself)
# --------------------------------------------------------------------------- #
def _selftest() -> int:
    fails = 0
    def check(name, cond):
        nonlocal fails
        print(f"  [{'PASS' if cond else 'FAIL'}] {name}")
        if not cond:
            fails += 1

    print("Ansh-108 Path A golden model — self-test")

    # CRT bijections (exhaustive)
    ok108, msg108 = check_crt_bijection(RNS108_MODULI)
    check(f"CRT bijection over Z/108 ({msg108})", ok108)
    okY, msgY = check_crt_bijection(COUNTER_MODULI)
    check(f"CRT bijection over counter Z/4320000 ({msgY})", okY)

    # arithmetic ops vs direct modular math (random-ish sweep)
    core = AnshCoreGolden()
    import random
    random.seed(108)
    mm = aa = ss = True
    for _ in range(20000):
        x, y = random.randrange(Q), random.randrange(Q)
        mm &= core.execute(encode_packet(MUL, x, y)).value == (x * y) % Q
        aa &= core.execute(encode_packet(ADD, x, y)).value == (x + y) % Q
        ss &= core.execute(encode_packet(SUB, x, y)).value == (x - y) % Q
    check("MUL == (x*y) mod q over 20k pairs", mm)
    check("ADD == (x+y) mod q over 20k pairs", aa)
    check("SUB == (x-y) mod q over 20k pairs", ss)

    # rns108 demo lane matches plain mod-108 multiply (exhaustive 108x108)
    r108 = all(rns108_mul(x, y) == (x * y) % 108 for x in range(108) for y in range(108))
    check("rns108 branch-free MUL == (x*y) mod 108 over all 11,664 pairs", r108)

    # VERIFY
    v1 = core.execute(encode_packet(VERIFY, 777, 777)).value == 1
    v2 = core.execute(encode_packet(VERIFY, 777, 778)).value == 0
    check("VERIFY equality 1/0", v1 and v2)

    # FOLD: matches a hand-computed Horner over feet, and is order-sensitive
    core.execute(encode_packet(FLUSH))
    feet = [5, 9, 12289 + 3]            # last term > q to exercise reduction
    h = FOLD_SEED
    for f in feet:
        h = (h * FOLD_B + f) % Q
    got = None
    for f in feet:
        got = core.execute(encode_data_packet(FOLD, f)).value
    check("FOLD == manual Horner over feet", got == h)
    check("FOLD order matters (aA vs Aa)", fold_text("aA") != fold_text("Aa"))
    check("FOLD deterministic (same text -> same stamp)", fold_text("aAaAbcD") == fold_text("aAaAbcD"))

    # text/slice helpers
    check("text_to_bits maps case correctly", text_to_bits("aA9 zZ") == [0, 1, 0, 1])
    check("slicer sunya-pads final foot", slice_bits_to_feet([1, 1], width=4) == [0b1100])

    # Time counter: wrap, monotonic, write-protection via RESET/FLUSH
    c = AnshCoreGolden()
    t0 = c.counter.value()
    c.tick(1)
    check("tick advances by 1", c.counter.value() == t0 + 1)
    c.tick(MAHA_YUGA - 1)
    check("counter wraps at one Maha Yuga (Pralaya -> 0)", c.counter.value() == 0)
    c.tick(123)
    before = c.counter.value()
    c.execute(encode_packet(RESET))
    c.execute(encode_packet(FLUSH))
    check("RESET/FLUSH do NOT touch the tick (can't-lie)", c.counter.value() == before)
    try:
        c.counter.tick(-1); rewind_blocked = False
    except ValueError:
        rewind_blocked = True
    check("counter cannot be rewound (monotonic)", rewind_blocked)

    # SEED_FROM_TICK
    c.execute(encode_packet(SEED_FROM_TICK))
    check("SEED_FROM_TICK loads tick into fold accumulator", c.h == c.counter.value() % Q)

    print(f"\n{'ALL PASS' if fails == 0 else str(fails) + ' FAILURE(S)'}")
    return fails


if __name__ == "__main__":
    raise SystemExit(_selftest())
