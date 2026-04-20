import os
import re
from bs4 import BeautifulSoup
from svgpathtools import parse_path

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SVG_DIR = os.path.join(SCRIPT_DIR, "output_svg")

# --- THE TOKEN VOCABULARY ---
# YOLO requires integer IDs. We will expand this list as we find new symbols.
CLASS_MAP = {
    "Note": 0,
    "TrebleClef": 1,
    "BassClef": 2,
    "TimeSig": 3,
    "MeasureNumber": 4,
    "BarLine": 5,
    "Rest": 6,
    "StaffLines": 7
}

def convert_to_yolo(svg_filename):
    svg_path = os.path.join(SVG_DIR, svg_filename)
    txt_filename = svg_filename.replace('.svg', '.txt')
    txt_path = os.path.join(SVG_DIR, txt_filename)
    
    with open(svg_path, 'r', encoding='utf-8') as file:
        soup = BeautifulSoup(file, 'xml')
    
    # 1. Find the Page Dimensions to normalize the YOLO coordinates
    page_width, page_height = 3319.9, 4555.4 # Default fallbacks
    page_rect = soup.find('path', class_=False)
    if page_rect and page_rect.get('d'):
        try:
            xmin, xmax, ymin, ymax = parse_path(page_rect.get('d')).bbox()
            page_width = xmax - xmin
            page_height = ymax - ymin
        except: pass

    # 2. Look for <use> tags (which place symbols on the page) and <path> tags
    elements = soup.find_all(['use', 'path'])
    
    yolo_lines = []
    
    for tag in elements:
        element_class = tag.get('class')
        if not element_class: continue
        
        class_id = CLASS_MAP.get(element_class, -1)
        if class_id == -1: continue 
        
        xmin, xmax, ymin, ymax = 0, 0, 0, 0
        valid_box = False
        
        # 1. Get the base bounding box (Path vs Use)
        if tag.name == 'path' and tag.get('d'):
            try:
                xmin, xmax, ymin, ymax = parse_path(tag.get('d')).bbox()
                valid_box = True
            except: pass
        elif tag.name == 'use':
            x_offset = float(tag.get('x', 0))
            y_offset = float(tag.get('y', 0))
            xmin = x_offset
            xmax = x_offset + 15 
            if element_class == "BarLine":
                ymin = y_offset
                ymax = y_offset + 120 
            else:
                ymin = y_offset - 30
                ymax = y_offset
            valid_box = True
        elif tag.name == 'polyline' and tag.get('points'):
            # 1. Extract the raw string: "X1,Y1 X2,Y2"
            points_str = tag.get('points')
            
            # 2. Slice the string into mathematical pairs
            try:
                pairs = [p.split(',') for p in points_str.strip().split()]
                x_coords = [float(p[0]) for p in pairs if len(p) == 2]
                y_coords = [float(p[1]) for p in pairs if len(p) == 2]
                
                if x_coords and y_coords:
                    xmin = min(x_coords)
                    xmax = max(x_coords)
                    ymin = min(y_coords)
                    ymax = max(y_coords)
                    
                    # 3. The YOLO Padding Fix
                    # If the line is perfectly vertical, give it a tiny width
                    if xmax - xmin < 1:
                        xmax += 5
                        xmin -= 5
                        
                    valid_box = True
            except: pass

        if not valid_box: continue

        # 2. GLOBAL TREE CLIMB: Apply parent translations to ALL elements
        for parent in tag.parents:
            if parent.name == 'g' and parent.get('transform'):
                transform_str = parent.get('transform')
                match = re.search(r'translate\(([-\d.]+)[,\s]+([-\d.]+)\)', transform_str)
                if match:
                    dx = float(match.group(1))
                    dy = float(match.group(2))
                    # Shift the entire bounding box by the parent's translation
                    xmin += dx
                    xmax += dx
                    ymin += dy
                    ymax += dy

        # 3. The YOLO Math (Normalization)
        raw_width = xmax - xmin
        raw_height = ymax - ymin
        
        center_x = xmin + (raw_width / 2.0)
        center_y = ymin + (raw_height / 2.0)
        
        norm_x = center_x / page_width
        norm_y = center_y / page_height
        norm_w = raw_width / page_width
        norm_h = raw_height / page_height
        
        if norm_w > 0 and norm_h > 0 and norm_x >= 0 and norm_y >= 0:
            yolo_lines.append(f"{class_id} {norm_x:.6f} {norm_y:.6f} {norm_w:.6f} {norm_h:.6f}")

    # 4. Save the perfect labels
    if yolo_lines:
        with open(txt_path, 'w') as f:
            f.write("\n".join(yolo_lines))
        print(f"SUCCESS: Generated YOLO labels for {svg_filename} ({len(yolo_lines)} symbols)")

if __name__ == "__main__":
    # Run conversion on all SVGs in the folder
    for filename in os.listdir(SVG_DIR):
        if filename.endswith(".svg"):
            convert_to_yolo(filename)