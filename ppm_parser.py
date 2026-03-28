# ppm_parser.py
import json
from pathlib import Path

DATA_FILE = Path("static/data/ppm_data.json")

def load_assets():
    if not DATA_FILE.exists():
        return []
    return json.loads(DATA_FILE.read_text()).get("assets", [])

def load_schedule():
    if not DATA_FILE.exists():
        return []
    return json.loads(DATA_FILE.read_text()).get("schedules", [])
