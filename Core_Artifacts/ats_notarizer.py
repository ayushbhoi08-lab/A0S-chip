#!/usr/bin/env python3
"""
Ansh-108 Core — Track A / A-TS : Tamper-evident timestamped NOTARIZER
=====================================================================
Host-side application built ENTIRELY on the proven golden model. No FPGA
board is required: this runs against `golden_model.py` (the software
source-of-truth) and is the same logic a later host<->RTL co-sim (S9) would
drive. The silicon does NOT change; this is a wrapper.

What this delivers (the three A-TS deliverables from the Watch & Applications
Plan):
  A-TS-1  Multi-chain FOLD bound to the monotonic tick  -> a wide fingerprint
          and a timestamp that cannot be rewound or forged.  Collision strength
          is MEASURED, not assumed (firewall item).
  A-TS-2  A stream/log NOTARIZER: ingest events, emit a timeline root; the root
          is order-sensitive end-to-end (proof-of-order).
  A-TS-3  A VERIFIER + an explicit threat model (see the .md writeup).

REUSE, not reinvention (honesty gate):
  - Chain 0 uses base B=108, seed=1 -> it is byte-for-byte the proven
    golden FOLD. `_selftest` asserts chain-0 == AnshCoreGolden.FOLD over the
    same data, so the multi-chain build provably extends the proven primitive.
  - The slicer (bytes -> 28-bit "feet") is the proven `slice_bits_to_feet`.
  - The clock is the proven `RnsCounter` (monotonic, no setter).

The single FOLD chain has ~log2(12289) = 13.585 bits of state. Eight chains
give ~108.7 bits (~54-bit collision resistance) -- the "108-bit fingerprint"
target falls out of the chip's own number, 8 * 13.585 ~= 108.7. We measure the
per-chain birthday behaviour and extrapolate honestly; we do NOT claim a
2^54 search was run.

Run:
    python ats_notarizer.py            # self-test gate (must be ALL PASS)
    python ats_notarizer.py --measure  # empirical collision + order-sensitivity
    python ats_notarizer.py --demo     # a worked notarize/verify/tamper demo

No third-party deps. Python 3.8+.
"""

import sys
import os
import random

# Make sure we import the golden model that sits next to this file.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from golden_model import (
    Q, FOLD_B, FOLD_SEED, DATA_BITS, MAHA_YUGA,
    AnshCoreGolden, RnsCounter,
    slice_bits_to_feet, encode_data_packet, FOLD,
)

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")  # Windows console safety


# --------------------------------------------------------------------------- #
# Base selection: distinct bases coprime to Q with large multiplicative order
# --------------------------------------------------------------------------- #
# Q = 12289 is prime, Q-1 = 12288 = 2^12 * 3. A base is a *primitive root* iff
# its multiplicative order is exactly Q-1 -> maximal diffusion for that chain.
def mult_order(a, q=Q):
    """Multiplicative order of a mod q (q prime). Returns 0 if a % q == 0."""
    a %= q
    if a == 0:
        return 0
    n = q - 1
    order = n
    for p in (2, 3):                       # the only prime factors of 12288
        while order % p == 0 and pow(a, order // p, q) == 1:
            order //= p
    return order


def is_primitive_root(a, q=Q):
    return mult_order(a, q) == q - 1


def pick_bases(n_chains):
    """Chain 0 = 108 (the proven canonical base). Chains 1.. = primitive roots.

    108 alone has a SMALL order mod 12289 (measured below) -> weak diffusion;
    that is exactly why chain 0 is never used alone. The strength chains use
    primitive roots (order = Q-1 = 12288).
    """
    bases = [FOLD_B]                        # 108, to match the proven golden FOLD
    a = 2
    while len(bases) < n_chains:
        if is_primitive_root(a) and a not in bases:
            bases.append(a)
        a += 1
    return bases[:n_chains]


# --------------------------------------------------------------------------- #
# Multi-chain FOLD  (N parallel Horner hashes, distinct base + seed)
# --------------------------------------------------------------------------- #
class MultiChainFold:
    """N parallel chains: h_i <- (h_i * B_i + foot) mod Q.

    Combined state is the N-tuple of chain values -> effective space Q^N.
    Identical per-step recurrence to golden_model FOLD (one chain per base),
    so chain 0 (B=108, seed=1) reproduces the proven core exactly.
    """

    def __init__(self, n_chains=8, bases=None, seeds=None):
        self.bases = bases or pick_bases(n_chains)
        self.n = len(self.bases)
        # Seeds: chain 0 = FOLD_SEED (=1) to match the golden core; others distinct, nonzero.
        self.seeds = seeds or ([FOLD_SEED] + list(range(2, self.n + 1)))
        self.reset()

    def reset(self):
        self.h = list(self.seeds)

    def fold_foot(self, foot):
        """Absorb one 28-bit foot into every chain."""
        for i in range(self.n):
            self.h[i] = (self.h[i] * self.bases[i] + foot) % Q

    def fold_feet(self, feet):
        for f in feet:
            self.fold_foot(f)

    def state(self):
        return tuple(self.h)

    def digest_bits(self):
        """Effective fingerprint width in bits = n * log2(Q)."""
        import math
        return self.n * math.log2(Q)

    def digest_hex(self):
        """Pack the N chain residues into one big integer / hex string."""
        v = 0
        for hi in self.h:
            v = (v << 14) | (hi & 0x3FFF)   # each residue < Q < 2^14
        width = (self.n * 14 + 3) // 4
        return f"{v:0{width}x}"


# --------------------------------------------------------------------------- #
# bytes -> feet, reusing the PROVEN slicer
# --------------------------------------------------------------------------- #
def bytes_to_feet(b):
    bits = []
    for byte in b:
        for k in range(7, -1, -1):
            bits.append((byte >> k) & 1)
    return slice_bits_to_feet(bits, DATA_BITS)   # proven sunya-padded slicer


# --------------------------------------------------------------------------- #
# The notarizer: ingest events, bind each to a monotonic tick, emit a root
# --------------------------------------------------------------------------- #
class LogEntry:
    __slots__ = ("seq", "tick", "event", "running_root")

    def __init__(self, seq, tick, event, running_root):
        self.seq = seq
        self.tick = tick
        self.event = event                  # raw bytes (the notarized payload)
        self.running_root = running_root     # multi-chain state AFTER this entry

    def __repr__(self):
        head = self.event[:24]
        return (f"#{self.seq} tick={self.tick} "
                f"root={'/'.join(str(x) for x in self.running_root)} "
                f"event={head!r}{'...' if len(self.event) > 24 else ''}")


class Notarizer:
    """Append-only, order-sensitive, timestamp-bound event notarizer.

    For each event we:
      1. advance the monotonic tick by 1 (it has no setter -> cannot be rewound),
      2. FOLD the tick value into every chain (binds time + order),
      3. FOLD the event bytes into every chain.
    The running multi-chain state after the last event is the timeline ROOT.

    Two independent tamper guards fall out of this:
      - the ROOT is order- and content-sensitive (recomputation catches edits), and
      - the recorded ticks are strictly increasing (reordering breaks monotonicity).
    """

    def __init__(self, n_chains=8, counter=None):
        self.fold = MultiChainFold(n_chains=n_chains)
        self.counter = counter or RnsCounter()
        self.log = []

    def notarize(self, event):
        if isinstance(event, str):
            event = event.encode("utf-8")
        t = self.counter.tick(1)                 # monotonic; cannot rewind
        self.fold.fold_foot(t)                    # bind the timestamp...
        self.fold.fold_feet(bytes_to_feet(event)) # ...then the content
        entry = LogEntry(len(self.log), t, event, self.fold.state())
        self.log.append(entry)
        return entry

    def root(self):
        return self.fold.state()

    def root_hex(self):
        return self.fold.digest_hex()


# --------------------------------------------------------------------------- #
# The verifier: independently replay the log and check every invariant
# --------------------------------------------------------------------------- #
class VerifyResult:
    def __init__(self):
        self.ok = True
        self.reasons = []

    def fail(self, why):
        self.ok = False
        self.reasons.append(why)

    def __repr__(self):
        if self.ok:
            return "VERIFIED (root matches, ticks monotonic, snapshots consistent)"
        return "TAMPER DETECTED: " + "; ".join(self.reasons)


def verify(log, claimed_root, n_chains=None):
    """Recompute the timeline from `log` and check it against `claimed_root`.

    Checks, in order:
      (1) ticks strictly increasing (monotonic, no rewind),
      (2) per-entry running-root snapshots reproduce on replay,
      (3) final root == claimed_root.
    Any single edit, reorder, or deletion trips at least one check.
    """
    res = VerifyResult()
    n = n_chains or len(claimed_root)
    fold = MultiChainFold(n_chains=n)

    prev_tick = -1
    for i, e in enumerate(log):
        if e.seq != i:
            res.fail(f"seq gap at index {i} (entry says #{e.seq})")
        if e.tick <= prev_tick:
            res.fail(f"non-monotonic tick at #{e.seq}: {e.tick} <= {prev_tick}")
        prev_tick = e.tick
        fold.fold_foot(e.tick)
        fold.fold_feet(bytes_to_feet(e.event if isinstance(e.event, bytes)
                                     else e.event.encode("utf-8")))
        if fold.state() != e.running_root:
            res.fail(f"running-root snapshot mismatch at #{e.seq}")
    if tuple(fold.state()) != tuple(claimed_root):
        res.fail("final root mismatch")
    return res


# --------------------------------------------------------------------------- #
# Self-test gate  (must be ALL PASS before any measurement is trusted)
# --------------------------------------------------------------------------- #
def _selftest():
    fails = 0

    def check(name, cond):
        nonlocal fails
        print(f"  [{'PASS' if cond else 'FAIL'}] {name}")
        if not cond:
            fails += 1

    print("A-TS notarizer — self-test (built on the proven golden model)")

    # (1) chain 0 reproduces the proven golden FOLD exactly  -> reuse, not reinvention
    feet = [5, 9, 12289 + 3, 1 << 27, 0]
    core = AnshCoreGolden()
    core.execute(encode_data_packet(FOLD, 0)) if False else None  # no-op, clarity
    golden_core = AnshCoreGolden()
    gh = None
    for f in feet:
        gh = golden_core.execute(encode_data_packet(FOLD, f)).value
    mcf = MultiChainFold(n_chains=8)
    mcf.fold_feet(feet)
    check("chain 0 (B=108,seed=1) == proven golden FOLD over same feet", mcf.h[0] == gh)

    # (2) base selection is sound
    bases = pick_bases(8)
    check("8 distinct bases", len(set(bases)) == 8)
    check("chain 0 base is the canonical 108", bases[0] == 108)
    check("strength chains (1..7) are primitive roots (order = Q-1)",
          all(is_primitive_root(b) for b in bases[1:]))

    # (3) notarize -> verify round-trips
    n1 = Notarizer(n_chains=8)
    events = [b"genesis", b"alpha", b"bravo", b"charlie", b"delta"]
    for ev in events:
        n1.notarize(ev)
    root = n1.root()
    check("clean log VERIFIES", verify(n1.log, root).ok)

    # (4) content tamper is caught
    n2 = Notarizer(n_chains=8)
    for ev in events:
        n2.notarize(ev)
    n2.log[2].event = b"BRAVO"                    # flip one event's bytes
    check("content edit -> TAMPER DETECTED", not verify(n2.log, n2.root()).ok)

    # (5) reorder tamper is caught (root AND tick-monotonicity)
    n3 = Notarizer(n_chains=8)
    for ev in events:
        n3.notarize(ev)
    n3.log[1], n3.log[2] = n3.log[2], n3.log[1]   # swap two entries
    r3 = verify(n3.log, n3.root())
    check("reorder -> TAMPER DETECTED", not r3.ok)
    check("reorder specifically breaks tick monotonicity",
          any("non-monotonic" in why for why in r3.reasons))

    # (6) deletion is caught
    n4 = Notarizer(n_chains=8)
    for ev in events:
        n4.notarize(ev)
    full_root = n4.root()
    del n4.log[2]
    check("deletion -> TAMPER DETECTED", not verify(n4.log, full_root).ok)

    # (7) order-sensitivity at the fingerprint level (no timestamps)
    a = MultiChainFold(8); a.fold_feet(bytes_to_feet(b"ab"))
    b = MultiChainFold(8); b.fold_feet(bytes_to_feet(b"ba"))
    check("multi-chain FOLD is order-sensitive (ab != ba)", a.state() != b.state())

    # (8) the tick cannot be rewound (inherited write-protect)
    c = RnsCounter()
    c.tick(10)
    rewind_blocked = False
    try:
        c.tick(-1)
    except ValueError:
        rewind_blocked = True
    check("tick cannot be rewound (monotonic, no setter)", rewind_blocked)

    print(f"\n{'ALL PASS' if fails == 0 else str(fails) + ' FAILURE(S)'}")
    return fails


# --------------------------------------------------------------------------- #
# Empirical measurement  (the firewall: MEASURE collision + order, don't assume)
# --------------------------------------------------------------------------- #
def _expected_birthday(space):
    import math
    return math.sqrt(math.pi * space / 2.0)


def _first_collision_count(n_chains, bases, seeds, rng, hard_cap):
    """Feed fresh random messages until two produce the same multi-chain state.
    Returns how many messages it took (the birthday count)."""
    seen = set()
    for k in range(1, hard_cap + 1):
        mcf = MultiChainFold(n_chains=n_chains, bases=bases, seeds=seeds)
        msg = rng.getrandbits(64).to_bytes(8, "big")
        mcf.fold_feet(bytes_to_feet(msg))
        st = mcf.state()
        if st in seen:
            return k
        seen.add(st)
    return None


def _measure():
    print("A-TS empirical measurement")
    print("=" * 64)
    rng = random.Random(108)

    ord108 = mult_order(FOLD_B)
    print(f"\n[bases] multiplicative order mod {Q}:")
    print(f"  base 108 (canonical, chain 0): order = {ord108}  "
          f"({'PRIMITIVE root' if ord108 == Q-1 else 'NOT primitive -> weak alone'})")
    roots = pick_bases(8)
    for b in roots[1:4]:
        print(f"  base {b:>5} (strength chain): order = {mult_order(b)}")

    # ---- single-chain birthday (108 vs a primitive root) ----
    print("\n[collision] single chain, mean first-collision over trials")
    print(f"  state space = Q = {Q};  birthday prediction ~= "
          f"{_expected_birthday(Q):.0f} messages")
    trials = 40
    for label, bases in (("B=108 (canonical)", [108]),
                         (f"B={roots[1]} (primitive root)", [roots[1]])):
        counts = []
        for _ in range(trials):
            c = _first_collision_count(1, bases, [1], rng, hard_cap=20000)
            if c is not None:
                counts.append(c)
        mean = sum(counts) / len(counts) if counts else float("nan")
        print(f"    {label:<26} mean first collision = {mean:7.1f}  "
              f"(n={len(counts)} trials)")

    # ---- two-chain birthday ----
    print("\n[collision] two chains (108 + one primitive root)")
    space2 = Q * Q
    print(f"  state space = Q^2 = {space2};  birthday prediction ~= "
          f"{_expected_birthday(space2):.0f} messages")
    bases2 = [108, roots[1]]
    counts = []
    for _ in range(8):
        c = _first_collision_count(2, bases2, [1, 2], rng, hard_cap=120000)
        if c is not None:
            counts.append(c)
    if counts:
        mean = sum(counts) / len(counts)
        print(f"    measured mean first collision = {mean:.0f}  "
              f"(n={len(counts)} trials)")
    else:
        print("    no collision within cap (consistent with the large space)")

    # ---- honest extrapolation ----
    import math
    print("\n[extrapolation] per added chain, the state space multiplies by Q:")
    for n in (1, 2, 4, 8):
        bits = n * math.log2(Q)
        coll_bits = bits / 2.0
        print(f"    {n} chain(s): ~{bits:6.1f}-bit fingerprint, "
              f"~{coll_bits:5.1f}-bit collision resistance "
              f"(~{_expected_birthday(Q**n):.3g} messages)")
    print("  -> 8 chains ~= 108.7-bit fingerprint (~54-bit collision resistance).")
    print("     This 54-bit figure is PREDICTED from the measured per-chain")
    print("     birthday behaviour, NOT from running a 2^54 search.")

    # ---- order-sensitivity ----
    print("\n[order] permuting a fixed event multiset (8 chains)")
    base_events = [f"event-{i:02d}".encode() for i in range(12)]
    perms = 5000
    roots_seen = {}
    coll = 0
    for _ in range(perms):
        ev = base_events[:]
        rng.shuffle(ev)
        mcf = MultiChainFold(n_chains=8)
        for e in ev:
            mcf.fold_feet(bytes_to_feet(e))
        st = mcf.state()
        if st in roots_seen and roots_seen[st] != tuple(ev):
            coll += 1
        roots_seen[st] = tuple(ev)
    print(f"    {perms} random permutations -> {len(roots_seen)} distinct roots, "
          f"{coll} cross-order collisions")
    print("    (cross-order collisions expected ~0; any reorder changes the root)")
    print("\n" + "=" * 64)
    print("Measurement complete. Numbers above are reproducible (seed=108).")


# --------------------------------------------------------------------------- #
# Worked demo
# --------------------------------------------------------------------------- #
def _demo():
    print("A-TS worked demo: notarize a log, then catch a tamper")
    print("=" * 64)
    notarizer = Notarizer(n_chains=8)
    events = [
        "boot: firmware v2.3.1 loaded",
        "user alice authenticated",
        "config changed: retention=90d",
        "export: dataset_4471 -> s3://audit/",
        "user alice logged out",
    ]
    print("\nNotarizing 5 events (each bound to a monotonic tick):")
    for ev in events:
        e = notarizer.notarize(ev)
        print(f"  {e}")
    root = notarizer.root()
    print(f"\nTimeline ROOT (8-chain, ~108-bit): {notarizer.root_hex()}")
    print(f"Verify clean log: {verify(notarizer.log, root)}")

    print("\nAdversary swaps events #1 and #2 to hide the config change order...")
    notarizer.log[1], notarizer.log[2] = notarizer.log[2], notarizer.log[1]
    print(f"Verify tampered log: {verify(notarizer.log, root)}")
    print("\n" + "=" * 64)


# --------------------------------------------------------------------------- #
if __name__ == "__main__":
    if "--measure" in sys.argv:
        _measure()
    elif "--demo" in sys.argv:
        _demo()
    else:
        raise SystemExit(_selftest())
