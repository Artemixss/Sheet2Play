"""Generate targeted rhythm test cases that isolate HOMR's actual failure mode.

The Step 1 diagnosis established that HOMR emits too much total time on 53% of systems, and
that tuplet-bearing systems are worst (95% inflated, mean 1.284x). But that is *observational*
- in real scores tuplets, polyrhythm and ties co-occur, so OLiMPiC cannot say which one does
the damage. It also only contained 20 tuplet systems, a thin basis for an engine decision.

The suspected mechanism is specific: HOMR's time cursor advances by the shortest duration in
each chord group (`SymbolChord.get_duration`), and its vocabulary has no tie token. So an
onset falling strictly inside a sustaining note cannot be placed - in real notation you spell
that by tying a split note. If that is right, the failure should track *polyrhythm*, not
tuplets as such.

These cases vary the two independently:

                        no polyrhythm          polyrhythm
    no tuplet     homophonic (control)      offset_entry
    tuplet        tuplet_aligned            triplet_vs_duple, triplet_vs_quadruple

plus `tie_across_barline`, which probes the missing tie token directly.

Every case is built with music21, so the label is exact by construction rather than
transcribed, then engraved through MuseScore to get a real image. The manifest is written in
the same shape as the OLiMPiC canary, so `compare_engines.py --manifest` and
`diagnose_rhythm.py --manifest` consume it with no changes.

    .venv/Scripts/python.exe generate_polyrhythm.py
    .venv/Scripts/python.exe compare_engines.py --engine homr --manifest data/polyrhythm/manifest.jsonl
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from fractions import Fraction
from pathlib import Path
from typing import Any, Callable

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

DEFAULT_MUSESCORE = r"C:\Program Files\MuseScore 4\bin\MuseScore4.exe"


class GeneratorError(RuntimeError):
    pass


# --- Case builders -------------------------------------------------------------------------
#
# Each returns a music21 Score. Voice 1 and voice 2 share one staff, which is the
# configuration under test: HOMR must place both layers on a single time cursor.


def _score(time_signature: str = "4/4", tempo_bpm: int = 60):
    from music21 import meter, stream, tempo

    score = stream.Score()
    part = stream.Part(id="P1")
    measure = stream.Measure(number=1)
    measure.insert(0, tempo.MetronomeMark(number=tempo_bpm))
    measure.insert(0, meter.TimeSignature(time_signature))
    part.append(measure)
    score.append(part)
    return score, part, measure


def _voices(measure, upper: list[tuple[str, Any, Any]], lower: list[tuple[str, Any, Any]]):
    """Attach two independent voices as (pitch, offset, quarterLength) triples."""
    from music21 import note, stream

    for index, entries in enumerate((upper, lower), start=1):
        voice = stream.Voice(id=str(index))
        for name, offset, length in entries:
            voice.insert(Fraction(offset), note.Note(name, quarterLength=Fraction(length)))
        measure.insert(0, voice)


def build_homophonic():
    """Control: both voices move together. No polyrhythm, no tuplets."""
    score, _, measure = _score()
    _voices(
        measure,
        upper=[("E5", 0, 1), ("F5", 1, 1), ("G5", 2, 1), ("A5", 3, 1)],
        lower=[("C4", 0, 1), ("D4", 1, 1), ("E4", 2, 1), ("F4", 3, 1)],
    )
    return score


def build_tuplet_aligned():
    """Tuplets, but both voices share them. Tests tuplet arithmetic without polyrhythm."""
    score, _, measure = _score()
    upper, lower = [], []
    for index in range(12):
        onset = Fraction(index, 3)
        upper.append((["C5", "D5", "E5"][index % 3], onset, Fraction(1, 3)))
        lower.append((["C4", "D4", "E4"][index % 3], onset, Fraction(1, 3)))
    return _finish(score, measure, upper, lower)


def build_offset_entry():
    """Polyrhythm without tuplets: an onset lands inside a sustaining note.

    Voice 1 is a dotted quarter then an eighth, so its second onset falls at beat 1.5 -
    strictly inside voice 2's quarter spanning 1.0 to 2.0. Spelling that requires tying
    voice 2's quarter into two eighths, and HOMR has no tie token.
    """
    score, _, measure = _score()
    return _finish(
        score,
        measure,
        upper=[("G5", 0, Fraction(3, 2)), ("A5", Fraction(3, 2), Fraction(1, 2)),
               ("B5", 2, 2)],
        lower=[("C4", 0, 1), ("D4", 1, 1), ("E4", 2, 1), ("F4", 3, 1)],
    )


def build_triplet_vs_duple():
    """3-against-2. Each voice's onsets land inside the other's notes."""
    score, _, measure = _score("2/4")
    upper = [(["C5", "D5", "E5"][i], Fraction(i, 3) * 2, Fraction(2, 3)) for i in range(3)]
    lower = [("C4", 0, 1), ("D4", 1, 1)]
    return _finish(score, measure, upper, lower)


def build_triplet_vs_quadruple():
    """3-against-4, the densest common piano polyrhythm."""
    score, _, measure = _score("2/4")
    upper = [(["C5", "D5", "E5"][i], Fraction(i, 3) * 2, Fraction(2, 3)) for i in range(3)]
    lower = [(["C4", "D4", "E4", "F4"][i], Fraction(i, 2), Fraction(1, 2)) for i in range(4)]
    return _finish(score, measure, upper, lower)


def build_tie_across_barline():
    """Probes the missing tie token directly: one note sounding across a barline."""
    from music21 import meter, note, stream, tempo, tie

    score = stream.Score()
    part = stream.Part(id="P1")

    first = stream.Measure(number=1)
    first.insert(0, tempo.MetronomeMark(number=60))
    first.insert(0, meter.TimeSignature("4/4"))
    first.insert(0, note.Note("C5", quarterLength=2))
    held = note.Note("G5", quarterLength=2)
    held.tie = tie.Tie("start")
    first.insert(2, held)
    part.append(first)

    second = stream.Measure(number=2)
    continued = note.Note("G5", quarterLength=2)
    continued.tie = tie.Tie("stop")
    second.insert(0, continued)
    second.insert(2, note.Note("E5", quarterLength=2))
    part.append(second)

    score.append(part)
    return score


def build_same_position_sustain():
    """The exact case from homr issue #142.

    A sustained note and a much shorter note of the *same pitch* start at the same position
    on the same staff. The maintainer's reply names this as the case homr never saw in
    training: the short note vanishes from the token stream, and every later duration in the
    measure is wrong as a result.
    """
    score, _, measure = _score()
    return _finish(
        score,
        measure,
        upper=[("A-2", 0, 2), ("B-2", 2, 2)],
        lower=[("A-2", 0, Fraction(1, 2)), ("A-3", Fraction(1, 2), Fraction(1, 2)),
               ("C4", 1, 1), ("E-4", 2, 2)],
    )


def build_quintuplet_vs_duple():
    """5-against-4. Uses note_5 (4/5 quarter), which is in homr's vocabulary."""
    score, _, measure = _score()
    upper = [
        (["C5", "D5", "E5", "F5", "G5"][i], Fraction(4 * i, 5), Fraction(4, 5))
        for i in range(5)
    ]
    lower = [(["C4", "D4", "E4", "F4"][i], i, 1) for i in range(4)]
    return _finish(score, measure, upper, lower)


def build_septuplet_vs_duple():
    """7-against-4. Uses note_7 (4/7 quarter).

    Deliberately avoids the 7:4 septuplet *eighth*, which would need `note_14` - absent from
    homr's vocabulary, so it could not be encoded correctly even in principle and would
    confound the measurement.
    """
    score, _, measure = _score()
    upper = [
        (["C5", "D5", "E5", "F5", "G5", "A5", "B5"][i], Fraction(4 * i, 7), Fraction(4, 7))
        for i in range(7)
    ]
    lower = [(["C4", "D4", "E4", "F4"][i], i, 1) for i in range(4)]
    return _finish(score, measure, upper, lower)


def build_three_voices():
    """Three independent layers on one staff: whole against halves against quarters."""
    from music21 import note, stream

    score, _, measure = _score()
    layers = [
        [("C5", 0, 4)],
        [("E4", 0, 2), ("F4", 2, 2)],
        [("G3", 0, 1), ("A3", 1, 1), ("B3", 2, 1), ("C4", 3, 1)],
    ]
    for index, entries in enumerate(layers, start=1):
        voice = stream.Voice(id=str(index))
        for name, offset, length in entries:
            voice.insert(Fraction(offset), note.Note(name, quarterLength=Fraction(length)))
        measure.insert(0, voice)
    return score


def build_syncopation():
    """Offbeat entries against a steady pulse - onsets land between the other voice's."""
    score, _, measure = _score()
    return _finish(
        score,
        measure,
        upper=[("G5", Fraction(1, 2), 1), ("A5", Fraction(3, 2), 1),
               ("B5", Fraction(5, 2), 1), ("C6", Fraction(7, 2), Fraction(1, 2))],
        lower=[("C4", 0, 1), ("D4", 1, 1), ("E4", 2, 1), ("F4", 3, 1)],
    )


def _finish(score, measure, upper, lower):
    _voices(measure, upper, lower)
    return score


CASES: dict[str, Callable[[], Any]] = {
    "homophonic": build_homophonic,
    "tuplet_aligned": build_tuplet_aligned,
    "offset_entry": build_offset_entry,
    "triplet_vs_duple": build_triplet_vs_duple,
    "triplet_vs_quadruple": build_triplet_vs_quadruple,
    "tie_across_barline": build_tie_across_barline,
    "same_position_sustain": build_same_position_sustain,
    "quintuplet_vs_duple": build_quintuplet_vs_duple,
    "septuplet_vs_duple": build_septuplet_vs_duple,
    "three_voices": build_three_voices,
    "syncopation": build_syncopation,
}

# Which axis each case exercises, for reporting.
TRAITS = {
    "homophonic": {"tuplet": False, "polyrhythm": False},
    "tuplet_aligned": {"tuplet": True, "polyrhythm": False},
    "offset_entry": {"tuplet": False, "polyrhythm": True},
    "triplet_vs_duple": {"tuplet": True, "polyrhythm": True},
    "triplet_vs_quadruple": {"tuplet": True, "polyrhythm": True},
    "tie_across_barline": {"tuplet": False, "polyrhythm": False},
    "same_position_sustain": {"tuplet": False, "polyrhythm": True},
    "quintuplet_vs_duple": {"tuplet": True, "polyrhythm": True},
    "septuplet_vs_duple": {"tuplet": True, "polyrhythm": True},
    "three_voices": {"tuplet": False, "polyrhythm": True},
    "syncopation": {"tuplet": False, "polyrhythm": True},
}


# --- Engraving -----------------------------------------------------------------------------


def find_musescore(explicit: str | None) -> str:
    import os

    for candidate in (
        explicit,
        os.environ.get("MUSESCORE_PATH"),
        DEFAULT_MUSESCORE,
        shutil.which("musescore4"),
        shutil.which("mscore"),
    ):
        if candidate and Path(candidate).exists():
            return str(candidate)
    raise GeneratorError(
        "MuseScore CLI not found. Pass --musescore <path> or set MUSESCORE_PATH."
    )


def engrave(musescore: str, musicxml: Path, destination: Path, dpi: int) -> Path:
    """Render MusicXML to a single PNG, returning its path."""
    with tempfile.TemporaryDirectory(prefix="polyrhythm-") as temporary:
        work = Path(temporary)
        target = work / "page.png"
        command = [musescore, "-o", str(target), str(musicxml), "-r", str(dpi)]
        completed = subprocess.run(
            command, capture_output=True, text=True,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        # MuseScore appends a page number when a score renders to multiple pages, and
        # sometimes even for one, so accept either spelling.
        pages = sorted(work.glob("page*.png"))
        if not pages:
            raise GeneratorError(
                f"MuseScore produced no PNG for {musicxml.name} "
                f"(exit {completed.returncode}): {completed.stderr[-400:]}"
            )
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(pages[0], destination)
    return destination


def parse_arguments(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--out", type=Path, default=HERE / "data" / "polyrhythm")
    parser.add_argument("--dpi", type=int, default=300)
    parser.add_argument("--musescore", help="Path to the MuseScore executable.")
    parser.add_argument("--cases", default="all",
                        help="Comma-separated case names, or 'all'. Available: "
                             + ", ".join(CASES))
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_arguments(argv)
    selected = list(CASES) if args.cases == "all" else [
        name.strip() for name in args.cases.split(",") if name.strip()
    ]
    unknown = [name for name in selected if name not in CASES]
    if unknown:
        print(f"Unknown case(s): {', '.join(unknown)}", file=sys.stderr)
        return 2

    musescore = find_musescore(args.musescore)
    print(f"musescore : {musescore}")
    print(f"output    : {args.out}\n")

    args.out.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, Any]] = []

    for name in selected:
        score = CASES[name]()
        musicxml = args.out / f"{name}.musicxml"
        score.write("musicxml", fp=str(musicxml))
        image = engrave(musescore, musicxml, args.out / f"{name}.png", args.dpi)
        rows.append(
            {
                "identifier": name,
                "score_id": name,
                "image": str(image),
                "musicxml": str(musicxml),
                "partition": "synthetic",
                "source": "generated",
                **TRAITS[name],
            }
        )
        traits = TRAITS[name]
        print(
            "  %-24s tuplet=%-5s polyrhythm=%-5s -> %s"
            % (name, traits["tuplet"], traits["polyrhythm"], image.name)
        )

    manifest = args.out / "manifest.jsonl"
    with manifest.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row) + "\n")
    print(f"\nmanifest  : {manifest} ({len(rows)} cases)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
