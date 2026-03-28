"""
TD FIRE FIGHTING MODULE — ROUTES
td_fire.py
Blueprint prefix: /td_fire
All function/variable names prefixed with: td_fire_

CRITICAL: All /api/* routes ALWAYS return application/json — never HTML.
          Prevents "Unexpected token '<'" JSON parse error in frontend.
"""

from flask import Blueprint, render_template, request, jsonify, session, redirect, make_response, send_file
from datetime import datetime
from pathlib import Path
import json

# ── Blueprint ─────────────────────────────────────────────────────────────────
td_fire_bp = Blueprint("td_fire_bp", __name__, url_prefix="/td_fire")

# ── Data storage ──────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).parent.resolve()
DATA_DIR  = BASE_DIR / "static" / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

TD_FIRE_ASSETS_FILE      = DATA_DIR / "td_fire_assets.json"
TD_FIRE_ALARMS_FILE      = DATA_DIR / "td_fire_alarms.json"
TD_FIRE_INSPECTIONS_FILE = DATA_DIR / "td_fire_inspections.json"
TD_FIRE_MAINTENANCE_FILE = DATA_DIR / "td_fire_maintenance.json"
TD_FIRE_INCIDENTS_FILE   = DATA_DIR / "td_fire_incidents.json"
TD_FIRE_TEAM_FILE        = DATA_DIR / "td_fire_team.json"
TD_FIRE_DRILLS_FILE      = DATA_DIR / "td_fire_drills.json"

# ── Helpers ───────────────────────────────────────────────────────────────────
def td_fire_load(path, default=None):
    if default is None:
        default = []
    try:
        if path.exists():
            with open(path) as f:
                return json.load(f)
    except Exception:
        pass
    return default

def td_fire_save(path, data):
    with open(path, "w") as f:
        json.dump(data, f, indent=2, default=str)

def td_fire_uid():
    return f"TD_FIRE_{int(datetime.now().timestamp()*1000)}"

def td_fire_now():
    return datetime.now().isoformat()

def td_fire_json(data, status=200):
    """Always returns JSON — never HTML redirect (prevents JSON parse errors)."""
    r = make_response(jsonify(data), status)
    r.headers["Content-Type"] = "application/json"
    return r

def td_fire_is_api():
    return (
        request.headers.get("X-Requested-With") == "XMLHttpRequest"
        or "application/json" in request.headers.get("Accept", "")
        or "/api/" in request.path
    )

def td_fire_auth_check():
    """Returns JSON 401 for API calls — never HTML login redirect."""
    if "user" not in session:
        if td_fire_is_api():
            return td_fire_json({"error": "Unauthorized — please log in"}, 401)
        return redirect("/login")
    return None


# ── Page route ────────────────────────────────────────────────────────────────
@td_fire_bp.route("/", methods=["GET"])
@td_fire_bp.route("", methods=["GET"])
def td_fire_index():
    guard = td_fire_auth_check()
    if guard:
        return guard
    session["active_property"] = "The District"
    return render_template("td_fire.html")


# ═══════════════════════════════════════════════════════════════════════════════
# DASHBOARD
# ═══════════════════════════════════════════════════════════════════════════════
@td_fire_bp.route("/api/dashboard", methods=["GET"])
def td_fire_dashboard():
    guard = td_fire_auth_check()
    if guard:
        return guard

    assets      = td_fire_load(TD_FIRE_ASSETS_FILE)
    alarms      = td_fire_load(TD_FIRE_ALARMS_FILE)
    inspections = td_fire_load(TD_FIRE_INSPECTIONS_FILE)
    maintenance = td_fire_load(TD_FIRE_MAINTENANCE_FILE)
    incidents   = td_fire_load(TD_FIRE_INCIDENTS_FILE)
    drills      = td_fire_load(TD_FIRE_DRILLS_FILE)

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
    return td_fire_json({
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
@td_fire_bp.route("/api/assets", methods=["GET"])
def td_fire_get_assets():
    guard = td_fire_auth_check()
    if guard:
        return guard
    assets = td_fire_load(TD_FIRE_ASSETS_FILE)
    if request.args.get("type"):
        assets = [a for a in assets if a.get("asset_type") == request.args["type"]]
    if request.args.get("status"):
        assets = [a for a in assets if a.get("status") == request.args["status"]]
    return td_fire_json(assets)


@td_fire_bp.route("/api/assets", methods=["POST"])
def td_fire_add_asset():
    guard = td_fire_auth_check()
    if guard:
        return guard
    data   = request.get_json(force=True, silent=True) or {}
    assets = td_fire_load(TD_FIRE_ASSETS_FILE)
    asset  = {
        "id":                   td_fire_uid(),
        "property_id":          "The District",
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
        "created_at":           td_fire_now(),
    }
    assets.insert(0, asset)
    td_fire_save(TD_FIRE_ASSETS_FILE, assets)
    return td_fire_json({"success": True, "asset": asset})


@td_fire_bp.route("/api/assets/<aid>", methods=["PATCH"])
def td_fire_update_asset(aid):
    guard = td_fire_auth_check()
    if guard:
        return guard
    data   = request.get_json(force=True, silent=True) or {}
    assets = td_fire_load(TD_FIRE_ASSETS_FILE)
    for a in assets:
        if a["id"] == aid:
            a.update({k: v for k, v in data.items() if k != "id"})
            a["updated_at"] = td_fire_now()
            break
    td_fire_save(TD_FIRE_ASSETS_FILE, assets)
    return td_fire_json({"success": True})


@td_fire_bp.route("/api/assets/<aid>", methods=["DELETE"])
def td_fire_delete_asset(aid):
    guard = td_fire_auth_check()
    if guard:
        return guard
    assets = [a for a in td_fire_load(TD_FIRE_ASSETS_FILE) if a["id"] != aid]
    td_fire_save(TD_FIRE_ASSETS_FILE, assets)
    return td_fire_json({"success": True})


# ═══════════════════════════════════════════════════════════════════════════════
# ALARMS
# ═══════════════════════════════════════════════════════════════════════════════
@td_fire_bp.route("/api/alarms", methods=["GET"])
def td_fire_get_alarms():
    guard = td_fire_auth_check()
    if guard:
        return guard
    return td_fire_json(td_fire_load(TD_FIRE_ALARMS_FILE))


@td_fire_bp.route("/api/alarms/trigger", methods=["POST"])
def td_fire_trigger_alarm():
    guard = td_fire_auth_check()
    if guard:
        return guard
    data   = request.get_json(force=True, silent=True) or {}
    alarms = td_fire_load(TD_FIRE_ALARMS_FILE)
    alarm  = {
        "id":               td_fire_uid(),
        "property_id":      "The District",
        "zone_id":          data.get("zone_id", ""),
        "zone_name":        data.get("zone_name", ""),
        "alarm_type":       data.get("alarm_type", "smoke"),
        "source_device_id": data.get("source_device_id", ""),
        "triggered_at":     td_fire_now(),
        "status":           "active",
        "acknowledged_by":  None,
        "resolved_at":      None,
        "remarks":          data.get("remarks", ""),
    }
    alarms.insert(0, alarm)
    td_fire_save(TD_FIRE_ALARMS_FILE, alarms)
    return td_fire_json({"success": True, "alarm": alarm})


@td_fire_bp.route("/api/alarms/<aid>/acknowledge", methods=["PATCH"])
def td_fire_ack_alarm(aid):
    guard = td_fire_auth_check()
    if guard:
        return guard
    data   = request.get_json(force=True, silent=True) or {}
    alarms = td_fire_load(TD_FIRE_ALARMS_FILE)
    for a in alarms:
        if a["id"] == aid:
            a["status"]          = "acknowledged"
            a["acknowledged_by"] = data.get("acknowledged_by", session.get("user", "System"))
            a["acknowledged_at"] = td_fire_now()
            break
    td_fire_save(TD_FIRE_ALARMS_FILE, alarms)
    return td_fire_json({"success": True})


@td_fire_bp.route("/api/alarms/<aid>/resolve", methods=["PATCH"])
def td_fire_resolve_alarm(aid):
    guard = td_fire_auth_check()
    if guard:
        return guard
    data   = request.get_json(force=True, silent=True) or {}
    alarms = td_fire_load(TD_FIRE_ALARMS_FILE)
    for a in alarms:
        if a["id"] == aid:
            a["status"]      = data.get("status", "resolved")
            a["resolved_at"] = td_fire_now()
            a["remarks"]     = data.get("remarks", a.get("remarks", ""))
            break
    td_fire_save(TD_FIRE_ALARMS_FILE, alarms)
    return td_fire_json({"success": True})


# ═══════════════════════════════════════════════════════════════════════════════
# INSPECTIONS
# ═══════════════════════════════════════════════════════════════════════════════
@td_fire_bp.route("/api/inspections", methods=["GET"])
def td_fire_get_inspections():
    guard = td_fire_auth_check()
    if guard:
        return guard
    insp = td_fire_load(TD_FIRE_INSPECTIONS_FILE)
    if request.args.get("asset_id"):
        insp = [i for i in insp if i.get("asset_id") == request.args["asset_id"]]
    if request.args.get("type"):
        insp = [i for i in insp if i.get("inspection_type") == request.args["type"]]
    return td_fire_json(insp)


@td_fire_bp.route("/api/inspections", methods=["POST"])
def td_fire_add_inspection():
    guard = td_fire_auth_check()
    if guard:
        return guard
    data   = request.get_json(force=True, silent=True) or {}
    insp   = td_fire_load(TD_FIRE_INSPECTIONS_FILE)
    record = {
        "id":              td_fire_uid(),
        "asset_id":        data.get("asset_id", ""),
        "asset_code":      data.get("asset_code", ""),
        "asset_type":      data.get("asset_type", ""),
        "location":        data.get("location", ""),
        "inspected_by":    data.get("inspected_by", session.get("user", "System")),
        "inspection_type": data.get("inspection_type", "daily"),
        "status":          data.get("status", "ok"),
        "checklist":       data.get("checklist", []),
        "remarks":         data.get("remarks", ""),
        "created_at":      td_fire_now(),
    }
    if record["asset_id"]:
        assets = td_fire_load(TD_FIRE_ASSETS_FILE)
        for a in assets:
            if a["id"] == record["asset_id"]:
                a["last_inspection_date"] = datetime.now().strftime("%Y-%m-%d")
                if record["status"] == "faulty":
                    a["status"] = "faulty"
        td_fire_save(TD_FIRE_ASSETS_FILE, assets)
    insp.insert(0, record)
    td_fire_save(TD_FIRE_INSPECTIONS_FILE, insp)
    return td_fire_json({"success": True, "inspection": record})


# ═══════════════════════════════════════════════════════════════════════════════
# MAINTENANCE
# ═══════════════════════════════════════════════════════════════════════════════
@td_fire_bp.route("/api/maintenance", methods=["GET"])
def td_fire_get_maintenance():
    guard = td_fire_auth_check()
    if guard:
        return guard
    tasks = td_fire_load(TD_FIRE_MAINTENANCE_FILE)
    today = datetime.now().strftime("%Y-%m-%d")
    changed = False
    for t in tasks:
        if t.get("status") == "Scheduled" and t.get("scheduled_date", "") < today:
            t["status"] = "Overdue"
            changed = True
    if changed:
        td_fire_save(TD_FIRE_MAINTENANCE_FILE, tasks)
    return td_fire_json(tasks)


@td_fire_bp.route("/api/maintenance", methods=["POST"])
def td_fire_add_maintenance():
    guard = td_fire_auth_check()
    if guard:
        return guard
    data  = request.get_json(force=True, silent=True) or {}
    tasks = td_fire_load(TD_FIRE_MAINTENANCE_FILE)
    task  = {
        "id":             td_fire_uid(),
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
        "created_at":     td_fire_now(),
    }
    tasks.insert(0, task)
    td_fire_save(TD_FIRE_MAINTENANCE_FILE, tasks)
    return td_fire_json({"success": True, "task": task})


@td_fire_bp.route("/api/maintenance/<tid>", methods=["PATCH"])
def td_fire_update_maintenance(tid):
    guard = td_fire_auth_check()
    if guard:
        return guard
    data  = request.get_json(force=True, silent=True) or {}
    tasks = td_fire_load(TD_FIRE_MAINTENANCE_FILE)
    for t in tasks:
        if t["id"] == tid:
            t.update({k: v for k, v in data.items() if k != "id"})
            t["updated_at"] = td_fire_now()
            break
    td_fire_save(TD_FIRE_MAINTENANCE_FILE, tasks)
    return td_fire_json({"success": True})


# ═══════════════════════════════════════════════════════════════════════════════
# INCIDENTS
# ═══════════════════════════════════════════════════════════════════════════════
@td_fire_bp.route("/api/incidents", methods=["GET"])
def td_fire_get_incidents():
    guard = td_fire_auth_check()
    if guard:
        return guard
    return td_fire_json(td_fire_load(TD_FIRE_INCIDENTS_FILE))


@td_fire_bp.route("/api/incidents", methods=["POST"])
def td_fire_add_incident():
    guard = td_fire_auth_check()
    if guard:
        return guard
    data      = request.get_json(force=True, silent=True) or {}
    incidents = td_fire_load(TD_FIRE_INCIDENTS_FILE)
    inc = {
        "id":            td_fire_uid(),
        "property_id":   "The District",
        "zone_id":       data.get("zone_id", ""),
        "zone_name":     data.get("zone_name", ""),
        "alarm_id":      data.get("alarm_id", ""),
        "severity":      data.get("severity", "medium"),
        "description":   data.get("description", ""),
        "reported_by":   data.get("reported_by", session.get("user", "System")),
        "start_time":    data.get("start_time", td_fire_now()),
        "end_time":      data.get("end_time", ""),
        "actions_taken": data.get("actions_taken", ""),
        "evacuation":    data.get("evacuation", False),
        "status":        data.get("status", "Open"),
        "created_at":    td_fire_now(),
    }
    incidents.insert(0, inc)
    td_fire_save(TD_FIRE_INCIDENTS_FILE, incidents)
    return td_fire_json({"success": True, "incident": inc})


@td_fire_bp.route("/api/incidents/<iid>", methods=["PATCH"])
def td_fire_update_incident(iid):
    guard = td_fire_auth_check()
    if guard:
        return guard
    data      = request.get_json(force=True, silent=True) or {}
    incidents = td_fire_load(TD_FIRE_INCIDENTS_FILE)
    for i in incidents:
        if i["id"] == iid:
            i.update({k: v for k, v in data.items() if k != "id"})
            i["updated_at"] = td_fire_now()
            break
    td_fire_save(TD_FIRE_INCIDENTS_FILE, incidents)
    return td_fire_json({"success": True})


# ═══════════════════════════════════════════════════════════════════════════════
# RESPONSE TEAM
# ═══════════════════════════════════════════════════════════════════════════════
@td_fire_bp.route("/api/team", methods=["GET"])
def td_fire_get_team():
    guard = td_fire_auth_check()
    if guard:
        return guard
    return td_fire_json(td_fire_load(TD_FIRE_TEAM_FILE))


@td_fire_bp.route("/api/team", methods=["POST"])
def td_fire_add_team():
    guard = td_fire_auth_check()
    if guard:
        return guard
    data   = request.get_json(force=True, silent=True) or {}
    team   = td_fire_load(TD_FIRE_TEAM_FILE)
    member = {
        "id":             td_fire_uid(),
        "property_id":    "The District",
        "name":           data.get("name", ""),
        "role":           data.get("role", "responder"),
        "contact_number": data.get("contact_number", ""),
        "zone":           data.get("zone", ""),
        "active":         True,
        "created_at":     td_fire_now(),
    }
    team.insert(0, member)
    td_fire_save(TD_FIRE_TEAM_FILE, team)
    return td_fire_json({"success": True, "member": member})


@td_fire_bp.route("/api/team/<tid>", methods=["DELETE"])
def td_fire_delete_team(tid):
    guard = td_fire_auth_check()
    if guard:
        return guard
    team = [m for m in td_fire_load(TD_FIRE_TEAM_FILE) if m["id"] != tid]
    td_fire_save(TD_FIRE_TEAM_FILE, team)
    return td_fire_json({"success": True})


# ═══════════════════════════════════════════════════════════════════════════════
# DRILLS
# ═══════════════════════════════════════════════════════════════════════════════
@td_fire_bp.route("/api/drills", methods=["GET"])
def td_fire_get_drills():
    guard = td_fire_auth_check()
    if guard:
        return guard
    return td_fire_json(td_fire_load(TD_FIRE_DRILLS_FILE))


@td_fire_bp.route("/api/drills", methods=["POST"])
def td_fire_add_drill():
    guard = td_fire_auth_check()
    if guard:
        return guard
    data   = request.get_json(force=True, silent=True) or {}
    drills = td_fire_load(TD_FIRE_DRILLS_FILE)
    drill  = {
        "id":           td_fire_uid(),
        "property_id":  "The District",
        "date":         data.get("date", ""),
        "conducted_by": data.get("conducted_by", ""),
        "drill_type":   data.get("drill_type", "evacuation"),
        "participants": data.get("participants", 0),
        "duration":     data.get("duration", ""),
        "score":        data.get("score", ""),
        "remarks":      data.get("remarks", ""),
        "status":       data.get("status", "Scheduled"),
        "created_at":   td_fire_now(),
    }
    drills.insert(0, drill)
    td_fire_save(TD_FIRE_DRILLS_FILE, drills)
    return td_fire_json({"success": True, "drill": drill})


@td_fire_bp.route("/api/drills/<did>", methods=["PATCH"])
def td_fire_update_drill(did):
    guard = td_fire_auth_check()
    if guard:
        return guard
    data   = request.get_json(force=True, silent=True) or {}
    drills = td_fire_load(TD_FIRE_DRILLS_FILE)
    for d in drills:
        if d["id"] == did:
            d.update({k: v for k, v in data.items() if k != "id"})
            d["updated_at"] = td_fire_now()
            break
    td_fire_save(TD_FIRE_DRILLS_FILE, drills)
    return td_fire_json({"success": True})


# ═══════════════════════════════════════════════════════════════════════════════
# EXPORT
# ═══════════════════════════════════════════════════════════════════════════════
@td_fire_bp.route("/api/export/<module>", methods=["GET"])
def td_fire_export(module):
    guard = td_fire_auth_check()
    if guard:
        return guard
    exports = {
        "assets":      (td_fire_load(TD_FIRE_ASSETS_FILE),
                        ["id","asset_code","asset_type","location","zone_id","capacity",
                         "installation_date","last_inspection_date","next_due_date","status","remarks"]),
        "alarms":      (td_fire_load(TD_FIRE_ALARMS_FILE),
                        ["id","zone_name","alarm_type","triggered_at","status",
                         "acknowledged_by","resolved_at","remarks"]),
        "inspections": (td_fire_load(TD_FIRE_INSPECTIONS_FILE),
                        ["id","asset_code","asset_type","location","inspected_by",
                         "inspection_type","status","remarks","created_at"]),
        "maintenance": (td_fire_load(TD_FIRE_MAINTENANCE_FILE),
                        ["id","asset_code","task_type","description","scheduled_date",
                         "completed_date","status","assigned_to","remarks"]),
        "incidents":   (td_fire_load(TD_FIRE_INCIDENTS_FILE),
                        ["id","zone_name","severity","description","reported_by",
                         "start_time","end_time","status","actions_taken"]),
        "drills":      (td_fire_load(TD_FIRE_DRILLS_FILE),
                        ["id","date","drill_type","conducted_by","participants",
                         "duration","score","status","remarks"]),
    }
    if module not in exports:
        return td_fire_json({"error": "Invalid module"}), 404
    data, cols = exports[module]
    rows = [{c: item.get(c, "") for c in cols} for item in data]
    return td_fire_json({"columns": cols, "rows": rows, "module": module})


# ═══════════════════════════════════════════════════════════════════════════════
# TEMPLATE DOWNLOAD
# ═══════════════════════════════════════════════════════════════════════════════
@td_fire_bp.route("/template/download", methods=["GET"])
def td_fire_template_download():
    guard = td_fire_auth_check()
    if guard:
        return guard
    template_path = DATA_DIR / "TD_Fire_Master_Template.xlsx"
    if not template_path.exists():
        return td_fire_json({"error": "Template not found. Contact admin."}, 404)
    return send_file(
        str(template_path),
        as_attachment=True,
        download_name="TD_Fire_Master_Template.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )


# ═══════════════════════════════════════════════════════════════════════════════
# REGISTER FUNCTION — called by server.py
# ═══════════════════════════════════════════════════════════════════════════════
def td_fire_register(app, login_required_decorator=None, require_property_decorator=None):
    """
    Registration shim for server.py:
        from td_fire import td_fire_register
        td_fire_register(app, login_required, require_property)
    Auth handled internally via td_fire_auth_check().
    """
    try:
        app.register_blueprint(td_fire_bp)
        print("✅ Registered: td_fire_bp (The District Fire Fighting) at /td_fire")
    except Exception as e:
        print(f"⚠️  td_fire_bp registration error: {e}")