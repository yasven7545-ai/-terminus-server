from pathlib import Path
import json

DATA_FILE = Path("static/data/ppm_data.json")

ID_MAP = {
}

def migrate():
    data = json.loads(DATA_FILE.read_text())

    for a in data.get("assets", []):
        if a["id"] in ID_MAP:
            a["id"] = ID_MAP[a["id"]]

    for s in data.get("schedules", []):
        if s.get("assetId") in ID_MAP:
            s["assetId"] = ID_MAP[s["assetId"]]

    for h in data.get("history", []):
        if h.get("assetId") in ID_MAP:
            h["assetId"] = ID_MAP[h["assetId"]]

    DATA_FILE.write_text(json.dumps(data, indent=2))

if __name__ == "__main__":
    migrate()
