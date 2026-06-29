#!/usr/bin/env python3
"""
Ansh-108 Core -- Path A, Phase 3 / S7: STAGING AGENT (the whole front chamber).
===============================================================================
Ties the S6 data path (parse / slice / assemble) to the S7 modules
(transport + result_reader + clock_led) into one driver:

    .txt  ->  parse/slice/assemble (S6)  ->  packets
          ->  clock/LED state machine (timing + colours)
          ->  loopback transport (whole packets only)  ->  core events
          ->  result reader (fingerprint read BEFORE the bindu)
          ->  human-readable result.

The headline is a chant fingerprint, but the agent also runs general A0S programs
(arith / verify / read-tick) and routes every result mode. The CLI prints the
packet stream, the LED/clock timeline, and the verified fingerprint.

HONESTY: this is host <-> SOFTWARE-GOLDEN loopback. It is NOT host <-> RTL co-sim
(that is S9) and there is NO real USB yet (Phase 7). Both gaps are explicit.

Pure Python 3.8+, no third-party deps. `python staging_agent.py <chant.txt>`.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Sequence, Tuple
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import host_staging as H                                              # noqa: E402
from transport import LoopbackTransport, Transport, CoreEvent         # noqa: E402
from result_reader import interpret, fold_fingerprint, Reading        # noqa: E402
from clock_led import ClockLed, State, LED_COLOR, program_duration_ms # noqa: E402
from golden_model import fold_text, RESET                             # noqa: E402


# --------------------------------------------------------------------------- #
# Structured result
# --------------------------------------------------------------------------- #
@dataclass
class StagingResult:
    source: str
    n_bits: int
    laghu: int
    guru: int
    feet: int
    pad_bits: int
    packets: List[int]
    fingerprint: int
    readings: List[Reading]
    timeline: list
    total_ms: int
    verified: bool                # fingerprint == host fold == golden fold
    final_led: str


# --------------------------------------------------------------------------- #
# The agent
# --------------------------------------------------------------------------- #
class StagingAgent:
    """Drives one chant/program through the full front chamber. Reusable; the
    transport's free-running tick persists across runs (write-protected clock)."""

    def __init__(self, transport: Optional[Transport] = None) -> None:
        self.transport = transport or LoopbackTransport()

    # -- chant: text -> fingerprint ----------------------------------------- #
    def run_text(self, text: str, source: str = "<text>") -> StagingResult:
        bits = H.parse_text(text)
        sr = H.slice_feet(bits)

        led = ClockLed()
        led.step("load", f"{len(bits)} laghu/guru")
        # COMPILE: build the exact packet stream (S6 data path)
        packets = H.assemble_fold(sr.feet, with_bindu=True)
        led.step("compile_ok", f"{len(packets)} packets ({len(sr.feet)} FOLD + bindu)")
        # WARNING: the 3-second abort window
        led.step("warn_done", "3 s warning elapsed")
        # EXECUTE (entered by warn_done): model per-syllable ISI timing AND stream
        # whole packets to the core.
        for b in bits:
            led.emit_syllable(b)
        events = self.transport.open().send(packets)
        led.step("exec_done", "bindu reached")
        led.step("flush_done", "reseeded")

        readings = interpret(events)
        fp = fold_fingerprint(events)              # read before the bindu reseed
        verified = (fp == H.fold_fingerprint(text) == fold_text(text))
        return StagingResult(
            source=source, n_bits=sr.n_bits, laghu=bits.count(0), guru=bits.count(1),
            feet=len(sr.feet), pad_bits=sr.pad_bits, packets=packets, fingerprint=fp,
            readings=readings, timeline=led.timeline, total_ms=led.t_ms,
            verified=verified, final_led=led.led)

    def run_file(self, path: str) -> StagingResult:
        with open(path, "r", encoding="utf-8", errors="ignore") as fh:
            return self.run_text(fh.read(), source=path)

    # -- general A0S program: list of ops -> routed readings ---------------- #
    def run_program(self, ops: Sequence[tuple]) -> List[Reading]:
        packets = H.assemble(ops)
        events = self.transport.open().send(packets)
        return interpret(events)


# --------------------------------------------------------------------------- #
# Human-readable report
# --------------------------------------------------------------------------- #
def format_report(r: StagingResult) -> str:
    lines = []
    lines.append(f"# source         : {r.source}")
    lines.append(f"# laghu/guru bits: {r.n_bits}  ({r.laghu} laghu / {r.guru} guru)")
    lines.append(f"# feet           : {r.feet}  (final foot zUnya-padded {r.pad_bits} bits)")
    lines.append(f"# packets        : {len(r.packets)}  (incl. 1 bindu exit)")
    lines.append(f"# fold fingerprint: {r.fingerprint}  (0x{r.fingerprint:04x})  "
                 f"[{'VERIFIED vs host+golden' if r.verified else 'MISMATCH!'}]")
    lines.append(f"# session time   : {r.total_ms} ms  (3 s warning + ISI + flush)")
    lines.append("# LED / clock timeline:")
    for e in r.timeline:
        lines.append(f"    {e.t_ms:6d} ms  {e.state:<11s} {e.led:<7s} {e.note}")
    lines.append("# packet stream:")
    for p in r.packets:
        op = (p >> 28) & 0xF
        lines.append(f"    {p:08x}  op={op:2d}")
    lines.append("# results:")
    for rd in r.readings:
        lines.append(f"    {rd.detail}")
    lines.append("# NOTE: host<->software-golden loopback (NOT host<->RTL = S9; no real USB = Phase 7).")
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def _cli(argv: List[str]) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    if len(argv) < 2:
        print("usage: staging_agent.py <chant.txt>")
        return 1
    agent = StagingAgent()
    res = agent.run_file(argv[1])
    print(format_report(res))
    return 0 if res.verified else 2


# --------------------------------------------------------------------------- #
# Self-test
# --------------------------------------------------------------------------- #
def _selftest() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    import random
    from golden_model import CRITICAL, HANDSHAKE, STREAM, FIRE_FORGET
    random.seed(108)
    fails = 0

    def check(name, cond):
        nonlocal fails
        print(f"  [{'PASS' if cond else 'FAIL'}] {name}")
        if not cond:
            fails += 1

    print("Ansh-108 S7 -- staging_agent (full front chamber) self-test")

    agent = StagingAgent()

    # ---- end-to-end chant: fingerprint verified vs host + golden ------------ #
    texts = ["", "a", "A", "aA", "Aa", "aAaAbcD", "a" * 28, "A" * 28, "a" * 29,
             "A" * 56 + "b", "Om Namah Shivaya", "AaAaAa bb CC dd"]
    texts += ["".join(random.choice("aAbZzq .,\n9") for _ in range(random.randint(0, 120)))
              for _ in range(2000)]
    e2e_ok = bindu_ok = led_ok = True
    for t in texts:
        r = agent.run_text(t)
        e2e_ok &= r.verified and r.fingerprint == fold_text(t)
        bindu_ok &= ((r.packets[-1] >> 28) & 0xF) == RESET
        led_ok &= (r.final_led == "BLUE")                     # ends back in HOLD/BLUE
    check(f"END-TO-END: agent fingerprint == host == golden over {len(texts)} chants", e2e_ok)
    check("every run ends in the bindu exit + returns to HOLD (BLUE)", bindu_ok and led_ok)

    # ---- timing matches the forward model ----------------------------------- #
    r = agent.run_text("aA AA aa")            # bits: 0,1,1,1,0,0  -> 3 laghu+3 guru = 450
    bits = H.parse_text("aA AA aa")
    check("session time == 3000 (warn) + ISI + 50 (flush)",
          r.total_ms == 3000 + program_duration_ms(bits) + 50)

    # ---- general program routes all four contracts -------------------------- #
    prog = [("MUL", 6, 7), ("ADD", 100, 23), ("VERIFY", 5, 5), ("FOLD", 9),
            ("READ_TICK",), ("FLUSH",)]
    rd = agent.run_program(prog)
    modes = {x.mode for x in rd}
    check("run_program routes CRITICAL+HANDSHAKE+STREAM+FIRE_FORGET",
          {CRITICAL, HANDSHAKE, STREAM, FIRE_FORGET} <= modes)
    check("run_program MUL reading == 42", any(x.value == 42 and x.mode == CRITICAL for x in rd))

    # ---- report renders without crashing (utf-8 diacritics) ----------------- #
    rep = format_report(agent.run_text("Om Namah Shivaya"))
    check("format_report renders fingerprint + timeline + VERIFIED",
          "fold fingerprint" in rep and "VERIFIED" in rep and "EXECUTE" in rep)

    # ---- determinism + order sensitivity through the whole agent ------------ #
    check("agent deterministic", agent.run_text("aAaAbcD").fingerprint
          == agent.run_text("aAaAbcD").fingerprint)
    check("agent order-sensitive (aA != Aa)",
          agent.run_text("aA").fingerprint != agent.run_text("Aa").fingerprint)

    print(f"\n{'ALL PASS' if fails == 0 else str(fails) + ' FAILURE(S)'}")
    return fails


if __name__ == "__main__":
    if len(sys.argv) >= 2 and sys.argv[1] not in ("--selftest", "-t"):
        raise SystemExit(_cli(sys.argv))
    raise SystemExit(_selftest())
