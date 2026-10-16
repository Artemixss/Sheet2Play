"""Freeze Phase 3 development inputs, crop evidence and page references before inference."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from sheet2play_omr.adapter_contract import sha256_file
from screening_cpu_profile import cpu_environment

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OUT = HERE / "reports/zeus-attribution/phase3"
OPEN_IDS = ("openscore-6211535", "openscore-6211549", "openscore-6211555")


def configure_cpu() -> None:
    import ctypes
    from ctypes import wintypes
    if os.name != "nt":
        raise RuntimeError("The pinned diagnostic runtime requires Windows CPU containment")
    os.environ.update(cpu_environment(8))
    os.environ["CUDA_VISIBLE_DEVICES"] = "-1"
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.GetCurrentProcess.restype = wintypes.HANDLE
    kernel.GetProcessAffinityMask.argtypes = [wintypes.HANDLE,
        ctypes.POINTER(ctypes.c_size_t), ctypes.POINTER(ctypes.c_size_t)]
    kernel.GetProcessAffinityMask.restype = wintypes.BOOL
    kernel.SetProcessAffinityMask.argtypes = [wintypes.HANDLE, ctypes.c_size_t]
    kernel.SetProcessAffinityMask.restype = wintypes.BOOL
    kernel.SetPriorityClass.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    kernel.SetPriorityClass.restype = wintypes.BOOL
    process = kernel.GetCurrentProcess()
    available, system = ctypes.c_size_t(), ctypes.c_size_t()
    if not kernel.GetProcessAffinityMask(process, ctypes.byref(available), ctypes.byref(system)):
        raise ctypes.WinError(ctypes.get_last_error())
    processors = [1 << bit for bit in range(ctypes.sizeof(available) * 8)
                  if available.value & (1 << bit)][:8]
    if not processors:
        raise RuntimeError("The process has no allowed CPU processors")
    if not kernel.SetProcessAffinityMask(process, sum(processors)):
        raise ctypes.WinError(ctypes.get_last_error())
    if not kernel.SetPriorityClass(process, 0x4000):
        raise ctypes.WinError(ctypes.get_last_error())


def save_json(path: Path, value: dict) -> None:
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")


def first_page(source: Path, destination: Path) -> dict:
    tree = ET.parse(source)
    parts = tree.getroot().findall("part")
    if not parts:
        raise ValueError("Reference has no parts")
    retained = {}
    for part in parts:
        started = False
        removed = False
        for measure in list(part.findall("measure")):
            if started and any(p.get("new-page") == "yes" for p in measure.findall("print")):
                removed = True
            if removed:
                part.remove(measure)
            else:
                started = True
        retained[part.get("id")] = len(part.findall("measure"))
    if len(set(retained.values())) != 1:
        raise ValueError(f"Page boundaries disagree between reference parts: {retained}")
    tree.write(destination, encoding="utf-8", xml_declaration=True)
    return {"retained_measures_per_part": retained, "page_policy": "first engraved page; no reference-informed crops"}


def install_cpu_segnet(segmentation, runtime) -> dict:
    """Use HOMR's existing FP16 CPU fallback with an explicit bounded session."""
    model_path = Path(segmentation.segnet_path_onnx_fp16)
    if not model_path.is_file():
        raise FileNotFoundError(f"Pinned FP16 detector weights missing: {model_path}")
    if segmentation._segnet_inference is not None:
        raise RuntimeError("Detector session already initialized")
    options = runtime.SessionOptions()
    options.intra_op_num_threads = 8
    options.inter_op_num_threads = 1
    options.execution_mode = runtime.ExecutionMode.ORT_SEQUENTIAL
    session = runtime.InferenceSession(str(model_path), sess_options=options,
                                       providers=["CPUExecutionProvider"])
    if session.get_providers() != ["CPUExecutionProvider"]:
        raise RuntimeError("Detector did not retain the explicit CPU provider")
    # Preserve the installed run/patch/merge implementation; only select its CPU session.
    detector = segmentation.Segnet.__new__(segmentation.Segnet)
    detector.model = session
    detector.fp16 = True
    detector.use_gpu = False
    detector.io_binding = session.io_binding()
    detector.device_id = 0
    detector.input_name = session.get_inputs()[0].name
    detector.output_name = session.get_outputs()[0].name
    segmentation._segnet_inference = detector
    return {"weights": str(model_path), "weights_sha256": sha256_file(model_path),
            "providers": session.get_providers(), "input_dtype": "float16",
            "intra_op_threads": 8, "inter_op_threads": 1, "execution_mode": "sequential",
            "policy": "Installed FP16 CPU fallback; explicit CPU session, unchanged run/patch/merge"}


def detect(source: Path, destination: Path) -> None:
    sys.path.insert(0, str(ROOT / "Bridge"))
    sys.path.insert(0, str(HERE / "src/sheet2play_omr"))
    from homr.main import ProcessingConfig, detect_staffs_in_image
    from homr.segmentation import inference_segnet
    import onnxruntime
    from phase2r_detector import save_detection
    runtime_evidence = install_cpu_segnet(inference_segnet, onnxruntime)
    config = ProcessingConfig(enable_debug=False, enable_cache=False, write_staff_positions=False,
        read_staff_positions=False, selected_staff=0, transformer_use_gpu=False,
        segnet_use_gpu=False, coreml_encoder=False, title_detection=False)
    systems, processed, _, _, _ = detect_staffs_in_image(str(source), config)
    save_detection(source, destination / "detector-preprocessed.png",
                   destination / "detected-systems.json", systems, processed)
    save_json(destination / "cpu-runtime.json", runtime_evidence)


def prepare(verification_result: Path) -> None:
    configure_cpu()
    from sheet2play_omr.phase2r_development import development_records, _reference_musicxml
    from sheet2play_omr.phase2r_vlm import crop_detected_systems
    receipt = json.loads(verification_result.read_text())
    if receipt["status"] != "complete" or receipt["worker_exit_code"] != 0:
        raise ValueError("Byte verification supervisor must have completed successfully")
    if str(Path(__file__).with_name("zeus_attribution_verify.py").name) not in " ".join(receipt["command"]):
        raise ValueError("Supervisor receipt must belong to the byte-only verifier")
    if not json.loads((OUT / "verified-bytes.json").read_text())["verified"]:
        raise ValueError("Diagnostic runtime bytes must be verified first")
    items = []
    for record in development_records(ROOT):
        if record.collection != "generated" and record.item_id not in OPEN_IDS:
            continue
        item_id = record.item_id if record.collection == "generated" else record.item_id + "-page-1"
        work = OUT / "inputs" / item_id
        work.mkdir(parents=True, exist_ok=False)
        image = record.page_images[0][0]
        if sha256_file(image) != record.page_images[0][1] or sha256_file(record.reference) != record.reference_sha256:
            raise ValueError(f"Frozen development bytes changed: {item_id}")
        reference_source = _reference_musicxml(record, work)
        reference = work / "page-reference.musicxml"
        if record.collection == "open":
            page_info = first_page(reference_source, reference)
        else:
            shutil.copy2(reference_source, reference)
            page_info = {"page_policy": "entire frozen generated page"}
            # The engraved baseline has two systems; its kern import has no layout markers.
            if record.item_id == "generated-baseline-piano-001":
                page_info["reference_system_measure_starts"] = [0, 5]
                page_info["reference_system_boundary_evidence"] = "pre-inference visual inspection of frozen page"
        detector = work / "detector"
        detector.mkdir()
        if record.item_id == OPEN_IDS[0]:
            prior = HERE / ".runtime/phase3/development-entry/zeus_page-openscore-6211535-page-1-0c7dfd900817/detector"
            for name in ("detected-systems.json", "detector-preprocessed.png"):
                shutil.copy2(prior / name, detector / name)
        else:
            command = [str(ROOT / "Bridge/.venv-homr-gpu/Scripts/python.exe"), "-B", str(Path(__file__)),
                       "detect", "--image", str(image), "--destination", str(detector)]
            subprocess.run(command, check=True, stdin=subprocess.DEVNULL, timeout=300)
        detection = json.loads((detector / "detected-systems.json").read_text())
        runtime_path = detector / "cpu-runtime.json"
        page_info["detector_runtime"] = (
            {"path": str(runtime_path), "sha256": sha256_file(runtime_path)}
            if runtime_path.is_file() else
            {"policy": "Reused representative detector artifacts verified in inherited identity"})
        crops = crop_detected_systems(detector / "detector-preprocessed.png", detection,
                                     detector / "crops", source_sha256=sha256_file(image))
        page_info["crop_policy"] = "verified corrected HOMR coordinate space; CPU detection or hash-pinned representative reuse"
        items.append({"item_id": item_id, "collection": record.collection,
            "image": str(image), "image_sha256": sha256_file(image),
            "reference_source": str(record.reference), "reference_source_sha256": record.reference_sha256,
            "reference": str(reference), "reference_sha256": sha256_file(reference),
            "crops": [{"path": str(p), "sha256": sha256_file(p)} for p in crops], **page_info})
        print(json.dumps({"prepared": item_id, "systems": len(crops)}), flush=True)
    if len(items) != 15:
        raise ValueError("Phase 3 requires 12 controls and 3 preselected pages")
    scripts = [Path(__file__), HERE / "zeus_attribution_infer.py", HERE / "zeus_attribution_analyze.py",
               HERE / "zeus_attribution_verify.py", HERE / "zeus_provenance_probe.py",
               HERE / "phase2_zeus_runner.py", HERE / "phase3_score.py", HERE / "screening_cpu_profile.py",
               *[HERE / "src/sheet2play_omr" / name for name in (
                   "zeus_trace.py", "metrics.py", "timing.py", "corrected_scoring.py", "phase3_scoring.py",
                   "phase2r_vlm.py", "phase2r_detector.py", "phase2r_development.py")],
               ROOT / "Bridge/musicxml_normalizer.py"]
    manifest = {"schema_version": 1, "diagnostic_identity": json.loads((OUT / "verified-bytes.json").read_text())["identity_sha256"],
                "verification_receipt": {"path": str(verification_result.resolve()),
                                         "sha256": sha256_file(verification_result)},
                "items": items, "sources": {str(p): sha256_file(p) for p in scripts},
                "settings": {"cpu_threads": 8, "CUDA_VISIBLE_DEVICES": "-1", "max_predict_length": 700,
                    "upstream_recipe": "LMXDataset.tf_dataset(training=False), Model.predict; single-example batch",
                    "local_recipe": "unmodified ZeusRunner.predict_image; white padding to multiple of 500"}}
    save_json(OUT / "experiment-manifest.json", manifest)
    print(json.dumps({"items": len(items), "systems": sum(len(i["crops"]) for i in items)}), flush=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("prepare", "detect"))
    parser.add_argument("--image", type=Path)
    parser.add_argument("--destination", type=Path)
    parser.add_argument("--verification-result", type=Path, default=OUT / "identity-bytes/result.json")
    args = parser.parse_args()
    if args.action == "detect":
        configure_cpu()
        if args.image is None or args.destination is None:
            parser.error("Detection requires image and destination")
        detect(args.image, args.destination)
    else:
        prepare(args.verification_result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
