import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))

from zeus_runner import ZeusRunner, lmx_to_musicxml

def main():
    model_dir = _HERE / "weights" / "zeus-olimpic-1.0-2024-02-12.model"
    image_path = _HERE.parent / "data" / "olimpic" / "olimpic-1.0-scanned" / "samples" / "6586696" / "p4-s1.png"
    output_xml = _HERE / "p4-s1.musicxml"
    
    print(f"Loading model from {model_dir}")
    runner = ZeusRunner(model_dir)
    
    print(f"Predicting on {image_path}")
    lmx = runner.predict_image(image_path)
    
    print("Predicted LMX:")
    print(lmx[:200] + "...")
    
    print(f"Saving to {output_xml}")
    lmx_to_musicxml(lmx, output_xml)
    print("Done!")

if __name__ == "__main__":
    main()
