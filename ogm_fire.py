"""
OGM FIRE FIGHTING MODULE — ROUTES
ogm_fire.py
Blueprint prefix : /ogm_fire
All names prefixed: ogm_fire_

CRITICAL: All /api/* routes ALWAYS return application/json — never HTML.
"""

from flask import Blueprint, render_template, request, jsonify, session, redirect, make_response, send_file
from datetime import datetime
from pathlib import Path
import json

# ── Blueprint ─────────────────────────────────────────────────────────────────
ogm_fire_bp = Blueprint("ogm_fire_bp", __name__, url_prefix="/ogm_fire")

# ── Data storage ──────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).parent.resolve()
DATA_DIR  = BASE_DIR / "static" / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

OGM_FIRE_ASSETS_FILE      = DATA_DIR / "ogm_fire_assets.json"
OGM_FIRE_ALARMS_FILE      = DATA_DIR / "ogm_fire_alarms.json"
OGM_FIRE_INSPECTIONS_FILE = DATA_DIR / "ogm_fire_inspections.json"
OGM_FIRE_MAINTENANCE_FILE = DATA_DIR / "ogm_fire_maintenance.json"
OGM_FIRE_INCIDENTS_FILE   = DATA_DIR / "ogm_fire_incidents.json"
OGM_FIRE_TEAM_FILE        = DATA_DIR / "ogm_fire_team.json"
OGM_FIRE_DRILLS_FILE      = DATA_DIR / "ogm_fire_drills.json"

# ── Helpers ───────────────────────────────────────────────────────────────────
def ogm_fire_load(path, default=None):
    if default is None:
        default = []
    try:
        if path.exists():
            with open(path) as f:
                return json.load(f)
    except Exception:
        pass
    return default

def ogm_fire_save(path, data):
    with open(path, "w") as f:
        json.dump(data, f, indent=2, default=str)

def ogm_fire_uid():
    return f"OGM_FIRE_{int(datetime.now().timestamp()*1000)}"

def ogm_fire_now():
    return datetime.now().isoformat()

def ogm_fire_json(data, status=200):
    r = make_response(jsonify(data), status)
    r.headers["Content-Type"] = "application/json"
    return r

def ogm_fire_is_api():
    return (
        request.headers.get("X-Requested-With") == "XMLHttpRequest"
        or "application/json" in request.headers.get("Accept", "")
        or "/api/" in request.path
    )

def ogm_fire_auth_check():
    if "user" not in session:
        if ogm_fire_is_api():
            return ogm_fire_json({"error": "Unauthorized — please log in"}, 401)
        return redirect("/login")
    return None


# ── Page route ────────────────────────────────────────────────────────────────
@ogm_fire_bp.route("/", methods=["GET"])
@ogm_fire_bp.route("", methods=["GET"])
def ogm_fire_index():
    guard = ogm_fire_auth_check()
    if guard:
        return guard
    session["active_property"] = "One Golden Mile"
    return render_template("ogm_fire.html")


# ═══════════════════════════════════════════════════════════════════════════════
# DASHBOARD
# ═══════════════════════════════════════════════════════════════════════════════
@ogm_fire_bp.route("/api/dashboard", methods=["GET"])
def ogm_fire_dashboard():
    guard = ogm_fire_auth_check()
    if guard: return guard

    assets      = ogm_fire_load(OGM_FIRE_ASSETS_FILE)
    alarms      = ogm_fire_load(OGM_FIRE_ALARMS_FILE)
    inspections = ogm_fire_load(OGM_FIRE_INSPECTIONS_FILE)
    maintenance = ogm_fire_load(OGM_FIRE_MAINTENANCE_FILE)
    incidents   = ogm_fire_load(OGM_FIRE_INCIDENTS_FILE)
    drills      = ogm_fire_load(OGM_FIRE_DRILLS_FILE)

    active_assets  = [a for a in assets if a.get("status") == "active"]
    faulty_assets  = [a for a in assets if a.get("status") == "faulty"]
    expired_assets = [a for a in assets if a.get("status") == "expired"]
    active_alarms  = [a for a in alarms  if a.get("status") == "active"]
    pending_maint  = [m for m in maintenance if m.get("status") in ("Scheduled", "Overdue")]
    open_incidents = [i for i in incidents   if i.get("status") not in ("Closed", "Resolved")]
    failed_insp    = [i for i in inspections if i.get("status") == "faulty"]

    total = len(assets) or 1
    compliance_pct = round((len(active_assets) / total) * 100)
    today = datetime.now().strftime("%Y-%m-%d")

    last_drill = None
    if drills:
        last_drill = sorted(drills, key=lambda d: d.get("date", ""), reverse=True)[0]

    return ogm_fire_json({
        "active_alarms":      len(active_alarms),
        "total_assets":       len(assets),
        "active_assets":      len(active_assets),
        "faulty_assets":      len(faulty_assets),
        "expired_assets":     len(expired_assets),
        "pending_maint":      len(pending_maint),
        "open_incidents":     len(open_incidents),
        "failed_inspections": len(failed_insp),
        "compliance_pct":     compliance_pct,
        "total_drills":       len(drills),
        "last_drill":         last_drill,
        "alarms_today":       len([a for a in alarms if a.get("triggered_at", "").startswith(today)]),
    })


# ═══════════════════════════════════════════════════════════════════════════════
# ASSETS
# ═══════════════════════════════════════════════════════════════════════════════
@ogm_fire_bp.route("/api/assets", methods=["GET"])
def ogm_fire_get_assets():
    guard = ogm_fire_auth_check()
    if guard: return guard
    assets = ogm_fire_load(OGM_FIRE_ASSETS_FILE)
    if request.args.get("type"):
        assets = [a for a in assets if a.get("asset_type") == request.args["type"]]
    if request.args.get("status"):
        assets = [a for a in assets if a.get("status") == request.args["status"]]
    return ogm_fire_json(assets)

@ogm_fire_bp.route("/api/assets", methods=["POST"])
def ogm_fire_add_asset():
    guard = ogm_fire_auth_check()
    if guard: return guard
    data   = request.get_json(force=True, silent=True) or {}
    assets = ogm_fire_load(OGM_FIRE_ASSETS_FILE)
    asset  = {
        "id": ogm_fire_uid(), "property_id": "One Golden Mile",
        "zone_id": data.get("zone_id",""), "asset_type": data.get("asset_type","extinguisher"),
        "asset_code": data.get("asset_code",""), "location": data.get("location",""),
        "capacity": data.get("capacity",""), "installation_date": data.get("installation_date",""),
        "last_inspection_date": data.get("last_inspection_date",""),
        "next_due_date": data.get("next_due_date",""), "status": data.get("status","active"),
        "remarks": data.get("remarks",""), "created_at": ogm_fire_now(),
    }
    assets.insert(0, asset)
    ogm_fire_save(OGM_FIRE_ASSETS_FILE, assets)
    return ogm_fire_json({"success": True, "asset": asset})

@ogm_fire_bp.route("/api/assets/<aid>", methods=["PATCH"])
def ogm_fire_update_asset(aid):
    guard = ogm_fire_auth_check()
    if guard: return guard
    data   = request.get_json(force=True, silent=True) or {}
    assets = ogm_fire_load(OGM_FIRE_ASSETS_FILE)
    for a in assets:
        if a["id"] == aid:
            a.update({k: v for k, v in data.items() if k != "id"})
            a["updated_at"] = ogm_fire_now()
            break
    ogm_fire_save(OGM_FIRE_ASSETS_FILE, assets)
    return ogm_fire_json({"success": True})

@ogm_fire_bp.route("/api/assets/<aid>", methods=["DELETE"])
def ogm_fire_delete_asset(aid):
    guard = ogm_fire_auth_check()
    if guard: return guard
    assets = [a for a in ogm_fire_load(OGM_FIRE_ASSETS_FILE) if a["id"] != aid]
    ogm_fire_save(OGM_FIRE_ASSETS_FILE, assets)
    return ogm_fire_json({"success": True})


# ═══════════════════════════════════════════════════════════════════════════════
# ALARMS
# ═══════════════════════════════════════════════════════════════════════════════
@ogm_fire_bp.route("/api/alarms", methods=["GET"])
def ogm_fire_get_alarms():
    guard = ogm_fire_auth_check()
    if guard: return guard
    return ogm_fire_json(ogm_fire_load(OGM_FIRE_ALARMS_FILE))

@ogm_fire_bp.route("/api/alarms/trigger", methods=["POST"])
def ogm_fire_trigger_alarm():
    guard = ogm_fire_auth_check()
    if guard: return guard
    data   = request.get_json(force=True, silent=True) or {}
    alarms = ogm_fire_load(OGM_FIRE_ALARMS_FILE)
    alarm  = {
        "id": ogm_fire_uid(), "property_id": "One Golden Mile",
        "zone_id": data.get("zone_id",""), "zone_name": data.get("zone_name",""),
        "alarm_type": data.get("alarm_type","smoke"), "source_device_id": data.get("source_device_id",""),
        "triggered_at": ogm_fire_now(), "status": "active",
        "acknowledged_by": None, "resolved_at": None, "remarks": data.get("remarks",""),
    }
    alarms.insert(0, alarm)
    ogm_fire_save(OGM_FIRE_ALARMS_FILE, alarms)
    return ogm_fire_json({"success": True, "alarm": alarm})

@ogm_fire_bp.route("/api/alarms/<aid>/acknowledge", methods=["PATCH"])
def ogm_fire_ack_alarm(aid):
    guard = ogm_fire_auth_check()
    if guard: return guard
    data   = request.get_json(force=True, silent=True) or {}
    alarms = ogm_fire_load(OGM_FIRE_ALARMS_FILE)
    for a in alarms:
        if a["id"] == aid:
            a["status"] = "acknowledged"
            a["acknowledged_by"] = data.get("acknowledged_by", session.get("user","System"))
            a["acknowledged_at"] = ogm_fire_now()
            break
    ogm_fire_save(OGM_FIRE_ALARMS_FILE, alarms)
    return ogm_fire_json({"success": True})

@ogm_fire_bp.route("/api/alarms/<aid>/resolve", methods=["PATCH"])
def ogm_fire_resolve_alarm(aid):
    guard = ogm_fire_auth_check()
    if guard: return guard
    data   = request.get_json(force=True, silent=True) or {}
    alarms = ogm_fire_load(OGM_FIRE_ALARMS_FILE)
    for a in alarms:
        if a["id"] == aid:
            a["status"]      = data.get("status", "resolved")
            a["resolved_at"] = ogm_fire_now()
            a["remarks"]     = data.get("remarks", a.get("remarks",""))
            break
    ogm_fire_save(OGM_FIRE_ALARMS_FILE, alarms)
    return ogm_fire_json({"success": True})


# ═══════════════════════════════════════════════════════════════════════════════
# INSPECTIONS
# ═══════════════════════════════════════════════════════════════════════════════
@ogm_fire_bp.route("/api/inspections", methods=["GET"])
def ogm_fire_get_inspections():
    guard = ogm_fire_auth_check()
    if guard: return guard
    insp = ogm_fire_load(OGM_FIRE_INSPECTIONS_FILE)
    if request.args.get("asset_id"):
        insp = [i for i in insp if i.get("asset_id") == request.args["asset_id"]]
    if request.args.get("type"):
        insp = [i for i in insp if i.get("inspection_type") == request.args["type"]]
    return ogm_fire_json(insp)

@ogm_fire_bp.route("/api/inspections", methods=["POST"])
def ogm_fire_add_inspection():
    guard = ogm_fire_auth_check()
    if guard: return guard
    data   = request.get_json(force=True, silent=True) or {}
    insp   = ogm_fire_load(OGM_FIRE_INSPECTIONS_FILE)
    record = {
        "id": ogm_fire_uid(), "asset_id": data.get("asset_id",""),
        "asset_code": data.get("asset_code",""), "asset_type": data.get("asset_type",""),
        "location": data.get("location",""),
        "inspected_by": data.get("inspected_by", session.get("user","System")),
        "inspection_type": data.get("inspection_type","daily"),
        "status": data.get("status","ok"), "checklist": data.get("checklist",[]),
        "remarks": data.get("remarks",""), "created_at": ogm_fire_now(),
    }
    if record["asset_id"]:
        assets = ogm_fire_load(OGM_FIRE_ASSETS_FILE)
        for a in assets:
            if a["id"] == record["asset_id"]:
                a["last_inspection_date"] = datetime.now().strftime("%Y-%m-%d")
                if record["status"] == "faulty":
                    a["status"] = "faulty"
        ogm_fire_save(OGM_FIRE_ASSETS_FILE, assets)
    insp.insert(0, record)
    ogm_fire_save(OGM_FIRE_INSPECTIONS_FILE, insp)
    return ogm_fire_json({"success": True, "inspection": record})


# ═══════════════════════════════════════════════════════════════════════════════
# MAINTENANCE
# ═══════════════════════════════════════════════════════════════════════════════
@ogm_fire_bp.route("/api/maintenance", methods=["GET"])
def ogm_fire_get_maintenance():
    guard = ogm_fire_auth_check()
    if guard: return guard
    tasks   = ogm_fire_load(OGM_FIRE_MAINTENANCE_FILE)
    today   = datetime.now().strftime("%Y-%m-%d")
    changed = False
    for t in tasks:
        if t.get("status") == "Scheduled" and t.get("scheduled_date","") < today:
            t["status"] = "Overdue"; changed = True
    if changed:
        ogm_fire_save(OGM_FIRE_MAINTENANCE_FILE, tasks)
    return ogm_fire_json(tasks)

@ogm_fire_bp.route("/api/maintenance", methods=["POST"])
def ogm_fire_add_maintenance():
    guard = ogm_fire_auth_check()
    if guard: return guard
    data  = request.get_json(force=True, silent=True) or {}
    tasks = ogm_fire_load(OGM_FIRE_MAINTENANCE_FILE)
    task  = {
        "id": ogm_fire_uid(), "asset_id": data.get("asset_id",""),
        "asset_code": data.get("asset_code",""), "asset_type": data.get("asset_type",""),
        "location": data.get("location",""), "task_type": data.get("task_type","PM"),
        "description": data.get("description",""), "scheduled_date": data.get("scheduled_date",""),
        "completed_date": data.get("completed_date",""), "status": data.get("status","Scheduled"),
        "assigned_to": data.get("assigned_to",""), "remarks": data.get("remarks",""),
        "created_at": ogm_fire_now(),
    }
    tasks.insert(0, task)
    ogm_fire_save(OGM_FIRE_MAINTENANCE_FILE, tasks)
    return ogm_fire_json({"success": True, "task": task})

@ogm_fire_bp.route("/api/maintenance/<tid>", methods=["PATCH"])
def ogm_fire_update_maintenance(tid):
    guard = ogm_fire_auth_check()
    if guard: return guard
    data  = request.get_json(force=True, silent=True) or {}
    tasks = ogm_fire_load(OGM_FIRE_MAINTENANCE_FILE)
    for t in tasks:
        if t["id"] == tid:
            t.update({k: v for k, v in data.items() if k != "id"})
            t["updated_at"] = ogm_fire_now(); break
    ogm_fire_save(OGM_FIRE_MAINTENANCE_FILE, tasks)
    return ogm_fire_json({"success": True})


# ═══════════════════════════════════════════════════════════════════════════════
# INCIDENTS
# ═══════════════════════════════════════════════════════════════════════════════
@ogm_fire_bp.route("/api/incidents", methods=["GET"])
def ogm_fire_get_incidents():
    guard = ogm_fire_auth_check()
    if guard: return guard
    return ogm_fire_json(ogm_fire_load(OGM_FIRE_INCIDENTS_FILE))

@ogm_fire_bp.route("/api/incidents", methods=["POST"])
def ogm_fire_add_incident():
    guard = ogm_fire_auth_check()
    if guard: return guard
    data      = request.get_json(force=True, silent=True) or {}
    incidents = ogm_fire_load(OGM_FIRE_INCIDENTS_FILE)
    inc = {
        "id": ogm_fire_uid(), "property_id": "One Golden Mile",
        "zone_id": data.get("zone_id",""), "zone_name": data.get("zone_name",""),
        "alarm_id": data.get("alarm_id",""), "severity": data.get("severity","medium"),
        "description": data.get("description",""),
        "reported_by": data.get("reported_by", session.get("user","System")),
        "start_time": data.get("start_time", ogm_fire_now()), "end_time": data.get("end_time",""),
        "actions_taken": data.get("actions_taken",""), "evacuation": data.get("evacuation", False),
        "status": data.get("status","Open"), "created_at": ogm_fire_now(),
    }
    incidents.insert(0, inc)
    ogm_fire_save(OGM_FIRE_INCIDENTS_FILE, incidents)
    return ogm_fire_json({"success": True, "incident": inc})

@ogm_fire_bp.route("/api/incidents/<iid>", methods=["PATCH"])
def ogm_fire_update_incident(iid):
    guard = ogm_fire_auth_check()
    if guard: return guard
    data      = request.get_json(force=True, silent=True) or {}
    incidents = ogm_fire_load(OGM_FIRE_INCIDENTS_FILE)
    for i in incidents:
        if i["id"] == iid:
            i.update({k: v for k, v in data.items() if k != "id"})
            i["updated_at"] = ogm_fire_now(); break
    ogm_fire_save(OGM_FIRE_INCIDENTS_FILE, incidents)
    return ogm_fire_json({"success": True})


# ═══════════════════════════════════════════════════════════════════════════════
# TEAM
# ═══════════════════════════════════════════════════════════════════════════════
@ogm_fire_bp.route("/api/team", methods=["GET"])
def ogm_fire_get_team():
    guard = ogm_fire_auth_check()
    if guard: return guard
    return ogm_fire_json(ogm_fire_load(OGM_FIRE_TEAM_FILE))

@ogm_fire_bp.route("/api/team", methods=["POST"])
def ogm_fire_add_team():
    guard = ogm_fire_auth_check()
    if guard: return guard
    data   = request.get_json(force=True, silent=True) or {}
    team   = ogm_fire_load(OGM_FIRE_TEAM_FILE)
    member = {
        "id": ogm_fire_uid(), "property_id": "One Golden Mile",
        "name": data.get("name",""), "role": data.get("role","responder"),
        "contact_number": data.get("contact_number",""), "zone": data.get("zone",""),
        "active": True, "created_at": ogm_fire_now(),
    }
    team.insert(0, member)
    ogm_fire_save(OGM_FIRE_TEAM_FILE, team)
    return ogm_fire_json({"success": True, "member": member})

@ogm_fire_bp.route("/api/team/<tid>", methods=["DELETE"])
def ogm_fire_delete_team(tid):
    guard = ogm_fire_auth_check()
    if guard: return guard
    team = [m for m in ogm_fire_load(OGM_FIRE_TEAM_FILE) if m["id"] != tid]
    ogm_fire_save(OGM_FIRE_TEAM_FILE, team)
    return ogm_fire_json({"success": True})


# ═══════════════════════════════════════════════════════════════════════════════
# DRILLS
# ═══════════════════════════════════════════════════════════════════════════════
@ogm_fire_bp.route("/api/drills", methods=["GET"])
def ogm_fire_get_drills():
    guard = ogm_fire_auth_check()
    if guard: return guard
    return ogm_fire_json(ogm_fire_load(OGM_FIRE_DRILLS_FILE))

@ogm_fire_bp.route("/api/drills", methods=["POST"])
def ogm_fire_add_drill():
    guard = ogm_fire_auth_check()
    if guard: return guard
    data   = request.get_json(force=True, silent=True) or {}
    drills = ogm_fire_load(OGM_FIRE_DRILLS_FILE)
    drill  = {
        "id": ogm_fire_uid(), "property_id": "One Golden Mile",
        "date": data.get("date",""), "conducted_by": data.get("conducted_by",""),
        "drill_type": data.get("drill_type","evacuation"),
        "participants": data.get("participants",0), "duration": data.get("duration",""),
        "score": data.get("score",""), "remarks": data.get("remarks",""),
        "status": data.get("status","Scheduled"), "created_at": ogm_fire_now(),
    }
    drills.insert(0, drill)
    ogm_fire_save(OGM_FIRE_DRILLS_FILE, drills)
    return ogm_fire_json({"success": True, "drill": drill})

@ogm_fire_bp.route("/api/drills/<did>", methods=["PATCH"])
def ogm_fire_update_drill(did):
    guard = ogm_fire_auth_check()
    if guard: return guard
    data   = request.get_json(force=True, silent=True) or {}
    drills = ogm_fire_load(OGM_FIRE_DRILLS_FILE)
    for d in drills:
        if d["id"] == did:
            d.update({k: v for k, v in data.items() if k != "id"})
            d["updated_at"] = ogm_fire_now(); break
    ogm_fire_save(OGM_FIRE_DRILLS_FILE, drills)
    return ogm_fire_json({"success": True})


# ═══════════════════════════════════════════════════════════════════════════════
# EXPORT
# ═══════════════════════════════════════════════════════════════════════════════
@ogm_fire_bp.route("/api/export/<module>", methods=["GET"])
def ogm_fire_export(module):
    guard = ogm_fire_auth_check()
    if guard: return guard
    exports = {
        "assets":      (ogm_fire_load(OGM_FIRE_ASSETS_FILE),
                        ["id","asset_code","asset_type","location","zone_id","capacity",
                         "installation_date","last_inspection_date","next_due_date","status","remarks"]),
        "alarms":      (ogm_fire_load(OGM_FIRE_ALARMS_FILE),
                        ["id","zone_name","alarm_type","triggered_at","status",
                         "acknowledged_by","resolved_at","remarks"]),
        "inspections": (ogm_fire_load(OGM_FIRE_INSPECTIONS_FILE),
                        ["id","asset_code","asset_type","location","inspected_by",
                         "inspection_type","status","remarks","created_at"]),
        "maintenance": (ogm_fire_load(OGM_FIRE_MAINTENANCE_FILE),
                        ["id","asset_code","task_type","description","scheduled_date",
                         "completed_date","status","assigned_to","remarks"]),
        "incidents":   (ogm_fire_load(OGM_FIRE_INCIDENTS_FILE),
                        ["id","zone_name","severity","description","reported_by",
                         "start_time","end_time","status","actions_taken"]),
        "drills":      (ogm_fire_load(OGM_FIRE_DRILLS_FILE),
                        ["id","date","drill_type","conducted_by","participants",
                         "duration","score","status","remarks"]),
    }
    if module not in exports:
        return ogm_fire_json({"error": "Invalid module"}), 404
    data, cols = exports[module]
    rows = [{c: item.get(c,"") for c in cols} for item in data]
    return ogm_fire_json({"columns": cols, "rows": rows, "module": module})


# ═══════════════════════════════════════════════════════════════════════════════
# TEMPLATE DOWNLOAD
# ═══════════════════════════════════════════════════════════════════════════════
@ogm_fire_bp.route("/template/download", methods=["GET"])
def ogm_fire_template_download():
    guard = ogm_fire_auth_check()
    if guard: return guard
    p = DATA_DIR / "OGM_Fire_Master_Template.xlsx"
    if not p.exists():
        return ogm_fire_json({"error": "Template not found. Contact admin."}, 404)
    return send_file(str(p), as_attachment=True,
                     download_name="OGM_Fire_Master_Template.xlsx",
                     mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


# ═══════════════════════════════════════════════════════════════════════════════
# REGISTER — called by server.py
# ═══════════════════════════════════════════════════════════════════════════════
def ogm_fire_register(app, login_required_decorator=None, require_property_decorator=None):
    try:
        app.register_blueprint(ogm_fire_bp)
        print("✅ Registered: ogm_fire_bp (OGM Fire Fighting) at /ogm_fire")
    except Exception as e:
        print(f"⚠️  ogm_fire_bp registration error: {e}")