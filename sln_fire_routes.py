"""
SLN FIRE FIGHTING MODULE — ROUTES
sln_fire_routes.py
Blueprint prefix: /sln_fire
All function names prefixed with: sln_fire_

CRITICAL: All /api/* routes ALWAYS return application/json — never HTML.
          This prevents the "Unexpected token '<'" JSON parse error in the frontend.
"""

from flask import Blueprint, render_template, request, jsonify, session, redirect, make_response
from datetime import datetime
from pathlib import Path
import json

# ── Blueprint ─────────────────────────────────────────────────────────────────
sln_fire_bp = Blueprint("sln_fire_bp", __name__, url_prefix="/sln_fire")

# ── Data storage ──────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).parent.resolve()
DATA_DIR  = BASE_DIR / "static" / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

FIRE_ASSETS_FILE      = DATA_DIR / "sln_fire_assets.json"
FIRE_ALARMS_FILE      = DATA_DIR / "sln_fire_alarms.json"
FIRE_INSPECTIONS_FILE = DATA_DIR / "sln_fire_inspections.json"
FIRE_MAINTENANCE_FILE = DATA_DIR / "sln_fire_maintenance.json"
FIRE_INCIDENTS_FILE   = DATA_DIR / "sln_fire_incidents.json"
FIRE_TEAM_FILE        = DATA_DIR / "sln_fire_team.json"
FIRE_DRILLS_FILE      = DATA_DIR / "sln_fire_drills.json"

# ── Helpers ───────────────────────────────────────────────────────────────────
def _load(path, default=None):
    if default is None:
        default = []
    try:
        if path.exists():
            with open(path) as f:
                return json.load(f)
    except Exception:
        pass
    return default

def _save(path, data):
    with open(path, "w") as f:
        json.dump(data, f, indent=2, default=str)

def _uid():
    return f"FIRE_{int(datetime.now().timestamp()*1000)}"

def _now():
    return datetime.now().isoformat()

def _json(data, status=200):
    """Always returns JSON with explicit Content-Type — never redirects."""
    r = make_response(jsonify(data), status)
    r.headers["Content-Type"] = "application/json"
    return r

def _is_api():
    """True when the request is an API call from JS fetch."""
    return (
        request.headers.get("X-Requested-With") == "XMLHttpRequest"
        or "application/json" in request.headers.get("Accept", "")
        or "/api/" in request.path
    )

def _auth_check():
    """
    Returns a JSON 401 if session has no user — NEVER redirects to HTML login
    for API calls, which would cause the 'Unexpected token <' JSON parse error.
    """
    if "user" not in session:
        if _is_api():
            return _json({"error": "Unauthorized — please log in"}, 401)
        return redirect("/login")
    return None


# ── Page route ────────────────────────────────────────────────────────────────
@sln_fire_bp.route("/", methods=["GET"])
@sln_fire_bp.route("", methods=["GET"])
def sln_fire_index():
    guard = _auth_check()
    if guard:
        return guard
    return render_template("sln_fire.html")


# ═══════════════════════════════════════════════════════════════════════════════
# DASHBOARD
# ═══════════════════════════════════════════════════════════════════════════════
@sln_fire_bp.route("/api/dashboard", methods=["GET"])
def sln_fire_dashboard():
    guard = _auth_check()
    if guard:
        return guard

    assets      = _load(FIRE_ASSETS_FILE)
    alarms      = _load(FIRE_ALARMS_FILE)
    inspections = _load(FIRE_INSPECTIONS_FILE)
    maintenance = _load(FIRE_MAINTENANCE_FILE)
    incidents   = _load(FIRE_INCIDENTS_FILE)
    drills      = _load(FIRE_DRILLS_FILE)

    active_assets  = [a for a in assets if a.get("status") == "active"]
    faulty_assets  = [a for a in assets if a.get("status") == "faulty"]
    expired_assets = [a for a in assets if a.get("status") == "expired"]
    active_alarms  = [a for a in alarms  if a.get("status") == "active"]
    pending_maint  = [m for m in maintenance if m.get("status") in ("Scheduled", "Overdue")]
    open_incidents = [i for i in incidents   if i.get("status") not in ("Closed", "Resolved")]
    failed_insp    = [i for i in inspections if i.get("status") == "faulty"]

    total = len(assets) or 1
    compliance_pct = round((len(active_assets) / total) * 100)

    last_drill = None
    if drills:
        last_drill = sorted(drills, key=lambda d: d.get("date", ""), reverse=True)[0]

    today = datetime.now().strftime("%Y-%m-%d")
    return _json({
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
        "alarms_today":       len([a for a in alarms
                                   if a.get("triggered_at", "").startswith(today)]),
    })


# ═══════════════════════════════════════════════════════════════════════════════
# ASSETS
# ═══════════════════════════════════════════════════════════════════════════════
@sln_fire_bp.route("/api/assets", methods=["GET"])
def sln_fire_get_assets():
    guard = _auth_check()
    if guard:
        return guard
    assets = _load(FIRE_ASSETS_FILE)
    if request.args.get("type"):
        assets = [a for a in assets if a.get("asset_type") == request.args["type"]]
    if request.args.get("status"):
        assets = [a for a in assets if a.get("status") == request.args["status"]]
    return _json(assets)


@sln_fire_bp.route("/api/assets", methods=["POST"])
def sln_fire_add_asset():
    guard = _auth_check()
    if guard:
        return guard
    data   = request.get_json(force=True, silent=True) or {}
    assets = _load(FIRE_ASSETS_FILE)
    asset  = {
        "id":                   _uid(),
        "property_id":          "SLN",
        "zone_id":              data.get("zone_id", ""),
        "asset_type":           data.get("asset_type", "extinguisher"),
        "asset_code":           data.get("asset_code", ""),
        "location":             data.get("location", ""),
        "capacity":             data.get("capacity", ""),
        "installation_date":    data.get("installation_date", ""),
        "last_inspection_date": data.get("last_inspection_date", ""),
        "next_due_date":        data.get("next_due_date", ""),
        "status":               data.get("status", "active"),
        "remarks":              data.get("remarks", ""),
        "created_at":           _now(),
    }
    assets.insert(0, asset)
    _save(FIRE_ASSETS_FILE, assets)
    return _json({"success": True, "asset": asset})


@sln_fire_bp.route("/api/assets/<aid>", methods=["PATCH"])
def sln_fire_update_asset(aid):
    guard = _auth_check()
    if guard:
        return guard
    data   = request.get_json(force=True, silent=True) or {}
    assets = _load(FIRE_ASSETS_FILE)
    for a in assets:
        if a["id"] == aid:
            a.update({k: v for k, v in data.items() if k != "id"})
            a["updated_at"] = _now()
            break
    _save(FIRE_ASSETS_FILE, assets)
    return _json({"success": True})


@sln_fire_bp.route("/api/assets/<aid>", methods=["DELETE"])
def sln_fire_delete_asset(aid):
    guard = _auth_check()
    if guard:
        return guard
    assets = [a for a in _load(FIRE_ASSETS_FILE) if a["id"] != aid]
    _save(FIRE_ASSETS_FILE, assets)
    return _json({"success": True})


# ═══════════════════════════════════════════════════════════════════════════════
# ALARMS
# ═══════════════════════════════════════════════════════════════════════════════
@sln_fire_bp.route("/api/alarms", methods=["GET"])
def sln_fire_get_alarms():
    guard = _auth_check()
    if guard:
        return guard
    return _json(_load(FIRE_ALARMS_FILE))


@sln_fire_bp.route("/api/alarms/trigger", methods=["POST"])
def sln_fire_trigger_alarm():
    guard = _auth_check()
    if guard:
        return guard
    data   = request.get_json(force=True, silent=True) or {}
    alarms = _load(FIRE_ALARMS_FILE)
    alarm  = {
        "id":               _uid(),
        "property_id":      "SLN",
        "zone_id":          data.get("zone_id", ""),
        "zone_name":        data.get("zone_name", ""),
        "alarm_type":       data.get("alarm_type", "smoke"),
        "source_device_id": data.get("source_device_id", ""),
        "triggered_at":     _now(),
        "status":           "active",
        "acknowledged_by":  None,
        "resolved_at":      None,
        "remarks":          data.get("remarks", ""),
    }
    alarms.insert(0, alarm)
    _save(FIRE_ALARMS_FILE, alarms)
    return _json({"success": True, "alarm": alarm})


@sln_fire_bp.route("/api/alarms/<aid>/acknowledge", methods=["PATCH"])
def sln_fire_ack_alarm(aid):
    guard = _auth_check()
    if guard:
        return guard
    data   = request.get_json(force=True, silent=True) or {}
    alarms = _load(FIRE_ALARMS_FILE)
    for a in alarms:
        if a["id"] == aid:
            a["status"]          = "acknowledged"
            a["acknowledged_by"] = data.get("acknowledged_by", session.get("user", "System"))
            a["acknowledged_at"] = _now()
            break
    _save(FIRE_ALARMS_FILE, alarms)
    return _json({"success": True})


@sln_fire_bp.route("/api/alarms/<aid>/resolve", methods=["PATCH"])
def sln_fire_resolve_alarm(aid):
    guard = _auth_check()
    if guard:
        return guard
    data   = request.get_json(force=True, silent=True) or {}
    alarms = _load(FIRE_ALARMS_FILE)
    for a in alarms:
        if a["id"] == aid:
            a["status"]      = data.get("status", "resolved")
            a["resolved_at"] = _now()
            a["remarks"]     = data.get("remarks", a.get("remarks", ""))
            break
    _save(FIRE_ALARMS_FILE, alarms)
    return _json({"success": True})


# ═══════════════════════════════════════════════════════════════════════════════
# INSPECTIONS
# ═══════════════════════════════════════════════════════════════════════════════
@sln_fire_bp.route("/api/inspections", methods=["GET"])
def sln_fire_get_inspections():
    guard = _auth_check()
    if guard:
        return guard
    insp = _load(FIRE_INSPECTIONS_FILE)
    if request.args.get("asset_id"):
        insp = [i for i in insp if i.get("asset_id") == request.args["asset_id"]]
    if request.args.get("type"):
        insp = [i for i in insp if i.get("inspection_type") == request.args["type"]]
    return _json(insp)


@sln_fire_bp.route("/api/inspections", methods=["POST"])
def sln_fire_add_inspection():
    guard = _auth_check()
    if guard:
        return guard
    data   = request.get_json(force=True, silent=True) or {}
    insp   = _load(FIRE_INSPECTIONS_FILE)
    record = {
        "id":              _uid(),
        "asset_id":        data.get("asset_id", ""),
        "asset_code":      data.get("asset_code", ""),
        "asset_type":      data.get("asset_type", ""),
        "location":        data.get("location", ""),
        "inspected_by":    data.get("inspected_by", session.get("user", "System")),
        "inspection_type": data.get("inspection_type", "daily"),
        "status":          data.get("status", "ok"),
        "checklist":       data.get("checklist", []),
        "remarks":         data.get("remarks", ""),
        "created_at":      _now(),
    }
    if record["asset_id"]:
        assets = _load(FIRE_ASSETS_FILE)
        for a in assets:
            if a["id"] == record["asset_id"]:
                a["last_inspection_date"] = datetime.now().strftime("%Y-%m-%d")
                if record["status"] == "faulty":
                    a["status"] = "faulty"
        _save(FIRE_ASSETS_FILE, assets)
    insp.insert(0, record)
    _save(FIRE_INSPECTIONS_FILE, insp)
    return _json({"success": True, "inspection": record})


# ═══════════════════════════════════════════════════════════════════════════════
# MAINTENANCE
# ═══════════════════════════════════════════════════════════════════════════════
@sln_fire_bp.route("/api/maintenance", methods=["GET"])
def sln_fire_get_maintenance():
    guard = _auth_check()
    if guard:
        return guard
    tasks = _load(FIRE_MAINTENANCE_FILE)
    today = datetime.now().strftime("%Y-%m-%d")
    changed = False
    for t in tasks:
        if t.get("status") == "Scheduled" and t.get("scheduled_date", "") < today:
            t["status"] = "Overdue"
            changed = True
    if changed:
        _save(FIRE_MAINTENANCE_FILE, tasks)
    return _json(tasks)


@sln_fire_bp.route("/api/maintenance", methods=["POST"])
def sln_fire_add_maintenance():
    guard = _auth_check()
    if guard:
        return guard
    data  = request.get_json(force=True, silent=True) or {}
    tasks = _load(FIRE_MAINTENANCE_FILE)
    task  = {
        "id":             _uid(),
        "asset_id":       data.get("asset_id", ""),
        "asset_code":     data.get("asset_code", ""),
        "asset_type":     data.get("asset_type", ""),
        "location":       data.get("location", ""),
        "task_type":      data.get("task_type", "PM"),
        "description":    data.get("description", ""),
        "scheduled_date": data.get("scheduled_date", ""),
        "completed_date": data.get("completed_date", ""),
        "status":         data.get("status", "Scheduled"),
        "assigned_to":    data.get("assigned_to", ""),
        "remarks":        data.get("remarks", ""),
        "created_at":     _now(),
    }
    tasks.insert(0, task)
    _save(FIRE_MAINTENANCE_FILE, tasks)
    return _json({"success": True, "task": task})


@sln_fire_bp.route("/api/maintenance/<tid>", methods=["PATCH"])
def sln_fire_update_maintenance(tid):
    guard = _auth_check()
    if guard:
        return guard
    data  = request.get_json(force=True, silent=True) or {}
    tasks = _load(FIRE_MAINTENANCE_FILE)
    for t in tasks:
        if t["id"] == tid:
            t.update({k: v for k, v in data.items() if k != "id"})
            t["updated_at"] = _now()
            break
    _save(FIRE_MAINTENANCE_FILE, tasks)
    return _json({"success": True})


# ═══════════════════════════════════════════════════════════════════════════════
# INCIDENTS
# ═══════════════════════════════════════════════════════════════════════════════
@sln_fire_bp.route("/api/incidents", methods=["GET"])
def sln_fire_get_incidents():
    guard = _auth_check()
    if guard:
        return guard
    return _json(_load(FIRE_INCIDENTS_FILE))


@sln_fire_bp.route("/api/incidents", methods=["POST"])
def sln_fire_add_incident():
    guard = _auth_check()
    if guard:
        return guard
    data      = request.get_json(force=True, silent=True) or {}
    incidents = _load(FIRE_INCIDENTS_FILE)
    inc = {
        "id":            _uid(),
        "property_id":   "SLN",
        "zone_id":       data.get("zone_id", ""),
        "zone_name":     data.get("zone_name", ""),
        "alarm_id":      data.get("alarm_id", ""),
        "severity":      data.get("severity", "medium"),
        "description":   data.get("description", ""),
        "reported_by":   data.get("reported_by", session.get("user", "System")),
        "start_time":    data.get("start_time", _now()),
        "end_time":      data.get("end_time", ""),
        "actions_taken": data.get("actions_taken", ""),
        "evacuation":    data.get("evacuation", False),
        "status":        data.get("status", "Open"),
        "created_at":    _now(),
    }
    incidents.insert(0, inc)
    _save(FIRE_INCIDENTS_FILE, incidents)
    return _json({"success": True, "incident": inc})


@sln_fire_bp.route("/api/incidents/<iid>", methods=["PATCH"])
def sln_fire_update_incident(iid):
    guard = _auth_check()
    if guard:
        return guard
    data      = request.get_json(force=True, silent=True) or {}
    incidents = _load(FIRE_INCIDENTS_FILE)
    for i in incidents:
        if i["id"] == iid:
            i.update({k: v for k, v in data.items() if k != "id"})
            i["updated_at"] = _now()
            break
    _save(FIRE_INCIDENTS_FILE, incidents)
    return _json({"success": True})


# ═══════════════════════════════════════════════════════════════════════════════
# RESPONSE TEAM
# ═══════════════════════════════════════════════════════════════════════════════
@sln_fire_bp.route("/api/team", methods=["GET"])
def sln_fire_get_team():
    guard = _auth_check()
    if guard:
        return guard
    return _json(_load(FIRE_TEAM_FILE))


@sln_fire_bp.route("/api/team", methods=["POST"])
def sln_fire_add_team():
    guard = _auth_check()
    if guard:
        return guard
    data   = request.get_json(force=True, silent=True) or {}
    team   = _load(FIRE_TEAM_FILE)
    member = {
        "id":             _uid(),
        "property_id":    "SLN",
        "name":           data.get("name", ""),
        "role":           data.get("role", "responder"),
        "contact_number": data.get("contact_number", ""),
        "zone":           data.get("zone", ""),
        "active":         True,
        "created_at":     _now(),
    }
    team.insert(0, member)
    _save(FIRE_TEAM_FILE, team)
    return _json({"success": True, "member": member})


@sln_fire_bp.route("/api/team/<tid>", methods=["DELETE"])
def sln_fire_delete_team(tid):
    guard = _auth_check()
    if guard:
        return guard
    team = [m for m in _load(FIRE_TEAM_FILE) if m["id"] != tid]
    _save(FIRE_TEAM_FILE, team)
    return _json({"success": True})


# ═══════════════════════════════════════════════════════════════════════════════
# DRILLS
# ═══════════════════════════════════════════════════════════════════════════════
@sln_fire_bp.route("/api/drills", methods=["GET"])
def sln_fire_get_drills():
    guard = _auth_check()
    if guard:
        return guard
    return _json(_load(FIRE_DRILLS_FILE))


@sln_fire_bp.route("/api/drills", methods=["POST"])
def sln_fire_add_drill():
    guard = _auth_check()
    if guard:
        return guard
    data   = request.get_json(force=True, silent=True) or {}
    drills = _load(FIRE_DRILLS_FILE)
    drill  = {
        "id":           _uid(),
        "property_id":  "SLN",
        "date":         data.get("date", ""),
        "conducted_by": data.get("conducted_by", ""),
        "drill_type":   data.get("drill_type", "evacuation"),
        "participants": data.get("participants", 0),
        "duration":     data.get("duration", ""),
        "score":        data.get("score", ""),
        "remarks":      data.get("remarks", ""),
        "status":       data.get("status", "Scheduled"),
        "created_at":   _now(),
    }
    drills.insert(0, drill)
    _save(FIRE_DRILLS_FILE, drills)
    return _json({"success": True, "drill": drill})


@sln_fire_bp.route("/api/drills/<did>", methods=["PATCH"])
def sln_fire_update_drill(did):
    guard = _auth_check()
    if guard:
        return guard
    data   = request.get_json(force=True, silent=True) or {}
    drills = _load(FIRE_DRILLS_FILE)
    for d in drills:
        if d["id"] == did:
            d.update({k: v for k, v in data.items() if k != "id"})
            d["updated_at"] = _now()
            break
    _save(FIRE_DRILLS_FILE, drills)
    return _json({"success": True})


# ═══════════════════════════════════════════════════════════════════════════════
# EXPORT — JSON payload for CSV download (client-side conversion)
# ═══════════════════════════════════════════════════════════════════════════════
@sln_fire_bp.route("/api/export/<module>", methods=["GET"])
def sln_fire_export(module):
    guard = _auth_check()
    if guard:
        return guard
    exports = {
        "assets":      (_load(FIRE_ASSETS_FILE),
                        ["id","asset_code","asset_type","location","zone_id","capacity",
                         "installation_date","last_inspection_date","next_due_date","status","remarks"]),
        "alarms":      (_load(FIRE_ALARMS_FILE),
                        ["id","zone_name","alarm_type","triggered_at","status",
                         "acknowledged_by","resolved_at","remarks"]),
        "inspections": (_load(FIRE_INSPECTIONS_FILE),
                        ["id","asset_code","asset_type","location","inspected_by",
                         "inspection_type","status","remarks","created_at"]),
        "maintenance": (_load(FIRE_MAINTENANCE_FILE),
                        ["id","asset_code","task_type","description","scheduled_date",
                         "completed_date","status","assigned_to","remarks"]),
        "incidents":   (_load(FIRE_INCIDENTS_FILE),
                        ["id","zone_name","severity","description","reported_by",
                         "start_time","end_time","status","actions_taken"]),
        "drills":      (_load(FIRE_DRILLS_FILE),
                        ["id","date","drill_type","conducted_by","participants",
                         "duration","score","status","remarks"]),
    }
    if module not in exports:
        return _json({"error": "Invalid module"}), 404
    data, cols = exports[module]
    rows = [{c: item.get(c, "") for c in cols} for item in data]
    return _json({"columns": cols, "rows": rows, "module": module})


# ═══════════════════════════════════════════════════════════════════════════════
# SERVE MASTER TEMPLATE FILE
# ═══════════════════════════════════════════════════════════════════════════════
@sln_fire_bp.route("/template/download", methods=["GET"])
def sln_fire_template_download():
    """Serve the pre-built multi-sheet Excel master template."""
    from flask import send_file
    guard = _auth_check()
    if guard:
        return guard
    template_path = DATA_DIR / "SLN_Fire_Master_Template.xlsx"
    if not template_path.exists():
        return _json({"error": "Template file not found on server. Please contact admin."}, 404)
    return send_file(
        str(template_path),
        as_attachment=True,
        download_name="SLN_Fire_Master_Template.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )