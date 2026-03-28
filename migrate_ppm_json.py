import json
from pathlib import Path
from datetime import datetime

DATA_FILE = Path("static/data/ppm_data.json")

def migrate():
    data = json.loads(DATA_FILE.read_text(encoding="utf-8"))

    new_schedules = []
    counter = 1

    for s in data.get("schedules", []):
        ppm_id = f"PPM-2026-01-{counter:04d}"
        counter += 1

        scheduled_date = s.get("scheduled_date") or s.get("date")

        status = s.get("status", "").lower()
        if status in ("closed", "completed"):
            new_status = "completed"
        else:
            new_status = "scheduled"

        new_schedules.append({
            "ppm_id": ppm_id,
            "asset_id": s.get("asset_id") or s.get("asset"),
            "task": s.get("task", "PPM Task"),
            "scheduled_date": scheduled_date,
            "assigned_to": s.get("assigned_to", "tech_01"),

            "status": new_status,

            "execution": {
                "started_at": None,
                "completed_at": None,
                "checklist": {},
                "readings": {},
                "remarks": "",
                "evidence": []
            },

            "audit": {
                "created_by": "migration",
                "created_at": datetime.now().isoformat(),
                "completed_by": None,
                "verified_by": None,
                "verified_at": None
            }
        })

    data["schedules"] = new_schedules
    DATA_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")
    print("PPM migration completed")

if __name__ == "__main__":
    migrate()
