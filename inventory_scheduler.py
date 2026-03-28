"""
inventory_scheduler.py

Isolated scheduler that evaluates inventory once per day and writes inventory_alerts.json.
Designed to be started from server.py (safe, non-blocking).

Usage:
    import inventory_scheduler
    inventory_scheduler.start()   # starts a background daemon thread

Notes:
 - Reads INVENTORY_MASTER_FILE env var or defaults to <project_root>/uploads/inventory_master.xlsx
 - Writes inventory_alerts.json next to this file (same directory)
"""

import threading
import time
import os
from pathlib import Path
import pandas as pd
import json

def get_inventory_path():
    env = os.getenv("INVENTORY_MASTER_FILE")
    if env:
        p = Path(env)
        if p.exists():
            return p
    p2 = Path(__file__).parent.resolve() / "uploads" / "inventory_master.xlsx"
    if p2.exists():
        return p2
    p3 = Path(__file__).parent.resolve() / "static" / "data" / "inventory_master.xlsx"
    if p3.exists():
        return p3
    return p2

def evaluate_inventory_alerts():
    inv_path = get_inventory_path()
    alerts = []
    if not inv_path.exists():
        # no inventory file — clear alerts file
        alerts_path = Path(__file__).parent.resolve() / "inventory_alerts.json"
        try:
            with open(alerts_path, "w") as f:
                json.dump([], f)
        except Exception:
            pass
        return

    try:
        df = pd.read_excel(inv_path)
    except Exception:
        return

    # Normalize columns
    cols = {c.strip().lower(): c for c in df.columns}
    def find_col(keys):
        for k in keys:
            if k in cols:
                return cols[k]
        return None

    item_col = find_col(["item_code","item","item_name","item code"])
    dept_col = find_col(["department","dept"])
    qty_col = find_col(["current_stock","qty","quantity","current"])
    min_col = find_col(["min_stock_level","min_stock","minimum","min level","min_level"])

    if not dept_col or not qty_col or not min_col:
        # Not enough columns to evaluate
        return

    for _, row in df.iterrows():
        try:
            qty = int(row.get(qty_col, 0) or 0)
            minimum = int(row.get(min_col, 0) or 0)
        except Exception:
            continue
        if qty <= minimum:
            alerts.append({
                "item": str(row.get(item_col, "")) if item_col else "",
                "department": str(row.get(dept_col, "")),
                "qty": qty,
                "min": minimum
            })

    alerts_path = Path(__file__).parent.resolve() / "inventory_alerts.json"
    try:
        with open(alerts_path, "w") as f:
            json.dump(alerts, f, indent=2)
    except Exception:
        pass

def _loop(interval_sec=60*60):
    """
    Loop that runs evaluate_inventory_alerts() once every day.
    For robustness in container/test environments the loop checks every interval_sec seconds.
    """
    while True:
        try:
            evaluate_inventory_alerts()
        except Exception:
            pass
        # Sleep for 1 hour and repeat; main check is daily logic inside evaluate() if needed.
        time.sleep(interval_sec)

_worker = None

def start():
    global _worker
    if _worker and _worker.is_alive():
        return
    _worker = threading.Thread(target=_loop, kwargs={"interval_sec":60*60}, daemon=True)
    _worker.start()

# If imported directly we don't auto-start; server.py should call inventory_scheduler.start()
