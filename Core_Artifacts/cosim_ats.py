#!/usr/bin/env python3
"""
Ansh-108 Core — A-TS host<->RTL co-sim DRIVER (Leg 1, isolated from S9).
========================================================================
Proves the genuinely novel A-TS claim against the REAL silicon design: a routed
FOLD chain (the integrated `core_top` RTL) reproduces the A-TS notarizer's
chain-0 stamps, bit-for-bit. The 8-chain notarizer's strength chains 1..7 are
host-side replication of the SAME proven primitive with different constants
(the documented replication story); chain 0 (B=108, seed=1) is the one the chip
itself runs, so it is the one the RTL must echo.

Pipeline (mirrors S9 but isolated -> never touches the proven S9 artifacts):
    A-TS notarized log (tick + event bytes per event, one continuous FOLD chain)
        -> the exact 28-bit foot sequence chain 0 consumes
        -> FOLD packets + a terminal RESET (bindu commits the maNDala)
        -> cosim_ats_vectors.txt
        -> [tb_cosim_ats.v drives Icarus-simulated core_top -> cosim_ats_out.txt]
        -> check_cosim_ats.py: RTL fingerprint == chain-0 stamp, per program.

Honesty cross-checks done HERE before any RTL runs:
  - chain-0 stamp == a REAL 8-chain `Notarizer`'s chain 0 over the same events,
  - chain-0 stamp == the proven S7 loopback host path (`last_committed_fp`).

Reuses (no re-impl): ats_notarizer (Notarizer/bytes_to_feet), golden_model
(packet encode + FOLD constants), cosim_s9 (Program/_classify/last_committed_fp/_counts).

Pure Python 3.8+. `python cosim_ats.py` (re)writes the vectors + golden sidecar.
"""
import os
import sys

ART = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ART)

from golden_model import (
    encode_data_packet, encode_packet, FOLD, RESET, FOLD_SEED, FOLD_B, Q,
)
from ats_notarizer import bytes_to_feet, Notarizer
from cosim_s9 import Program, _classify, last_committed_fp, _counts

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

VEC_FILE = os.path.join(ART, "cosim_ats_vectors.txt")
GOLD_FILE = os.path.join(ART, "cosim_ats_golden.txt")


def _as_bytes(ev):
    return ev if isinstance(ev, bytes) else ev.encode("utf-8")


def chain0_feet(events):
    """The exact foot sequence the notarizer's chain 0 consumes: for each event,
    the monotonic tick (counter starts at 0, +1 per event) then the event feet."""
    feet = []
    for i, ev in enumerate(events):
        feet.append(i + 1)                     # tick value (fits in 28 bits)
        feet.extend(bytes_to_feet(_as_bytes(ev)))
    return feet


def chain0_fold(feet):
    h = FOLD_SEED
    for f in feet:
        h = (h * FOLD_B + f) % Q               # the proven golden FOLD recurrence
    return h


def ats_program(name, events):
    feet = chain0_feet(events)
    fp = chain0_fold(feet)

    # cross-check 1: a REAL 8-chain notarizer's chain 0 must equal this stamp
    notar = Notarizer(n_chains=8)
    for ev in events:
        notar.notarize(ev)
    assert notar.fold.h[0] == fp, f"{name}: chain-0 != real Notarizer chain 0"

    # build the packet stream the RTL will run: FOLD each foot, then a bindu
    packets = [encode_data_packet(FOLD, f) for f in feet] + [encode_packet(RESET)]

    # cross-check 2: the proven S7 loopback host path agrees
    assert fp == last_committed_fp(packets), f"{name}: loopback host path disagreement"

    resets, pushes = _counts(packets)
    return Program(name, "ats", packets, fp, resets, pushes)


def build_battery():
    demo = [
        "boot: firmware v2.3.1 loaded",
        "user alice authenticated",
        "config changed: retention=90d",
        "export: dataset_4471 -> s3://audit/",
        "user alice logged out",
    ]
    swap = demo[:]
    swap[1], swap[2] = swap[2], swap[1]        # reorder two events -> must differ
    with open(os.path.join(ART, "cosim_chants", "gAyatrI.txt"), "rb") as f:
        gayatri = f.read()

    return [
        ats_program("ats_single", [b"alpha"]),
        ats_program("ats_demo", demo),
        ats_program("ats_demo_swap", swap),
        ats_program("ats_chant_gayatri", [gayatri]),
    ]


def write_vectors(progs):
    total = 0
    with open(VEC_FILE, "w", encoding="ascii", newline="\n") as vf:
        for pid, prog in enumerate(progs):
            for pkt in prog.packets:
                vf.write(f"{pid} {_classify(pkt)} {pkt:08x}\n")
                total += 1
    with open(GOLD_FILE, "w", encoding="ascii", newline="\n") as gf:
        for pid, prog in enumerate(progs):
            gf.write(f"P {pid} {prog.fp:04x} {prog.resets} {prog.resets} "
                     f"{prog.pushes} {prog.kind} {prog.name}\n")
    return len(progs), total


if __name__ == "__main__":
    progs = build_battery()
    n, total = write_vectors(progs)
    print("Ansh-108 A-TS co-sim driver (Leg 1: real notarizer -> vectors + golden)")
    print(f"  battery : {n} A-TS programs, {total} packets")
    print(f"  vectors : {VEC_FILE}")
    print(f"  golden  : {GOLD_FILE}")
    print("  per-program chain-0 stamp (what the RTL core_top must echo):")
    for pid, p in enumerate(progs):
        print(f"    [{pid}] {p.name:<20s} fp={p.fp:5d} (0x{p.fp:04x})  feet={p.pushes}")
    a = next(p for p in progs if p.name == "ats_demo").fp
    b = next(p for p in progs if p.name == "ats_demo_swap").fp
    print(f"  order check (host): fp(demo)=0x{a:04x} != fp(demo_swap)=0x{b:04x} -> {a != b}")
