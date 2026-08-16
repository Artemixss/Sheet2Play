from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any

from .assets import RuntimePaths
from .errors import ResearchError
from .events import _load_music21, extract_canonical_events, write_exports
from .input_pages import iter_document_pages
from .inference import ProgressCallback, _progress

def infer_zeus_document(
    input_path: Path,
    output_dir: Path,
    *,
    paths: RuntimePaths | None = None,
    progress_callback: ProgressCallback | None = None,
) -> dict[str, Any]:
    progress = progress_callback or _progress
    
    # Path(__file__) is Research/omr/src/sheet2play_omr/zeus_engine.py
    # .parent.parent.parent is Research/omr
    omr_dir = Path(__file__).resolve().parent.parent.parent
    zeus_dir = omr_dir / "zeus"
    zeus_python = zeus_dir / ".venv" / "Scripts" / "python.exe"
    infer_batch_script = zeus_dir / "infer_batch.py"
    
    if not zeus_python.exists() or not infer_batch_script.exists():
        raise ResearchError(
            "ZEUS_MISSING",
            "model_load",
            f"Zeus environment not found at {zeus_dir}. Ensure Zeus is installed."
        )

    output_dir.mkdir(parents=True, exist_ok=True)
    
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        
        # 1. Extract Images and Crop Systems
        images_payload = []
        sys_counter = 1
        
        # Path to detect_systems.py
        bridge_dir = omr_dir.parent.parent / "Bridge"
        homr_python = bridge_dir / ".venv-homr-gpu" / "Scripts" / "python.exe"
        detect_script = bridge_dir / "detect_systems.py"
        
        with iter_document_pages(input_path) as pages:
            for info, image in pages:
                progress("page_start", page=info.number, total_pages=info.total, decoder="zeus")
                img_path = tmp_path / f"page_{info.number}.png"
                image.save(img_path)
                
                # Detect systems
                systems_json = tmp_path / f"systems_{info.number}.json"
                try:
                    subprocess.run(
                        [str(homr_python), str(detect_script), str(img_path), str(systems_json)],
                        check=True,
                        capture_output=True,
                        text=True
                    )
                    
                    with open(systems_json, "r") as f:
                        systems_data = json.load(f)
                        
                    # Crop systems
                    for idx, sys_box in enumerate(systems_data["systems"]):
                        min_x, max_x = sys_box["min_x"], sys_box["max_x"]
                        min_y, max_y = sys_box["min_y"], sys_box["max_y"]
                        
                        # Add a small horizontal margin (optional, HOMR margin was already added vertically in detect_script)
                        # We just use the box directly, but expand width to the full page to avoid missing key signatures
                        sys_img = image.crop((0, max(0, min_y), image.width, min(image.height, max_y)))
                        
                        sys_img_path = tmp_path / f"sys_{sys_counter}.png"
                        sys_img.save(sys_img_path)
                        
                        images_payload.append({"page": sys_counter, "path": str(sys_img_path)})
                        sys_counter += 1
                        
                except Exception as e:
                    raise ResearchError("SYSTEM_DETECTION_FAILED", "inference", f"Failed to detect systems on page {info.number}: {e}")
                
        json_path = tmp_path / "images.json"
        with open(json_path, "w") as f:
            json.dump(images_payload, f)
            
        # 2. Run Zeus subprocess
        progress("zeus_inference_start", pages=len(images_payload))
        zeus_out_dir = tmp_path / "zeus_out"
        
        try:
            result = subprocess.run(
                [str(zeus_python), str(infer_batch_script), str(json_path), str(zeus_out_dir)],
                capture_output=True,
                text=True,
                check=False
            )
        except OSError as e:
            raise ResearchError("ZEUS_FAILED", "inference", f"Failed to start Zeus subprocess: {e}") from e
        
        if result.returncode != 0:
            stderr_tail = result.stderr[-2000:] if result.stderr else "(no stderr)"
            raise ResearchError("ZEUS_FAILED", "inference", f"Zeus inference failed (exit {result.returncode}): {stderr_tail}")
            
        # 3. Read results
        summary_file = zeus_out_dir / "zeus_summary.json"
        if not summary_file.exists():
            raise ResearchError("ZEUS_FAILED", "inference", "Zeus summary JSON not produced.")
            
        with open(summary_file, "r") as f:
            zeus_summary = json.load(f)
            
        # 4. Combine MusicXML pages at the XML level (avoids music21 makeRests/makeTies bugs)
        progress("symbolic_parse", pages=len(images_payload))
        
        import xml.etree.ElementTree as ET
        ET.register_namespace("", "http://www.musicxml.org/dtd/MusicXML")
        
        page_results = []
        xml_files = []
        
        for item in zeus_summary:
            if item["status"] != "success":
                raise ResearchError("ZEUS_PAGE_FAILED", "inference", f"Page {item['page']} failed: {item.get('error')}")
            
            xml_file = Path(item["xml_path"])
            
            # Copy per-page XML to output dir — use these stable paths for combining
            final_xml = output_dir / f"page-{item['page']:04d}.musicxml"
            final_xml.write_text(xml_file.read_text(encoding="utf-8"), encoding="utf-8")
            xml_files.append(final_xml)  # store output_dir path, not zeus_tmp path
            
            page_results.append({
                "page": item["page"],
                "total_pages": len(images_payload),
                "mode": "zeus",
                "tokens": 0,
                "seconds": item["seconds"],
                "source_width": 0,
                "source_height": 0,
                "peak_vram_bytes": 0,
                "appended_terminator": True,
                "retained_vram_bytes": 0
            })
            progress("page_complete", page=item["page"], seconds=item["seconds"])
        
    # Combine XML pages: take part structure from page 1, append measures from subsequent pages
    combined_path = output_dir / "score.musicxml"
    if len(xml_files) == 1:
        combined_path.write_text(xml_files[0].read_text(encoding="utf-8"), encoding="utf-8")
    else:
        # Parse all pages
        trees = [ET.parse(str(f)) for f in xml_files]
        base_root = trees[0].getroot()
        ns = {"mx": "http://www.musicxml.org/dtd/MusicXML"}
        
        # Find parts in base
        base_parts = base_root.findall(".//part") or base_root.findall(".//{http://www.musicxml.org/dtd/MusicXML}part")
        if not base_parts:
            # Try without namespace
            base_parts = list(base_root.iter("part"))
        
        for tree in trees[1:]:
            root = tree.getroot()
            extra_parts = root.findall(".//part") or root.findall(".//{http://www.musicxml.org/dtd/MusicXML}part")
            if not extra_parts:
                extra_parts = list(root.iter("part"))
            for bp, ep in zip(base_parts, extra_parts):
                measures = ep.findall("measure") or ep.findall("{http://www.musicxml.org/dtd/MusicXML}measure")
                if not measures:
                    measures = list(ep.iter("measure"))
                for m in measures:
                    bp.append(m)
        
        trees[0].write(str(combined_path), encoding="unicode", xml_declaration=True)
    
    # Parse the combined XML through music21 for event extraction
    _, converter, _, _, _, _ = _load_music21(register_converter=False)
    combined_score = converter.parse(str(combined_path))
    
    canonical = extract_canonical_events(combined_score, validate_ties=False, validate_voice_overlap=False)
    
    # Build omr_result JSON directly — avoids calling score.write("musicxml") inside
    # write_exports which triggers music21's makeTies KeyError on some stitched scores.
    from sheet2play_omr.events import _tempo_changes, _seconds_at, _fraction
    engine_revision = "df0d842596ccd199882ff958e628d59327ca6cba"
    tempos = _tempo_changes(combined_score)
    notes_out: list[dict] = []
    for event in canonical.events:
        if event.kind != "note":
            continue
        start = float(_fraction(event.onset))
        duration = float(_fraction(event.duration))
        end = start + duration
        start_secs = _seconds_at(start, tempos)
        notes_out.append({
            "pitch": event.pitch,
            "midi_pitch": event.midi_pitch,
            "start_beat": start,
            "duration_beats": duration,
            "start_seconds": start_secs,
            "duration_seconds": _seconds_at(end, tempos) - start_secs,
            "part_index": 0,
            "staff_index": event.staff,
            "voice_identifier": event.voice,
        })
    notes_out.sort(key=lambda n: (n["start_beat"], n["staff_index"], n["voice_identifier"], n["midi_pitch"]))
    omr_result = {
        "schema_version": 2,
        "engine": "zeus",
        "engine_revision": engine_revision,
        "tempo_changes": [{"start_beat": b, "bpm": bpm} for b, bpm in tempos],
        "notes": notes_out,
    }
    omr_result_path = output_dir / "omr-result.json"
    omr_result_path.write_text(json.dumps(omr_result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    
    # Write MIDI for playback (best-effort — skip if music21 chokes on this score)
    try:
        combined_score.write("midi", fp=str(output_dir / "score.mid"))
    except Exception:
        pass
    
    summary = {
        "decoder": "zeus",
        "input": str(input_path.resolve()),
        "pages": page_results,
        "page_count": len(page_results),
        "staff_count": len(combined_score.parts),
        "note_events": sum(event.kind == "note" for event in canonical.events),
        "runtime": {"decoder": "zeus", "model_revision": "2024-02-12"},
        "retained_vram_growth_bytes_after_warmup": 0,
        "outputs": {
            "musicxml": str(combined_path.resolve()),
            "omr_result": str(omr_result_path.resolve()),
        },
        "omr_result": omr_result,
    }
    (output_dir / "run.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    progress("complete", pages=len(page_results), note_events=summary["note_events"])
    return summary
