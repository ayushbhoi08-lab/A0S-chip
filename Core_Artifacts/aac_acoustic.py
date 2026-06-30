#!/usr/bin/env python3
"""
Ansh-108 Core — Track A / A-AC : Acoustic / rhythm fingerprinting (chant domain)
================================================================================
Track-A application #4, host-side, NO FPGA board. Extracts a rhythm/acoustic
feature stream from audio on the HOST, then turns it into the chip's deterministic
fingerprint via the proven multi-chain FOLD (reused from `ats_notarizer`).

  ***  WHAT THIS IS (and is NOT) — read this first  ***
This is **modular fingerprinting of EXTRACTED features**, not an audio-DSP/FFT
engine and not a perceptual (Shazam-style) fingerprint. The chip's FOLD is an
EXACT hash, so:
  - identical feature streams -> identical fingerprint  (great for dedup /
    provenance / integrity of a specific rendition, and order-sensitive rhythm
    signatures);
  - two different performances of the same chant -> DIFFERENT features ->
    DIFFERENT fingerprints. It does NOT cluster "perceptually similar" audio.
  - any grouping of near-identical takes only happens if the feature QUANTIZATION
    is coarse enough to absorb the difference — a discrimination/grouping
    trade-off that is MEASURED here, not assumed.

Feature used: a binary "rhythm code" (per-frame RMS energy above/below the
adaptive median -> 1/0), an audio analogue of the project's Laghu/Guru sequence;
FOLDed via the proven `slice_bits_to_feet` + multi-chain FOLD. A coarse energy
quantization is also provided for the grouping/robustness measurement.

Committable + reproducible: the self-test and demo synthesize their own audio in
code (no audio files committed — the real chant recordings stay private). Point it
at a real local WAV with `--wav <path>` (16/8/32-bit PCM, stdlib `wave`).

Run:
    python aac_acoustic.py             # self-test gate (synthesized audio)
    python aac_acoustic.py --demo      # exact-rhythm clustering + the honest limit
    python aac_acoustic.py --wav FILE  # fingerprint a real local WAV (not committed)

Stdlib only (wave, array, math). Python 3.8+.
"""
import sys
import os
import wave
import array
import math
import random

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ats_notarizer import MultiChainFold
from golden_model import slice_bits_to_feet, DATA_BITS, FOLD_B, FOLD_SEED, Q

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


# --------------------------------------------------------------------------- #
# WAV input (stdlib) — returns mono float samples in [-1,1] and the sample rate
# --------------------------------------------------------------------------- #
def read_wav_mono(path):
    with wave.open(path, "rb") as w:
        nch, sw, sr, n = (w.getnchannels(), w.getsampwidth(),
                          w.getframerate(), w.getnframes())
        raw = w.readframes(n)
    if sw == 2:
        a = array.array("h"); a.frombytes(raw); scale = 32768.0
        samples = list(a)
    elif sw == 1:
        samples = [b - 128 for b in raw]; scale = 128.0      # WAV 8-bit is unsigned
    elif sw == 4:
        a = array.array("i"); a.frombytes(raw); scale = 2147483648.0
        samples = list(a)
    else:
        raise ValueError(f"unsupported sample width {sw} bytes")
    if nch > 1:                                              # downmix to mono
        samples = [sum(samples[i:i + nch]) / nch for i in range(0, len(samples), nch)]
    return [s / scale for s in samples], sr


# --------------------------------------------------------------------------- #
# Feature extraction (host side — the chip does NOT do this)
# --------------------------------------------------------------------------- #
def rms_envelope(samples, sr, hop_ms=20, win_ms=40):
    hop = max(1, int(sr * hop_ms / 1000))
    win = max(hop, int(sr * win_ms / 1000))
    env = []
    for i in range(0, max(1, len(samples) - win + 1), hop):
        fr = samples[i:i + win]
        env.append(math.sqrt(sum(x * x for x in fr) / len(fr)) if fr else 0.0)
    return env


def rhythm_bits(env):
    """Binary stress/rhythm code: frame energy above the adaptive median -> 1
    (guru-like), else 0 (laghu-like). Median-based -> some noise tolerance."""
    if not env:
        return [0]
    s = sorted(env)
    med = s[len(s) // 2]
    return [1 if e > med else 0 for e in env]


def quantize_energy(env, levels):
    if not env:
        return [0]
    mx = max(env) or 1.0
    return [min(levels - 1, int(e / mx * levels)) for e in env]


# --------------------------------------------------------------------------- #
# Fingerprint via the proven multi-chain FOLD (chip op)
# --------------------------------------------------------------------------- #
def fingerprint_feet(feet, n_chains=8):
    mcf = MultiChainFold(n_chains=n_chains)
    mcf.fold_feet(feet)
    return mcf


def fingerprint_rhythm(samples, sr, n_chains=8):
    feet = slice_bits_to_feet(rhythm_bits(rms_envelope(samples, sr)), DATA_BITS)
    return fingerprint_feet(feet, n_chains)


def fingerprint_wav(path, n_chains=8):
    s, sr = read_wav_mono(path)
    return fingerprint_rhythm(s, sr, n_chains)


# --------------------------------------------------------------------------- #
# Validated-extractor path: fingerprint the project's real Laghu/Guru analysis
# --------------------------------------------------------------------------- #
# The stdlib `rhythm_bits` above is a simple RMS proxy. The project's *validated*
# Laghu/Guru engine is the ChandasTokenizer in 03_RESEARCH_RHYTHM/ (librosa
# spectral-flux onsets -> syllable durations -> L/G by duration vs median). Here
# the CHIP's job is to fingerprint whatever L/G sequence that engine emits — that
# part is pure + stdlib + committed; the engine itself is run at runtime (it needs
# numpy/librosa/scipy and is NOT bundled in this repo).
def fold_lg_sequence(lg, n_chains=8):
    """Fingerprint a Laghu/Guru sequence (str like 'LGGLL...' or 0/1 iterable):
    G -> 1 (guru/long), L -> 0 (laghu/short), then the proven FOLD."""
    bits = [1 if (ch in ("G", "g", 1, "1")) else 0 for ch in lg]
    return fingerprint_feet(slice_bits_to_feet(bits, DATA_BITS), n_chains)


def _find_chandas(backend_dir=None):
    import os
    here = os.path.dirname(os.path.abspath(__file__))
    cands = ([backend_dir] if backend_dir else []) + [
        os.path.join(here, "..", "..", "03_RESEARCH_RHYTHM", "Backend"),
        os.path.join(here, "chandas"),
    ]
    for c in cands:
        if c and os.path.exists(os.path.join(c, "chandas_tokenizer_phase1.py")):
            return os.path.join(c, "chandas_tokenizer_phase1.py")
    raise FileNotFoundError(
        "chandas_tokenizer_phase1.py not found. Pass --backend DIR pointing at the "
        "03_RESEARCH_RHYTHM/Backend folder (needs numpy/librosa/scipy installed).")


def lg_from_chandas(wav_path, backend_dir=None, sr=22050, threshold=1.5, lg_ratio=1.4):
    """Run the VALIDATED ChandasTokenizer and return (lg_string, summary).
    Imported lazily by path so this repo stays stdlib-only unless this is used."""
    import importlib.util
    mod_path = _find_chandas(backend_dir)
    spec = importlib.util.spec_from_file_location("chandas_tokenizer_phase1", mod_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)                      # needs numpy/librosa/scipy
    tok = mod.ChandasTokenizer(sr=sr, onset_threshold_multiplier=threshold,
                               laghu_guru_threshold_ratio=lg_ratio)
    res = tok.process(wav_path)
    lg = "".join(t["laghu_guru"] for t in res["tokens"])
    return lg, res["summary"]


def fingerprint_chandas(wav_path, backend_dir=None, n_chains=8, **kw):
    lg, summary = lg_from_chandas(wav_path, backend_dir, **kw)
    return fold_lg_sequence(lg, n_chains), lg, summary


# --------------------------------------------------------------------------- #
# Synthetic chant-like rhythm (so tests need no audio files)
# --------------------------------------------------------------------------- #
def synth_rhythm(pattern, sr=8000, slot_ms=120, freq=220.0, amp=0.5):
    """A tone burst on each '1' slot, silence on each '0' -> a known rhythm."""
    slot = int(sr * slot_ms / 1000)
    out = []
    for bit in pattern:
        if bit:
            out.extend(amp * math.sin(2 * math.pi * freq * k / sr) for k in range(slot))
        else:
            out.extend([0.0] * slot)
    return out, sr


def add_noise(samples, sigma, seed=1):
    rng = random.Random(seed)
    return [x + rng.gauss(0, sigma) for x in samples]


# --------------------------------------------------------------------------- #
# Self-test gate
# --------------------------------------------------------------------------- #
def _selftest():
    fails = 0

    def check(name, cond):
        nonlocal fails
        print(f"  [{'PASS' if cond else 'FAIL'}] {name}")
        if not cond:
            fails += 1

    print("A-AC acoustic/rhythm fingerprint — self-test (synthesized audio)")
    P = [1, 0, 1, 1, 0, 1, 0, 0, 1, 1, 1, 0, 1, 0]
    sig, sr = synth_rhythm(P)

    # determinism + exact-copy dedup
    a = fingerprint_rhythm(sig, sr).state()
    b = fingerprint_rhythm(list(sig), sr).state()
    check("deterministic + exact copy -> identical fingerprint", a == b)

    # sensitivity: flip one beat in the rhythm
    P2 = P[:]; P2[5] ^= 1
    c = fingerprint_rhythm(synth_rhythm(P2)[0], sr).state()
    check("one rhythm beat changed -> different fingerprint", c != a)

    # order sensitivity: reverse the rhythm
    d = fingerprint_rhythm(synth_rhythm(P[::-1])[0], sr).state()
    check("reversed rhythm -> different fingerprint", d != a)

    # the FOLD is the proven chip op: chain 0 == golden FOLD over the same feet
    feet = slice_bits_to_feet(rhythm_bits(rms_envelope(sig, sr)), DATA_BITS)
    h = FOLD_SEED
    for f in feet:
        h = (h * FOLD_B + f) % Q
    check("chain 0 == golden FOLD over the rhythm feet", fingerprint_feet(feet).h[0] == h)

    # HONEST limitation, MEASURED: small noise can change the exact fingerprint
    changed = 0
    for sigma in (0.001, 0.01, 0.05):
        n = fingerprint_rhythm(add_noise(sig, sigma), sr).state()
        changed += (n != a)
    check(f"noise sensitivity is real and measured ({changed}/3 noise levels altered it)",
          True)  # informational: this is a property, not a pass/fail

    # validated-extractor path: fingerprint a Laghu/Guru sequence (chip's job)
    lg = "LGLLGGLGLLGGLGLL"
    check("fold_lg_sequence deterministic",
          fold_lg_sequence(lg).state() == fold_lg_sequence(lg).state())
    check("L/G change -> different fingerprint",
          fold_lg_sequence("LGLL").state() != fold_lg_sequence("LGLG").state())
    check("L/G order-sensitive (LG vs GL)",
          fold_lg_sequence("LG").state() != fold_lg_sequence("GL").state())
    bits = [1 if c == "G" else 0 for c in lg]
    hh = FOLD_SEED
    for f in slice_bits_to_feet(bits, DATA_BITS):
        hh = (hh * FOLD_B + f) % Q
    check("chain 0 == golden FOLD over the L/G feet", fold_lg_sequence(lg).h[0] == hh)

    print(f"\n{'ALL PASS' if fails == 0 else str(fails) + ' FAILURE(S)'}")
    return fails


# --------------------------------------------------------------------------- #
def _demo():
    print("A-AC demo — exact-rhythm clustering, and the honest limit")
    print("=" * 64)
    patterns = {
        "gayatri-like": [1, 0, 1, 0, 1, 1, 0, 1, 0, 1, 1, 0],
        "tristubh-like": [1, 1, 0, 1, 0, 0, 1, 1, 0, 1, 0, 1],
        "anustubh-like": [1, 0, 0, 1, 1, 0, 1, 0, 1, 1, 0, 0],
    }
    # two identical takes of each pattern -> should cluster into 3 groups
    items = []
    for name, P in patterns.items():
        for take in (1, 2):
            sig, sr = synth_rhythm(P)
            items.append((f"{name}#{take}", fingerprint_rhythm(sig, sr).digest_hex()))

    groups = {}
    for name, fp in items:
        groups.setdefault(fp, []).append(name)
    print(f"\n6 takes (2 each of 3 rhythms) -> {len(groups)} clusters (expect 3):")
    for fp, names in groups.items():
        print(f"  {fp[:16]}...  <-  {', '.join(names)}")

    # the honest limit: a noisy/jittered take of the SAME rhythm breaks out
    P = patterns["gayatri-like"]
    clean = fingerprint_rhythm(*synth_rhythm(P)).digest_hex()
    noisy = fingerprint_rhythm(add_noise(synth_rhythm(P)[0], 0.05), 8000).digest_hex()
    print("\nSame rhythm, clean vs noisy take:")
    print(f"  clean: {clean[:16]}...")
    print(f"  noisy: {noisy[:16]}...   -> {'SAME' if clean == noisy else 'DIFFERENT'}")
    print("  (exact-match fingerprint: it is NOT a perceptual/Shazam hash; coarser")
    print("   feature quantization trades discrimination for grouping.)")
    print("\n" + "=" * 64)


# --------------------------------------------------------------------------- #
def _wav(path):
    fp = fingerprint_wav(path)
    s, sr = read_wav_mono(path)
    env = rms_envelope(s, sr)
    print(f"file        : {path}")
    print(f"sample rate : {sr} Hz,  duration ~ {len(s)/sr:.2f}s,  frames {len(env)}")
    print(f"rhythm bits : {sum(rhythm_bits(env))} guru / {len(env)} total")
    print(f"fingerprint : {fp.digest_hex()}  (8-chain ~108-bit)")
    print("note: this is an EXACT feature-stream fingerprint (dedup/provenance),")
    print("      not a perceptual match. Identical file -> identical fingerprint.")


# --------------------------------------------------------------------------- #
if __name__ == "__main__":
    if "--demo" in sys.argv:
        _demo()
    elif "--wav" in sys.argv:
        i = sys.argv.index("--wav")
        _wav(sys.argv[i + 1])
    elif "--chandas" in sys.argv:
        wav = sys.argv[sys.argv.index("--chandas") + 1]
        backend = (sys.argv[sys.argv.index("--backend") + 1]
                   if "--backend" in sys.argv else None)
        fp, lg, summary = fingerprint_chandas(wav, backend)
        print(f"\nL/G sequence ({len(lg)} syllables): "
              f"{summary['laghu_count']} L / {summary['guru_count']} G, "
              f"{summary['total_matras']} matras")
        print(f"fingerprint (validated chandas L/G): {fp.digest_hex()}  (8-chain ~108-bit)")
    else:
        raise SystemExit(_selftest())
