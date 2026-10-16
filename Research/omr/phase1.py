#!/usr/bin/env python3
"""Freeze Phase-1 inputs, scoring rules, and reference-validation evidence.

This command performs no OMR inference and imports no candidate adapter. Its output is the
boundary between dataset/protocol preparation (Phase 1) and adapter work (Phase 2).
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import re
import sys
import warnings
from collections import Counter
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from typing import Any, Iterable

HERE = Path(__file__).resolve().parent
WORKSPACE = HERE.parent.parent
sys.path.insert(0, str(HERE / "src"))
sys.path.insert(0, str(WORKSPACE / "Bridge"))

from musicxml_normalizer import normalize_musicxml  # noqa: E402
from phase1_development import freeze_development  # noqa: E402
from sheet2play_omr.events import parse_kern  # noqa: E402

SMB_REVISION = "96332e8c4ac81cbdb7f61093ec5a4bfff76a0adb"
OLIMPIC_REVISION = "df0d842596ccd199882ff958e628d59327ca6cba"
REFERENCE_VALIDATOR_VERSION = 2
OLIMPIC_NON_FATAL_WARNING_PREFIXES = (
    "Could not import wedge: Error in getting DynamicWedges",
    "Could not import pedal: Error in getting PedalMark",
    "Could not import octave-shift: Error in getting Ottava",
    "Line <dashes> stop without start",
    "Line <bracket> stop without start",
)
CANDIDATE_KEYS = (
    "shipped_homr",
    "completed_homr_finetune",
    "homr_pr156",
    "legato",
    "zeus",
    "audiveris",
)


def sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def canonical_hash(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return sha256_bytes(payload.encode("utf-8"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as error:
            raise ValueError(f"{path}:{line_number}: invalid JSON: {error}") from error
        if not isinstance(value, dict):
            raise ValueError(f"{path}:{line_number}: expected an object")
        rows.append(value)
    return rows


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def write_json_atomic(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    content = "".join(
        json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
        for row in rows
    )
    path.write_text(content, encoding="utf-8")


def relative_path(path: Path) -> str:
    return path.resolve().relative_to(WORKSPACE.resolve()).as_posix()


def require_unique(rows: Iterable[dict[str, Any]], field: str, collection: str) -> None:
    identifiers = [str(row[field]) for row in rows]
    duplicates = sorted(identifier for identifier, count in Counter(identifiers).items() if count > 1)
    if duplicates:
        raise ValueError(f"{collection} has duplicate {field} values: {duplicates[:5]}")


def require_subset(subset: set[str], superset: set[str], label: str) -> None:
    missing = sorted(subset - superset)
    if missing:
        raise ValueError(f"{label} is not a subset of the frozen parent collection: {missing[:5]}")


def reference_validator_signature() -> str:
    return canonical_hash(
        {
            "validator_version": REFERENCE_VALIDATOR_VERSION,
            "converter21": "4.0.1",
            "music21": "9.9.1",
            "smb_parser": "sheet2play_omr.events.parse_kern",
            "olimpic_normalizer": "Bridge.musicxml_normalizer.normalize_musicxml",
            "expand_repeats": False,
            "skip_grace_notes": True,
            "warnings_are_failures": True,
        }
    )


def olimpic_reference_validator_signature() -> str:
    return canonical_hash(
        {
            "base_signature": reference_validator_signature(),
            "force_source": True,
            "non_fatal_warning_prefixes": OLIMPIC_NON_FATAL_WARNING_PREFIXES,
            "validator_version": 4,
        }
    )


def olimpic_warning_is_fatal(message: str) -> bool:
    return not message.startswith(OLIMPIC_NON_FATAL_WARNING_PREFIXES)


def load_validation_cache(
    path: Path | None, validator_signature: str | None = None
) -> dict[str, Any]:
    expected_signature = validator_signature or reference_validator_signature()
    empty = {
        "schema_version": 1,
        "validator_signature": expected_signature,
        "entries": {},
    }
    if path is None or not path.is_file():
        return empty
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return empty
    if (
        document.get("schema_version") != 1
        or document.get("validator_signature") != expected_signature
        or not isinstance(document.get("entries"), dict)
    ):
        return empty
    return document


def save_validation_cache(path: Path | None, cache: dict[str, Any]) -> None:
    if path is not None:
        write_json_atomic(path, cache)


def cached_result(cache: dict[str, Any], identifier: str, cache_key: str) -> dict[str, Any] | None:
    entry = cache["entries"].get(identifier)
    if (
        isinstance(entry, dict)
        and entry.get("cache_key") == cache_key
        and isinstance(entry.get("valid"), bool)
        and isinstance(entry.get("errors"), list)
    ):
        return entry
    return None


def captured_messages(output: io.StringIO, error: io.StringIO) -> list[str]:
    lines = [line.strip() for line in (output.getvalue() + "\n" + error.getvalue()).splitlines()]
    return [f"parser warning: {line[:240]}" for line in lines if line]


def print_progress(
    collection: str,
    current: int,
    total: int,
    eligible: int,
    excluded: int,
    progress_every: int,
) -> None:
    if progress_every and (current % progress_every == 0 or current == total):
        print(
            f"{collection}: {current}/{total} ({eligible} eligible, {excluded} excluded)",
            flush=True,
        )


def training_overlap_by_candidate(collection: str) -> dict[str, str]:
    unknown = {candidate: "unknown" for candidate in CANDIDATE_KEYS}
    if collection.startswith("smb"):
        unknown["completed_homr_finetune"] = (
            "absent by project policy; SMB is held out from training and checkpoint selection"
        )
    elif collection.startswith("olimpic"):
        unknown["completed_homr_finetune"] = (
            "absent by Phase-1 holdout policy; verify against the final training manifest"
        )
        unknown["zeus"] = (
            "absent from the released OLiMPiC training split; same corpus and repertoire family"
        )
    elif collection == "local-diagnostics":
        unknown = {
            candidate: "unknown; private files are not direct training inputs, repertoire overlap may exist"
            for candidate in CANDIDATE_KEYS
        }
    return unknown


def kern_notation_features(kern_regions: list[str]) -> dict[str, Any]:
    joined = "\n".join(kern_regions)
    reciprocal_values = [
        int(value)
        for value in re.findall(r"(?<![0-9])(\d+)(?=[.A-Ga-grq])", joined)
        if int(value) > 0
    ]
    meters = sorted(set(re.findall(r"\*M(\d+/\d+)", joined)))
    note_tokens = [
        token
        for line in joined.splitlines()
        if line and not line.startswith(("*", "=", "!"))
        for token in line.split("\t")
        if token not in {"", "."} and "r" not in token.casefold()
    ]
    return {
        "annotated_region_count": len(kern_regions),
        "cross_staff": "unknown",
        "has_independent_voices": "*^" in joined,
        "has_meter_changes": len(meters) > 1,
        "has_repeats": "=:" in joined or ":|" in joined or "|:" in joined,
        "has_ties": any(marker in joined for marker in ("[", "_", "]")),
        "has_tuplets": any(value & (value - 1) for value in reciprocal_values),
        "meter_signatures": meters,
        "note_token_count": len(note_tokens),
    }


def musicxml_notation_features(path: Path) -> dict[str, Any]:
    document = path.read_text(encoding="utf-8", errors="replace")
    voices = sorted(set(re.findall(r"<voice>([^<]+)</voice>", document)))
    staves = sorted(set(re.findall(r"<staff>([^<]+)</staff>", document)))
    time_blocks = re.findall(r"<time(?:\s[^>]*)?>.*?</time>", document, flags=re.DOTALL)
    return {
        "cross_staff": "unknown",
        "has_grace_notes": "<grace" in document,
        "has_independent_voices": len(voices) > 1 or "<backup" in document,
        "has_meter_changes": len(set(time_blocks)) > 1,
        "has_octave_shift": "<octave-shift" in document,
        "has_repeats": "<repeat" in document or "<ending" in document,
        "has_ties": "<tie " in document or "<tied " in document,
        "has_tuplets": "<tuplet" in document or "<time-modification" in document,
        "note_count": document.count("<note"),
        "staff_identifiers": staves,
        "voice_identifiers": voices,
    }


def load_smb_image_hashes(path: Path) -> dict[str, dict[str, Any]]:
    document = json.loads(path.read_text(encoding="utf-8"))
    if document.get("revision") != SMB_REVISION:
        raise ValueError(
            f"SMB image hashes use revision {document.get('revision')}; expected {SMB_REVISION}"
        )
    images = document.get("images")
    if not isinstance(images, dict) or len(images) != 685:
        raise ValueError(f"SMB image-hash manifest must contain 685 images; found {len(images or {})}")
    return images


def freeze_smb(
    metadata_path: Path,
    image_hashes_path: Path,
    *,
    collection: str = "smb-pianoform",
    texture: str | None = "pianoform",
    cache_path: Path | None = None,
    progress_every: int = 0,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    source_rows = load_jsonl(metadata_path)
    selected = (
        source_rows
        if texture is None
        else [
            row
            for row in source_rows
            if str(row.get("page_texture", "")).casefold() == texture.casefold()
        ]
    )
    expected_selected = 685 if texture is None else 469
    if len(source_rows) != 685 or len(selected) != expected_selected:
        raise ValueError(
            f"SMB revision {SMB_REVISION} expected 685 total/{expected_selected} selected pages; "
            f"found {len(source_rows)}/{len(selected)}"
        )
    require_unique(selected, "file_name", f"{collection} source metadata")
    image_hashes = load_smb_image_hashes(image_hashes_path)
    cache = load_validation_cache(cache_path)

    frozen: list[dict[str, Any]] = []
    exclusions: list[dict[str, Any]] = []
    ordered = sorted(selected, key=lambda item: str(item["file_name"]))
    for item_index, row in enumerate(ordered, start=1):
        identifier = str(row["file_name"])
        image = image_hashes.get(identifier)
        if not isinstance(image, dict) or not image.get("sha256") or not image.get("size"):
            raise ValueError(f"SMB image hash is missing or invalid: {identifier}")
        regions = row.get("regions")
        if not isinstance(regions, list) or not regions:
            exclusions.append(
                {"collection": collection, "id": identifier, "reason": "no annotated regions"}
            )
            continue
        region_hashes: list[str] = []
        region_fingerprints: list[str | None] = []
        kern_regions: list[tuple[int, str]] = []
        for index, region in enumerate(regions):
            kern = region.get("kern") if isinstance(region, dict) else None
            if not isinstance(kern, str) or not kern.strip():
                region_fingerprints.append(None)
                kern_regions.append((index, ""))
                continue
            region_hash = sha256_bytes(kern.encode("utf-8"))
            region_hashes.append(region_hash)
            region_fingerprints.append(region_hash)
            kern_regions.append((index, kern))
        cache_key = canonical_hash(
            {
                "collection": "smb",
                "id": identifier,
                "image_sha256": str(image["sha256"]),
                "region_sha256": region_fingerprints,
                "validator_signature": reference_validator_signature(),
            }
        )
        result = cached_result(cache, identifier, cache_key)
        if result is None:
            errors: list[str] = []
            for index, kern in kern_regions:
                if not kern:
                    errors.append(f"region {index}: missing kern")
                    continue
                output = io.StringIO()
                error_output = io.StringIO()
                caught_warnings: list[warnings.WarningMessage] = []
                try:
                    with warnings.catch_warnings(record=True) as caught_warnings:
                        warnings.simplefilter("always")
                        with redirect_stdout(output), redirect_stderr(error_output):
                            parse_kern(kern)
                except Exception as error:  # one defective reference must not stop the sweep
                    errors.append(f"region {index}: {type(error).__name__}: {str(error)[:160]}")
                errors.extend(
                    f"region {index}: parser warning: {warning.category.__name__}: "
                    f"{str(warning.message)[:200]}"
                    for warning in caught_warnings
                )
                errors.extend(f"region {index}: {message}" for message in captured_messages(output, error_output))
            result = {"cache_key": cache_key, "valid": not errors, "errors": errors}
            cache["entries"][identifier] = result
            save_validation_cache(cache_path, cache)
        errors = [str(value) for value in result.get("errors", [])]
        if not result["valid"] and not errors:
            errors = ["cached validation result was invalid without diagnostics"]
        if errors:
            exclusions.append(
                {
                    "collection": collection,
                    "id": identifier,
                    "reason": "reference validation failed",
                    "details": errors,
                }
            )
            print_progress(
                collection,
                item_index,
                len(ordered),
                len(frozen),
                len(exclusions),
                progress_every,
            )
            continue
        frozen.append(
            {
                "composition_group": str(row["original_score"]),
                "ground_truth_provenance": "SMB expert-generated **kern regions",
                "id": identifier,
                "image_path": identifier,
                "image_sha256": str(image["sha256"]),
                "image_size": int(image["size"]),
                "notation_features": kern_notation_features(
                    [kern for _, kern in kern_regions if kern]
                ),
                "page_system_identity": {
                    "page": Path(identifier).stem,
                    "systems": [
                        f"{Path(identifier).stem}-region-{index}"
                        for index in range(1, len(kern_regions) + 1)
                    ],
                },
                "page_texture": str(row.get("page_texture", "")),
                "printed_or_scanned": "printed",
                "reference_region_sha256": region_hashes,
                "source_revision": SMB_REVISION,
                "training_overlap": "unknown",
                "training_overlap_by_candidate": training_overlap_by_candidate(collection),
            }
        )
        print_progress(
            collection,
            item_index,
            len(ordered),
            len(frozen),
            len(exclusions),
            progress_every,
        )
    require_unique(frozen, "id", collection)
    return frozen, exclusions


def freeze_olimpic(
    manifest_path: Path,
    collection: str,
    *,
    cache_path: Path | None = None,
    progress_every: int = 0,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    source_rows = load_jsonl(manifest_path)
    require_unique(source_rows, "identifier", f"{collection} source manifest")
    validator_signature = olimpic_reference_validator_signature()
    cache = load_validation_cache(cache_path, validator_signature)
    frozen: list[dict[str, Any]] = []
    exclusions: list[dict[str, Any]] = []
    ordered = sorted(source_rows, key=lambda item: str(item["identifier"]))
    for item_index, row in enumerate(ordered, start=1):
        identifier = str(row["identifier"])
        image = Path(str(row["image"]))
        musicxml = Path(str(row["musicxml"]))
        missing = [label for label, path in (("image", image), ("musicxml", musicxml)) if not path.is_file()]
        if missing:
            exclusions.append(
                {"collection": collection, "id": identifier, "reason": f"missing {', '.join(missing)}"}
            )
            continue
        image_sha256 = sha256_file(image)
        musicxml_sha256 = sha256_file(musicxml)
        cache_key = canonical_hash(
            {
                "collection": "olimpic-test",
                "id": identifier,
                "image_sha256": image_sha256,
                "musicxml_sha256": musicxml_sha256,
                "validator_signature": validator_signature,
            }
        )
        result = cached_result(cache, identifier, cache_key)
        if result is None:
            errors: list[str] = []
            output = io.StringIO()
            error_output = io.StringIO()
            caught_warnings: list[warnings.WarningMessage] = []
            try:
                with warnings.catch_warnings(record=True) as caught_warnings:
                    warnings.simplefilter("always")
                    with redirect_stdout(output), redirect_stderr(error_output):
                        score = normalize_musicxml(
                            musicxml,
                            expand_repeats=False,
                            skip_grace_notes=True,
                            force_source=True,
                        )
                if not score.notes:
                    errors.append("ValueError: normalizer produced no notes")
            except Exception as error:
                errors.append(f"{type(error).__name__}: {str(error)[:160]}")
            warning_messages = [
                f"{warning.category.__name__}: {str(warning.message)[:200]}"
                for warning in caught_warnings
            ]
            errors.extend(
                f"parser warning: {message}"
                for message in warning_messages
                if olimpic_warning_is_fatal(message.split(": ", 1)[-1])
            )
            errors.extend(captured_messages(output, error_output))
            result = {
                "cache_key": cache_key,
                "valid": not errors,
                "errors": errors,
                "warnings": warning_messages,
            }
            cache["entries"][identifier] = result
            save_validation_cache(cache_path, cache)
        errors = [str(value) for value in result.get("errors", [])]
        validation_warnings = [str(value) for value in result.get("warnings", [])]
        if not result["valid"] and not errors:
            errors = ["cached validation result was invalid without diagnostics"]
        if errors:
            exclusions.append(
                {
                    "collection": collection,
                    "id": identifier,
                    "reason": "reference validation failed",
                    "details": errors,
                    "warnings": validation_warnings,
                }
            )
            print_progress(
                collection,
                item_index,
                len(ordered),
                len(frozen),
                len(exclusions),
                progress_every,
            )
            continue
        frozen.append(
            {
                "composition_group": str(row["score_id"]),
                "ground_truth_provenance": "OLiMPiC 1.0 scanned test partition MusicXML",
                "id": identifier,
                "image_path": relative_path(image),
                "image_sha256": image_sha256,
                "musicxml_path": relative_path(musicxml),
                "musicxml_sha256": musicxml_sha256,
                "notation_features": musicxml_notation_features(musicxml),
                "page_system_identity": {
                    "page_system": identifier.rsplit("/", 1)[-1],
                    "score": str(row["score_id"]),
                },
                "printed_or_scanned": "scanned",
                "reference_validation_warnings": validation_warnings,
                "source_revision": OLIMPIC_REVISION,
                "training_overlap": "known overlap with OpenScore Lieder repertoire",
                "training_overlap_by_candidate": training_overlap_by_candidate(collection),
            }
        )
        print_progress(
            collection,
            item_index,
            len(ordered),
            len(frozen),
            len(exclusions),
            progress_every,
        )
    require_unique(frozen, "id", collection)
    return frozen, exclusions


def freeze_local_diagnostics(
    pairs_path: Path, review_path: Path, library_path: Path
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    if not pairs_path.is_file():
        raise ValueError(f"Local diagnostic review is missing: {pairs_path}")
    document = json.loads(pairs_path.read_text(encoding="utf-8"))
    confirmed = [entry for entry in document.get("pairs", []) if entry.get("status") == "confirmed"]
    if len(confirmed) != 7:
        raise ValueError(f"Expected seven confirmed local diagnostic pairs; found {len(confirmed)}")
    require_unique(confirmed, "pdf", "local diagnostic pairs")
    review_document = json.loads(review_path.read_text(encoding="utf-8"))
    reviews = review_document.get("items")
    if not isinstance(reviews, list) or len(reviews) != 7:
        raise ValueError("Local diagnostic review must contain exactly seven items")
    require_unique(reviews, "private_id_sha256", "local diagnostic review")
    reviews_by_id = {str(review["private_id_sha256"]): review for review in reviews}
    items = []
    exclusions: list[dict[str, Any]] = []
    for entry in confirmed:
        pdf_name = str(entry.get("pdf", ""))
        reference_name = str(entry.get("reference", ""))
        why = str(entry.get("why", "")).strip()
        if not pdf_name or not reference_name or not why:
            raise ValueError("Every confirmed local pair requires pdf, reference, and review evidence")
        pdf_path = library_path / "pdf" / f"{pdf_name}.pdf"
        reference_candidates = (library_path / reference_name, HERE / reference_name)
        reference_path = next((path for path in reference_candidates if path.is_file()), None)
        if not pdf_path.is_file():
            raise ValueError(f"Confirmed local PDF is missing: {pdf_name}")
        if reference_path is None:
            raise ValueError(f"Confirmed local reference is missing for: {pdf_name}")
        identity = sha256_bytes(pdf_name.encode("utf-8"))
        review = reviews_by_id.get(identity)
        if review is None:
            raise ValueError(f"Confirmed local pair has no review: {identity}")
        review_fields = ("edition", "page_coverage", "pickup", "repeats", "transcription_alignment", "reason")
        if any(not str(review.get(field, "")).strip() for field in review_fields):
            raise ValueError(f"Local diagnostic review is incomplete: {identity}")
        eligible = bool(review.get("eligible", False))
        pdf_sha256 = sha256_file(pdf_path)
        reference_sha256 = sha256_file(reference_path)
        items.append(
            {
                "composition_group": identity,
                "eligible": eligible,
                "ground_truth_provenance": "user-confirmed local symbolic reference",
                "id": identity,
                "notation_features": {
                    "edition_review": str(review["edition"]),
                    "page_coverage_review": str(review["page_coverage"]),
                    "pickup_review": str(review["pickup"]),
                    "repeat_review": str(review["repeats"]),
                    "transcription_alignment_review": str(review["transcription_alignment"]),
                },
                "page_system_identity": {
                    "document": identity,
                    "page_coverage": str(review["page_coverage"]),
                },
                "printed_or_scanned": "unknown private source",
                "private_id_sha256": identity,
                "pdf_sha256": pdf_sha256,
                "reference_sha256": reference_sha256,
                "review_record_sha256": canonical_hash(entry),
                "phase1_review_sha256": canonical_hash(review),
                "status": "confirmed",
                "source_revision": canonical_hash(
                    {"pdf_sha256": pdf_sha256, "reference_sha256": reference_sha256}
                ),
                "training_overlap_by_candidate": training_overlap_by_candidate(
                    "local-diagnostics"
                ),
            }
        )
        if not eligible:
            exclusions.append(
                {
                    "collection": "local-diagnostics",
                    "id": identity,
                    "reason": str(review["reason"]),
                }
            )
    summary = {
        "available": True,
        "confirmed": len(confirmed),
        "reviewed": len(items),
        "eligible": sum(item["eligible"] for item in items),
        "excluded": len(exclusions),
        "privacy": "names and paths intentionally omitted from tracked output",
        "items": sorted(items, key=lambda item: item["private_id_sha256"]),
    }
    return summary, exclusions


def historical_audit() -> list[dict[str, Any]]:
    return [
        {
            "artifact": "eval_zeus_on_olimpic.py console averages",
            "ranking_eligible": False,
            "reason": "random 20-item sample, per-engine success denominators, asymmetric extraction, and no captured provenance-complete report",
            "retained_as": "exploratory evidence only",
        },
        {
            "artifact": "reports/diagnosis/diagnosis.json",
            "ranking_eligible": False,
            "reason": "identifiable canary inputs and failures, but no immutable checkpoint/environment record and not the frozen Phase-1 scoring protocol",
            "retained_as": "HOMR failure diagnosis only",
        },
        {
            "artifact": "reports/phase3/canary-report.json",
            "ranking_eligible": False,
            "reason": "identifiable manifest and decoder state, but belongs to the removed Transcoda experiment and uses superseded gates",
            "retained_as": "historical regression evidence only",
        },
        {
            "artifact": "reports/*/comparison.json",
            "ranking_eligible": False,
            "reason": "reports do not jointly pin code revision, checkpoint, preprocessing, scorer settings, and common failure denominator",
            "retained_as": "exploratory evidence only",
        },
        {
            "artifact": "reports/library/*.json",
            "ranking_eligible": False,
            "reason": "private diagnostic material is not an untouched evaluation collection and report provenance predates this protocol",
            "retained_as": "application diagnostics only",
        },
    ]


def scoring_protocol() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "primary_metric": "composition-macro pitch+onset+duration F1",
        "recognition_ranking": "accuracy metrics only, independent of hardware suitability",
        "practical_ranking": "accuracy plus resource use, latency, failures, and integration effort",
        "time_unit": "rational quarter-note time",
        "measurement_paths": {
            "reference_round_trip": "known symbolic truth through each native representation and back; no recognition",
            "annotated_crops": "identical ground-truth system regions for compatible system recognizers",
            "complete_document": "same preserved 300-DPI pages through segmentation, recognition, conversion, and stitching",
        },
        "normalization": {
            "merge_tied_continuations": True,
            "preserve_pickups": True,
            "expand_repeats": False,
            "grace_notes_in_primary": False,
            "prediction_alignment": "none for headline results",
        },
        "failure_policy": {
            "same_eligible_items_for_every_engine": True,
            "failed_prediction_primary_f1": 0.0,
            "report_invalid_timeout_and_document_failure_separately": True,
            "omr_ned": "valid-output and failure-penalized summaries reported separately",
            "empty_output_is_failure": True,
            "missing_middle_system_is_document_failure": True,
        },
        "reported_accuracy_metrics": [
            "pitch+onset+duration F1",
            "pitch+onset F1",
            "pitch-only F1",
            "OMR-NED with pinned notation-detail settings",
            "duration confusion matrix for pitch/onset-matched notes",
            "unmatched, missing, and extra note counts",
            "missed-system, invalid-output, timeout, and complete-document failure rates",
            "timeline length error and first divergent measure",
        ],
        "reported_performance_metrics": [
            "median and 95th-percentile processing time",
            "cold-start time",
            "peak RAM and VRAM",
            "actual cloud cost",
        ],
        "duration_classification": {
            "report_confusion_matrix": True,
            "report_majority_baseline": True,
            "report_macro_f1": True,
            "report_balanced_accuracy": True,
            "reject_degenerate_single_class_predictor": True,
        },
        "feature_breakdowns": [
            "independent voices",
            "cross-staff writing",
            "ties",
            "tuplets",
            "meter changes",
            "density",
            "document length",
        ],
        "statistics": {
            "bootstrap_resamples": 10000,
            "bootstrap_group": "composition_group",
            "multiple_testing": "Holm correction across challengers",
            "paired_by_item": True,
        },
        "rendering": {
            "source_dpi": 300,
            "preserve_source_pages": True,
            "engine_internal_scaling_allowed": True,
            "alternative_settings_selected_on_development_only": True,
        },
        "practical_eligibility": {
            "unattended_local_operation_required": True,
            "maximum_peak_vram_fraction": 0.90,
            "maximum_peak_ram_fraction": 0.75,
            "maximum_p95_page_latency_vs_homr": 2.0,
        },
        "evaluation_machinery_fixture_contract": [
            "identical score",
            "omitted note",
            "inserted note",
            "shifted onset",
            "tied versus sustained equivalent",
            "overlapping voices",
            "tuplets",
            "pickup",
            "meter change",
            "repeats",
            "empty output",
            "malformed XML",
            "missing middle system",
            "source MusicXML to app control",
        ],
        "replacement_gate": {
            "minimum_primary_f1_gain": 0.03,
            "maximum_pitch_f1_loss": 0.01,
            "maximum_failure_rate_increase": 0.01,
            "maximum_failure_penalized_omr_ned_increase": 0.01,
            "conversion_or_stitching_corruption_allowed": False,
        },
        "frozen_parser_versions": {
            "converter21": "4.0.1",
            "music21": "9.9.1",
            "musicdiff": "5.2",
        },
        "budget": {
            "cloud_total_usd": 10.0,
            "estimate_from_development_before_full_cloud_run": True,
            "local_gpu_first": True,
        },
    }


def phase1_plan_checklist() -> list[dict[str, Any]]:
    return [
        {"requirement": "historical results audited", "status": "passed"},
        {"requirement": "SMB pianoform and complete SMB frozen", "status": "passed"},
        {"requirement": "OLiMPiC canary and parent test partition frozen", "status": "passed"},
        {"requirement": "seven local pairs reviewed", "status": "passed"},
        {"requirement": "20 open plus 12 generated development examples frozen", "status": "passed"},
        {"requirement": "composition overlap checked", "status": "passed"},
        {"requirement": "references validated before candidate predictions", "status": "passed"},
        {"requirement": "scoring, statistics, failure, resource, and promotion rules frozen", "status": "passed"},
        {"requirement": "source MusicXML to app control", "status": "passed"},
        {"requirement": "candidate inference or adapter work", "status": "not_started_phase_2"},
        {
            "requirement": "adapter-dependent evaluation fixture contract execution",
            "status": "deferred_to_phase_2_adapter_verification",
        },
    ]


def require_collection_partition(
    eligible: list[dict[str, Any]],
    exclusions: list[dict[str, Any]],
    *,
    collection: str,
    expected_total: int,
) -> None:
    require_unique(eligible, "id", collection)
    require_unique(exclusions, "id", f"{collection} exclusions")
    eligible_ids = {str(row["id"]) for row in eligible}
    excluded_ids = {str(row["id"]) for row in exclusions}
    overlap = sorted(eligible_ids & excluded_ids)
    if overlap:
        raise ValueError(f"{collection} has IDs in both eligible and excluded outputs: {overlap[:5]}")
    actual_total = len(eligible) + len(exclusions)
    if actual_total != expected_total:
        raise ValueError(
            f"{collection} expected {expected_total} frozen outcomes; found {actual_total}"
        )


def require_sha256(value: Any, label: str) -> None:
    text = str(value)
    if len(text) != 64 or any(character not in "0123456789abcdef" for character in text):
        raise ValueError(f"{label} is not a lowercase SHA-256 digest")


def require_evaluation_metadata(rows: list[dict[str, Any]], collection: str) -> None:
    for row in rows:
        for field in (
            "composition_group",
            "ground_truth_provenance",
            "page_system_identity",
            "printed_or_scanned",
            "source_revision",
        ):
            if not row.get(field):
                raise ValueError(f"{collection} {row.get('id')} lacks required {field}")
        if not isinstance(row.get("notation_features"), dict) or not row["notation_features"]:
            raise ValueError(f"{collection} {row.get('id')} has no notation-feature record")
        overlap = row.get("training_overlap_by_candidate")
        if not isinstance(overlap, dict) or set(overlap) != set(CANDIDATE_KEYS):
            raise ValueError(
                f"{collection} {row.get('id')} lacks candidate-specific overlap disclosure"
            )
        if any(not str(value).strip() for value in overlap.values()):
            raise ValueError(f"{collection} {row.get('id')} has an empty overlap disclosure")


def collection_output_paths(out: Path, collection: str) -> tuple[Path, Path]:
    return out / f"{collection}.jsonl", out / f"{collection}-exclusions.jsonl"


def write_collection_outputs(
    out: Path,
    collection: str,
    eligible: list[dict[str, Any]],
    exclusions: list[dict[str, Any]],
) -> dict[str, Any]:
    eligible_path, exclusions_path = collection_output_paths(out, collection)
    write_jsonl(eligible_path, eligible)
    write_jsonl(exclusions_path, exclusions)
    return {
        "collection": collection,
        "eligible": len(eligible),
        "excluded": len(exclusions),
        "eligible_path": relative_path(eligible_path),
        "exclusions_path": relative_path(exclusions_path),
    }


def run_reference_collection(args: argparse.Namespace, collection: str) -> dict[str, Any]:
    args.cache_dir.mkdir(parents=True, exist_ok=True)
    if collection in {"smb-pianoform", "smb-complete"}:
        texture = "pianoform" if collection == "smb-pianoform" else None
        eligible, exclusions = freeze_smb(
            args.smb_metadata,
            args.smb_image_hashes,
            collection=collection,
            texture=texture,
            cache_path=args.cache_dir / "smb-reference-cache.json",
            progress_every=25,
        )
        expected_total = 469 if collection == "smb-pianoform" else 685
        require_collection_partition(
            eligible, exclusions, collection=collection, expected_total=expected_total
        )
    elif collection in {"olimpic-full", "olimpic-canary"}:
        manifest = args.olimpic_full if collection == "olimpic-full" else args.olimpic_canary
        eligible, exclusions = freeze_olimpic(
            manifest,
            collection,
            cache_path=args.cache_dir / "olimpic-reference-cache.json",
            progress_every=50,
        )
        expected_total = 1493 if collection == "olimpic-full" else 100
        require_collection_partition(
            eligible, exclusions, collection=collection, expected_total=expected_total
        )
    else:
        raise ValueError(f"Unsupported reference collection: {collection}")
    return write_collection_outputs(args.out, collection, eligible, exclusions)


def run_development_collection(args: argparse.Namespace) -> dict[str, Any]:
    open_rows, controlled_rows = freeze_development(
        args.openscore_pairs,
        args.olimpic_full,
        args.controlled_manifest,
        args.baseline_dir,
        args.development_render_root,
    )
    write_jsonl(args.out / "development-open.jsonl", open_rows)
    write_jsonl(args.out / "development-controlled.jsonl", controlled_rows)
    return {
        "collection": "development",
        "open_compositions": len(open_rows),
        "controlled_examples": len(controlled_rows),
        "composition_overlap_with_evaluation": False,
    }


def load_collection_outputs(
    out: Path, collection: str, expected_total: int
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    eligible_path, exclusions_path = collection_output_paths(out, collection)
    if not eligible_path.is_file() or not exclusions_path.is_file():
        raise ValueError(
            f"{collection} outputs are incomplete; run --collection {collection} first"
        )
    eligible = load_jsonl(eligible_path)
    exclusions = load_jsonl(exclusions_path)
    require_collection_partition(
        eligible, exclusions, collection=collection, expected_total=expected_total
    )
    return eligible, exclusions


def assemble_phase1(args: argparse.Namespace) -> dict[str, Any]:
    smb, smb_exclusions = load_collection_outputs(args.out, "smb-pianoform", 469)
    smb_complete, smb_complete_exclusions = load_collection_outputs(
        args.out, "smb-complete", 685
    )
    olimpic_full, full_exclusions = load_collection_outputs(args.out, "olimpic-full", 1493)
    olimpic_canary, canary_exclusions = load_collection_outputs(
        args.out, "olimpic-canary", 100
    )
    development_open_path = args.out / "development-open.jsonl"
    development_controlled_path = args.out / "development-controlled.jsonl"
    if not development_open_path.is_file() or not development_controlled_path.is_file():
        raise ValueError("development outputs are incomplete; run --collection development first")
    development_open = load_jsonl(development_open_path)
    development_controlled = load_jsonl(development_controlled_path)
    if len(development_open) != 20 or len(development_controlled) != 12:
        raise ValueError(
            "development collection expected 20 open compositions and 12 controlled examples; "
            f"found {len(development_open)} and {len(development_controlled)}"
        )
    require_unique(development_open, "id", "open development collection")
    require_unique(development_controlled, "id", "controlled development collection")
    if any(row.get("composition_overlap_with_evaluation") is not False for row in development_open):
        raise ValueError("open development collection contains unresolved evaluation overlap")
    full_ids = {str(row["id"]) for row in olimpic_full + full_exclusions}
    canary_ids = {str(row["id"]) for row in olimpic_canary + canary_exclusions}
    require_subset(canary_ids, full_ids, "OLiMPiC canary")
    smb_complete_ids = {str(row["id"]) for row in smb_complete + smb_complete_exclusions}
    smb_pianoform_ids = {str(row["id"]) for row in smb + smb_exclusions}
    require_subset(smb_pianoform_ids, smb_complete_ids, "SMB pianoform")
    for collection, rows in (("smb-pianoform", smb), ("smb-complete", smb_complete)):
        require_evaluation_metadata(rows, collection)
        for row in rows:
            require_sha256(row.get("image_sha256"), f"{collection} {row.get('id')} image")
            region_hashes = row.get("reference_region_sha256")
            if not isinstance(region_hashes, list) or not region_hashes:
                raise ValueError(f"{collection} {row.get('id')} has no reference-region hashes")
            for index, digest in enumerate(region_hashes):
                require_sha256(digest, f"{collection} {row.get('id')} region {index}")
    for collection, rows in (
        ("olimpic-full", olimpic_full),
        ("olimpic-canary", olimpic_canary),
    ):
        require_evaluation_metadata(rows, collection)
        for row in rows:
            require_sha256(row.get("image_sha256"), f"{collection} {row.get('id')} image")
            require_sha256(row.get("musicxml_sha256"), f"{collection} {row.get('id')} MusicXML")

    local, local_exclusions = freeze_local_diagnostics(
        args.library_pairs, args.local_review, args.library
    )
    require_evaluation_metadata(local["items"], "local-diagnostics")
    exclusions = (
        smb_exclusions
        + smb_complete_exclusions
        + full_exclusions
        + canary_exclusions
        + local_exclusions
    )
    protocol = scoring_protocol()
    audit = historical_audit()
    checklist = phase1_plan_checklist()
    write_jsonl(args.out / "exclusions.jsonl", exclusions)
    write_json(args.out / "scoring-protocol.json", protocol)
    write_json(args.out / "historical-audit.json", audit)
    write_json(args.out / "local-diagnostics.json", local)
    write_json(args.out / "phase1-plan-checklist.json", checklist)

    report = {
        "schema_version": 1,
        "phase": 1,
        "phase_2_started": False,
        "status": "passed",
        "reference_validator": {
            "cache_schema_version": 1,
            "signatures": {
                "smb": reference_validator_signature(),
                "olimpic": olimpic_reference_validator_signature(),
            },
            "musicxml_force_source": True,
            "warning_policy": "unknown or note-event-affecting warnings fail; explicitly allowlisted notation-spanner warnings are recorded",
        },
        "historical_ranking_eligible": sum(item["ranking_eligible"] for item in audit),
        "collections": {
            "smb_pianoform": {"eligible": len(smb), "excluded": len(smb_exclusions)},
            "smb_complete": {
                "eligible": len(smb_complete),
                "excluded": len(smb_complete_exclusions),
            },
            "olimpic_full": {"eligible": len(olimpic_full), "excluded": len(full_exclusions)},
            "olimpic_canary": {
                "eligible": len(olimpic_canary),
                "excluded": len(canary_exclusions),
            },
            "local_diagnostics": {"eligible": local["eligible"], "excluded": local["excluded"]},
            "development": {
                "open_compositions": len(development_open),
                "controlled_examples": len(development_controlled),
                "ranking_eligible": False,
            },
        },
        "invariants": {
            "all_reference_inputs_hashed": True,
            "canary_is_full_partition_subset": True,
            "smb_pianoform_is_complete_collection_subset": True,
            "completed_outcome_count_matches_source": True,
            "eligible_and_excluded_ids_are_disjoint": True,
            "development_composition_overlap_with_evaluation": False,
            "candidate_specific_training_overlap_disclosed": True,
            "notation_features_recorded": True,
            "source_musicxml_to_app_control_tested": True,
        },
        "limitations": [
            "SMB training overlap is unknown and must not be described as unseen.",
            "OLiMPiC overlaps OpenScore Lieder repertoire and is a regression collection, not independent generalization evidence.",
            "Local diagnostics are already-inspected private material, not an untouched test set.",
        ],
        "scope_boundary": {
            "phase_1_complete": True,
            "phase_2_started": False,
            "deferred": [
                "candidate adapters",
                "candidate inference",
                "adapter-dependent evaluation fixture execution",
            ],
        },
        "artifact_sha256": {},
    }
    for name in (
        "smb-pianoform.jsonl",
        "smb-pianoform-exclusions.jsonl",
        "smb-complete.jsonl",
        "smb-complete-exclusions.jsonl",
        "olimpic-full.jsonl",
        "olimpic-full-exclusions.jsonl",
        "olimpic-canary.jsonl",
        "olimpic-canary-exclusions.jsonl",
        "development-open.jsonl",
        "development-controlled.jsonl",
        "exclusions.jsonl",
        "scoring-protocol.json",
        "historical-audit.json",
        "local-diagnostics.json",
        "phase1-plan-checklist.json",
    ):
        report["artifact_sha256"][name] = sha256_file(args.out / name)
    write_json(args.out / "phase1-report.json", report)
    return report


def parse_arguments(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=HERE / "reports" / "phase1")
    parser.add_argument(
        "--collection",
        choices=(
            "all",
            "smb-pianoform",
            "smb-complete",
            "olimpic-full",
            "olimpic-canary",
            "development",
            "assemble",
        ),
        default="all",
        help="Run one resumable reference collection or assemble completed outputs.",
    )
    parser.add_argument("--cache-dir", type=Path, default=HERE / ".runtime" / "phase1")
    parser.add_argument("--smb-metadata", type=Path, default=HERE / "data" / "smb" / "metadata.jsonl")
    parser.add_argument(
        "--smb-image-hashes",
        type=Path,
        default=HERE / "data" / "smb" / "smb-image-hashes.json",
    )
    parser.add_argument(
        "--olimpic-full",
        type=Path,
        default=HERE / "reports" / "phase3" / "olimpic-scanned-test.jsonl",
    )
    parser.add_argument(
        "--olimpic-canary",
        type=Path,
        default=HERE / "reports" / "phase3" / "olimpic-scanned-canary.jsonl",
    )
    parser.add_argument(
        "--library-pairs", type=Path, default=HERE / "reports" / "library" / "pairs.json"
    )
    parser.add_argument(
        "--openscore-pairs",
        type=Path,
        default=HERE / "data" / "openscore" / "lieder" / "pairs.jsonl",
    )
    parser.add_argument(
        "--controlled-manifest",
        type=Path,
        default=HERE / "data" / "polyrhythm" / "manifest.jsonl",
    )
    parser.add_argument(
        "--baseline-dir",
        type=Path,
        default=HERE / "tests" / "fixtures" / "transcoda-baseline",
    )
    parser.add_argument(
        "--development-render-root",
        type=Path,
        default=HERE / "data" / "phase1-development" / "open",
    )
    parser.add_argument(
        "--local-review", type=Path, default=HERE / "local-diagnostic-review.json"
    )
    parser.add_argument(
        "--library",
        type=Path,
        default=Path.home() / "AppData" / "Local" / "Sheet2Play" / "songs",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_arguments(argv)
    try:
        if args.collection == "all":
            collection_results = [
                run_reference_collection(args, collection)
                for collection in (
                    "smb-pianoform",
                    "smb-complete",
                    "olimpic-full",
                    "olimpic-canary",
                )
            ]
            collection_results.append(run_development_collection(args))
            report = assemble_phase1(args)
            result: dict[str, Any] = {"collections": collection_results, "report": report}
        elif args.collection == "assemble":
            result = assemble_phase1(args)
        elif args.collection == "development":
            result = run_development_collection(args)
        else:
            result = run_reference_collection(args, args.collection)
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as error:
        print(json.dumps({"status": "failed", "phase": 1, "error": str(error)}), file=sys.stderr)
        return 2

    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
