"""Measure end-to-end MIDI-to-audio latency for Sheet2Play's playback path.

Sheet2Play compensates for synthesiser latency by sending MIDI note-on events
`audioOffsetSeconds` early (Visualization_engine/Playback.cs). That constant is only
correct when it equals the real latency of the output chain, which depends on the
synth, the output device and any virtual processing device in between. This script
measures that latency instead of guessing it.

Method: send a note-on to the synth at a known timestamp, capture the system output
via WASAPI loopback, locate the onset in the captured audio, and difference the two.
Send and capture share one perf_counter() clock because they run in one process.

KNOWN LIMITATION -- the absolute number is not trustworthy. WASAPI loopback via
soundcard delivers audio at the correct *rate* but lags real time by an unknown
constant, and a constant pipeline delay produces zero measurable drift. That means
capture lag and genuine synth latency are indistinguishable here: measured runs on
this machine returned ~300 ms at the default endpoint and ~430 ms at the Bluetooth
endpoint, both far larger than any latency the app could plausibly have.

What this script IS good for: proving which endpoint the synth actually renders to
(run it against each loopback device and see which ones detect onsets at all), and
comparing two configurations captured through the same device.

Getting a trustworthy absolute figure needs a reference the capture path cannot
distort -- an external microphone recording both a physical reference click and the
speaker output, or hardware loopback. Do not use this script's absolute output to set
`audioOffsetSeconds`.

Usage:
    python measure_latency.py --list
    python measure_latency.py --device FxSound --trials 20
    python measure_latency.py --device FxSound --validate
"""

from __future__ import annotations

import argparse
import statistics
import sys
import time

import numpy as np
import rtmidi
import soundcard as sc

SAMPLE_RATE = 48000
MIDI_PORT_MATCH = "VirtualMIDISynth"
WARMUP_SECONDS = 0.20
CAPTURE_SECONDS = 0.60
NOTE_VELOCITY = 100
# Long enough for these soundfonts' release tails to decay, short enough that the
# synth keeps its output stream open between trials.
RELEASE_SECONDS = 1.2
# Onset is declared where a short moving RMS first exceeds the pre-send noise floor by
# this factor. High enough to ignore dither and idle hiss, low enough to catch a piano
# attack at its true start rather than partway up the transient.
# Fraction of the note's own peak envelope that marks the attack.
ONSET_THRESHOLD = 0.15
ONSET_WINDOW = 32


def open_midi() -> rtmidi.MidiOut:
    out = rtmidi.MidiOut()
    for index, name in enumerate(out.get_ports()):
        if MIDI_PORT_MATCH.lower() in name.lower():
            out.open_port(index)
            return out
    raise SystemExit(
        f"No MIDI port matching {MIDI_PORT_MATCH!r}. Ports: {out.get_ports()}"
    )


def find_loopback(match: str):
    mics = [m for m in sc.all_microphones(include_loopback=True) if m.isloopback]
    for mic in mics:
        if match.lower() in mic.name.lower():
            return mic
    raise SystemExit(
        f"No loopback device matching {match!r}. Available: {[m.name for m in mics]}"
    )


def find_onset(block: np.ndarray, noise_floor: float) -> tuple[int | None, float]:
    """Index of the note attack, plus the block's peak envelope for diagnostics.

    Thresholding relative to the block's own peak rather than to the noise floor,
    because these soundfonts have multi-second release tails: a floor sampled just
    before the note still carries the previous note's decay and would swamp any
    fixed threshold.
    """
    mono = np.abs(block).max(axis=1) if block.ndim > 1 else np.abs(block)
    kernel = np.ones(ONSET_WINDOW) / ONSET_WINDOW
    envelope = np.convolve(mono, kernel, mode="same")
    peak = float(envelope.max()) if envelope.size else 0.0

    # A note must stand clearly above both silence and whatever was still ringing.
    if peak < 1e-3 or peak < noise_floor * 4.0:
        return None, peak

    above = np.flatnonzero(envelope > peak * ONSET_THRESHOLD)
    return (int(above[0]) if above.size else None), peak


def drain(rec, noise_samples: list) -> float:
    """Consume backlog until the capture stream is delivering in real time.

    record() returns immediately while a backlog exists, so timing a block against
    the wall clock is only valid once we have caught up. Chunks consumed here also
    give us an idle noise floor for this device.
    """
    chunk = int(SAMPLE_RATE * 0.02)
    for _ in range(50):
        t0 = time.perf_counter()
        block = rec.record(numframes=chunk)
        elapsed = time.perf_counter() - t0
        if block.size:
            noise_samples.append(float(np.abs(block).mean()))
        # A blocking call means the buffer is empty and we are live.
        if elapsed > (chunk / SAMPLE_RATE) * 0.5:
            break
    return statistics.median(noise_samples[-10:]) if noise_samples else 0.0


def one_trial(rec, midi: rtmidi.MidiOut, pitch: int, injected_delay: float, noise_samples: list):
    """Return (latency_from_reference, latency_from_send, drift) in seconds, or None."""
    noise_floor = drain(rec, noise_samples)

    t_ref = time.perf_counter()
    if injected_delay:
        time.sleep(injected_delay)
    midi.send_message([0x90, pitch, NOTE_VELOCITY])
    t_send = time.perf_counter()

    frames = int(SAMPLE_RATE * CAPTURE_SECONDS)
    block = rec.record(numframes=frames)
    t_end = time.perf_counter()

    midi.send_message([0x80, pitch, 0])

    # The block begins where draining left off, i.e. at t_ref. If capture really ran
    # in real time, its wall duration matches its sample count; drift says otherwise.
    drift = (t_end - t_ref) - (len(block) / SAMPLE_RATE)

    onset, peak = find_onset(block, noise_floor)
    if onset is None:
        return None

    t_onset = t_ref + onset / SAMPLE_RATE
    return t_onset - t_ref, t_onset - t_send, drift, peak


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--list", action="store_true", help="list MIDI and loopback devices")
    parser.add_argument("--device", help="substring of the loopback device name")
    parser.add_argument("--trials", type=int, default=15)
    parser.add_argument(
        "--validate",
        action="store_true",
        help="inject a known 100ms delay; the measured latency must rise by 100ms",
    )
    args = parser.parse_args()

    if args.list:
        out = rtmidi.MidiOut()
        print("MIDI out ports:")
        for i, n in enumerate(out.get_ports()):
            print(f"  [{i}] {n}")
        print("\nLoopback devices:")
        for m in sc.all_microphones(include_loopback=True):
            if m.isloopback:
                print(f"  {m.name}")
        print(f"\nDefault speaker: {sc.default_speaker().name}")
        return 0

    if not args.device:
        parser.error("--device is required (or use --list)")

    mic = find_loopback(args.device)
    midi = open_midi()
    injected = 0.100 if args.validate else 0.0

    print(f"device : {mic.name}")
    print(f"synth  : {MIDI_PORT_MATCH}")
    if args.validate:
        print("mode   : validation, 100ms injected delay")
    print()

    # Spread pitches so a single dead sample zone in the soundfont cannot skew the run.
    pitches = [48, 55, 60, 64, 67, 72]
    from_send: list[float] = []
    from_ref: list[float] = []
    drifts: list[float] = []
    noise_samples: list[float] = []

    # One recorder for the whole run. Opening a stream per trial charges each
    # measurement for WASAPI stream startup, which dwarfs the latency being measured.
    with mic.recorder(samplerate=SAMPLE_RATE, channels=2) as rec:
        # Prime the synth so its render stream is already open, matching continuous
        # playback. A cold first note pays device wake-up that real playback does not.
        midi.send_message([0x90, 60, NOTE_VELOCITY])
        time.sleep(0.25)
        midi.send_message([0x80, 60, 0])
        time.sleep(0.25)
        drain(rec, noise_samples)

        for trial in range(args.trials):
            pitch = pitches[trial % len(pitches)]
            result = one_trial(rec, midi, pitch, injected, noise_samples)
            if result is None:
                print(f"  trial {trial + 1:2d}  pitch {pitch:3d}  NO ONSET DETECTED")
                time.sleep(RELEASE_SECONDS)
                continue
            ref_latency, send_latency, drift, peak = result
            from_ref.append(ref_latency)
            from_send.append(send_latency)
            drifts.append(drift)
            print(
                f"  trial {trial + 1:2d}  pitch {pitch:3d}  "
                f"from send {send_latency * 1000:7.1f} ms   drift {drift * 1000:6.1f} ms   peak {peak:.4f}"
            )
            # Short enough that the synth keeps its output stream open between trials.
            time.sleep(RELEASE_SECONDS)

    midi.close_port()

    if not from_send:
        print("\nNo onsets detected at all. Is the synth audible on this device?")
        return 1

    median = statistics.median(from_send)
    print(f"\n  n            : {len(from_send)} of {args.trials}")
    print(f"  median       : {median * 1000:.1f} ms")
    print(f"  mean         : {statistics.fmean(from_send) * 1000:.1f} ms")
    if len(from_send) > 1:
        print(f"  stdev        : {statistics.stdev(from_send) * 1000:.1f} ms")
    print(f"  min / max    : {min(from_send) * 1000:.1f} / {max(from_send) * 1000:.1f} ms")
    if drifts:
        worst = max(abs(d) for d in drifts)
        print(f"  capture drift: {worst * 1000:.1f} ms worst case")
        if worst > 0.030:
            print("  Capture was not running in real time; treat the result with suspicion.")

    if args.validate:
        # The real invariant: sending the note 100ms later must move its onset 100ms
        # later too, leaving latency-from-send unchanged. Comparing from_ref against
        # from_send instead would be circular -- they differ by the injected sleep by
        # construction, so that check passes even when the mapping is nonsense.
        print("\n  Compare this median against a --validate-free run on the same device.")
        print("  They must agree within a few ms. If they do not, the block-start")
        print("  assumption is broken and the absolute figure is meaningless.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
