#!/usr/bin/env python3
"""
Ansh-108 Core -- Path A, Phase 3 / S7: CLOCK / LED state machine (the front face).
==================================================================================
A PURE, DETERMINISTIC forward-model of the staging machine's clock + LED state
machine. No real LEDs, no wall-clock timing -- it computes the exact state
sequence and the forward-modeled inter-syllable timing so the rest of the agent
(and, later, the firmware) has a single reference for "what colour, for how long."

Timing (forward-modeled ISI, plan §3 Phase 3):
  * laghu (short, bit 0) = 50 ms
  * guru  (long,  bit 1) = 100 ms
  * a 3-second warning window before EXECUTE (the abort window).

States + the LOCKED LED colour map (locked here in S7 -- the plan referenced a
"locked table" that had not yet been written down; this is it):

  HOLD        BLUE     idle / waiting for a program ("Enter" hold)
  COMPILE     AMBER    host parsing / slicing / assembling the packet stream
  WARNING_3S  ORANGE   3 s countdown before execution (abort still possible)
  EXECUTE     GREEN    streaming pAdas to the core (per-syllable ISI timing)
  FLUSH       WHITE    reseed / bindu / zUnya (resonates with the canon "white")
  ERROR       RED      parse or runtime fault

The colour map is engineering-locked; the cosmology behind it (Agni-triangle, the
five elements) lives in the story canon and the S8 grammar layer, not here.

Pure Python 3.8+, no third-party deps. Importable + `python clock_led.py` test.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Sequence, Tuple
import sys


# --------------------------------------------------------------------------- #
# Locked timing + colour constants
# --------------------------------------------------------------------------- #
LAGHU_MS = 50            # short syllable / bit 0
GURU_MS = 100            # long syllable / bit 1
WARNING_MS = 3000        # the 3-second pre-execute warning (abort window)
FLUSH_MS = LAGHU_MS      # one laghu pulse to reseed
COMPILE_MS = 0           # host compile is modeled as instantaneous (pure software)


class State(Enum):
    HOLD = "HOLD"
    COMPILE = "COMPILE"
    WARNING_3S = "WARNING_3S"
    EXECUTE = "EXECUTE"
    FLUSH = "FLUSH"
    ERROR = "ERROR"


# the LOCKED LED colour map (S7)
LED_COLOR: Dict[State, str] = {
    State.HOLD: "BLUE",
    State.COMPILE: "AMBER",
    State.WARNING_3S: "ORANGE",
    State.EXECUTE: "GREEN",
    State.FLUSH: "WHITE",
    State.ERROR: "RED",
}

# the LOCKED transition table: TRANSITIONS[state][event] = next_state.
# Any (state, event) not present is an illegal transition (the model raises).
TRANSITIONS: Dict[State, Dict[str, State]] = {
    State.HOLD:       {"load": State.COMPILE, "ack": State.HOLD},
    State.COMPILE:    {"compile_ok": State.WARNING_3S, "compile_fail": State.ERROR},
    State.WARNING_3S: {"warn_done": State.EXECUTE, "abort": State.HOLD},
    State.EXECUTE:    {"exec_done": State.FLUSH, "exec_fail": State.ERROR},
    State.FLUSH:      {"flush_done": State.HOLD},
    State.ERROR:      {"ack": State.HOLD},
}


def isi_ms(bit: int) -> int:
    """Forward-modeled inter-syllable interval for a laghu (0) or guru (1)."""
    return GURU_MS if bit else LAGHU_MS


def program_duration_ms(bits: Sequence[int]) -> int:
    """Total ISI time to stream a laghu/guru bit sequence."""
    return sum(isi_ms(b) for b in bits)


# --------------------------------------------------------------------------- #
# The deterministic FSM
# --------------------------------------------------------------------------- #
@dataclass
class TimelineEntry:
    t_ms: int
    state: str
    led: str
    note: str


@dataclass
class ClockLed:
    """Deterministic clock/LED FSM. `step(event)` applies a locked transition and
    advances the modeled clock by that event's known duration; illegal transitions
    raise. `timeline` records (t_ms, state, led, note) for human-readable output."""
    state: State = State.HOLD
    t_ms: int = 0
    timeline: List[TimelineEntry] = field(default_factory=list)

    def __post_init__(self):
        self._record("genesis")

    # -- introspection ------------------------------------------------------- #
    @property
    def led(self) -> str:
        return LED_COLOR[self.state]

    def _record(self, note: str) -> None:
        self.timeline.append(TimelineEntry(self.t_ms, self.state.value, self.led, note))

    def _advance(self, ms: int) -> None:
        if ms < 0:
            raise ValueError("time cannot run backwards")
        self.t_ms += ms

    # -- the one transition primitive ---------------------------------------- #
    def step(self, event: str, note: str = "") -> State:
        table = TRANSITIONS[self.state]
        if event not in table:
            raise ValueError(f"illegal transition: {event!r} not allowed from {self.state.value}")
        # durations attached to specific transitions (forward-modeled)
        if event == "load":
            self.t_ms = 0                          # genesis of a new session clock
        elif event == "compile_ok":
            self._advance(COMPILE_MS)
        elif event == "warn_done":
            self._advance(WARNING_MS)              # the 3-second warning elapsed
        elif event == "flush_done":
            self._advance(FLUSH_MS)
        self.state = table[event]
        self._record(note or event)
        return self.state

    # -- EXECUTE-only: emit one syllable, advancing the ISI clock ------------ #
    def emit_syllable(self, bit: int) -> int:
        if self.state is not State.EXECUTE:
            raise ValueError("syllables can only be emitted in EXECUTE")
        self._advance(isi_ms(bit))
        return self.t_ms

    # -- high-level convenience: run a whole chant through the face ---------- #
    def run_program(self, bits: Sequence[int], emit_syllables: bool = True) -> int:
        """HOLD -> COMPILE -> WARNING_3S -> EXECUTE (stream bits) -> FLUSH -> HOLD.
        Returns the total modeled session time in ms."""
        self.step("load", "program loaded")
        self.step("compile_ok", "compiled -> packets")
        self.step("warn_done", "3 s warning elapsed")          # +3000 ms
        if emit_syllables:
            for b in bits:
                self.emit_syllable(b)                            # +50/100 ms each
        else:
            self._advance(program_duration_ms(bits))
        self.step("exec_done", "bindu reached")
        self.step("flush_done", "reseeded")                    # +50 ms
        return self.t_ms

    def fault(self, where: str = "exec", note: str = "fault") -> State:
        """Drive into ERROR from COMPILE (parse) or EXECUTE (runtime)."""
        if where == "compile":
            return self.step("compile_fail", note)
        return self.step("exec_fail", note)


# --------------------------------------------------------------------------- #
# Self-test
# --------------------------------------------------------------------------- #
def _selftest() -> int:
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

    print("Ansh-108 S7 -- clock_led (clock/LED state machine) self-test")

    # ---- colour map: every state has a locked colour, all distinct ---------- #
    check("LED colour map covers all 6 states, all distinct",
          set(LED_COLOR) == set(State) and len(set(LED_COLOR.values())) == 6)
    check("locked colours: HOLD=BLUE EXECUTE=GREEN ERROR=RED FLUSH=WHITE WARNING=ORANGE COMPILE=AMBER",
          LED_COLOR[State.HOLD] == "BLUE" and LED_COLOR[State.EXECUTE] == "GREEN"
          and LED_COLOR[State.ERROR] == "RED" and LED_COLOR[State.FLUSH] == "WHITE"
          and LED_COLOR[State.WARNING_3S] == "ORANGE" and LED_COLOR[State.COMPILE] == "AMBER")

    # ---- ISI timing exact ---------------------------------------------------- #
    check("isi: laghu=50, guru=100", isi_ms(0) == 50 and isi_ms(1) == 100)
    bits = [0, 1, 1, 0, 0, 1]      # 3 laghu (150) + 3 guru (300) = 450
    check("program_duration == 50*laghu + 100*guru", program_duration_ms(bits) == 450)

    # ---- the happy-path transition sequence is exact ------------------------ #
    m = ClockLed()
    seq = []
    m.step("load"); seq.append(m.state)
    m.step("compile_ok"); seq.append(m.state)
    m.step("warn_done"); seq.append(m.state)
    m.step("exec_done"); seq.append(m.state)
    m.step("flush_done"); seq.append(m.state)
    check("HOLD->COMPILE->WARNING_3S->EXECUTE->FLUSH->HOLD exact",
          seq == [State.COMPILE, State.WARNING_3S, State.EXECUTE, State.FLUSH, State.HOLD])

    # ---- run_program timing: 3000 (warn) + ISI + 50 (flush) ----------------- #
    m = ClockLed()
    total = m.run_program(bits)
    check("run_program total == WARNING_MS + ISI + FLUSH_MS",
          total == WARNING_MS + program_duration_ms(bits) + FLUSH_MS == 3000 + 450 + 50)
    # the EXECUTE syllable clock advances exactly per syllable
    exec_entries = [e for e in m.timeline if e.state == "EXECUTE"]
    check("EXECUTE entered with GREEN at t = WARNING window end",
          exec_entries and exec_entries[0].led == "GREEN" and exec_entries[0].t_ms == 3000)

    # ---- abort window: WARNING_3S can return to HOLD ------------------------ #
    m = ClockLed()
    m.step("load"); m.step("compile_ok")
    m.step("abort")
    check("abort during the 3 s warning returns to HOLD (BLUE)",
          m.state == State.HOLD and m.led == "BLUE")

    # ---- ERROR paths -------------------------------------------------------- #
    m = ClockLed(); m.step("load")
    m.fault("compile", "bad token")
    check("compile_fail -> ERROR (RED)", m.state == State.ERROR and m.led == "RED")
    check("ack from ERROR -> HOLD", m.step("ack") == State.HOLD)
    m = ClockLed(); m.step("load"); m.step("compile_ok"); m.step("warn_done")
    m.fault("exec", "core stall")
    check("exec_fail from EXECUTE -> ERROR (RED)", m.state == State.ERROR and m.led == "RED")

    # ---- illegal transitions raise ------------------------------------------ #
    raised = 0
    for st_setup, ev in [((), "warn_done"),               # warn_done from HOLD
                         (("load",), "flush_done"),       # flush_done from COMPILE
                         (("load", "compile_ok"), "exec_done")]:  # exec_done from WARNING
        mm = ClockLed()
        for e in st_setup:
            mm.step(e)
        try:
            mm.step(ev)
        except ValueError:
            raised += 1
    check("illegal transitions raise (3/3)", raised == 3)
    # emit_syllable only legal in EXECUTE
    try:
        ClockLed().emit_syllable(0); guarded = False
    except ValueError:
        guarded = True
    check("emit_syllable outside EXECUTE raises", guarded)

    # ---- time never runs backwards ------------------------------------------ #
    m = ClockLed(); m.run_program([1, 0, 1])
    monotone = all(m.timeline[i].t_ms <= m.timeline[i + 1].t_ms
                   for i in range(len(m.timeline) - 1))
    check("clock is monotonic non-decreasing across the timeline", monotone)

    print(f"\n{'ALL PASS' if fails == 0 else str(fails) + ' FAILURE(S)'}")
    return fails


if __name__ == "__main__":
    raise SystemExit(_selftest())
