"""Diagnose the deferred chord tie using bounded XML controls and unchanged normalization."""
from __future__ import annotations

import argparse
from copy import deepcopy
from fractions import Fraction
from pathlib import Path
import shutil
import xml.etree.ElementTree as ET

from zeus_attribution_prepare import OUT, configure_cpu, save_json
from sheet2play_omr.adapter_contract import sha256_file
from sheet2play_omr.zeus_trace import xml_trace, merge_segments, normalized_notes, metric_summary


def event_signature(notes) -> list[tuple]:
    return sorted((note.pitch, note.onset, note.duration) for note in notes)


def controls(source: Path) -> list[tuple[str, ET.Element, bool]]:
    original = ET.parse(source).getroot()
    rows = []
    layout = deepcopy(original)
    for measure in layout.findall("part/measure"):
        for marker in list(measure.findall("print")):
            measure.remove(marker)
    rows.append(("without-system-layout", layout, True))

    single = deepcopy(original)
    pickup = single.find("part/measure")
    if pickup is None:
        raise ValueError("Reproducer has no pickup measure")
    for node in list(pickup):
        if node.tag == "backup" or (node.tag == "note" and node.findtext("voice") == "2"):
            pickup.remove(node)
    rows.append(("without-independent-voice", single, False))

    consistent = deepcopy(original)
    measures = consistent.findall("part/measure")
    _, trace = xml_trace(source)
    if len(measures) != 2 or len(trace) != 2:
        raise ValueError("Expected the fixed two-measure reproducer")
    duration = Fraction(trace[1]["used"]) * trace[1]["divisions"]
    if duration.denominator != 1 or duration <= 0:
        raise ValueError("Second voice rest requires a positive integer XML duration")
    backup = ET.SubElement(measures[1], "backup")
    ET.SubElement(backup, "duration").text = str(duration.numerator)
    rest = ET.SubElement(measures[1], "note")
    ET.SubElement(rest, "rest")
    ET.SubElement(rest, "duration").text = str(duration.numerator)
    ET.SubElement(rest, "voice").text = "2"
    rows.append(("consistent-voice-containers", consistent, True))

    untyped = deepcopy(original)
    for note in untyped.findall("part/measure/note"):
        for node in list(note):
            if node.tag in ("type", "time-modification"):
                note.remove(node)
    rows.append(("exact-divisions-without-note-types", untyped, True))
    return rows


def diagnose(destination: Path) -> None:
    source = OUT.parent / "phase2/cross-system-chord-tie.musicxml"
    original_raw, _ = xml_trace(source)
    destination.mkdir(parents=True, exist_ok=False)
    original = destination / "original.musicxml"
    shutil.copy2(source, original)
    cases = [("original", original, True)]
    for name, root, preserves in controls(source):
        path = destination / f"{name}.musicxml"
        ET.ElementTree(root).write(path, encoding="utf-8", xml_declaration=True)
        cases.append((name, path, preserves))
    rows = []
    for name, path, preserves in cases:
        raw, measures = xml_trace(path)
        unchanged = event_signature(raw) == event_signature(original_raw)
        if preserves and not unchanged:
            raise ValueError(f"Control unexpectedly changed pitched events: {name}")
        merged, issues = merge_segments(raw)
        normalized = normalized_notes(path)
        rows.append({"case": name, "input_sha256": sha256_file(path),
            "pitched_events_preserved": unchanged, "raw_segments": [n.json() for n in raw],
            "exact_merged_notes": [n.json() for n in merged], "tie_issues": issues,
            "normalized_notes": [{"pitch": n.pitch, "onset": str(n.onset),
                "duration": str(n.duration), "staff": n.staff, "voice": n.voice} for n in normalized],
            "normalization_vs_exact": metric_summary(normalized, [n.metric() for n in merged]),
            "measures": measures})
    save_json(destination / "diagnosis.json", {"source": str(source),
        "source_sha256": sha256_file(source), "diagnostic_source_sha256": sha256_file(Path(__file__)),
        "normalizer_policy": "unchanged Bridge; controls diagnose causes and are not benchmark remedies",
        "cases": rows})


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    configure_cpu()
    diagnose(args.output.resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
