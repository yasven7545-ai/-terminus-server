import json
from pathlib import Path
from ppm.ppm_model import mark_overdue

DATA_FILE = Path("static/data/ppm_data.json")

def update_overdue_ppms():
    data = json.loads(DATA_FILE.read_text())

    for ppm in data["schedules"]:
        mark_overdue(ppm)

    DATA_FILE.write_text(json.dumps(data, indent=2))
