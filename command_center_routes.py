"""
COMMAND CENTER ROUTES
Global command center portal and property status API.
"""
from flask import Blueprint, render_template, session, jsonify
from datetime import datetime
import json

command_center_bp = Blueprint("command_center", __name__)

from decorators import login_required
from config import BASE_DIR, WO_JSON

# =====================================================
# COMMAND CENTER PORTAL
# =====================================================
@command_center_bp.route("/command_center")
@login_required
def command_center():
    """
    Global Command Center — portfolio-wide operations.
    Accessible to all authenticated users; property-level
    access is enforced inside the page via JS + breakdown APIs.
    """
    print(f"\n🌐 Command Center - User: {session.get('user')} | Role: {session.get('role')}")
    return render_template("command_center.html")


# =====================================================
# PROPERTY STATUS API
# =====================================================
@command_center_bp.route("/api/properties/status")
@login_required
def api_properties_status():
    """Live status for all 5 properties — feeds Overview table in Command Center."""

    wo_counts = {p: 0 for p in ["SLN Terminus", "ONEWEST", "The District",
                                  "One Golden Mile", "Nine Hills"]}
    try:
        if WO_JSON.exists():
            with open(WO_JSON, encoding="utf-8") as f:
                wos = json.load(f).get("work_orders", [])
            open_statuses = {"open", "in-progress", "overdue"}
            for wo in wos:
                prop = wo.get("location", wo.get("property", ""))
                if prop in wo_counts and wo.get("status", "").lower() in open_statuses:
                    wo_counts[prop] += 1
    except Exception as e:
        print(f"⚠️  api_properties_status WO read: {e}")

    alert_counts = {p: 0 for p in wo_counts}
    try:
        bd_file = BASE_DIR / "static" / "data" / "breakdown_data.json"
        if bd_file.exists():
            with open(bd_file, encoding="utf-8") as f:
                bd = json.load(f)
            for ticket in bd.get("engineering_breakdowns", []):
                prop = ticket.get("property", "")
                if prop in alert_counts and ticket.get("status") not in ("Resolved", "Closed"):
                    alert_counts[prop] += 1
    except Exception as e:
        print(f"⚠️  api_properties_status breakdown read: {e}")

    properties = [
        {"id": "sln", "name": "SLN Terminus",    "code": "SLN", "type": "Commercial",
         "city": "Hyderabad", "status": "online",    "redirect": "/sln_terminus",
         "open_wo": wo_counts["SLN Terminus"],    "alerts": alert_counts["SLN Terminus"],
         "occupancy": None, "energy": None},
        {"id": "ow",  "name": "ONEWEST",          "code": "OW",  "type": "Commercial",
         "city": "Hyderabad", "status": "online",    "redirect": "/onewest",
         "open_wo": wo_counts["ONEWEST"],          "alerts": alert_counts["ONEWEST"],
         "occupancy": None, "energy": None},
        {"id": "td",  "name": "The District",     "code": "TD",  "type": "Commercial",
         "city": "Hyderabad", "status": "attention", "redirect": "/the_district",
         "open_wo": wo_counts["The District"],     "alerts": alert_counts["The District"],
         "occupancy": None, "energy": None},
        {"id": "ogm", "name": "One Golden Mile",  "code": "OGM", "type": "Commercial",
         "city": "Hyderabad", "status": "online",    "redirect": "/ogm",
         "open_wo": wo_counts["One Golden Mile"],  "alerts": alert_counts["One Golden Mile"],
         "occupancy": None, "energy": None},
        {"id": "nh",  "name": "Nine Hils",        "code": "NH",  "type": "Life Science",
         "city": "Hyderabad", "status": "online",    "redirect": "/nine_hills/",
         "open_wo": wo_counts["Nine Hills"],       "alerts": alert_counts["Nine Hills"],
         "occupancy": None, "energy": None},
    ]

    return jsonify({
        "success":      True,
        "properties":   properties,
        "generated_at": datetime.now().isoformat(),
    })
