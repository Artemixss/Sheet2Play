from __future__ import annotations

import json
import random
import time
import sys
from pathlib import Path

from sheet2play_omr.olimpic import load_test_partition
from sheet2play_omr.zeus_engine import infer_zeus_document
from sheet2play_omr.metrics import calculate_note_metrics, MetricNote
import sys; sys.path.insert(0, str((Path(__file__).parents[2] / "Bridge").resolve())); import bridge

def run_homr_on_image(image_path: Path) -> list[MetricNote]:
    output = bridge.run_homr_engine(image_path, )
    notes = []
    for note in output.score.notes:
        notes.append(
            MetricNote(
                pitch=note.midi_pitch,
                onset=note.start_beat,
                duration=note.duration_beats,
                staff=note.staff_index,
                voice=note.voice_identifier,
            )
        )
    return notes


def _fraction(value) -> any:
    from fractions import Fraction
    if isinstance(value, Fraction):
        return value
    return Fraction(str(value)).limit_denominator(4096)


def load_ground_truth_notes(path: Path) -> list[MetricNote]:
    bridge_path = str((Path(__file__).parents[2] / "Bridge").resolve())
    if bridge_path not in sys.path:
        sys.path.insert(0, bridge_path)
    from musicxml_normalizer import normalize_musicxml

    score = normalize_musicxml(
        path,
        expand_repeats=False,
        skip_grace_notes=True,
    )
    notes = [
        MetricNote(
            pitch=note.midi_pitch,
            onset=_fraction(note.start_beat),
            duration=_fraction(note.duration_beats),
            staff=note.staff_index,
            voice=note.voice_identifier,
        )
        for note in score.notes
    ]
    return notes


def run_eval():
    dataset_root = Path("data/olimpic/olimpic-1.0-scanned").resolve()
    all_samples = load_test_partition(dataset_root)
    random.seed(42)
    test_samples = random.sample(all_samples, 20)

    print(f"Evaluating Zeus vs HOMR on {len(test_samples)} random samples from OLiMPiC")
    
    zeus_metrics = []
    homr_metrics = []

    for i, sample in enumerate(test_samples):
        print(f"[{i+1}/{len(test_samples)}] Processing {sample.identifier}...")
        image_path = Path(sample.image)
        gt_path = Path(sample.musicxml)
        
        try:
            gt_notes = load_ground_truth_notes(gt_path)
        except Exception as e:
            print(f"  Skipping (GT parse error): {e}")
            continue
            
        try:
            t0 = time.time()
            homr_notes = run_homr_on_image(image_path)
            homr_notes = [MetricNote(n.pitch, _fraction(n.onset), _fraction(n.duration), n.staff, n.voice) for n in homr_notes]
            if not homr_notes:
                raise ValueError("No notes")
            homr_res = calculate_note_metrics(homr_notes, gt_notes)
            homr_metrics.append((time.time()-t0, homr_res))
            print(f"  HOMR: Pitch F1={homr_res.pitch_f1:.2f}, Onset F1={homr_res.onset_f1:.2f}")
        except Exception as e:
            print(f"  HOMR failed: {e}")

        try:
            out_dir = Path(f"zeus_eval_tmp_{i}")
            out_dir.mkdir(exist_ok=True)
            t0 = time.time()
            infer_zeus_document(image_path, out_dir)
            zeus_result_path = out_dir / "omr-result.json"
            if not zeus_result_path.exists():
                raise ValueError("omr-result.json not found")
            z_doc = json.loads(zeus_result_path.read_text("utf-8"))
            z_notes = []
            for item in z_doc.get("notes", []):
                z_notes.append(MetricNote(
                    pitch=int(item["midi_pitch"]),
                    onset=_fraction(item["start_beat"]),
                    duration=_fraction(item["duration_beats"]),
                    staff=0, 
                    voice="1",
                ))
            if not z_notes:
                raise ValueError("No notes")
            zeus_res = calculate_note_metrics(z_notes, gt_notes)
            zeus_metrics.append((time.time()-t0, zeus_res))
            print(f"  Zeus: Pitch F1={zeus_res.pitch_f1:.2f}, Onset F1={zeus_res.onset_f1:.2f}")
        except Exception as e:
            print(f"  Zeus failed: {e}")

    def avg(lst): return sum(lst)/len(lst) if lst else 0
    
    print("\n--- RESULTS ---")
    print(f"HOMR Evaluated: {len(homr_metrics)}")
    print(f"HOMR Pitch F1: {avg([r.pitch_f1 for _,r in homr_metrics]):.3f}")
    print(f"HOMR Onset F1: {avg([r.onset_f1 for _,r in homr_metrics]):.3f}")
    print(f"HOMR Time/sys: {avg([t for t,_ in homr_metrics]):.2f}s")
    
    print(f"\nZeus Evaluated: {len(zeus_metrics)}")
    print(f"Zeus Pitch F1: {avg([r.pitch_f1 for _,r in zeus_metrics]):.3f}")
    print(f"Zeus Onset F1: {avg([r.onset_f1 for _,r in zeus_metrics]):.3f}")
    print(f"Zeus Time/sys: {avg([t for t,_ in zeus_metrics]):.2f}s")

if __name__ == "__main__":
    run_eval()
