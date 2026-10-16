"""Score a complete screened candidate with the unchanged Phase-1 scorer."""
from __future__ import annotations

import argparse
import contextlib
import json
import os
from pathlib import Path
import statistics
import subprocess
import sys
import time
import uuid
from typing import Any

import psutil

from screening_common import (HERE, POLICY, RUNNABLE, WORKSPACE, completed_path, digest,
                              output_root, read_json, rename_directory_with_retry,
                              
                              result_identity, scored_path, verify_completed,
                              write_new)
from screening_cpu_manifest import require_current_policy, verify_manifest
from screening_cpu_run import acquire_lock, close_session, release_lock, session_budget, stop_tree
RUNNABLE = ("audiveris_page", "zeus_page")

from screening_stage1_development import pressure_expired
from screening_stage1_preflight import resource_sample
from sheet2play_omr.adapter_contract import sha256_file
from sheet2play_omr.phase3_scoring import score_result


LEGACY_SCORE_RUNNER_SHA256 = "b9fcfaf358787aa45932e309db2269c899bfab51d5c1fc59a488c4d90028f6b5"
PRESERVED_SHIPPED_SCORE_RUNNER_SHA256 = "8b9016261e673799e125e46bc1c6e7093b82aa858a843e6b5430c851aabaeca2"


def score_identity(manifest: dict[str, Any], candidate: str, item: dict[str, Any],
                   result_path: Path) -> dict[str, Any]:
    return {"sample_sha256": manifest["sample_sha256"],
            "configuration_sha256": manifest["candidates"][candidate]["identity_sha256"],
            "item_id": item["id"], "result_sha256": sha256_file(result_path),
            "reference_sha256": item["reference_sha256"],
            "scorer_sha256": manifest["scorer_sha256"],
            "runner_sha256": sha256_file(Path(__file__))}


def compatible_score_identity(expected: dict[str, Any], saved: dict[str, Any]) -> bool:
    if saved == expected:
        return True
    return (saved.get("runner_sha256") in {
                LEGACY_SCORE_RUNNER_SHA256, PRESERVED_SHIPPED_SCORE_RUNNER_SHA256} and
            {**saved, "runner_sha256": expected["runner_sha256"]} == expected)


def verify_score(path: Path, identity: dict[str, Any]) -> dict[str, Any]:
    if set(p.name for p in path.iterdir()) != {"score.json", "identity.json", "score-sha256.json"}:
        raise ValueError(f"Incomplete score directory: {path}")
    if not compatible_score_identity(identity, read_json(path / "identity.json")):
        raise ValueError(f"Score identity differs: {path}")
    if read_json(path / "score-sha256.json") != {"sha256": sha256_file(path / "score.json")}:
        raise ValueError(f"Score bytes differ: {path}")
    score = read_json(path / "score.json")
    if score["item_id"] != identity["item_id"] or score["status"] not in {"succeeded", "failed"}:
        raise ValueError(f"Score item/status differs: {path}")
    return score


def commit_score(path: Path, identity: dict[str, Any], score: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.parent / f".{path.name}.{uuid.uuid4().hex}.tmp"
    temporary.mkdir()
    try:
        write_new(temporary / "score.json", score)
        write_new(temporary / "identity.json", identity)
        write_new(temporary / "score-sha256.json",
                  {"sha256": sha256_file(temporary / "score.json")})
        if path.exists():
            raise FileExistsError(f"Score already completed: {path}")
        rename_directory_with_retry(temporary, path)
        verify_score(path, identity)
    finally:
        if temporary.exists():
            for entry in temporary.iterdir():
                entry.unlink()
            temporary.rmdir()


def require_complete_results(root: Path, manifest: dict[str, Any], candidate: str) -> None:
    for index, item in enumerate(manifest["items"], 1):
        identity = result_identity(manifest, candidate, item)
        path = completed_path(root, candidate, item["id"],
                              manifest["candidates"][candidate]["identity_sha256"])
        if not path.is_dir():
            raise RuntimeError(f"Screening result pending at {index}/{len(manifest['items'])}: {item['id']}")
        verify_completed(path, identity)


def score_worker(manifest_path: Path, candidate: str, index: int, attempt: Path) -> None:
    manifest = verify_manifest(manifest_path)
    require_current_policy(manifest)
    item = manifest["items"][index]
    root = output_root(manifest_path)
    result_path = completed_path(root, candidate, item["id"],
                                 manifest["candidates"][candidate]["identity_sha256"])
    result = verify_completed(result_path, result_identity(manifest, candidate, item))
    reference_path = WORKSPACE / item["reference_path"]
    if sha256_file(reference_path) != item["reference_sha256"]:
        raise ValueError("Selected reference changed")
    reference = read_json(reference_path)
    score = score_result(result, reference, WORKSPACE)
    score["timing_source"] = result["provenance"].get("timing_source", "unknown")
    write_new(attempt / "staged-score.json", score)


def run_score_worker(manifest_path: Path, candidate: str, index: int,
                     attempt: Path, deadline: float) -> dict[str, Any]:
    attempt.mkdir(parents=True, exist_ok=True)
    command = [sys.executable, str(Path(__file__).resolve()), "--manifest", str(manifest_path),
               "--candidate", candidate, "--worker-index", str(index), "--attempt", str(attempt)]
    write_new(attempt / "job.json", {"command": command, "working_directory": str(WORKSPACE),
                                     "status": "pending"})
    started, since = time.monotonic(), None
    reason = None
    with (attempt / "worker.stdout.log").open("x") as stdout, \
            (attempt / "worker.stderr.log").open("x") as stderr:
        process = subprocess.Popen(command, cwd=WORKSPACE, stdin=subprocess.DEVNULL,
                                   stdout=stdout, stderr=stderr,
                                   creationflags=subprocess.CREATE_NO_WINDOW | subprocess.BELOW_NORMAL_PRIORITY_CLASS)
        root = psutil.Process(process.pid)
        root.cpu_affinity(root.cpu_affinity()[:max(1, (os.cpu_count() or 1) // 2)])
        write_new(attempt / "process.json", {"pid": root.pid, "creation_time": root.create_time(),
                                              "executable": root.exe(), "command": command})
        try:
            with (attempt / "resources.jsonl").open("x") as stream:
                while True:
                    sample = resource_sample()
                    stream.write(json.dumps(sample) + "\n")
                    stream.flush()
                    now = time.monotonic()
                    since, expired = pressure_expired(now, since, bool(sample["admission_blockers"]))
                    if expired or now >= deadline - POLICY["shutdown_reserve_seconds"]:
                        reason = "resource_interruption" if expired else "session_limit"
                        stop_tree(root)
                        break
                    if process.poll() is not None:
                        break
                    time.sleep(POLICY["sample_seconds"])
            process.wait(timeout=10)
        finally:
            if process.poll() is None:
                stop_tree(root)
    outcome = {"status": "pending", "reason": reason, "exit_code": process.returncode,
               "elapsed_seconds": time.monotonic() - started}
    write_new(attempt / "outcome.json", outcome)
    return outcome


def summary(root: Path, manifest: dict[str, Any], candidate: str,
            scores: list[dict[str, Any]]) -> Path:
    from phase3_score import _summary
    lookup = {item["id"]: item for item in manifest["items"]}
    training = {candidate: sorted({item["training_overlap_by_candidate"].get(
        "shipped_homr" if candidate == "homr_page" else
        "audiveris" if candidate == "audiveris_page" else
        "zeus" if candidate == "zeus_page" else candidate, "unknown")
        for item in manifest["items"]})}
    result = _summary(scores, lookup, {"training_overlap": training}, candidate)
    complete_times = [row["elapsed_seconds"] for row in scores
                      if row.get("timing_source") == "screening_complete_path"]
    from phase3_score import _percentile
    result["latency_seconds"] = {"median": statistics.median(complete_times)
                                 if complete_times else None,
                                 "p95": _percentile(complete_times, 0.95),
                                 "includes_failures": True,
                                 "comparable_page_count": len(complete_times),
                                 "excluded_noncomparable_page_count": len(scores) - len(complete_times)}
    result.update(scope=f"bounded_{len(manifest['items'])}_page_screen_descriptive",
                  sample_sha256=manifest["sample_sha256"],
                  configuration_sha256=manifest["candidates"][candidate]["identity_sha256"],
                  scorer_sha256=manifest["scorer_sha256"],
                  item_score_sha256={item["id"]: sha256_file(scored_path(
                      root, candidate, item["id"],
                      manifest["candidates"][candidate]["identity_sha256"],
                      manifest["scorer_sha256"]) / "score.json")
                      for item in manifest["items"]})
    path = (root / "summaries" / candidate /
            manifest["candidates"][candidate]["identity_sha256"][:12] /
            f"summary-{digest(result)[:12]}.json")
    if path.exists():
        if read_json(path) != result:
            raise ValueError(f"Existing summary differs: {path}")
    else:
        write_new(path, result)
    return path


def score(manifest_path: Path, candidate: str, session_id: str,
          retry_pending: bool, recover_stale_lock: bool) -> Path:
    if candidate not in RUNNABLE:
        raise ValueError("Candidate cannot be scored")
    manifest = verify_manifest(manifest_path)
    require_current_policy(manifest)
    root = output_root(manifest_path)
    lock = acquire_lock(root, recover_stale_lock)
    session_path, started = None, time.monotonic()
    try:
        require_complete_results(root, manifest, candidate)
        session_path, deadline = session_budget(root, session_id)
        rows = []
        for index, item in enumerate(manifest["items"]):
            config_sha256 = manifest["candidates"][candidate]["identity_sha256"]
            result_path = completed_path(root, candidate, item["id"], config_sha256)
            identity = score_identity(manifest, candidate, item, result_path / "result.json")
            path = scored_path(root, candidate, item["id"], config_sha256,
                               manifest["scorer_sha256"])
            if path.is_dir():
                rows.append(verify_score(path, identity))
                continue
            attempt_parent = (root / "score-attempts" / candidate / config_sha256[:12] /
                              manifest["scorer_sha256"][:12] / digest(item["id"])[:20])
            attempts = sorted(attempt_parent.glob("attempt-*"))
            staged = []
            for prior in attempts:
                if not (prior / "staged-score.json").is_file():
                    continue
                outcome_file = prior / "outcome.json"
                outcome = read_json(outcome_file) if outcome_file.is_file() else None
                if outcome is None or (outcome.get("reason") is None and outcome.get("exit_code") == 0):
                    staged.append(prior)
            if staged:
                if len(staged) != 1 or not compatible_score_identity(
                        identity, read_json(staged[0] / "identity.json")):
                    raise ValueError("Ambiguous or changed staged score")
                staged_identity = read_json(staged[0] / "identity.json")
                commit_score(path, staged_identity, read_json(staged[0] / "staged-score.json"))
            else:
                if attempts and not retry_pending:
                    raise RuntimeError(f"Pending score needs --retry-pending: {item['id']}")
                if resource_sample()["admission_blockers"] or time.monotonic() >= deadline - POLICY["shutdown_reserve_seconds"]:
                    raise RuntimeError(f"Scoring admission blocked; item remains pending: {item['id']}")
                attempt = attempt_parent / f"attempt-{uuid.uuid4().hex}"
                attempt.parent.mkdir(parents=True, exist_ok=True)
                attempt.mkdir()
                write_new(attempt / "identity.json", identity)
                # The worker writes only to this empty attempt; the parent commits after verification.
                outcome = run_score_worker(manifest_path, candidate, index, attempt, deadline)
                if outcome["reason"] or outcome["exit_code"] != 0:
                    raise RuntimeError(f"Score attempt remains pending: {attempt}")
                staged_score = attempt / "staged-score.json"
                if not staged_score.is_file():
                    raise RuntimeError(f"Score worker exited without a result: {attempt}")
                commit_score(path, identity, read_json(staged_score))
            rows.append(verify_score(path, identity))
        return summary(root, manifest, candidate, rows)
    finally:
        if session_path is not None:
            close_session(session_path, started)
        release_lock(lock)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--candidate", choices=RUNNABLE, required=True)
    parser.add_argument("--session-id")
    parser.add_argument("--retry-pending", action="store_true")
    parser.add_argument("--recover-stale-lock", action="store_true")
    parser.add_argument("--worker-index", type=int, help=argparse.SUPPRESS)
    parser.add_argument("--attempt", type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.worker_index is not None:
        if args.attempt is None:
            raise ValueError("Score worker attempt is required")
        score_worker(args.manifest.resolve(), args.candidate, args.worker_index, args.attempt.resolve())
    else:
        if args.session_id is None:
            raise ValueError("A session ID is required for scoring")
        path = score(args.manifest.resolve(), args.candidate, args.session_id,
                     args.retry_pending, args.recover_stale_lock)
        print(json.dumps({"summary": str(path), "sha256": sha256_file(path)}))


if __name__ == "__main__":
    main()
