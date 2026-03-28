"""Emergency work order generator - bypasses date parsing issues"""
import json
from pathlib import Path
from datetime import datetime

# Create dummy work orders for today
work_orders = [
    {
        "work_order_id": "WO-PPM-2026-02-0001",
        "asset_id": "HT I/C VCB-1",
        "asset_name": "HT Panel I/C Source -1 VCB",
        "location": "HT Room",
        "due_date": "2026-02-01",
        "priority": "High",
        "status": "overdue",
        "created_at": datetime.now().isoformat()
    },
    {
        "work_order_id": "WO-PPM-2026-02-0002",
        "asset_id": "DG-01",
        "asset_name": "DG set-1 1500 KVA",
        "location": "DG Room",
        "due_date": "2026-02-01",
        "priority": "High",
        "status": "open",
        "created_at": datetime.now().isoformat()
    },
    {
        "work_order_id": "WO-PPM-2026-02-0003",
        "asset_id": "TR-1",
        "asset_name": "Transformer-1 - 1600KVA",
        "location": "Transformer Room",
        "due_date": "2026-02-02",
        "priority": "Medium",
        "status": "open",
        "created_at": datetime.now().isoformat()
    }
]

# Save to work_orders.json
WO_JSON = Path("static/data/work_orders.json")
WO_JSON.parent.mkdir(parents=True, exist_ok=True)

with open(WO_JSON, 'w') as f:
    json.dump({
        "work_orders": work_orders,
        "last_updated": datetime.now().isoformat(),
        "total_count": len(work_orders)
    }, f, indent=2)

print(f"✅ Created {len(work_orders)} sample work orders")
print(f"✅ Saved to: {WO_JSON}")
print("✅ Refresh PPM Dashboard → Work Orders tab to see them!")