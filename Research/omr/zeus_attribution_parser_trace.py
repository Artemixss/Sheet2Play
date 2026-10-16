"""Supplement exact-XML failures with explicitly labeled Bridge-parser observations."""
from __future__ import annotations

import json
from pathlib import Path
import sys

from zeus_attribution_prepare import OUT, ROOT, configure_cpu, save_json
from zeus_attribution_analyze import rebase, system_truth, part_staff_counts
from sheet2play_omr.adapter_contract import sha256_file
from sheet2play_omr.zeus_trace import Segment, local_metrics, merge_segments, metric_summary, normalized_notes
from sheet2play_omr.timing import rational_time


def parsed_trace(path: Path) -> tuple[list[Segment], list[dict]]:
    sys.path.insert(0, str(ROOT / "Bridge"))
    from musicxml_normalizer import _load_music21_types, _parse_musicxml_with_repair, _voice_identifier
    chord_type, converter, _, stream_type = _load_music21_types()
    score = _parse_musicxml_with_repair(converter, path, force_source=True)
    segments, measures = [], []
    for staff, part in enumerate(score.parts):
        identity = f"parsed-part-{staff:04d}"
        for index, measure in enumerate(part.getElementsByClass(stream_type.Measure)):
            start = rational_time(float(measure.getOffsetInHierarchy(part)))
            measures.append({"part": identity, "index": index, "start": str(start),
                             "new_system": False, "number": str(measure.number)})
            for element in measure.recurse().notes:
                if element.duration.isGrace:
                    continue
                duration = rational_time(float(element.duration.quarterLength))
                local = rational_time(float(element.getOffsetInHierarchy(measure)))
                if duration <= 0 or local < 0:
                    raise ValueError("Parsed diagnostic note has invalid timing")
                notes = element.notes if isinstance(element, chord_type.Chord) else [element]
                for note in notes:
                    midi = float(note.pitch.midi)
                    if not midi.is_integer() or not 0 <= midi <= 127:
                        raise ValueError("Unsupported parsed MIDI pitch")
                    tie = (("stop", "start") if note.tie.type == "continue" else (note.tie.type,)) \
                        if note.tie is not None else ()
                    segments.append(Segment(int(midi), start + local, duration, staff,
                        _voice_identifier(element, stream_type), identity, index, local, tie))
    if not measures:
        raise ValueError("Bridge parser returned no measures")
    return segments, measures


def main() -> int:
    configure_cpu()
    manifest_path = OUT / "experiment-manifest.json"
    manifest = json.loads(manifest_path.read_text())
    for filename, expected in manifest["sources"].items():
        if sha256_file(Path(filename)) != expected:
            raise ValueError(f"Pinned source changed: {filename}")
    analysis = json.loads((OUT / "analysis-report.json").read_text())
    destination = OUT / "parser-diagnostics"
    destination.mkdir(exist_ok=False)
    rows = []
    for item, result in zip(manifest["items"], analysis["items"], strict=True):
        if item["item_id"] != result["item_id"]:
            raise ValueError("Analysis/manifest item mismatch")
        reference, reference_measures = parsed_trace(Path(item["reference"]))
        boundaries = item.get("reference_system_measure_starts")
        if boundaries is None:
            from sheet2play_omr.zeus_trace import xml_trace
            _, xml_measures = xml_trace(Path(item["reference"]))
            boundaries = [m["index"] for m in xml_measures if m["part"] == xml_measures[0]["part"]
                          and (m["index"] == 0 or m["new_system"])]
        reference_systems = system_truth(reference, reference_measures, boundaries)
        variants = {}
        for variant in ("upstream", "wrapper"):
            row = result["variants"][variant]
            if row["status"] != "succeeded":
                variants[variant] = {"status": "unavailable", "reason": "Primary pipeline failed"}
                continue
            page = OUT / "analysis" / item["item_id"] / f"{variant}-stitched.musicxml"
            raw, measures = parsed_trace(page)
            merged, ties = merge_segments(raw)
            systems = []
            for number in range(1, len(item["crops"]) + 1):
                xml = OUT / "inference" / item["item_id"] / f"system-{number:04d}" / f"{variant}.musicxml"
                notes, _ = parsed_trace(xml)
                expected = rebase(reference_systems[number - 1], reference_measures, boundaries[number - 1]) \
                    if number <= len(reference_systems) else []
                systems.append({"system": number, "raw_notes": len(notes),
                    "system_local_parsed_raw": metric_summary([n.metric() for n in notes], [n.metric() for n in expected])})
            variants[variant] = {"status": "observed", "raw_notes": len(raw),
                "part_staff_counts": part_staff_counts(raw), "tie_issues": ties,
                "earliest_pitched_onset": str(min(n.onset for n in raw)) if raw else None,
                "measure_local_parsed_raw": local_metrics(raw, reference), "systems": systems,
                "stitch_raw_note_count_preserved": len(raw) == sum(s["raw_notes"] for s in systems),
                "normalizer_vs_parser_merged": metric_summary(normalized_notes(page), [n.metric() for n in merged])}
            save_json(destination / f"{item['item_id']}-{variant}-trace.json",
                {"notes": [n.json() for n in raw], "measures": measures})
        rows.append({"item_id": item["item_id"], "reference_parsed_notes": len(reference), "variants": variants})
    save_json(OUT / "parser-diagnostics.json", {"items": rows,
        "identity": {"script_sha256": sha256_file(Path(__file__)),
                     "manifest_sha256": sha256_file(manifest_path),
                     "analysis_sha256": sha256_file(OUT / "analysis-report.json")},
        "policy": "Observed unchanged Bridge-parser interpretation before stripTies; not a literal XML-duration trace. "
                  "Parser-inferred missing-rest timing and backup handling remain explicit limitations. "
                  "Ordinal local comparison, no reference alignment or primary score changes."})
    print(json.dumps({"items": len(rows), "parser_traces": sum(len(r["variants"]) for r in rows)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
