#!/usr/bin/env python3
"""
Ansh-108 Core -- Path A, Phase 5 / S9: CO-SIM COMPARATOR (the integration gate).
================================================================================
Compares the Icarus-simulated RTL core_top output (cosim_rtl_out.txt) against the
golden values the REAL host pipeline produced (cosim_golden.txt / cosim_s9.py).
This is the leg that finally proves "the chant drove the actual chip design": the
host packet stream, executed by the RTL itself, agrees with the software golden.

Asserts:
  (a) RTL fingerprint == golden, for every program (chant / A0S / op).
  (b) every stream is bindu-terminated and fires exactly one bindu pulse per RESET
      (bindu_count == reset_count == golden #maNDalas), with 0 mid-stream gaps.
  (c) order sensitivity on the RTL: fp("aA") != fp("Aa").
  (d) VERIFY / REDUCE / arith match golden exactly; READ_TICK residues are in range,
      the HOST CRT reconstruction is self-consistent (host_ops == golden CRT ==
      Garner mixed-radix) and within one Maha-Yuga, and successive reads advance
      (monotonic, the write-protected free-running clock).

Plus a reproducibility sanity: the golden file is re-derived from the REAL host
path (cosim_s9.build_battery) and must match what was written.

Prints a per-program PASS table + ALL PASS/FAIL.  Exit 0 iff all pass.
Pure Python 3.8+ (numpy only transitively via host_ops cross-checks).
"""
from __future__ import annotations

from typing import Dict, List, Optional, Tuple
import os
import sys

ART = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ART)

import cosim_s9 as S9                                                  # noqa: E402
import host_ops                                                       # noqa: E402
from golden_model import (                                            # noqa: E402
    crt_reconstruct, COUNTER_MODULI, MAHA_YUGA,
    MUL, ADD, SUB, REDUCE, VERIFY, READ_TICK)

GOLD_FILE = os.path.join(ART, "cosim_golden.txt")
RTL_FILE = os.path.join(ART, "cosim_rtl_out.txt")
TICK_SENTINEL = S9.TICK_SENTINEL


# --------------------------------------------------------------------------- #
# Parsers
# --------------------------------------------------------------------------- #
def parse_golden() -> Dict[int, dict]:
    progs: Dict[int, dict] = {}
    with open(GOLD_FILE, "r", encoding="ascii") as fh:
        for line in fh:
            tok = line.split()
            if not tok:
                continue
            if tok[0] == "P":
                pid = int(tok[1])
                progs[pid] = {"fp": int(tok[2], 16), "bindu": int(tok[3]),
                              "resets": int(tok[4]), "pushes": int(tok[5]),
                              "kind": tok[6], "name": tok[7], "ops": []}
            elif tok[0] == "O":
                pid, opidx, opcode, exp = int(tok[1]), int(tok[2]), int(tok[3]), int(tok[4], 16)
                progs[pid]["ops"].append((opidx, opcode, exp))
    return progs


def parse_rtl() -> Tuple[Dict[int, dict], dict]:
    progs: Dict[int, dict] = {}
    summary: dict = {}
    with open(RTL_FILE, "r", encoding="ascii") as fh:
        for line in fh:
            tok = line.split()
            if not tok:
                continue
            if tok[0] == "P":
                # O lines for a program are emitted before its P line (P is written
                # at program close) -- merge, don't overwrite, the ops list.
                pid = int(tok[1])
                p = progs.setdefault(pid, {"ops": []})
                p.update({"fp": int(tok[2], 16), "bindu": int(tok[3]),
                          "reset": int(tok[4]), "pushes": int(tok[5]),
                          "gaps": int(tok[6])})
            elif tok[0] == "O":
                pid, opidx, opcode, res = int(tok[1]), int(tok[2]), int(tok[3]), int(tok[4], 16)
                progs.setdefault(pid, {"ops": []})["ops"].append((opidx, opcode, res))
            elif tok[0] == "SUMMARY":
                for kv in tok[1:]:
                    k, _, v = kv.partition("=")
                    summary[k] = int(v)
    return progs, summary


# --------------------------------------------------------------------------- #
# READ_TICK: unpack {c0[7:0], c1[4:0], c2[9:0]} and CRT-reconstruct host-side
# --------------------------------------------------------------------------- #
def unpack_tick(word: int) -> Tuple[int, int, int]:
    return ((word >> 15) & 0xFF, (word >> 10) & 0x1F, word & 0x3FF)


def tick_value(word: int) -> Tuple[int, Tuple[int, int, int], List[str]]:
    """Reconstruct the absolute tick host-side; return (value, residues, errors)."""
    res = unpack_tick(word)
    errs: List[str] = []
    lim = (256, 27, 625)
    for r, m in zip(res, lim):
        if not (0 <= r < m):
            errs.append(f"residue {r} out of range mod {m}")
    v_host = host_ops.reconstruct(res, COUNTER_MODULI)        # S7 host CRT
    v_gold = crt_reconstruct(list(res), COUNTER_MODULI)       # S1 golden CRT
    v_garner = host_ops.mixed_radix_value(res, COUNTER_MODULI)  # Garner cross-check
    if not (v_host == v_gold == v_garner):
        errs.append(f"CRT disagreement host={v_host} gold={v_gold} garner={v_garner}")
    if not (0 <= v_host < MAHA_YUGA):
        errs.append(f"tick {v_host} outside one Maha-Yuga")
    return v_host, res, errs


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #
def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    print("Ansh-108 S9 -- host<->RTL co-sim comparator (the integration gate)")

    if not (os.path.exists(GOLD_FILE) and os.path.exists(RTL_FILE)):
        print("  [FATAL] run cosim_s9.py then the iverilog TB first "
              "(missing cosim_golden.txt / cosim_rtl_out.txt)")
        return 2

    gold = parse_golden()
    rtl, summary = parse_rtl()

    fails = 0

    checks: List[Tuple[str, bool]] = []

    def check(name, cond):
        nonlocal fails
        if not cond:
            fails += 1
        checks.append((name, bool(cond)))
        return cond

    # ---- reproducibility: golden file == fresh real-host-path recompute ------ #
    battery = S9.build_battery()
    repro_ok = (len(battery) == len(gold))
    for pid, prog in enumerate(battery):
        g = gold.get(pid)
        if g is None:
            repro_ok = False
            break
        exp_ops = [(i, code, (TICK_SENTINEL if exp is None else exp))
                   for i, (code, exp) in enumerate(prog.ops)]
        repro_ok &= (g["fp"] == prog.fp and g["resets"] == prog.resets
                     and g["pushes"] == prog.pushes and g["name"] == prog.name
                     and g["ops"] == exp_ops)
    check("golden sidecar reproducible from the real host path (cosim_s9.build_battery)",
          repro_ok)

    # ---- per-program comparison (the headline integration check) ------------ #
    name_to_pid = {g["name"]: pid for pid, g in gold.items()}
    print("\n  per-program co-sim (RTL core_top vs golden host pipeline):")
    print(f"    {'pid':>3s} {'program':<22s} {'kind':<5s} {'golden':>7s} {'rtl':>7s} "
          f"{'bindu':>6s} {'feet':>5s} {'ops':>4s}  result")

    OPNAME = {MUL: "MUL", ADD: "ADD", SUB: "SUB", REDUCE: "REDUCE",
              VERIFY: "VERIFY", READ_TICK: "READ_TICK"}

    n_mismatch = 0
    for pid in sorted(gold):
        g = gold[pid]
        r = rtl.get(pid)
        prog_fail = []
        if r is None:
            prog_fail.append("NO RTL OUTPUT")
        else:
            # (a) fingerprint
            if r["fp"] != g["fp"]:
                prog_fail.append(f"fp {r['fp']}!={g['fp']}")
            # (b) bindu-terminated, one pulse per RESET, no gaps
            if not (r["bindu"] == r["reset"] == g["bindu"] == g["resets"]):
                prog_fail.append(f"bindu {r['bindu']}/reset {r['reset']} vs {g['resets']}")
            if r["pushes"] != g["pushes"]:
                prog_fail.append(f"feet {r['pushes']}!={g['pushes']}")
            if r["gaps"] != 0:
                prog_fail.append(f"gaps {r['gaps']}")
            # (d) gated ops
            rtl_ops = {(i, op): res for (i, op, res) in r["ops"]}
            for (i, op, exp) in g["ops"]:
                got = rtl_ops.get((i, op))
                if got is None:
                    prog_fail.append(f"op[{i}] {OPNAME.get(op,op)} missing")
                    continue
                if op == READ_TICK:
                    v, res, errs = tick_value(got)
                    if errs:
                        prog_fail.append(f"op[{i}] READ_TICK {errs}")
                else:
                    if got != exp:
                        prog_fail.append(f"op[{i}] {OPNAME.get(op,op)} {got}!={exp}")

        status = "PASS" if not prog_fail else "FAIL: " + "; ".join(prog_fail)
        if prog_fail:
            n_mismatch += 1
        rfp = r["fp"] if r else -1
        print(f"    {pid:3d} {g['name']:<22s} {g['kind']:<5s} {g['fp']:7d} {rfp:7d} "
              f"{g['resets']:6d} {g['pushes']:5d} {len(g['ops']):4d}  {status}")

    check(f"every program: RTL fingerprint == golden, bindu-terminated, ops match "
          f"({len(gold)} programs, {n_mismatch} mismatch)", n_mismatch == 0)

    # ---- (c) order sensitivity on the RTL ----------------------------------- #
    if "order_aA" in name_to_pid and "order_Aa" in name_to_pid:
        fa = rtl[name_to_pid["order_aA"]]["fp"]
        fb = rtl[name_to_pid["order_Aa"]]["fp"]
        check(f"order sensitivity on RTL: fp(aA)={fa} != fp(Aa)={fb}", fa != fb)
    else:
        check("order sensitivity pair present", False)

    # ---- (d) READ_TICK monotonic (write-protected free-running clock) -------- #
    if "op_readtick" in name_to_pid:
        rp = rtl[name_to_pid["op_readtick"]]
        ticks = [tick_value(res)[0] for (_, op, res) in sorted(rp["ops"]) if op == READ_TICK]
        mono = len(ticks) >= 2 and all(b > a for a, b in zip(ticks, ticks[1:]))
        check(f"READ_TICK monotonic across reads (advancing clock): {ticks}", mono)
    else:
        check("op_readtick program present", False)

    # ---- summary consistency ------------------------------------------------ #
    check(f"TB tick monitor clean over the whole battery (tick_errors=0)",
          summary.get("tick_errors", -1) == 0)
    check("TB program count == battery size",
          summary.get("programs", -1) == len(gold))

    total_pkts = summary.get("packets", -1)
    print(f"\n  battery: {len(gold)} programs, {total_pkts} packets driven into RTL core_top")
    print("  legs: Leg 1 (golden = real S6/S7/S8 host path) + "
          "Leg 2 (Icarus core_top + 9 submodules)")

    print("\n  gate legs:")
    for name, ok in checks:
        print(f"    [{'PASS' if ok else 'FAIL'}] {name}")

    print(f"\n{'ALL PASS' if fails == 0 else str(fails) + ' FAILURE(S)'}")
    return 0 if fails == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
