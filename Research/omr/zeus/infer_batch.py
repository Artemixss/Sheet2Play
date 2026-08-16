import sys
import os
import json
import time
from pathlib import Path
from PIL import Image

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))
sys.path.insert(0, str(_HERE / "source"))

from zeus_runner import ZeusRunner
from zeus_runner import lmx_to_musicxml

def main():
    if len(sys.argv) < 3:
        print("Usage: python infer_batch.py <input_json> <output_dir>")
        sys.exit(1)
        
    input_json = Path(sys.argv[1])
    output_dir = Path(sys.argv[2])
    output_dir.mkdir(parents=True, exist_ok=True)
    
    with open(input_json, "r", encoding="utf-8-sig") as f:
        images_to_process = json.load(f) # list of dicts: {"page": 1, "path": "..."}
        
    model_dir = _HERE / "weights" / "zeus-olimpic-1.0-2024-02-12.model"
    runner = ZeusRunner(model_dir)
    
    results = []
    
    for item in images_to_process:
        page_num = item["page"]
        img_path = item["path"]
        
        start = time.time()
        
        try:
            # Predict
            lmx = runner.predict_image(img_path)
            
            # Save XML
            out_xml = output_dir / f"page-{page_num:04d}.musicxml"
            
            lmx_to_musicxml(lmx, out_xml)
            
            elapsed = time.time() - start
            results.append({
                "page": page_num,
                "status": "success",
                "seconds": elapsed,
                "xml_path": str(out_xml.resolve())
            })
            
        except Exception as e:
            results.append({
                "page": page_num,
                "status": "error",
                "error": str(e),
                "seconds": time.time() - start
            })
            
    # Write summary
    summary_path = output_dir / "zeus_summary.json"
    with open(summary_path, "w") as f:
        json.dump(results, f, indent=2)

if __name__ == "__main__":
    main()
