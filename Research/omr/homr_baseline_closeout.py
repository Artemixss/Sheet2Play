"""Verify retained Phase 1 evidence without repeating inference or fetching bytes."""
from __future__ import annotations

import argparse
import ast
import json
from pathlib import Path
import xml.etree.ElementTree as ET

from homr_baseline import digest, save


def verify_rows(rows: list[dict]) -> int:
    for row in rows:
        if digest(Path(row["path"])) != row["sha256"]:
            raise ValueError("Protected artifact changed: " + row["path"])
    return len(rows)


def patch_inventory(inventory: dict) -> dict:
    exporter = Path(inventory["probe"]["module_origins"]["exporter"])
    source = exporter.read_text(encoding="utf-8")
    tree = ast.parse(source)
    functions = {node.name: ast.get_source_segment(source, node)
                 for node in tree.body if isinstance(node, ast.FunctionDef)}
    import hashlib
    plans = {name: hashlib.sha256(text.encode()).hexdigest()
             for name, text in functions.items() if name.startswith("_plan_")}
    package_root = exporter.parent.parent
    metadata = list(package_root.glob("homr-*.dist-info/direct_url.json"))
    if len(metadata) != 1:
        raise ValueError("Expected exactly one HOMR installation provenance record")
    return {
        "exporter_path": str(exporter), "exporter_sha256": digest(exporter),
        "planner_function_hashes": plans,
        "voice_planner": "Runs on measures whose grouped duration differs from the expected meter; skips multi-rests and fewer than two groups",
        "upstream_markers": {name: name in functions for name in
                             ("_advance_to_next_group", "split_mixed_chords")},
        "positive_duration_guards": "Backup/forward and mixed note/rest paths assert positive duration",
        "tuplet_diagnostic_switch": "SHEET2PLAY_HOMR_KEEP_TUPLETS=1 bypasses vocabulary cleanup; absent for this baseline",
        "source_provenance": json.loads(metadata[0].read_text()),
        "provenance_record_sha256": digest(metadata[0]),
        "local_vendor_differences": inventory["local_vendor_differences"],
        "provenance_limit": inventory["vendor_comparison_limit"],
        "capture_boundary": "Staff2Score.predict returns ScoreDecoder.generate symbols before staff_parsing.remove_duplicated_symbols cleanup; exporter_inputs capture the later cleaned stream",
    }


def failure_traces(output: Path, ledger: list[dict], analysis: dict) -> list[dict]:
    findings = {
        "generated-offset_entry": ("MusicXML onset placement", "Source and crop retain the independent stems. Decoder/exporter inputs retain the expected pitches and durations, but lack explicit independent voice IDs. XML places A5 at 2 instead of 3/2, B5 and E4 at 5/2 instead of 2, and F4 at 7/2 instead of 3. This establishes a representation/export boundary defect, not exporter-only causal attribution."),
        "generated-quintuplet_vs_duple": ("Decoder output", "The crop retains five upper notes and the visible tuplet numeral 5. The pre-cleanup decoder emits plain quarters, omits upper G5 and loses lower F4; malformed trailing symbols are retained in tokens.json. XML/timed events propagate the wrong rhythm."),
        "generated-septuplet_vs_duple": ("Decoder output", "The crop retains seven upper notes and numeral 7. Pre-cleanup tokens use ordinary quarters and timeSignature/2; source requires seven 4/7-quarter durations in 4/4. Wrong rhythm is already demonstrated before exporter cleanup."),
        "generated-syncopation": ("Decoder output", "The crop retains the source noteheads/stems. Pre-cleanup tokens use timeSignature/2 instead of the visible 4/4 and lack chord separators/independent voice information. Individual note pitches and durations are retained, but XML serializes them and shifts onsets. The source deliberately hides the initial voice-1 eighth rest (print-object=no), so omission is not proof of rest recognition failure; spatial voice reconstruction remains ambiguous. Crop margins also clip parts of stems/tempo marks."),
        "generated-same_position_sustain": ("Staff crop", "The source has two simultaneous low Ab2 notes of durations 2 and 1/2 quarter beats. Native staff crop cuts off their low ledger-line noteheads at its bottom edge. Decoder begins C3 and lacks the sustained unison; XML cannot recover omitted content. Crop loss is demonstrated before decoding; its initiating detector/geometry cause is unverified."),
    }
    eligible = {row["item_id"]: row for row in ledger}
    traces = []
    for row in analysis["development"]:
        if row["item_id"] not in findings:
            continue
        stage, finding = findings[row["item_id"]]
        source = eligible[row["item_id"]]
        root = output / "development" / row["item_id"]
        paths = [root / name for name in
                 ("input.png", "input_staff-0_input.jpg", "tokens.json", "input.musicxml")]
        traces.append({"item_id": row["item_id"], "first_difference": row["first_difference"],
                       "earliest_demonstrated_stage": stage, "finding": finding,
                       "method": "Visual source/crop review plus captured token and literal XML/event comparison; no reference-driven token correction or alignment",
                       "reference": source["reference"],
                       "artifacts": [{"path": str(path.resolve()), "sha256": digest(path)} for path in paths]})
    return traces


def closeout(output: Path) -> dict:
    inventory = json.loads((output / "runtime-inventory.json").read_text())
    ledger = json.loads((output / "reference-eligibility.json").read_text())
    analysis = json.loads((output / "development-analysis.json").read_text())
    protected = verify_rows(inventory["homr_source"] + inventory["active_weights"] +
                            inventory["installed_bridge"] + inventory["tokenizers"] +
                            [inventory["python"], inventory["executable"]])
    inference_artifacts = 0
    for row in analysis["development"]:
        receipt = output / "development" / row["item_id"] / "result.json"
        if digest(receipt) != row["result_sha256"]:
            raise ValueError("Inference receipt changed")
        inference_artifacts += verify_rows(json.loads(receipt.read_text())["artifacts"])
    jobs = {}
    for receipt in sorted((output / "jobs").glob("*/result.json")):
        job = json.loads(receipt.read_text())
        jobs[receipt.parent.name] = {key: job.get(key) for key in
                                    ("status", "worker_exit_code", "stop_reason", "elapsed_seconds")}
    suite = ET.parse(output / "regression-final.xml").getroot().find("testsuite")
    counters = {key: int(suite.attrib[key]) for key in ("tests", "failures", "errors", "skipped")}
    if counters["failures"] or counters["errors"]:
        raise ValueError("Regression failed")
    namespace = {"t": "http://microsoft.com/schemas/VisualStudio/TeamTest/2010"}
    frontend = ET.parse(output / "playback-results/phase1-frontend.trx").find("t:ResultSummary/t:Counters", namespace)
    if frontend is None or int(frontend.attrib["failed"]) or int(frontend.attrib["passed"]) != 69:
        raise ValueError("Frontend regression evidence inconsistent")
    save(output / "patch-inventory.json", patch_inventory(inventory))
    save(output / "failure-traces.json", failure_traces(output, ledger, analysis))
    result = {"phase": 1, "status": "partial; resource-stopped", "phase2_started": False,
              "runtime_identity": inventory["identity_sha256"], "protected_artifacts_verified": protected,
              "inference_artifacts_verified": inference_artifacts,
              "reference_ledger_items": len(ledger), "pre_resource_failure_controls": 8,
              "post_resource_failure_xml_quarantined": 2, "allocation_failures": 22,
              "regression": counters, "frontend_tests": frontend.attrib, "jobs": jobs,
              "remaining": "Resource diagnosis and explicitly reviewed fresh execution for two failed generated controls, two quarantined controls and all 20 OpenScore pages; independently verify OpenScore page ranges before numerical accuracy claims",
              "network": json.loads((output / "network-closeout.json").read_text(encoding="utf-8-sig")),
              "midi_artifacts": [{"path": str(path.resolve()), "sha256": digest(path)}
                                 for path in sorted(output.glob("*.mid"))]}
    save(output / "closeout.json", result)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    report = closeout(parser.parse_args().output)
    print(json.dumps({key: report[key] for key in
                      ("status", "protected_artifacts_verified", "inference_artifacts_verified", "regression")}))
