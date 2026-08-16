from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path, PurePosixPath
from typing import Iterable

from .errors import ResearchError


@dataclass(frozen=True, slots=True)
class OlimpicSample:
    identifier: str
    score_id: str
    image: str
    musicxml: str
    lmx: str
    partition: str = "test"
    source: str = "scanned"


def _sample_path(root: Path, logical: PurePosixPath, suffix: str) -> Path:
    candidate = root.joinpath(*logical.parts).with_suffix(suffix).resolve()
    if not candidate.is_file():
        raise ResearchError("DATASET_INVALID", "olimpic", f"Missing OLiMPiC asset: {candidate}")
    return candidate


def load_test_partition(root: Path) -> list[OlimpicSample]:
    resolved_root = root.resolve()
    partition_path = resolved_root / "samples.test.txt"
    try:
        lines = partition_path.read_text(encoding="utf-8").splitlines()
    except OSError as error:
        raise ResearchError(
            "DATASET_INVALID", "olimpic", f"Cannot read {partition_path}: {error}"
        ) from error

    samples: list[OlimpicSample] = []
    for line_number, line in enumerate(lines, start=1):
        value = line.strip()
        if not value:
            continue
        logical = PurePosixPath(value)
        if logical.is_absolute() or ".." in logical.parts or len(logical.parts) != 3:
            raise ResearchError(
                "DATASET_INVALID",
                "olimpic",
                f"Invalid test sample path on line {line_number}: {value!r}",
            )
        score_id = logical.parts[1]
        sample_name = logical.parts[2]
        samples.append(
            OlimpicSample(
                identifier=f"{score_id}/{sample_name}",
                score_id=score_id,
                image=str(_sample_path(resolved_root, logical, ".png")),
                musicxml=str(_sample_path(resolved_root, logical, ".musicxml")),
                lmx=str(_sample_path(resolved_root, logical, ".lmx")),
            )
        )
    if len(samples) != 1493:
        raise ResearchError(
            "DATASET_INVALID", "olimpic", f"Expected 1493 test systems, found {len(samples)}"
        )
    identifiers = [sample.identifier for sample in samples]
    if len(identifiers) != len(set(identifiers)):
        raise ResearchError("DATASET_INVALID", "olimpic", "Duplicate OLiMPiC sample identifiers")
    score_ids = {sample.score_id for sample in samples}
    if len(score_ids) != 100:
        raise ResearchError(
            "DATASET_INVALID", "olimpic", f"Expected 100 test scores, found {len(score_ids)}"
        )
    return sorted(samples, key=lambda sample: sample.identifier)


def _rank(seed: int, value: str) -> str:
    return hashlib.sha256(f"{seed}:{value}".encode("utf-8")).hexdigest()


def select_stratified_canary(
    samples: Iterable[OlimpicSample],
    *,
    count: int = 100,
    seed: int = 20260814,
) -> list[OlimpicSample]:
    available = list(samples)
    if count < 1 or count > len(available):
        raise ResearchError(
            "BENCHMARK_INVALID",
            "canary_selection",
            f"Canary size must be between 1 and {len(available)}, received {count}",
        )
    by_score: dict[str, list[OlimpicSample]] = defaultdict(list)
    for sample in available:
        by_score[sample.score_id].append(sample)

    score_order = sorted(by_score, key=lambda score_id: (_rank(seed, score_id), score_id))
    selected: list[OlimpicSample] = []
    for score_id in score_order[: min(count, len(score_order))]:
        selected.append(
            min(
                by_score[score_id],
                key=lambda sample: (_rank(seed, sample.identifier), sample.identifier),
            )
        )
    if len(selected) < count:
        selected_ids = {sample.identifier for sample in selected}
        remaining = sorted(
            (sample for sample in available if sample.identifier not in selected_ids),
            key=lambda sample: (_rank(seed, sample.identifier), sample.identifier),
        )
        selected.extend(remaining[: count - len(selected)])
    return sorted(selected, key=lambda sample: sample.identifier)


def write_benchmark_manifest(samples: Iterable[OlimpicSample], path: Path) -> str:
    rows = list(samples)
    if not rows:
        raise ResearchError("BENCHMARK_INVALID", "manifest", "Cannot write an empty manifest")
    path.parent.mkdir(parents=True, exist_ok=True)
    content = "".join(json.dumps(asdict(sample), sort_keys=True) + "\n" for sample in rows)
    path.write_text(content, encoding="utf-8")
    return hashlib.sha256(content.encode("utf-8")).hexdigest()
