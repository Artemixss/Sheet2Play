#!/usr/bin/env python3
"""Freeze Phase-1 development inputs without running an OMR candidate."""

from __future__ import annotations

import hashlib
import io
import json
import shutil
import subprocess
import sys
import warnings
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from typing import Any, Callable

HERE = Path(__file__).resolve().parent
WORKSPACE = HERE.parent.parent
sys.path.insert(0, str(HERE / "src"))
sys.path.insert(0, str(WORKSPACE / "Bridge"))

from musicxml_normalizer import normalize_musicxml  # noqa: E402
from sheet2play_omr.events import parse_kern  # noqa: E402

OPENSCORE_REVISION = "6b2dc542ce2e8aa4b78c8ee62103b210efc07015"


class DevelopmentFreezeError(ValueError):
    pass


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as error:
            raise DevelopmentFreezeError(f"{path}:{line_number}: invalid JSON: {error}") from error
        if not isinstance(value, dict):
            raise DevelopmentFreezeError(f"{path}:{line_number}: expected an object")
        rows.append(value)
    return rows


def relative_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(WORKSPACE.resolve()).as_posix()
    except ValueError as error:
        raise DevelopmentFreezeError(f"Development artifact is outside the workspace: {path}") from error


def require_unique(rows: list[dict[str, Any]], field: str, label: str) -> None:
    identifiers = [str(row[field]) for row in rows]
    duplicates = sorted({identifier for identifier in identifiers if identifiers.count(identifier) > 1})
    if duplicates:
        raise DevelopmentFreezeError(f"{label} has duplicate {field} values: {duplicates[:5]}")


def capture_validation(
    action: Callable[[], Any],
    label: str,
    *,
    warnings_are_failures: bool = True,
    require_notes: bool = True,
) -> list[str]:
    output = io.StringIO()
    error_output = io.StringIO()
    caught_warnings: list[warnings.WarningMessage] = []
    try:
        with warnings.catch_warnings(record=True) as caught_warnings:
            warnings.simplefilter("always")
            with redirect_stdout(output), redirect_stderr(error_output):
                result = action()
    except Exception as error:
        raise DevelopmentFreezeError(
            f"{label} failed validation: {type(error).__name__}: {str(error)[:240]}"
        ) from error
    messages = [
        line.strip()
        for line in (output.getvalue() + "\n" + error_output.getvalue()).splitlines()
        if line.strip()
    ]
    messages.extend(
        f"{warning.category.__name__}: {str(warning.message)[:240]}"
        for warning in caught_warnings
    )
    if messages and warnings_are_failures:
        raise DevelopmentFreezeError(f"{label} emitted parser warnings: {messages[:3]}")
    notes = getattr(result, "notes", None)
    if require_notes and not notes:
        raise DevelopmentFreezeError(f"{label} produced no canonical notes")
    return messages


def render_pdf_pages(pdf: Path, destination: Path, renderer: str) -> list[Path]:
    destination.mkdir(parents=True, exist_ok=True)
    existing = sorted(destination.glob("page-*.png"))
    if not existing:
        result = subprocess.run(
            [renderer, "-png", "-r", "300", str(pdf), str(destination / "page")],
            capture_output=True,
            text=True,
            timeout=300,
            check=False,
        )
        if result.returncode != 0:
            detail = (result.stderr or result.stdout or "unknown renderer failure").strip()[:240]
            raise DevelopmentFreezeError(f"300-DPI render failed for {pdf}: {detail}")
        existing = sorted(destination.glob("page-*.png"))
    if not existing:
        raise DevelopmentFreezeError(f"300-DPI render produced no pages for {pdf}")
    return existing


def freeze_open_development(
    pairs_path: Path,
    olimpic_manifest: Path,
    render_root: Path,
    renderer: str | None = None,
) -> list[dict[str, Any]]:
    pairs = load_jsonl(pairs_path)
    if len(pairs) != 20:
        raise DevelopmentFreezeError(f"Expected 20 OpenScore development pairs; found {len(pairs)}")
    require_unique(pairs, "score", "OpenScore development selection")
    olimpic_ids = {str(row["score_id"]) for row in load_jsonl(olimpic_manifest)}
    if len(olimpic_ids) != 100:
        raise DevelopmentFreezeError(
            f"Expected 100 OLiMPiC evaluation compositions; found {len(olimpic_ids)}"
        )
    renderer_path = renderer or shutil.which("pdftoppm")
    if not renderer_path:
        raise DevelopmentFreezeError("pdftoppm is required for frozen 300-DPI development pages")
    root = pairs_path.parent
    frozen: list[dict[str, Any]] = []
    for pair in pairs:
        score = root / "source" / str(pair["score"])
        label = root / str(pair["label"])
        pdf = root / str(pair.get("pdf", ""))
        for kind, path in (("source", score), ("MusicXML", label), ("PDF", pdf)):
            if not path.is_file():
                raise DevelopmentFreezeError(f"OpenScore {kind} is missing: {path}")
        score_id = score.stem.removeprefix("lc")
        if score_id in olimpic_ids:
            raise DevelopmentFreezeError(
                f"Development composition overlaps OLiMPiC evaluation: {score_id}"
            )
        validation_warnings = capture_validation(
            lambda label=label: normalize_musicxml(
                label,
                expand_repeats=False,
                skip_grace_notes=True,
                force_source=True,
            ),
            f"OpenScore {score_id}",
            warnings_are_failures=False,
        )
        pages = render_pdf_pages(pdf, render_root / score_id, renderer_path)
        frozen.append(
            {
                "composition_group": score_id,
                "composition_overlap_with_evaluation": False,
                "ground_truth_provenance": "OpenScore Lieder CC0 MuseScore source",
                "id": f"openscore-{score_id}",
                "license": "CC0-1.0",
                "musicxml_path": relative_path(label),
                "musicxml_sha256": sha256_file(label),
                "page_images": [
                    {
                        "path": relative_path(page),
                        "sha256": sha256_file(page),
                    }
                    for page in pages
                ],
                "pdf_path": relative_path(pdf),
                "pdf_sha256": sha256_file(pdf),
                "printed_or_scanned": "printed",
                "render_dpi": 300,
                "reference_validation_warnings": validation_warnings,
                "source_path": relative_path(score),
                "source_revision": OPENSCORE_REVISION,
                "source_sha256": sha256_file(score),
                "training_overlap": "known possible OpenScore Lieder overlap; development-only",
            }
        )
    require_unique(frozen, "id", "frozen OpenScore development collection")
    return sorted(frozen, key=lambda row: str(row["id"]))


def freeze_controlled_development(
    controlled_manifest: Path, baseline_dir: Path
) -> list[dict[str, Any]]:
    source_rows = load_jsonl(controlled_manifest)
    if len(source_rows) != 11:
        raise DevelopmentFreezeError(f"Expected 11 polyrhythm controls; found {len(source_rows)}")
    require_unique(source_rows, "identifier", "polyrhythm controls")
    frozen: list[dict[str, Any]] = []
    for row in source_rows:
        image = Path(str(row["image"]))
        musicxml = Path(str(row["musicxml"]))
        if not image.is_file() or not musicxml.is_file():
            raise DevelopmentFreezeError(f"Generated control is incomplete: {row['identifier']}")
        capture_validation(
            lambda musicxml=musicxml: normalize_musicxml(
                musicxml,
                expand_repeats=False,
                skip_grace_notes=True,
                force_source=True,
            ),
            f"generated control {row['identifier']}",
        )
        frozen.append(
            {
                "composition_group": str(row["score_id"]),
                "composition_overlap_with_evaluation": False,
                "generator": "Research/omr/generate_polyrhythm.py",
                "ground_truth_provenance": "project-generated MusicXML",
                "id": f"generated-{row['identifier']}",
                "image_path": relative_path(image),
                "image_sha256": sha256_file(image),
                "license": "project-owned",
                "musicxml_path": relative_path(musicxml),
                "musicxml_sha256": sha256_file(musicxml),
                "traits": {
                    "polyrhythm": bool(row.get("polyrhythm", False)),
                    "tuplet": bool(row.get("tuplet", False)),
                },
            }
        )
    baseline_image = baseline_dir / "baseline-piano.png"
    baseline_kern = baseline_dir / "baseline-piano.krn"
    if not baseline_image.is_file() or not baseline_kern.is_file():
        raise DevelopmentFreezeError("Deterministic baseline control is incomplete")
    capture_validation(
        lambda: parse_kern(baseline_kern.read_text(encoding="utf-8")),
        "deterministic baseline control",
        require_notes=False,
    )
    frozen.append(
        {
            "composition_group": "baseline-piano-001",
            "composition_overlap_with_evaluation": False,
            "generator": "Research/omr/tools/generate_baseline_fixture.py",
            "ground_truth_provenance": "project-generated **kern",
            "id": "generated-baseline-piano-001",
            "image_path": relative_path(baseline_image),
            "image_sha256": sha256_file(baseline_image),
            "kern_path": relative_path(baseline_kern),
            "kern_sha256": sha256_file(baseline_kern),
            "license": "project-owned",
            "traits": {"polyrhythm": False, "tuplet": False},
        }
    )
    require_unique(frozen, "id", "frozen controlled development collection")
    if len(frozen) != 12:
        raise DevelopmentFreezeError(f"Expected 12 controlled examples; found {len(frozen)}")
    return sorted(frozen, key=lambda row: str(row["id"]))


def freeze_development(
    pairs_path: Path,
    olimpic_manifest: Path,
    controlled_manifest: Path,
    baseline_dir: Path,
    render_root: Path,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    return (
        freeze_open_development(pairs_path, olimpic_manifest, render_root),
        freeze_controlled_development(controlled_manifest, baseline_dir),
    )
