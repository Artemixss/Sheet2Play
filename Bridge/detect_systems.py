import sys
import json
from pathlib import Path

# Add Bridge dir to path to import homr_gpu
bridge_dir = Path(__file__).resolve().parent
if str(bridge_dir) not in sys.path:
    sys.path.insert(0, str(bridge_dir))

import homr_gpu
homr_gpu.configure_cuda()

from homr.main import ProcessingConfig, detect_staffs_in_image

def main():
    if len(sys.argv) != 3:
        print("Usage: detect_systems.py <input_image> <output_json>")
        sys.exit(1)
        
    image_path = sys.argv[1]
    output_json = sys.argv[2]
    
    config = ProcessingConfig(
        enable_debug=False,
        enable_cache=False,
        write_staff_positions=False,
        read_staff_positions=False,
        selected_staff=0,
        transformer_use_gpu=True,
        segnet_use_gpu=True,
        coreml_encoder=False
    )
    
    multi_staffs, _, _, _ = detect_staffs_in_image(image_path, config)
    
    systems = []
    for multi in multi_staffs:
        min_x = float(min(staff.min_x for staff in multi.staffs))
        max_x = float(max(staff.max_x for staff in multi.staffs))
        min_y = float(min(staff.min_y for staff in multi.staffs))
        max_y = float(max(staff.max_y for staff in multi.staffs))
        
        # Add some margin
        height = max_y - min_y
        min_y = max(0, min_y - height * 0.2)
        max_y = max_y + height * 0.2
        
        systems.append({
            "min_x": min_x,
            "max_x": max_x,
            "min_y": min_y,
            "max_y": max_y
        })
        
    with open(output_json, "w", encoding="utf-8") as f:
        json.dump({"systems": systems}, f, indent=2)

if __name__ == "__main__":
    main()
