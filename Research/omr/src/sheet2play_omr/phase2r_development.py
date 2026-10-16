"""Audit frozen development references and the selected ABC converter."""
from __future__ import annotations

import json
import re
import subprocess
import tempfile
import xml.etree.ElementTree as ET
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from .adapter_contract import portable_path, sha256_file
from .phase2_adapters import _canonicalize
from .phase2r_vlm import convert_abc


AUDIT_REVISION = sha256_file(Path(__file__))


@dataclass(frozen=True, slots=True)
class DevelopmentRecord:
    item_id: str
    collection: str
    composition_group: str
    image: Path
    image_sha256: str
    page_images: tuple[tuple[Path, str], ...]
    reference: Path
    reference_sha256: str
    reference_format: str
    page_count: int
    declared_traits: dict[str, Any]


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def development_records(workspace: Path) -> list[DevelopmentRecord]:
    frozen = workspace / "Research" / "omr" / "reports" / "phase1"
    controlled = _load_jsonl(frozen / "development-controlled.jsonl")
    opened = _load_jsonl(frozen / "development-open.jsonl")
    if len(controlled) != 12 or len(opened) != 20:
        raise ValueError("The frozen development collection must contain 12 generated controls and 20 open compositions")
    records: list[DevelopmentRecord] = []
    for row in controlled:
        if row.get("composition_overlap_with_evaluation") is not False:
            raise ValueError(f"Controlled development overlap is not excluded: {row['id']}")
        reference_key = "musicxml_path" if "musicxml_path" in row else "kern_path"
        hash_key = "musicxml_sha256" if reference_key == "musicxml_path" else "kern_sha256"
        records.append(DevelopmentRecord(
            str(row["id"]), "generated", str(row["composition_group"]),
            workspace / row["image_path"], str(row["image_sha256"]),
            ((workspace / row["image_path"], str(row["image_sha256"])),),
            workspace / row[reference_key], str(row[hash_key]),
            "musicxml" if reference_key == "musicxml_path" else "kern",
            1, dict(row.get("traits", {})),
        ))
    for row in opened:
        if row.get("composition_overlap_with_evaluation") is not False:
            raise ValueError(f"Open development overlap is not excluded: {row['id']}")
        pages = row["page_images"]
        if not pages:
            raise ValueError(f"No development pages for {row['id']}")
        records.append(DevelopmentRecord(
            str(row["id"]), "open", str(row["composition_group"]),
            workspace / pages[0]["path"], str(pages[0]["sha256"]),
            tuple((workspace / page["path"], str(page["sha256"])) for page in pages),
            workspace / row["musicxml_path"], str(row["musicxml_sha256"]),
            "musicxml", len(pages), {},
        ))
    if len({record.item_id for record in records}) != len(records):
        raise ValueError("Development item IDs are not unique")
    return records


def _verify_input(record: DevelopmentRecord) -> None:
    inputs = [(f"page-{index}", path, expected) for index, (path, expected) in enumerate(record.page_images, 1)]
    inputs.append(("reference", record.reference, record.reference_sha256))
    for kind, path, expected in inputs:
        if not path.is_file():
            raise FileNotFoundError(f"{record.item_id} {kind} is missing")
        if sha256_file(path) != expected:
            raise ValueError(f"{record.item_id} {kind} hash differs from the frozen development manifest")


def _reference_musicxml(record: DevelopmentRecord, work: Path) -> Path:
    if record.reference_format == "musicxml":
        return record.reference
    from music21 import converter

    destination = work / "reference.musicxml"
    score = converter.parse(str(record.reference), forceSource=True)
    score.write("musicxml", fp=destination)
    return destination


def _features(xml: Path, page_count: int) -> dict[str, Any]:
    root = ET.parse(xml).getroot()
    ties = sum(node.tag.rsplit("}", 1)[-1] == "tie" for node in root.iter())
    tuplets = sum(node.tag.rsplit("}", 1)[-1] == "time-modification" for node in root.iter())
    systems = sum(
        node.tag.rsplit("}", 1)[-1] == "print" and node.attrib.get("new-system") == "yes"
        for node in root.iter()
    )
    meters: set[tuple[str, str]] = set()
    voices_by_part: list[set[str]] = []
    for part in (node for node in root if node.tag.rsplit("}", 1)[-1] == "part"):
        voices: set[str] = set()
        for node in part.iter():
            name = node.tag.rsplit("}", 1)[-1]
            if name == "voice" and node.text:
                voices.add(node.text.strip())
            if name == "time":
                beats = [child.text for child in node if child.tag.rsplit("}", 1)[-1] == "beats"]
                beat_type = [child.text for child in node if child.tag.rsplit("}", 1)[-1] == "beat-type"]
                if beats and beat_type:
                    meters.add((beats[0] or "", beat_type[0] or ""))
        voices_by_part.append(voices)
    return {
        "ties": ties > 0,
        "tuplets": tuplets > 0,
        "independent_voices": any(len(voices) > 1 for voices in voices_by_part),
        "meter_changes": len(meters) > 1,
        "engraved_system_changes": systems,
        "multi_page": page_count > 1,
        "page_count": page_count,
    }


def _event_counter(path: Path) -> Counter[tuple[Any, ...]]:
    document = json.loads(path.read_text(encoding="utf-8"))
    return Counter(
        (note["midi_pitch"], note["onset"], note["duration"])
        for note in document["notes"]
    )


def _exact_event_f1(predicted: Counter[tuple[Any, ...]], expected: Counter[tuple[Any, ...]]) -> float:
    true_positive = sum((predicted & expected).values())
    denominator = sum(predicted.values()) + sum(expected.values())
    return 2 * true_positive / denominator if denominator else 0.0


def _diagnostic_codes(output: str) -> dict[str, int]:
    return dict(sorted(Counter(re.findall(r"(?:warning|error)\[([^]]+)\]", output)).items()))


def _convert_reference(xml: Path, work: Path, converter: Path) -> tuple[Path, Path, dict[str, int]]:
    abc = work / "reference.abc"
    completed = subprocess.run(
        [str(converter), "read", str(xml), "--format", "abc", "--output", str(abc)],
        check=False, capture_output=True, text=True, timeout=120,
        encoding="utf-8", errors="replace",
    )
    if completed.returncode != 0 or not abc.is_file():
        raise RuntimeError((completed.stderr or completed.stdout or "croma MusicXML reader failed")[-1200:])
    roundtrip = work / "roundtrip.musicxml"
    convert_abc(abc.read_text(encoding="utf-8"), roundtrip, converter)
    return abc, roundtrip, _diagnostic_codes(completed.stderr)


def _diagnostic_roundtrip(abc: Path, roundtrip: Path, converter: Path) -> dict[str, Any]:
    """Measure reference projection loss, never as an accepted prediction conversion."""
    completed = subprocess.run(
        [str(converter), "xml", "--strict", str(abc), "--output", str(roundtrip)],
        check=False, capture_output=True, text=True, timeout=120,
        encoding="utf-8", errors="replace",
    )
    return {
        "exit_status": completed.returncode,
        "warning_codes": _diagnostic_codes(completed.stderr),
        "musicxml_written": roundtrip.is_file() and roundtrip.stat().st_size > 0,
    }


def audit_development_item(record: DevelopmentRecord, converter: Path, output: Path) -> dict[str, Any]:
    _verify_input(record)
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="s2p-phase2r-audit-") as temporary:
        work = Path(temporary)
        reference_xml = _reference_musicxml(record, work)
        expected_path = work / "expected-events.json"
        _canonicalize(reference_xml, expected_path)
        features = _features(reference_xml, record.page_count)
        result: dict[str, Any] = {
            "item_id": record.item_id,
            "collection": record.collection,
            "composition_group": record.composition_group,
            "image_sha256": record.image_sha256,
            "reference_sha256": record.reference_sha256,
            "converter_sha256": sha256_file(converter),
            "audit_revision": AUDIT_REVISION,
            "reference_format": record.reference_format,
            "features": features,
            "declared_traits": record.declared_traits,
            "reference_note_count": sum(_event_counter(expected_path).values()),
        }
        abc = work / "reference.abc"
        roundtrip = work / "roundtrip.musicxml"
        try:
            abc, roundtrip, read_warnings = _convert_reference(reference_xml, work, converter)
            actual_path = work / "roundtrip-events.json"
            _canonicalize(roundtrip, actual_path)
            result["converter_status"] = "succeeded"
            result["reference_read_warning_codes"] = read_warnings
            result["roundtrip_exact_event_f1"] = _exact_event_f1(
                _event_counter(actual_path), _event_counter(expected_path)
            )
            result["abc_sha256"] = sha256_file(abc)
            result["roundtrip_musicxml_sha256"] = sha256_file(roundtrip)
        except Exception as error:
            result["converter_status"] = "failed"
            result["converter_error"] = f"{type(error).__name__}: {error}"[:1200]
            if abc.is_file():
                diagnostic = _diagnostic_roundtrip(abc, roundtrip, converter)
                result["diagnostic_roundtrip"] = diagnostic
                if diagnostic["exit_status"] == 0 and diagnostic["musicxml_written"]:
                    try:
                        diagnostic_events = work / "diagnostic-events.json"
                        _canonicalize(roundtrip, diagnostic_events)
                        result["diagnostic_roundtrip_exact_event_f1"] = _exact_event_f1(
                            _event_counter(diagnostic_events), _event_counter(expected_path)
                        )
                    except Exception as diagnostic_error:
                        result["diagnostic_roundtrip_error"] = (
                            f"{type(diagnostic_error).__name__}: {diagnostic_error}"[:500]
                        )
    destination = output / f"{record.item_id}.json"
    temporary = destination.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(destination)
    return result


def audit_development_collection(workspace: Path, converter: Path, output: Path) -> list[dict[str, Any]]:
    if not converter.is_file():
        raise FileNotFoundError("Pinned ABC converter is missing")
    converter_sha256 = sha256_file(converter)
    results = []
    for record in development_records(workspace):
        saved = output / f"{record.item_id}.json"
        if saved.is_file():
            prior = json.loads(saved.read_text(encoding="utf-8"))
            if (
                prior.get("reference_sha256") == record.reference_sha256
                and prior.get("image_sha256") == record.image_sha256
                and prior.get("converter_sha256") == converter_sha256
                and prior.get("audit_revision") == AUDIT_REVISION
            ):
                _verify_input(record)
                results.append(prior)
                print(f"{record.item_id}: reused {prior['converter_status']}", flush=True)
                continue
        result = audit_development_item(record, converter, output)
        results.append(result)
        print(f"{record.item_id}: {result['converter_status']}", flush=True)
    return results
