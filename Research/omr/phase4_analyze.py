"""Use the unchanged Phase3 analyzer and failure policy on explicit recipe views."""
from __future__ import annotations

import json
from pathlib import Path
import shutil

import zeus_attribution_analyze as analyzer
from zeus_attribution_prepare import HERE, configure_cpu, save_json
from phase4_validation import file_hash
from sheet2play_omr.research_ties import normalize_ties_exact, verify_midi
from sheet2play_omr.zeus_trace import normalized_notes, xml_trace

OUT = HERE / "reports/zeus-attribution/phase4"
OLD = OUT.parent / "phase3"


def read(path: Path) -> dict:
    return json.loads(path.read_text())


def recipe_view(item: dict, source: Path, destination: Path, *, mask: bool = False, indices: list[int] | None = None) -> dict:
    selected = indices or list(range(1, len(item["crops"]) + 1))
    crops = []
    for new_index, old_index in enumerate(selected, 1):
        crop = item["crops"][old_index - 1]
        original = source / "inference" / item["item_id"] / f"system-{old_index:04d}"
        work = destination / "inference" / item["item_id"] / f"system-{new_index:04d}"
        work.mkdir(parents=True, exist_ok=False)
        prediction = read(original / "prediction.json")
        if prediction["crop_sha256"] != crop["sha256"] or file_hash(Path(crop["path"])) != crop["sha256"]:
            raise ValueError("Prediction/crop identity mismatch")
        mapping = {"upstream": "upstream", "wrapper": "wrapper_valid_mask" if mask else "wrapper"}
        if mask:
            masked = read(original / "mask-prediction.json")
            if masked["crop_sha256"] != crop["sha256"]:
                raise ValueError("Masked crop identity mismatch")
            prediction["wrapper"] = masked["wrapper_valid_mask"]
        for target, recipe in mapping.items():
            row = prediction[target]
            if row["conversion"]["status"] == "succeeded":
                xml = original / f"{recipe}.musicxml"
                if file_hash(xml) != row["conversion"]["musicxml_sha256"]:
                    raise ValueError("Prediction XML identity mismatch")
                shutil.copyfile(xml, work / f"{target}.musicxml")
        save_json(work / "prediction.json", {**prediction, "analysis_view_mapping": mapping,
            "original_system_index": old_index})
        crops.append(crop)
    return {**item, "crops": crops}


def tie_evidence() -> None:
    source = OUT.parent / "phase2/cross-system-chord-tie.musicxml"
    raw, _ = xml_trace(source)
    result = normalize_ties_exact(source)
    midi = verify_midi(result.notes, OUT / "cross-system-chord-tie.mid")
    if len(raw) != 6 or len(result.notes) != 4 or result.issues:
        raise ValueError("Independent-voice reproducer acceptance failed")
    save_json(OUT / "tie-acceptance.json", {"source": str(source), "source_sha256": file_hash(source),
        "raw_segments": len(raw), "unchanged_bridge_events": len(normalized_notes(source)),
        "repaired_events": [n.json() for n in result.notes], "issues": result.issues,
        "midi": midi, "midi_sha256": file_hash(OUT / "cross-system-chord-tie.mid"),
        "normalizer_sha256": file_hash(HERE / "src/sheet2play_omr/research_ties.py"),
        "scope": "Literal exact MusicXML; unsupported repeat/duration cases fail closed; no playback calibration claim"})


def main() -> None:
    configure_cpu()
    manifest = read(OUT / "experiment-manifest.json")
    rows = []
    view = OUT / "mask-view"
    for item in manifest["items"]:
        destination = OUT / "analysis" / item["item_id"]
        destination.mkdir(parents=True, exist_ok=False)
        analyzer.OUT = OUT
        row = analyzer.analyze_item(item, destination)
        masked = recipe_view(item, OUT, view, mask=True)
        mask_destination = OUT / "analysis-mask" / item["item_id"]
        mask_destination.mkdir(parents=True, exist_ok=False)
        analyzer.OUT = view
        mask_row = analyzer.analyze_item(masked, mask_destination)
        row["variants"]["wrapper_valid_mask"] = mask_row["variants"]["wrapper"]
        save_json(destination / "result.json", row)
        rows.append(row)
        print(json.dumps({"item_id": item["item_id"], "primary": {name: v["global"]["onset_duration_f1"] for name,v in row["variants"].items()}}), flush=True)
    original = next(i for i in read(OLD / "experiment-manifest.json")["items"] if i["item_id"] == "openscore-6211555-page-1")
    dedup_root = OUT / "dedup-only-view"
    dedup = recipe_view(original, OLD, dedup_root, indices=[1, 3])
    analyzer.OUT = dedup_root
    destination = OUT / "dedup-only-analysis"
    destination.mkdir(exist_ok=False)
    dedup_result = analyzer.analyze_item(dedup, destination)
    save_json(destination / "result.json", dedup_result)
    previous = read(OLD / "analysis-report.json")
    variants = ("upstream", "wrapper", "wrapper_valid_mask")
    comparisons = []
    for item in manifest["items"]:
        for number, _ in enumerate(item["crops"], 1):
            work = OUT / "inference" / item["item_id"] / f"system-{number:04d}"
            normal, masked = read(work / "prediction.json"), read(work / "mask-prediction.json")["wrapper_valid_mask"]
            comparisons.append({"item_id": item["item_id"], "system": number,
                "upstream_vs_wrapper_equal": normal["upstream"]["token_ids"] == normal["wrapper"]["token_ids"],
                "wrapper_vs_valid_mask_equal": normal["wrapper"]["token_ids"] == masked["token_ids"],
                "upstream_vs_valid_mask_equal": normal["upstream"]["token_ids"] == masked["token_ids"],
                "mask_evidence": masked["mask_evidence"]})
    tie_evidence()
    save_json(OUT / "analysis-report.json", {"items": rows,
        "aggregate": {v: analyzer.aggregate(rows, v) for v in variants},
        "prior_aggregate": previous["aggregate"], "mask_comparisons": comparisons,
        "dedup_only": dedup_result,
        "source_sha256": file_hash(Path(__file__)), "analyzer_sha256": file_hash(HERE / "zeus_attribution_analyze.py"),
        "manifest_sha256": file_hash(OUT / "experiment-manifest.json"),
        "metric_policy": "Fixed development item macro, all failures retained; unchanged Bridge/reference processing. No benchmark/composition-macro ranking.",
        "mask_view_policy": "wrapper label in analysis-mask is an explicit alias for wrapper_valid_mask; upstream duplicate analysis excluded from aggregate"})


if __name__ == "__main__":
    main()
