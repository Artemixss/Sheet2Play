from __future__ import annotations

import hashlib
import json
import random
from collections import defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

from .errors import ResearchError


REQUIRED_FIXTURE_TAGS = {
    "dotted",
    "tuplet",
    "tie",
    "multiple_voices",
    "dense_chord",
    "accidental",
    "repeat",
    "cross_staff",
    "numeric_tempo",
}


@dataclass(frozen=True, slots=True)
class DatasetRecord:
    identifier: str
    source: str
    musicxml: str
    composition_hash: str
    staff_count: int
    instrument: str
    license_conflict: bool
    tags: tuple[str, ...] = ()


def _composition_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def load_source_manifest(path: Path) -> list[DatasetRecord]:
    records: list[DatasetRecord] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as error:
        raise ResearchError("DATASET_INVALID", "dataset", f"Cannot read {path}: {error}") from error
    for line_number, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        try:
            raw = json.loads(line)
            musicxml = Path(raw["musicxml"]).resolve()
            record = DatasetRecord(
                identifier=str(raw["id"]),
                source=str(raw["source"]),
                musicxml=str(musicxml),
                composition_hash=str(raw.get("composition_hash") or _composition_hash(musicxml)),
                staff_count=int(raw["staff_count"]),
                instrument=str(raw["instrument"]),
                license_conflict=bool(raw.get("license_conflict", False)),
                tags=tuple(sorted({str(tag) for tag in raw.get("tags", [])})),
            )
        except (KeyError, OSError, TypeError, ValueError, json.JSONDecodeError) as error:
            raise ResearchError(
                "DATASET_INVALID",
                "dataset",
                f"Invalid manifest line {line_number}: {error}",
            ) from error
        if musicxml.is_file() and record.staff_count == 2 and record.instrument.casefold() == "piano":
            if record.source.casefold() != "pdmx" or not record.license_conflict:
                records.append(record)
    return records


def split_by_composition(
    records: Iterable[DatasetRecord],
    *,
    seed: int,
    train_count: int,
    validation_count: int,
    test_count: int,
) -> dict[str, list[DatasetRecord]]:
    requested = {"train": train_count, "validation": validation_count, "test": test_count}
    if any(value < 0 for value in requested.values()):
        raise ResearchError("DATASET_INVALID", "dataset", "Split counts cannot be negative")
    by_composition: dict[str, list[DatasetRecord]] = defaultdict(list)
    for record in records:
        by_composition[record.composition_hash].append(record)
    groups = list(by_composition.values())
    random.Random(seed).shuffle(groups)
    groups.sort(key=len, reverse=True)
    assigned: dict[str, list[DatasetRecord]] = {name: [] for name in requested}
    composition_sets: dict[str, set[str]] = {name: set() for name in requested}

    for group in groups:
        candidates = [name for name, target in requested.items() if len(assigned[name]) < target]
        if not candidates:
            break
        destination = max(
            candidates,
            key=lambda name: (requested[name] - len(assigned[name])) / max(1, requested[name]),
        )
        remaining = requested[destination] - len(assigned[destination])
        assigned[destination].extend(group[:remaining])
        composition_sets[destination].add(group[0].composition_hash)

    for name, target in requested.items():
        if len(assigned[name]) != target:
            raise ResearchError(
                "DATASET_INSUFFICIENT",
                "dataset",
                f"Requested {target} {name} systems but only assigned {len(assigned[name])}",
            )
    names = tuple(composition_sets)
    for index, left in enumerate(names):
        for right in names[index + 1 :]:
            overlap = composition_sets[left] & composition_sets[right]
            if overlap:
                raise ResearchError("DATASET_LEAKAGE", "dataset", f"Composition leakage: {sorted(overlap)}")
    return assigned


def write_splits(splits: dict[str, list[DatasetRecord]], output_dir: Path) -> dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    paths: dict[str, Path] = {}
    for name, records in splits.items():
        destination = output_dir / f"{name}.jsonl"
        content = "".join(json.dumps(asdict(record), sort_keys=True) + "\n" for record in records)
        destination.write_text(content, encoding="utf-8")
        paths[name] = destination
    return paths


def validate_fixture_coverage(records: Iterable[DatasetRecord]) -> set[str]:
    available = {tag for record in records for tag in record.tags}
    return REQUIRED_FIXTURE_TAGS - available

