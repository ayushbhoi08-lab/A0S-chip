#!/usr/bin/env python3
"""
Ansh-108 Core S6 -- verification leg for the host staging agent (host_staging.py).
==================================================================================
Phase-3 gate (plan §3 / §5 row S6): unit tests on parser/slicer/assembler with
golden vectors, every algorithm cross-checked against the S1 source of truth
golden_model.py, plus a SOFTWARE LOOPBACK: the host's emitted packet stream, run
through golden_model, reproduces golden_model.fold_text(text) EXACTLY -- i.e. the
host turns a .txt into the precise stream a known-good (software) core consumes.

This is a software phase: the gate is unit tests + golden cross-check + software
loopback. The HARDWARE co-sim (driving the real core_top RTL) is Phase 5 / S9.
"""
import os
import sys
import random

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import host_staging as H                                              # noqa: E402
from golden_model import (                                            # noqa: E402
    text_to_bits, slice_bits_to_feet, encode_packet, encode_data_packet,
    decode_packet, fold_text, AnshCoreGolden,
    MUL, ADD, SUB, REDUCE, FOLD, VERIFY, READ_TICK, FLUSH, RESET, Q)


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    fails = 0

    def check(name, cond):
        nonlocal fails
        print(f"  [{'PASS' if cond else 'FAIL'}] {name}")
        if not cond:
            fails += 1

    print("Ansh-108 S6 -- host staging agent (parser/slicer/assembler) verification")
    random.seed(108)

    # ---- 1. PARSER ----------------------------------------------------------- #
    check("parser maps case + strips non-letters",
          H.parse_text("aA9 zZ.\n\tB-c") == [0, 1, 0, 1, 1, 0])
    check("parser empty -> []", H.parse_text("") == [] and H.parse_text("123 .,\n") == [])
    # cross-check vs golden text_to_bits over random unicode-ish strings
    alphabet = "aAbBzZ09 .,\n\t!@#x_Q"
    pok = True
    for _ in range(5000):
        s = "".join(random.choice(alphabet) for _ in range(random.randint(0, 40)))
        if H.parse_text(s) != text_to_bits(s):
            pok = False
            break
    check("parser == golden text_to_bits over 5000 random strings", pok)

    # ---- 2. SLICER ----------------------------------------------------------- #
    # directed: zUnya-pad of a short final foot (golden vector)
    sr = H.slice_feet([1, 1], width=4)
    check("slicer zUnya-pads final foot ([1,1],w=4 -> 0b1100)", sr.feet == [0b1100] and sr.pad_bits == 2)
    check("slicer empty -> single all-zUnya foot", H.slice_feet([]).feet == [0] and H.slice_feet([]).pad_bits == 28)
    # exact-multiple: no pad
    sr2 = H.slice_feet([1, 0, 1, 0], width=4)
    check("slicer exact multiple -> 0 pad", sr2.feet == [0b1010] and sr2.pad_bits == 0)
    # cross-check feet vs golden slice_bits_to_feet (width 28) over random lengths
    sok = padok = True
    for _ in range(5000):
        n = random.randint(0, 200)
        bits = [random.randint(0, 1) for _ in range(n)]
        r = H.slice_feet(bits)
        if r.feet != slice_bits_to_feet(bits, width=28):
            sok = False
            break
        # pad accounting must be self-consistent: width*nfeet == nbits + pad  (nonempty)
        if n > 0 and 28 * len(r.feet) != n + r.pad_bits:
            padok = False
            break
    check("slicer feet == golden slice_bits_to_feet over 5000 random lengths", sok)
    check("slicer pad accounting consistent (28*nfeet == nbits + pad)", padok)

    # ---- 3. ASSEMBLER / packet builders ------------------------------------- #
    # builders match golden encode_* exactly
    eok = True
    for _ in range(20000):
        x, y = random.randrange(Q), random.randrange(Q)
        d = random.randrange(1 << 28)
        if (H.pkt_fast(MUL, x, y) != encode_packet(MUL, x, y)
                or H.pkt_data(FOLD, d) != encode_data_packet(FOLD, d)):
            eok = False
            break
    check("pkt_fast/pkt_data == golden encode_packet/encode_data_packet (20k)", eok)
    # decode round-trip of fast-lane operands
    rok = True
    for _ in range(20000):
        x, y = random.randrange(1 << 14), random.randrange(1 << 14)
        dd = decode_packet(H.pkt_fast(ADD, x, y))
        if not (dd["opcode"] == ADD and dd["x"] == x and dd["y"] == y):
            rok = False
            break
    check("fast-lane packets round-trip through golden decode_packet (20k)", rok)
    # assemble_fold structure: all FOLD then exactly one RESET (bindu) at the end
    feet = [5, 9, (1 << 28) - 1]
    pk = H.assemble_fold(feet)
    check("assemble_fold: N FOLD packets + 1 bindu(RESET) exit",
          len(pk) == 4
          and all(((p >> 28) & 0xF) == FOLD for p in pk[:-1])
          and ((pk[-1] >> 28) & 0xF) == RESET)
    # general assembler round-trips ops and injects bindu
    prog = [("MUL", 12345, 6789), ("ADD", 1, 2), ("REDUCE", 268435455),
            ("VERIFY", 7, 7), ("FOLD", 42), ("READ_TICK",), ("FLUSH",)]
    apk = H.assemble(prog)
    aok = (len(apk) == len(prog) + 1 and ((apk[-1] >> 28) & 0xF) == RESET)
    decoded = [decode_packet(p) for p in apk]
    aok &= (decoded[0]["opcode"] == MUL and decoded[0]["x"] == 12345 and decoded[0]["y"] == 6789)
    aok &= (decoded[2]["opcode"] == REDUCE and decoded[2]["data"] == 268435455)
    aok &= (decoded[5]["opcode"] == READ_TICK)
    check("assemble(): ops round-trip + bindu appended", aok)
    check("assemble(): no double bindu if program already ends in RESET",
          ((H.assemble([("RESET",)])) == [H.pkt_data(RESET, 0)]))

    # ---- 4. SOFTWARE LOOPBACK (host stream -> golden == fold_text) ----------- #
    # The headline S6 contract: a chant .txt -> host packets -> executed by the
    # golden core -> the fingerprint matches golden_model.fold_text(text), and the
    # stream ends in the bindu exit. Run over many random chants incl. corners.
    texts = ["", "a", "A", "aA", "Aa", "aAaAbcD",
             "a" * 28, "A" * 28, "a" * 29, "A" * 56 + "b",
             "Om Namah Shivaya", "AaAaAa bb CC dd"]
    texts += ["".join(random.choice("aAbZzq .,\n9") for _ in range(random.randint(0, 120)))
              for _ in range(3000)]
    lok = bindu_ok = True
    for t in texts:
        pkts = H.text_to_fold_packets(t)
        if ((pkts[-1] >> 28) & 0xF) != RESET:        # bindu exit present
            bindu_ok = False
            break
        core = AnshCoreGolden()                       # fresh: h = seed = 1
        h = None
        for p in pkts[:-1]:                            # execute FOLD packets (read before bindu)
            h = core.execute(p).value
        if not (h == fold_text(t) == H.fold_fingerprint(t)):
            lok = False
            break
    check(f"LOOPBACK: host stream -> golden == fold_text over {len(texts)} chants", lok)
    check("every stream ends in the bindu (RESET) exit", bindu_ok)
    # order-sensitivity + determinism survive the full host pipeline
    check("host pipeline order-sensitive (aA != Aa)",
          H.fold_fingerprint("aA") != H.fold_fingerprint("Aa"))
    check("host pipeline deterministic",
          H.text_to_fold_packets("aAaAbcD") == H.text_to_fold_packets("aAaAbcD"))

    print(f"\n{'ALL PASS' if fails == 0 else str(fails) + ' FAILURE(S)'}")
    return fails


if __name__ == "__main__":
    raise SystemExit(main())
