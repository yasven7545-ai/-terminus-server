from pathlib import Path
import json
import re

DATA_FILE = Path("static/data/ppm_data.json")

def normalize(raw):
    s = raw.upper()
    s = re.sub(r"[’']", "", s)
    s = re.sub(r"[^A-Z0-9]+", "_", s)
    s = re.sub(r"_+", "_", s)
    return s.strip("_")

def generate():
    data = json.loads(DATA_FILE.read_text())

    id_map = {}
    for a in data.get("assets", []):
        old = a["id"]
        new = normalize(old)
        if old != new:
            id_map[old] = new

    print("ID_MAP = {")
    for k, v in id_map.items():
        print(f'    "{k}": "{v}",')
    print("}")

if __name__ == "__main__":
    generate()
