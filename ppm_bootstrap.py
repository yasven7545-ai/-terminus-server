from datetime import date
from dateutil.relativedelta import relativedelta
from pathlib import Path
import json

DATA_FILE = Path("static/data/ppm_data.json")
HORIZON_MONTHS = 12

FREQ_STEP = {
    "Monthly": relativedelta(months=1),
    "Quarterly": relativedelta(months=3),
    "Yearly": relativedelta(years=1),
}

def load_data():
    return json.loads(DATA_FILE.read_text())

def save_data(data):
    DATA_FILE.write_text(json.dumps(data, indent=2))

def generate_schedules(asset, existing_keys):
    """
    Generate schedules strictly based on asset['frequencies']
    """
    last = asset.get("lastService")
    if not isinstance(last, str):
        return []

    start = date.fromisoformat(last)
    today = date.today()
    horizon = today + relativedelta(months=HORIZON_MONTHS)

    out = []

    for freq in asset.get("frequencies", []):
        step = FREQ_STEP.get(freq)
        if not step:
            continue

        due = start + step

        # 🔴 YEARLY → ONLY ONE ENTRY
        if freq == "Yearly":
            if today <= due <= horizon:
                key = (asset["id"], freq, due.isoformat())
                if key not in existing_keys:
                    out.append({
                        "assetId": asset["id"],
                        "assetName": asset.get("name", ""),
                        "frequency": freq,
                        "date": due.isoformat(),
                        "assigned": False,
                        "completed": False,
                        "status": "Scheduled"
                    })
                    existing_keys.add(key)
            continue

        # 🟢 Monthly / Quarterly → recurring
        while due <= horizon:
            if due >= today:
                key = (asset["id"], freq, due.isoformat())
                if key not in existing_keys:
                    out.append({
                        "assetId": asset["id"],
                        "assetName": asset.get("name", ""),
                        "frequency": freq,
                        "date": due.isoformat(),
                        "assigned": False,
                        "completed": False,
                        "status": "Scheduled"
                    })
                    existing_keys.add(key)
            due += step

    return out

def bootstrap():
    data = load_data()

    assets = data.get("assets", [])
    schedules = data.setdefault("schedules", [])

    # Track existing schedules to prevent duplication
    existing_keys = {
        (s["assetId"], s["frequency"], s["date"])
        for s in schedules
    }

    added = 0
    for asset in assets:
        new_items = generate_schedules(asset, existing_keys)
        schedules.extend(new_items)
        added += len(new_items)

    save_data(data)

    print("BOOTSTRAP COMPLETE")
    print("Assets     :", len(assets))
    print("Schedules  :", len(schedules))
    print("Added      :", added)

if __name__ == "__main__":
    bootstrap()
