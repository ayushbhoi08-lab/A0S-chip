#!/usr/bin/env python3
"""
Ansh-108 Core -- Path A, Phase 3 / S7: TRANSPORT (packet streamer).
===================================================================
The wire between the host staging agent and the core. Its one hard rule is the
collision-proof contract from the locked spec:

    SEND COMPLETE PACKETS ONLY -- never emit a partial 32-bit pAda.

A 32-bit pAda is 4 bytes. The `PacketFramer` accumulates a raw byte stream and
only releases whole 4-byte words; a partial tail is buffered until completed, so
the core never sees half a packet (which would alias into a wrong opcode/data and
collide on the shared result port).

This module provides the SOFTWARE-LOOPBACK transport for the pre-hardware arc: it
drives `golden_model.AnshCoreGolden` and returns a `CoreEvent` per executed packet
(opcode, result-mode class, value, the bindu pulse, and -- for READ_TICK -- the raw
tick residues for the host to CRT-recombine). The `UsbTransport` seam is declared
but intentionally NOT implemented: the real USB bridge is Phase 7 (board, January);
host↔RTL co-sim is S9. Both honest gaps are stated, not faked.

Pure Python 3.8+, no third-party deps. Importable + `python transport.py` self-test.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Optional, Sequence, Tuple
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from golden_model import (                                            # noqa: E402
    AnshCoreGolden, decode_packet, RESULT_MODE, OPNAME, COUNTER_MODULI,
    FOLD_SEED, FOLD, FLUSH, RESET, READ_TICK, STREAM)

PACKET_BYTES = 4                         # a pAda = 32 bits = 4 bytes


# --------------------------------------------------------------------------- #
# The event a transport returns for each executed packet
# --------------------------------------------------------------------------- #
@dataclass
class CoreEvent:
    index: int                                  # position in the delivered stream
    packet: int                                 # the 32-bit pAda
    opcode: int
    opname: str
    result_mode: str                            # critical/stream/handshake/fire_forget
    value: Optional[int]                        # result value (None for fire-forget / READ_TICK)
    bindu: bool                                 # RESET raised the sequence-complete pulse
    tick_residues: Optional[Tuple[int, ...]]    # READ_TICK: raw dials -> host CRT recombines
    held_fold: int                              # fold-accumulator mirror AFTER this packet


# --------------------------------------------------------------------------- #
# Whole-packet framer (the collision-proof buffer)
# --------------------------------------------------------------------------- #
class PacketFramer:
    """Accumulate a raw byte stream; release only COMPLETE 32-bit packets.
    A partial (<4-byte) tail is held back until its remaining bytes arrive."""

    def __init__(self) -> None:
        self._buf = bytearray()

    def feed_bytes(self, data: bytes) -> List[int]:
        """Add bytes (any chunking, even mid-packet); return whole packets ready."""
        self._buf.extend(data)
        out: List[int] = []
        while len(self._buf) >= PACKET_BYTES:
            word = bytes(self._buf[:PACKET_BYTES])
            del self._buf[:PACKET_BYTES]
            out.append(int.from_bytes(word, "big"))
        return out

    def pending(self) -> int:
        """Bytes currently buffered as an incomplete (un-emitted) pAda."""
        return len(self._buf)

    def reset(self) -> None:
        self._buf.clear()


def packets_to_bytes(packets: Sequence[int]) -> bytes:
    return b"".join((p & 0xFFFFFFFF).to_bytes(PACKET_BYTES, "big") for p in packets)


# --------------------------------------------------------------------------- #
# Transport base: framing + protocol shared by loopback and (future) USB
# --------------------------------------------------------------------------- #
class Transport(ABC):
    """Frame on the way in (whole packets only), then `_deliver` to the core."""

    def __init__(self) -> None:
        self._framer = PacketFramer()
        self._index = 0

    def open(self) -> "Transport":
        return self

    def close(self) -> None:
        pass

    def __enter__(self) -> "Transport":
        return self.open()

    def __exit__(self, *exc) -> None:
        self.close()

    def send(self, packets: Sequence[int]) -> List[CoreEvent]:
        """Send a list of complete packets (serialized through the framer)."""
        whole = self._framer.feed_bytes(packets_to_bytes(packets))
        return self._deliver(whole)

    def send_bytes(self, chunk: bytes) -> List[CoreEvent]:
        """Feed an ARBITRARY byte chunk (may split a packet); only whole packets
        reach the core. Models a real, chunked wire -- proves collision safety."""
        return self._deliver(self._framer.feed_bytes(chunk))

    def pending_bytes(self) -> int:
        return self._framer.pending()

    @abstractmethod
    def _deliver(self, packets: Sequence[int]) -> List[CoreEvent]:
        ...


# --------------------------------------------------------------------------- #
# Software loopback: drive the golden core, return events per result mode
# --------------------------------------------------------------------------- #
class LoopbackTransport(Transport):
    """Drives `AnshCoreGolden`. The free-running Yuga tick is advanced
    `ticks_per_packet` per processed packet -- a deterministic stand-in for the
    hardware's per-clock advance (absolute cycle->seconds still needs a disciplined
    oscillator, plan §8.8). Reseeds the fold mirror on FLUSH/RESET exactly like
    `fold_hash`, so the read-before-bindu contract is real, not decorative."""

    def __init__(self, core: Optional[AnshCoreGolden] = None,
                 ticks_per_packet: int = 1) -> None:
        super().__init__()
        self.core = core or AnshCoreGolden()
        self.ticks_per_packet = ticks_per_packet
        self._held_fold = self.core.h

    def open(self) -> "LoopbackTransport":
        # fresh sequence: reseed datapath, keep the (write-protected) tick running
        self.core.h = self.core.fold_seed
        self._held_fold = self.core.h
        self._framer.reset()
        self._index = 0
        return self

    def close(self) -> None:
        pass

    def _deliver(self, packets: Sequence[int]) -> List[CoreEvent]:
        events: List[CoreEvent] = []
        for pkt in packets:
            d = decode_packet(pkt)
            op = d["opcode"]
            # snapshot the tick residues BEFORE executing (READ_TICK reads "now")
            tick_res = tuple(self.core.counter.residues()) if op == READ_TICK else None
            res = self.core.execute(pkt)        # golden model = source of truth
            # mirror the fold accumulator (reseeds on FLUSH/RESET, like fold_hash)
            self._held_fold = self.core.h
            ev = CoreEvent(
                index=self._index,
                packet=pkt,
                opcode=op,
                opname=OPNAME.get(op, f"op{op}"),
                result_mode=RESULT_MODE.get(op, "critical"),
                value=(None if op == READ_TICK else res.value),
                bindu=(op == RESET),
                tick_residues=tick_res,
                held_fold=self._held_fold,
            )
            events.append(ev)
            self._index += 1
            # the free-running clock advances every cycle (write-protected tick)
            if self.ticks_per_packet:
                self.core.tick(self.ticks_per_packet)
        return events

    # -- convenience for the read-before-bindu contract --------------------- #
    def live_fold(self) -> int:
        """The CURRENT fold accumulator (post-reseed if a RESET/bindu just ran).
        Reading this AFTER the bindu yields the seed, not the fingerprint -- which
        is exactly why the host must read the fingerprint from the stream first."""
        return self.core.h


# --------------------------------------------------------------------------- #
# USB seam -- Phase 7 (NOT implemented in S7; honest gap)
# --------------------------------------------------------------------------- #
class UsbTransport(Transport):
    """Clean seam for the real USB bridge (UART/FTDI first, plan §3 Phase 7 / S11+).
    Shares the whole-packet framing + the CoreEvent protocol with the loopback, so
    swapping it in later is a drop-in. Deliberately unimplemented now: there is no
    board and no pyserial dependency in the pre-silicon arc."""

    def __init__(self, port: Optional[str] = None, baud: int = 1_000_000) -> None:
        super().__init__()
        self.port = port
        self.baud = baud

    def open(self) -> "UsbTransport":
        raise NotImplementedError(
            "Real USB transport is Phase 7 (physical board, January / S11+). "
            "Use LoopbackTransport for the pre-hardware arc; host<->RTL co-sim is S9."
        )

    def _deliver(self, packets: Sequence[int]) -> List[CoreEvent]:
        raise NotImplementedError("UsbTransport is a Phase-7 seam; not wired in S7.")


# --------------------------------------------------------------------------- #
# Self-test
# --------------------------------------------------------------------------- #
def _selftest() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    import random
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import host_staging as H
    from golden_model import fold_text, encode_packet, MUL, ADD
    random.seed(108)
    fails = 0

    def check(name, cond):
        nonlocal fails
        print(f"  [{'PASS' if cond else 'FAIL'}] {name}")
        if not cond:
            fails += 1

    print("Ansh-108 S7 -- transport (whole-packet streamer) self-test")

    # ---- framer: only whole packets emitted; partial tail buffered ----------- #
    fr = PacketFramer()
    out = fr.feed_bytes(b"\x40\x00\x00\x01\xF0\x00")     # 1.5 packets
    check("framer emits exactly the complete packet, buffers the partial tail",
          out == [0x40000001] and fr.pending() == 2)
    out2 = fr.feed_bytes(b"\x00\x00")                    # completes the 2nd
    check("framer completes the buffered packet when the rest arrives",
          out2 == [0xF0000000] and fr.pending() == 0)

    # ---- arbitrary byte-chunking never delivers a partial pAda --------------- #
    pkts = H.assemble([("MUL", 1, 2), ("FOLD", 7), ("READ_TICK",)])
    raw = packets_to_bytes(pkts)
    # split the stream at every awkward boundary (1 byte at a time)
    t = LoopbackTransport().open()
    evs: List[CoreEvent] = []
    for i in range(len(raw)):
        evs += t.send_bytes(raw[i:i + 1])
    chunk_ok = ([e.packet for e in evs] == list(pkts) and t.pending_bytes() == 0)
    check("byte-by-byte chunking delivers exactly the whole packets, in order", chunk_ok)

    # ---- loopback executes correctly vs golden (arith) ----------------------- #
    t = LoopbackTransport().open()
    aok = True
    for _ in range(20000):
        x, y = random.randrange(12289), random.randrange(12289)
        e = t.send([encode_packet(MUL, x, y)])[0]
        aok &= (e.value == (x * y) % 12289 and e.result_mode == "critical")
    check("loopback MUL events == golden over 20k", aok)

    # ---- FOLD stream + read-before-bindu ------------------------------------- #
    lb_ok = bindu_ok = reseed_ok = True
    texts = ["", "a", "A", "aA", "Om Namah Shivaya", "A" * 56 + "b"]
    texts += ["".join(random.choice("aAbZz .,9") for _ in range(random.randint(0, 90)))
              for _ in range(2000)]
    for txt in texts:
        pk = H.text_to_fold_packets(txt)
        tr = LoopbackTransport().open()
        ev = tr.send(pk)
        fold_vals = [e.held_fold for e in ev if e.result_mode == STREAM]
        fp = fold_vals[-1] if fold_vals else FOLD_SEED   # last FOLD push = fingerprint
        lb_ok &= (fp == fold_text(txt))
        bindu_ok &= (ev[-1].bindu and ev[-1].opcode == RESET)
        # AFTER the bindu, the live fold accumulator is reseeded to the seed --
        # proving you must read the fingerprint from the stream BEFORE the bindu.
        reseed_ok &= (tr.live_fold() == FOLD_SEED)
    check(f"loopback FOLD fingerprint (read before bindu) == fold_text over {len(texts)}", lb_ok)
    check("every stream ends in the bindu (RESET) pulse", bindu_ok)
    check("live fold accumulator is reseeded AFTER bindu (read-before-bindu matters)", reseed_ok)

    # ---- READ_TICK returns raw residues; tick advances per packet ------------ #
    tr = LoopbackTransport(ticks_per_packet=1).open()
    # send N filler FOLDs then a READ_TICK; tick should equal #packets-before
    n_before = 5
    seq = H.assemble([("FOLD", 1)] * n_before + [("READ_TICK",)], with_bindu=False)
    ev = tr.send(seq)
    rt = ev[-1]
    tick_ok = (rt.tick_residues == tuple(v % m for v, m in
               zip([n_before] * 3, COUNTER_MODULI)) and rt.value is None)
    check("READ_TICK carries raw tick residues (host reconstructs) after N ticks", tick_ok)

    # ---- USB seam is an explicit, honest Phase-7 gap ------------------------- #
    raised = False
    try:
        UsbTransport(port="COM3").open()
    except NotImplementedError:
        raised = True
    check("UsbTransport.open() raises NotImplementedError (Phase-7 seam, honest gap)", raised)

    print(f"\n{'ALL PASS' if fails == 0 else str(fails) + ' FAILURE(S)'}")
    return fails


if __name__ == "__main__":
    raise SystemExit(_selftest())
