from openpyxl import Workbook
import json
from pathlib import Path

DATA_FILE = Path("static/data/ppm_data.json")

def export_history_excel(filepath):
    data = json.loads(DATA_FILE.read_text())
    history = data.get("history", [])

    wb = Workbook()
    ws = wb.active
    ws.title = "Work Order History"

    ws.append([
        "Work Order No",
        "Asset ID",
        "Frequency",
        "Action",
        "Date",
        "Remarks"
    ])

    for h in history:
        ws.append([
            h.get("workOrderNo"),
            h.get("assetId"),
            h.get("frequency"),
            h.get("action"),
            h.get("actionDate"),
            h.get("remarks")
        ])

    wb.save(filepath)
