"""Verify complete Phase 2 provenance, preserved assets and conservative budget."""
from __future__ import annotations

from collections import Counter, defaultdict
import importlib.metadata
import json
from pathlib import Path
import statistics
import sys

from homr_465_analyze import checked_receipt, converted_notes
from homr_465_common import write_new
from homr_465_compatibility import checked_source
from homr_465_prepare import EVIDENCE, HERE, WORKSPACE, artifact
from screening_homr_compatibility import digest, sha256_file
from screening_homr_statistics import paired_statistics
from screening_report import holm_adjust
from sheet2play_omr.corrected_scoring import metric_notes
from sheet2play_omr.zeus_trace import metric_summary


def read(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def record_scoring_environment() -> None:
    import musicxml_normalizer
    import numpy
    record = {"python": artifact(Path(sys.executable)), "python_version": sys.version,
              "python_prefix": sys.prefix, "numpy_version": importlib.metadata.version("numpy"),
              "numpy_origin": str(Path(numpy.__file__).resolve()),
              "normalizer": artifact(Path(musicxml_normalizer.__file__)),
              "analysis": artifact(HERE / "homr_465_analyze.py"),
              "scope": "Recorded before first 59-page score computation; capture runtime is separately pinned"}
    write_new(EVIDENCE / "scoring-environment.json", record)


def verify_artifacts(rows: list[dict]) -> int:
    for row in rows:
        if sha256_file(Path(row["path"])) != row["sha256"]:
            raise ValueError("Artifact drift: " + row["path"])
    return len(rows)


def profiles() -> dict:
    result = {}
    for name in ("candidate", "control"):
        config = read(EVIDENCE / (name + "-configuration.json"))
        identity = config.pop("identity_sha256")
        if digest(config) != identity:
            raise ValueError("Profile identity drift")
        config["identity_sha256"] = identity
        verify_artifacts(config["source_files"] + list(config["models"].values()) +
                         [config["segnet"], config["python"], config["capture_script"]])
        if "contract" in config:
            verify_artifacts([config["contract"]])
            checked_source(Path(config["source"]), read(EVIDENCE / "acquisition.json"))
        package_root = Path(config["python"]["path"]).parent.parent / "Lib/site-packages"
        versions = {distribution.metadata["Name"].lower().replace("_", "-"): distribution.version
                    for distribution in importlib.metadata.distributions(path=[str(package_root)])}
        for package, version in config["package_versions"].items():
            if versions.get(package.lower().replace("_", "-")) != version:
                raise ValueError("Shared runtime version drift: " + package)
        result[name] = config
    return result


def network() -> dict:
    budget = read(EVIDENCE / "network-budget.json")
    cap = budget["cap_bytes"]
    if cap != 3_000_000_000 or budget["reserved_bytes"] > cap:
        raise ValueError("Network cap violated")
    charged = sum(row.get("charged_payload_upper_bound", row["received_bytes"])
                  for row in budget["requests"])
    if charged > budget["reserved_bytes"]:
        raise ValueError("Network reservations do not contain charged payload")
    complete = sum(row["received_bytes"] for row in budget["requests"] if row["status"] == "complete")
    partial = sum(path.stat().st_size for path in (HERE / ".runtime/homr-465-upstream/download").glob("*.failed.zip"))
    gate = EVIDENCE / "gate/blocked-actions.jsonl"
    return {"cap_bytes": cap, "reserved_bytes": budget["reserved_bytes"],
            "complete_download_payload_bytes": complete, "retained_partial_bytes": partial,
            "retained_payload_bytes": complete + partial, "charged_payload_upper_bound_bytes": charged,
            "blocked_offline_actions": len(gate.read_text().splitlines()) if gate.exists() else 0,
            "scope": "Task-controlled transfers plus conservative protocol/control reservations; unrelated host traffic unavailable"}


def reproduce_score(root: Path, row: dict, receipt: dict, score: dict) -> None:
    verify_artifacts([row["reference"]])
    reference = read(Path(row["reference"]["path"]))
    if reference["item_id"] != row["original_item_id"] or reference["image_sha256"] != row["image"]["sha256"]:
        raise ValueError("Reference correspondence drift")
    if sha256_file(WORKSPACE / reference["reference_musicxml"]) != reference["reference_musicxml_sha256"]:
        raise ValueError("Reference MusicXML drift")
    notes, status, error = converted_notes(root, receipt["status"])
    metrics = metric_summary(notes, metric_notes(reference))
    if status != "complete":
        for name in ("pitch_f1", "onset_f1", "onset_duration_f1"):
            metrics[name] = 0.0
    if metrics != score["metrics"] or status != score["status"] or error != score["conversion_error"]:
        raise ValueError("Recomputed score differs: " + row["item_id"])
    timed = read(root / "timed-events.json")
    events = [{"pitch": n.pitch, "onset": str(n.onset), "duration": str(n.duration),
               "staff": n.staff, "voice": n.voice} for n in notes]
    if timed["production_normalized_events"] != events:
        raise ValueError("Recomputed timed events differ")


def native_provenance(root: Path, receipt: dict, config: dict, inputs_path: Path, name: str) -> None:
    if (receipt["configuration_sha256"] != sha256_file(EVIDENCE / (name + "-configuration.json")) or
            receipt["inputs_sha256"] != sha256_file(inputs_path) or
            Path(receipt["python_executable"]) != Path(config["python"]["path"])):
        raise ValueError("Native capture configuration/interpreter drift")
    sources = {Path(row["path"]) for row in config["source_files"]}
    origins = [receipt["homr_origin"]] + list(receipt.get("module_origins", {}).values())
    if any(Path(origin) not in sources for origin in origins):
        raise ValueError("Native imported origin is outside the pinned source inventory")
    sessions = read(root / "tokens.json")["sessions"]
    expected_models = {Path(row["path"]) for row in list(config["models"].values()) + [config["segnet"]]}
    if {Path(session["model"]) for session in sessions} != expected_models:
        raise ValueError("Native model selection differs from the profile")
    for session in sessions:
        if (session["providers"][0] != config["provider"] or
                session["intra_op_threads"] != 8 or session["inter_op_threads"] != 1):
            raise ValueError("Native provider/thread evidence differs from the profile")


def reproduce_statistics(report: dict, freeze: dict) -> None:
    for result in report["outputs"].values():
        groups = defaultdict(list)
        for row in result["scores"]:
            groups[row["composition_group"]].append(row)
        for metric in ("pitch_f1", "onset_f1", "onset_duration_f1"):
            macro = statistics.mean(statistics.mean(row[metric] for row in group) for group in groups.values())
            if macro != result["summary"][metric]:
                raise ValueError("Recomputed composition macro differs")
    paired = paired_statistics(report["outputs"]["candidate"]["scores"], report["outputs"]["control"]["scores"],
                               freeze["statistics"]["bootstrap_seed"])
    paired["holm_adjusted_p"] = holm_adjust({"465_over_shipped": paired["one_sided_superiority_p"]})["465_over_shipped"]
    if paired != report["paired"]:
        raise ValueError("Recomputed bootstrap/label-swap statistics differ")


def resumption_and_runtime(rows: list[dict]) -> dict:
    admission = read(EVIDENCE / "resumption-admission-20261008.json")
    verify_artifacts([admission["failed_supervisor"]])
    original = EVIDENCE / "comparison/control" / admission["interrupted_item"]
    preserved = Path(admission["preservation_destination"])
    archived = [{**row, "path": str(preserved / Path(row["path"]).relative_to(original))}
                for row in admission["partial_capture_artifacts"]]
    verify_artifacts(archived)
    cutoff = admission["utc"]
    cohorts = defaultdict(lambda: {"pairs": 0, "successful_pairs": 0,
                                   "candidate_seconds": [], "control_seconds": []})
    for row in rows:
        profiles_for_item = {}
        for name in ("candidate", "control"):
            suffix = "-resume-20261008" if name == "control" and row["item_id"] == admission["interrupted_item"] else ""
            job = read(EVIDENCE / "jobs" / ("comparison-" + name + "-" + row["item_id"] + suffix) / "result.json")
            receipt = read(EVIDENCE / "comparison" / name / row["item_id"] / "result.json")
            if job["status"] == "blocked" or job["stop_reason"] is not None:
                raise ValueError("A final comparison capture has a supervisor stop")
            cohort = "after_ram_upgrade" if job["initial"]["utc"] >= cutoff else "before_ram_upgrade"
            profiles_for_item[name] = (cohort, receipt)
        key = profiles_for_item["candidate"][0] if profiles_for_item["candidate"][0] == profiles_for_item["control"][0] else "cross_transition"
        cohorts[key]["pairs"] += 1
        if all(receipt["status"] == "complete" for _, receipt in profiles_for_item.values()):
            cohorts[key]["successful_pairs"] += 1
            for name, (_, receipt) in profiles_for_item.items():
                cohorts[key][name + "_seconds"].append(receipt["elapsed_seconds"])
    summary = {}
    for key, value in cohorts.items():
        summary[key] = {name: value[name] for name in ("pairs", "successful_pairs")}
        for name in ("candidate", "control"):
            times = value[name + "_seconds"]
            summary[key][name + "_mean_seconds"] = statistics.mean(times) if times else None
            summary[key][name + "_median_seconds"] = statistics.median(times) if times else None
    return {"preserved_interrupted_artifacts_verified": len(archived),
            "post_upgrade_physical_total_bytes": admission["physical_total_bytes"],
            "cohorts": summary,
            "interpretation": "Descriptive native capture times for successful pairs; cross-transition pair excluded from matched performance claims; no causal RAM speedup claim"}


def audit() -> None:
    configs = profiles()
    acquisition = read(EVIDENCE / "acquisition.json")
    downloads = HERE / ".runtime/homr-465-upstream/download"
    archive_artifacts = [{"path": str(downloads / row["name"]), "sha256": row["sha256"]}
                         for row in acquisition["archives"].values()]
    archive_artifacts.append({"path": str(downloads / (acquisition["source_revision"] + ".zip")),
                              "sha256": acquisition["source_archive"]["sha256"]})
    archive_count = verify_artifacts(archive_artifacts)
    protected = verify_artifacts(read(EVIDENCE / "protected-artifacts.json"))
    scoring = read(EVIDENCE / "scoring-environment.json")
    verify_artifacts([scoring[key] for key in ("python", "normalizer", "analysis")])
    compared = read(EVIDENCE / "comparison-report.json")
    freeze = read(EVIDENCE / "comparison-freeze.json")
    identity = freeze.pop("identity_sha256")
    if digest(freeze) != identity or identity != compared["comparison_identity"]:
        raise ValueError("Comparison identity drift")
    declarations = [value for value in freeze.values() if isinstance(value, dict) and "path" in value and "sha256" in value]
    verify_artifacts(declarations + freeze["additional_scoring_sources"])
    receipts, artifact_count, gpu_peak = [], 0, 0
    development_inputs = read(EVIDENCE / "development-inputs.json")
    comparison_inputs = read(EVIDENCE / "comparison-inputs.json")
    if len(development_inputs) != 32 or len(comparison_inputs) != 59:
        raise ValueError("Input count drift")
    for mode, rows, names in (("development", development_inputs, ("candidate",)),
                              ("comparison", comparison_inputs, ("candidate", "control"))):
        for name in names:
            scores = compared["outputs"][name]["scores"] if mode == "comparison" else []
            by_item = {score["item_id"]: score for score in scores}
            if mode == "comparison" and (len(by_item) != 59 or len({row["composition_group"] for row in rows}) != 18):
                raise ValueError("Comparison page/group count drift")
            for row in rows:
                root = EVIDENCE / mode / name / row["item_id"] if mode == "comparison" else EVIDENCE / mode / row["item_id"]
                receipt = checked_receipt(root, row, configs[name])
                if receipt is None or receipt["status"] == "resource_stopped":
                    raise ValueError("Missing/resource-stopped receipt")
                verify_artifacts([row["image"]])
                native_provenance(root, receipt, configs[name], EVIDENCE / (mode + "-inputs.json"), name)
                artifact_count += len(receipt["artifacts"])
                receipts.append(receipt)
                if mode == "comparison":
                    score = read(root / "score.json")
                    if score != by_item[row["item_id"]]:
                        raise ValueError("Report/individual score mismatch")
                    reproduce_score(root, row, receipt, score)
                if not (root / "timed-events.json").exists():
                    raise ValueError("Timed-event evidence missing")
                for line in (root / "gpu-resources.jsonl").read_text().splitlines():
                    sample = json.loads(line)
                    if sample["used_mib"] >= sample["total_mib"] * 0.9:
                        raise ValueError("GPU pressure stop was crossed")
                    gpu_peak = max(gpu_peak, sample["used_mib"])
    reproduce_statistics(compared, freeze)
    jobs = [read(path) for path in (EVIDENCE / "jobs").glob("*/result.json")]
    source_files = sorted(HERE.glob("homr_465_*.py")) + [HERE / "run-homr-465-phase2.ps1"]
    report = {"status": "verified", "comparison_identity": identity, "native_receipts": len(receipts),
              "native_statuses": dict(Counter(row["status"] for row in receipts)),
              "declared_capture_artifacts_verified": artifact_count, "protected_assets_verified": protected,
              "acquisition_archives_verified": archive_count,
              "recomputed_scores": 118, "composition_macro_and_paired_statistics_reproduced": True,
              "gpu_peak_mib": gpu_peak,
              "peak_system_ram_percent": max(job.get("peak_physical_percent", 0) for job in jobs),
              "peak_system_commit_percent": max(job.get("peak_commit_percent", 0) for job in jobs),
              "job_statuses": dict(Counter(job["status"] for job in jobs)), "network": network(),
              "resumption_and_runtime": resumption_and_runtime(comparison_inputs),
              "research_sources": [{"path": str(path), "sha256": sha256_file(path)} for path in source_files],
              "report_sha256": sha256_file(EVIDENCE / "comparison-report.json"),
              "scoring_environment_sha256": sha256_file(EVIDENCE / "scoring-environment.json"),
              "reproduction_python": sys.executable, "reproduction_numpy_version": importlib.metadata.version("numpy"),
              "source_identity_note": "Current download helper includes the diagnosed journal fix; earlier failed receipts are preserved"}
    write_new(EVIDENCE / "audit.json", report)
    print(json.dumps({key: report[key] for key in ("status", "native_receipts", "native_statuses", "declared_capture_artifacts_verified", "protected_assets_verified", "gpu_peak_mib", "network")}))


if __name__ == "__main__":
    audit()
