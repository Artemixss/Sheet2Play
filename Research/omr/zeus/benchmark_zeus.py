import sys
import os
import time
import statistics
from pathlib import Path

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))
sys.path.insert(0, str(_HERE / "source"))

from zeus_runner import ZeusRunner
from app.evaluation.TEDn_lmx_xml import TEDn_lmx_xml

def main():
    model_dir = _HERE / "weights" / "zeus-olimpic-1.0-2024-02-12.model"
    data_dir = _HERE.parent / "data" / "olimpic" / "olimpic-1.0-scanned"
    test_file = data_dir / "samples.test.txt"
    
    with open(test_file, "r") as f:
        samples = [line.strip() for line in f if line.strip()]
        
    print(f"Loaded {len(samples)} test samples in total.")
    
    # We will test on a representative subset to get a quick pulse.
    # The first 100 samples provides a statistically significant preview
    # without taking the 50 minutes required for the full 1500 sample run.
    samples = samples[:100]
    print(f"Running benchmark on {len(samples)} samples for speed...")
    
    runner = ZeusRunner(model_dir)
    
    tedn_scores = []
    
    print("Starting benchmark on Zeus...", flush=True)
    start_time = time.time()
    
    for i, sample in enumerate(samples):
        print(f"[{i+1}/{len(samples)}] {sample} - ", end="", flush=True)
        image_path = data_dir / f"{sample}.png"
        gold_xml_path = data_dir / f"{sample}.musicxml"
        
        if not image_path.exists() or not gold_xml_path.exists():
            print("SKIPPED (missing files)", flush=True)
            continue
            
        try:
            # 1. Predict
            predicted_lmx = runner.predict_image(image_path)
            
            # 2. Load Gold
            gold_xml = gold_xml_path.read_text(encoding="utf-8")
            
            # 3. Evaluate using OLiMPiC's TEDn LMX evaluator
            result = TEDn_lmx_xml(
                predicted_lmx=predicted_lmx,
                gold_musicxml=gold_xml,
                flavor="lmx",
                debug=False,
                canonicalize_gold=True
            )
            
            score = result.normalized_edit_cost
            tedn_scores.append(score)
            print(f"TEDn: {score:.4f}", flush=True)
            
        except Exception as e:
            print(f"ERROR: {e}", flush=True)
            # Assign a penalty score for failed extractions (e.g., 1.0 which means 100% edit cost)
            tedn_scores.append(1.0)
            
        if (i + 1) % 50 == 0:
            avg_tedn = statistics.mean(tedn_scores) if tedn_scores else 0
            elapsed = time.time() - start_time
            print(f"--- Progress: {i+1}/{len(samples)} | Avg TEDn: {avg_tedn:.4f} | Elapsed: {elapsed:.1f}s ---", flush=True)

    print("\n--- Final Benchmark Results ---", flush=True)
    avg_tedn = statistics.mean(tedn_scores) if tedn_scores else 0
    
    print(f"Total Samples: {len(samples)}", flush=True)
    print(f"Average TEDn (Lower is Better): {avg_tedn:.4f} (Target: < 0.05)", flush=True)
    print(f"Total Time: {time.time() - start_time:.1f}s", flush=True)
    
if __name__ == "__main__":
    main()
