"""Capture shipped native-page intermediates without altering installed sources."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import threading
import time
import traceback


def sha256(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def gpu_sample() -> dict:
    result = subprocess.run(["nvidia-smi", "--query-gpu=memory.total,memory.used",
                             "--format=csv,noheader,nounits"], capture_output=True,
                            text=True, timeout=10, check=True)
    lines = result.stdout.strip().splitlines()
    if len(lines) != 1:
        raise RuntimeError("Exactly one local GPU required")
    total, used = map(int, lines[0].split(","))
    if total <= 0 or used < 0 or used >= total * 0.9:
        raise RuntimeError("GPU memory admission/pressure stop at 90 percent")
    return {"utc": time.time(), "total_mib": total, "used_mib": used}


def resource_failure(error: Exception) -> bool:
    if isinstance(error, MemoryError):
        return True
    message = str(error).lower()
    return any(term in message for term in (
        "bad allocation", "out of memory", "not enough quota", "unable to allocate",
        "cuda_error_out_of_memory", "cublas_status_alloc_failed"))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--item")
    parser.add_argument("--capture-root", type=Path)
    parser.add_argument("--memory-telemetry", action="store_true")
    args = parser.parse_args()
    import sitecustomize
    if not getattr(sitecustomize, "INSTALLED", False):
        raise RuntimeError("Offline gate missing")
    inventory = json.loads((args.evidence / "runtime-inventory.json").read_text())
    rows = json.loads((args.evidence / "reference-eligibility.json").read_text())
    for item in inventory["homr_source"] + inventory["active_weights"] + inventory["installed_bridge"]:
        if sha256(Path(item["path"])) != item["sha256"]:
            raise RuntimeError("Baseline bytes drifted: " + item["path"])
    capture_root = args.capture_root or args.evidence
    capture_root.mkdir(exist_ok=True)
    root = capture_root / "development"
    root.mkdir(exist_ok=True)
    if args.item and not any(row["item_id"] == args.item for row in rows):
        raise ValueError("Unknown development item: " + args.item)
    for row in rows:
        prior = root / row["item_id"] / "result.json"
        if prior.exists():
            old = json.loads(prior.read_text())
            if old["status"] == "resource_stopped" or resource_failure(
                    RuntimeError(old.get("error", ""))):
                raise RuntimeError("Prior resource failure requires review and a new execution record")
    initial = gpu_sample()
    stopped = threading.Event()
    samples = capture_root / ("gpu-" + (args.item or "remaining") + ".jsonl")
    sample_stream = samples.open("x", encoding="utf-8")

    def watch_gpu() -> None:
        with sample_stream as stream:
            stream.write(json.dumps(initial) + "\n")
            while not stopped.wait(2):
                try:
                    sample = gpu_sample()
                except Exception as error:
                    stream.write(json.dumps({"stop": str(error)}) + "\n")
                    stream.flush()
                    os._exit(90)
                stream.write(json.dumps(sample) + "\n")
                stream.flush()

    watcher = threading.Thread(target=watch_gpu, daemon=True)
    watcher.start()
    workspace = Path(__file__).resolve().parents[2]
    sys.path.insert(0, str(workspace / "dist/Bridge"))
    from homr_gpu import configure_cuda
    configure_cuda()
    import homr.main as native
    from homr.transformer.staff2score import Staff2Score
    original_predict = Staff2Score.predict
    original_export = native.generate_xml
    captured: dict = {}

    def record_memory(stage):
        if args.memory_telemetry:
            from homr_baseline_resources import memory_sample
            sample = {"stage": stage, **memory_sample()}
            captured.setdefault("memory", []).append(sample)

    def observe_stage(function, stage):
        def observed(*arguments, **keywords):
            record_memory("before_" + stage)
            result = function(*arguments, **keywords)
            record_memory("after_" + stage)
            return result
        return observed

    def predict(self, image):
        result = original_predict(self, image)
        captured.setdefault("decoder_outputs", []).append([str(s) for s in result])
        return result

    def export(arguments, staffs, title):
        captured["exporter_inputs"] = [[str(s) for s in voice] for voice in staffs]
        return original_export(arguments, staffs, title)

    Staff2Score.predict = predict
    native.generate_xml = export
    if args.memory_telemetry:
        native.detect_staffs_in_image = observe_stage(native.detect_staffs_in_image, "detection")
        native.parse_staffs = observe_stage(native.parse_staffs, "parsing")
    config = native.ProcessingConfig(True, False, True, False, -1, True, True, False, True)
    export_args = native.XmlGeneratorArguments(False, None, None)
    failures = 0
    try:
        for row in rows:
            if args.item and row["item_id"] != args.item:
                continue
            destination = root / row["item_id"]
            receipt = destination / "result.json"
            if receipt.exists():
                old = json.loads(receipt.read_text())
                if old["runtime_identity"] != inventory["identity_sha256"]:
                    raise RuntimeError("Existing inference identity mismatch")
                for artifact in old["artifacts"]:
                    if sha256(Path(artifact["path"])) != artifact["sha256"]:
                        raise RuntimeError("Existing inference artifact drift")
                failures += old["status"] != "complete"
                continue
            destination.mkdir(exist_ok=False)
            image = destination / "input.png"
            if sha256(Path(row["image"]["path"])) != row["image"]["sha256"]:
                raise RuntimeError("Development input drift")
            shutil.copyfile(row["image"]["path"], image)
            captured.clear()
            started = time.monotonic()
            result = {"item_id": row["item_id"], "runtime_identity": inventory["identity_sha256"],
                      "input_sha256": row["image"]["sha256"], "status": "complete",
                      "profile": "native shipped CUDA page pipeline; debug and position capture enabled",
                      "numeric_accuracy_eligible": row["numeric_accuracy_eligible"],
                      "python_executable": sys.executable, "python_prefix": sys.prefix,
                      "homr_origin": str(Path(native.__file__).resolve()),
                      "capture_script_sha256": sha256(Path(__file__))}
            pressure_stop = False
            try:
                record_memory("before_image")
                native.process_image(str(image), config, export_args)
                record_memory("after_image")
            except Exception as error:
                result["status"] = "failed"
                result["error"] = f"{type(error).__name__}: {error}"
                failures += 1
                pressure_stop = resource_failure(error)
                if pressure_stop:
                    result["status"] = "resource_stopped"
                (destination / "failure-traceback.txt").write_text(traceback.format_exc())
                record_memory("after_failure")
            (destination / "tokens.json").write_text(json.dumps(captured, indent=2) + "\n")
            result["elapsed_seconds"] = time.monotonic() - started
            result["artifacts"] = [{"path": str(p.resolve()), "sha256": sha256(p), "bytes": p.stat().st_size}
                                   for p in sorted(destination.iterdir()) if p.is_file()]
            receipt.write_text(json.dumps(result, indent=2) + "\n")
            print(json.dumps({k: result[k] for k in ("item_id", "status", "elapsed_seconds")}), flush=True)
            if pressure_stop:
                return 2
    finally:
        stopped.set()
        watcher.join(timeout=12)
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
