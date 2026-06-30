#!/usr/bin/env python3
"""
Ansh-108 Core — A-TS host<->RTL co-sim COMPARATOR (Leg 2 gate, isolated from S9).
=================================================================================
Compares the Icarus-simulated RTL `core_top` output (cosim_ats_out.txt) against
the A-TS chain-0 stamps the real notarizer produced (cosim_ats_golden.txt /
cosim_ats.py). This is the leg that proves "the routed FOLD chain echoes the
A-TS stamps": the notarizer's timestamped fingerprint, executed by the actual
chip RTL, agrees bit-for-bit.

Asserts:
  (a) RTL fingerprint == golden chain-0 stamp, for every A-TS program.
  (b) order sensitivity on the RTL: fp(ats_demo) != fp(ats_demo_swap).
  (c) the tick monitor was clean (free-running, write-protected clock held).
  (d) golden is reproducible from the real notarizer path (cosim_ats.build_battery).

Exit 0 iff all pass.  Pure Python 3.8+.
"""
import os
import sys

ART = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ART)
import cosim_ats as D

GOLD = os.path.join(ART, "cosim_ats_golden.txt")
RTL = os.path.join(ART, "cosim_ats_out.txt")

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def parse_golden():
    progs = {}
    with open(GOLD, encoding="ascii") as fh:
        for line in fh:
            t = line.split()
            if t and t[0] == "P":
                progs[int(t[1])] = {"fp": int(t[2], 16), "name": t[7]}
    return progs


def parse_rtl():
    progs, summary = {}, {}
    with open(RTL, encoding="ascii") as fh:
        for line in fh:
            t = line.split()
            if not t:
                continue
            if t[0] == "P":
                progs[int(t[1])] = {"fp": int(t[2], 16)}
            elif t[0] == "SUMMARY":
                for kv in t[1:]:
                    k, v = kv.split("=")
                    summary[k] = int(v)
    return progs, summary


def main():
    fails = 0
    checks = []

    def check(name, ok):
        nonlocal fails
        checks.append((name, ok))
        if not ok:
            fails += 1

    gold = parse_golden()
    rtl, summary = parse_rtl()

    # (d) reproducibility: golden re-derived from the real notarizer path
    battery = D.build_battery()
    repro = (len(battery) == len(gold) and
             all(p.fp == gold[i]["fp"] for i, p in enumerate(battery)))
    check("golden reproducible from real notarizer (cosim_ats.build_battery)", repro)

    # (a) per-program RTL == golden chain-0 stamp
    name_to_pid = {g["name"]: pid for pid, g in gold.items()}
    mism = 0
    for pid, g in gold.items():
        if pid not in rtl or rtl[pid]["fp"] != g["fp"]:
            mism += 1
    check(f"RTL core_top fp == chain-0 stamp for all {len(gold)} A-TS programs "
          f"({mism} mismatch)", mism == 0)

    # (b) order sensitivity on the RTL
    if "ats_demo" in name_to_pid and "ats_demo_swap" in name_to_pid:
        fa = rtl[name_to_pid["ats_demo"]]["fp"]
        fb = rtl[name_to_pid["ats_demo_swap"]]["fp"]
        check(f"order sensitivity on RTL: fp(demo)=0x{fa:04x} != "
              f"fp(demo_swap)=0x{fb:04x}", fa != fb)
    else:
        check("order-sensitivity pair present", False)

    # (c) tick monitor clean + program count
    check("tick monitor clean over the run (tick_errors=0)",
          summary.get("tick_errors", -1) == 0)
    check("RTL program count == golden battery size",
          summary.get("programs", -1) == len(gold))

    print("A-TS host<->RTL co-sim gate (routed core_top vs notarizer chain-0)")
    print(f"  battery: {len(gold)} A-TS programs, "
          f"{summary.get('packets','?')} packets driven into RTL core_top")
    print("  per-program echo:")
    for pid in sorted(gold):
        g, r = gold[pid]["fp"], rtl.get(pid, {}).get("fp")
        mark = "OK " if r == g else "XX "
        print(f"    [{pid}] {gold[pid]['name']:<20s} golden=0x{g:04x} "
              f"rtl=0x{r:04x} {mark}")
    print("\n  gate legs:")
    for name, ok in checks:
        print(f"    [{'PASS' if ok else 'FAIL'}] {name}")
    print(f"\n{'ALL PASS' if fails == 0 else str(fails) + ' FAILURE(S)'}")
    return 0 if fails == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
