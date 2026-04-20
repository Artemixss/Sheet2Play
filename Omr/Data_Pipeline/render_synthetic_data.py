import os
import subprocess

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

INPUT_DIR = os.path.join(SCRIPT_DIR, "input_xml")
OUTPUT_DIR = os.path.join(SCRIPT_DIR, "output_svg")

MUSESCORE_PATH = r"C:\Program Files\MuseScore 4\bin\MuseScore4.exe" 

def batch_render_xml_to_svg():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    for filename in os.listdir(INPUT_DIR):
        if filename.endswith(".xml") or filename.endswith(".mxl"):
            input_path = os.path.join(INPUT_DIR, filename)

            base_name = filename.rsplit('.', 1)[0]
            output_path = os.path.join(OUTPUT_DIR, f"{base_name}.svg")

            print(f"Rendering: {filename} -> SVG...")

            command = [MUSESCORE_PATH, "-o", output_path, input_path]
            
            try:
                subprocess.run(command, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                print(f"SUCCESS: {base_name}.svg created.")
            except subprocess.CalledProcessError:
                print(f"FAILED: Could not render {filename}")

if __name__ == "__main__":
    batch_render_xml_to_svg()
    print("\nBatch rendering complete. Check your output_svg folder.")