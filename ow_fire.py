"""
OW FIRE FIGHTING MODULE — ROUTES
ow_fire.py
Blueprint prefix: /ow_fire
All function names prefixed with: ow_fire_

CRITICAL: All /api/* routes ALWAYS return application/json — never HTML.
          Prevents "Unexpected token '<'" JSON parse error in frontend.
"""

from flask import Blueprint, render_template, request, jsonify, session, redirect, make_response, send_file
from datetime import datetime
from pathlib import Path
import json

# ── Blueprint ─────────────────────────────────────────────────────────────────
ow_fire_bp = Blueprint("ow_fire_bp", __name__, url_prefix="/ow_fire")

# ── Data storage ──────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).parent.resolve()
DATA_DIR  = BASE_DIR / "static" / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

OW_FIRE_ASSETS_FILE      = DATA_DIR / "ow_fire_assets.json"
OW_FIRE_ALARMS_FILE      = DATA_DIR / "ow_fire_alarms.json"
OW_FIRE_INSPECTIONS_FILE = DATA_DIR / "ow_fire_inspections.json"
OW_FIRE_MAINTENANCE_FILE = DATA_DIR / "ow_fire_maintenance.json"
OW_FIRE_INCIDENTS_FILE   = DATA_DIR / "ow_fire_incidents.json"
OW_FIRE_TEAM_FILE        = DATA_DIR / "ow_fire_team.json"
OW_FIRE_DRILLS_FILE      = DATA_DIR / "ow_fire_drills.json"

# ── Helpers ───────────────────────────────────────────────────────────────────
def ow_fire_load(path, default=None):
    if default is None:
        default = []
    try:
        if path.exists():
            with open(path) as f:
                return json.load(f)
    except Exception:
        pass
    return default

def ow_fire_save(path, data):
    with open(path, "w") as f:
        json.dump(data, f, indent=2, default=str)

def ow_fire_uid():
    return f"OW_FIRE_{int(datetime.now().timestamp()*1000)}"

def ow_fire_now():
    return datetime.now().isoformat()

def ow_fire_json(data, status=200):
    """Always returns JSON with explicit Content-Type — never redirects."""
    r = make_response(jsonify(data), status)
    r.headers["Content-Type"] = "application/json"
    return r

def ow_fire_is_api():
    return (
        request.headers.get("X-Requested-With") == "XMLHttpRequest"
        or "application/json" in request.headers.get("Accept", "")
        or "/api/" in request.path
    )

def ow_fire_auth_check():
    """
    Returns JSON 401 for API calls if session missing — never HTML redirect.
    Prevents the 'Unexpected token <' JSON parse error.
    """
    if "user" not in session:
        if ow_fire_is_api():
            return ow_fire_json({"error": "Unauthorized — please log in"}, 401)
        return redirect("/login")
    return None


# ── Page route ────────────────────────────────────────────────────────────────
@ow_fire_bp.route("/", methods=["GET"])
@ow_fire_bp.route("", methods=["GET"])
def ow_fire_index():
    guard = ow_fire_auth_check()
    if guard:
        return guard
    session["active_property"] = "ONEWEST"
    return render_template("ow_fire.html")


# ═══════════════════════════════════════════════════════════════════════════════
# DASHBOARD
# ═══════════════════════════════════════════════════════════════════════════════
@ow_fire_bp.route("/api/dashboard", methods=["GET"])
def ow_fire_dashboard():
    guard = ow_fire_auth_check()
    if guard:
        return guard

    assets      = ow_fire_load(OW_FIRE_ASSETS_FILE)
    alarms      = ow_fire_load(OW_FIRE_ALARMS_FILE)
    inspections = ow_fire_load(OW_FIRE_INSPECTIONS_FILE)
    maintenance = ow_fire_load(OW_FIRE_MAINTENANCE_FILE)
    incidents   = ow_fire_load(OW_FIRE_INCIDENTS_FILE)
    drills      = ow_fire_load(OW_FIRE_DRILLS_FILE)

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
    return ow_fire_json({
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
@ow_fire_bp.route("/api/assets", methods=["GET"])
def ow_fire_get_assets():
    guard = ow_fire_auth_check()
    if guard:
        return guard
    assets = ow_fire_load(OW_FIRE_ASSETS_FILE)
    if request.args.get("type"):
        assets = [a for a in assets if a.get("asset_type") == request.args["type"]]
    if request.args.get("status"):
        assets = [a for a in assets if a.get("status") == request.args["status"]]
    return ow_fire_json(assets)


@ow_fire_bp.route("/api/assets", methods=["POST"])
def ow_fire_add_asset():
    guard = ow_fire_auth_check()
    if guard:
        return guard
    data   = request.get_json(force=True, silent=True) or {}
    assets = ow_fire_load(OW_FIRE_ASSETS_FILE)
    asset  = {
        "id":                   ow_fire_uid(),
        "property_id":          "ONEWEST",
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
        "created_at":           ow_fire_now(),
    }
    assets.insert(0, asset)
    ow_fire_save(OW_FIRE_ASSETS_FILE, assets)
    return ow_fire_json({"success": True, "asset": asset})


@ow_fire_bp.route("/api/assets/<aid>", methods=["PATCH"])
def ow_fire_update_asset(aid):
    guard = ow_fire_auth_check()
    if guard:
        return guard
    data   = request.get_json(force=True, silent=True) or {}
    assets = ow_fire_load(OW_FIRE_ASSETS_FILE)
    for a in assets:
        if a["id"] == aid:
            a.update({k: v for k, v in data.items() if k != "id"})
            a["updated_at"] = ow_fire_now()
            break
    ow_fire_save(OW_FIRE_ASSETS_FILE, assets)
    return ow_fire_json({"success": True})


@ow_fire_bp.route("/api/assets/<aid>", methods=["DELETE"])
def ow_fire_delete_asset(aid):
    guard = ow_fire_auth_check()
    if guard:
        return guard
    assets = [a for a in ow_fire_load(OW_FIRE_ASSETS_FILE) if a["id"] != aid]
    ow_fire_save(OW_FIRE_ASSETS_FILE, assets)
    return ow_fire_json({"success": True})


# ═══════════════════════════════════════════════════════════════════════════════
# ALARMS
# ═══════════════════════════════════════════════════════════════════════════════
@ow_fire_bp.route("/api/alarms", methods=["GET"])
def ow_fire_get_alarms():
    guard = ow_fire_auth_check()
    if guard:
        return guard
    return ow_fire_json(ow_fire_load(OW_FIRE_ALARMS_FILE))


@ow_fire_bp.route("/api/alarms/trigger", methods=["POST"])
def ow_fire_trigger_alarm():
    guard = ow_fire_auth_check()
    if guard:
        return guard
    data   = request.get_json(force=True, silent=True) or {}
    alarms = ow_fire_load(OW_FIRE_ALARMS_FILE)
    alarm  = {
        "id":               ow_fire_uid(),
        "property_id":      "ONEWEST",
        "zone_id":          data.get("zone_id", ""),
        "zone_name":        data.get("zone_name", ""),
        "alarm_type":       data.get("alarm_type", "smoke"),
        "source_device_id": data.get("source_device_id", ""),
        "triggered_at":     ow_fire_now(),
        "status":           "active",
        "acknowledged_by":  None,
        "resolved_at":      None,
        "remarks":          data.get("remarks", ""),
    }
    alarms.insert(0, alarm)
    ow_fire_save(OW_FIRE_ALARMS_FILE, alarms)
    return ow_fire_json({"success": True, "alarm": alarm})


@ow_fire_bp.route("/api/alarms/<aid>/acknowledge", methods=["PATCH"])
def ow_fire_ack_alarm(aid):
    guard = ow_fire_auth_check()
    if guard:
        return guard
    data   = request.get_json(force=True, silent=True) or {}
    alarms = ow_fire_load(OW_FIRE_ALARMS_FILE)
    for a in alarms:
        if a["id"] == aid:
            a["status"]          = "acknowledged"
            a["acknowledged_by"] = data.get("acknowledged_by", session.get("user", "System"))
            a["acknowledged_at"] = ow_fire_now()
            break
    ow_fire_save(OW_FIRE_ALARMS_FILE, alarms)
    return ow_fire_json({"success": True})


@ow_fire_bp.route("/api/alarms/<aid>/resolve", methods=["PATCH"])
def ow_fire_resolve_alarm(aid):
    guard = ow_fire_auth_check()
    if guard:
        return guard
    data   = request.get_json(force=True, silent=True) or {}
    alarms = ow_fire_load(OW_FIRE_ALARMS_FILE)
    for a in alarms:
        if a["id"] == aid:
            a["status"]      = data.get("status", "resolved")
            a["resolved_at"] = ow_fire_now()
            a["remarks"]     = data.get("remarks", a.get("remarks", ""))
            break
    ow_fire_save(OW_FIRE_ALARMS_FILE, alarms)
    return ow_fire_json({"success": True})


# ═══════════════════════════════════════════════════════════════════════════════
# INSPECTIONS
# ═══════════════════════════════════════════════════════════════════════════════
@ow_fire_bp.route("/api/inspections", methods=["GET"])
def ow_fire_get_inspections():
    guard = ow_fire_auth_check()
    if guard:
        return guard
    insp = ow_fire_load(OW_FIRE_INSPECTIONS_FILE)
    if request.args.get("asset_id"):
        insp = [i for i in insp if i.get("asset_id") == request.args["asset_id"]]
    if request.args.get("type"):
        insp = [i for i in insp if i.get("inspection_type") == request.args["type"]]
    return ow_fire_json(insp)


@ow_fire_bp.route("/api/inspections", methods=["POST"])
def ow_fire_add_inspection():
    guard = ow_fire_auth_check()
    if guard:
        return guard
    data   = request.get_json(force=True, silent=True) or {}
    insp   = ow_fire_load(OW_FIRE_INSPECTIONS_FILE)
    record = {
        "id":              ow_fire_uid(),
        "asset_id":        data.get("asset_id", ""),
        "asset_code":      data.get("asset_code", ""),
        "asset_type":      data.get("asset_type", ""),
        "location":        data.get("location", ""),
        "inspected_by":    data.get("inspected_by", session.get("user", "System")),
        "inspection_type": data.get("inspection_type", "daily"),
        "status":          data.get("status", "ok"),
        "checklist":       data.get("checklist", []),
        "remarks":         data.get("remarks", ""),
        "created_at":      ow_fire_now(),
    }
    if record["asset_id"]:
        assets = ow_fire_load(OW_FIRE_ASSETS_FILE)
        for a in assets:
            if a["id"] == record["asset_id"]:
                a["last_inspection_date"] = datetime.now().strftime("%Y-%m-%d")
                if record["status"] == "faulty":
                    a["status"] = "faulty"
        ow_fire_save(OW_FIRE_ASSETS_FILE, assets)
    insp.insert(0, record)
    ow_fire_save(OW_FIRE_INSPECTIONS_FILE, insp)
    return ow_fire_json({"success": True, "inspection": record})


# ═══════════════════════════════════════════════════════════════════════════════
# MAINTENANCE
# ═══════════════════════════════════════════════════════════════════════════════
@ow_fire_bp.route("/api/maintenance", methods=["GET"])
def ow_fire_get_maintenance():
    guard = ow_fire_auth_check()
    if guard:
        return guard
    tasks = ow_fire_load(OW_FIRE_MAINTENANCE_FILE)
    today = datetime.now().strftime("%Y-%m-%d")
    changed = False
    for t in tasks:
        if t.get("status") == "Scheduled" and t.get("scheduled_date", "") < today:
            t["status"] = "Overdue"
            changed = True
    if changed:
        ow_fire_save(OW_FIRE_MAINTENANCE_FILE, tasks)
    return ow_fire_json(tasks)


@ow_fire_bp.route("/api/maintenance", methods=["POST"])
def ow_fire_add_maintenance():
    guard = ow_fire_auth_check()
    if guard:
        return guard
    data  = request.get_json(force=True, silent=True) or {}
    tasks = ow_fire_load(OW_FIRE_MAINTENANCE_FILE)
    task  = {
        "id":             ow_fire_uid(),
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
        "created_at":     ow_fire_now(),
    }
    tasks.insert(0, task)
    ow_fire_save(OW_FIRE_MAINTENANCE_FILE, tasks)
    return ow_fire_json({"success": True, "task": task})


@ow_fire_bp.route("/api/maintenance/<tid>", methods=["PATCH"])
def ow_fire_update_maintenance(tid):
    guard = ow_fire_auth_check()
    if guard:
        return guard
    data  = request.get_json(force=True, silent=True) or {}
    tasks = ow_fire_load(OW_FIRE_MAINTENANCE_FILE)
    for t in tasks:
        if t["id"] == tid:
            t.update({k: v for k, v in data.items() if k != "id"})
            t["updated_at"] = ow_fire_now()
            break
    ow_fire_save(OW_FIRE_MAINTENANCE_FILE, tasks)
    return ow_fire_json({"success": True})


# ═══════════════════════════════════════════════════════════════════════════════
# INCIDENTS
# ═══════════════════════════════════════════════════════════════════════════════
@ow_fire_bp.route("/api/incidents", methods=["GET"])
def ow_fire_get_incidents():
    guard = ow_fire_auth_check()
    if guard:
        return guard
    return ow_fire_json(ow_fire_load(OW_FIRE_INCIDENTS_FILE))


@ow_fire_bp.route("/api/incidents", methods=["POST"])
def ow_fire_add_incident():
    guard = ow_fire_auth_check()
    if guard:
        return guard
    data      = request.get_json(force=True, silent=True) or {}
    incidents = ow_fire_load(OW_FIRE_INCIDENTS_FILE)
    inc = {
        "id":            ow_fire_uid(),
        "property_id":   "ONEWEST",
        "zone_id":       data.get("zone_id", ""),
        "zone_name":     data.get("zone_name", ""),
        "alarm_id":      data.get("alarm_id", ""),
        "severity":      data.get("severity", "medium"),
        "description":   data.get("description", ""),
        "reported_by":   data.get("reported_by", session.get("user", "System")),
        "start_time":    data.get("start_time", ow_fire_now()),
        "end_time":      data.get("end_time", ""),
        "actions_taken": data.get("actions_taken", ""),
        "evacuation":    data.get("evacuation", False),
        "status":        data.get("status", "Open"),
        "created_at":    ow_fire_now(),
    }
    incidents.insert(0, inc)
    ow_fire_save(OW_FIRE_INCIDENTS_FILE, incidents)
    return ow_fire_json({"success": True, "incident": inc})


@ow_fire_bp.route("/api/incidents/<iid>", methods=["PATCH"])
def ow_fire_update_incident(iid):
    guard = ow_fire_auth_check()
    if guard:
        return guard
    data      = request.get_json(force=True, silent=True) or {}
    incidents = ow_fire_load(OW_FIRE_INCIDENTS_FILE)
    for i in incidents:
        if i["id"] == iid:
            i.update({k: v for k, v in data.items() if k != "id"})
            i["updated_at"] = ow_fire_now()
            break
    ow_fire_save(OW_FIRE_INCIDENTS_FILE, incidents)
    return ow_fire_json({"success": True})


# ═══════════════════════════════════════════════════════════════════════════════
# RESPONSE TEAM
# ═══════════════════════════════════════════════════════════════════════════════
@ow_fire_bp.route("/api/team", methods=["GET"])
def ow_fire_get_team():
    guard = ow_fire_auth_check()
    if guard:
        return guard
    return ow_fire_json(ow_fire_load(OW_FIRE_TEAM_FILE))


@ow_fire_bp.route("/api/team", methods=["POST"])
def ow_fire_add_team():
    guard = ow_fire_auth_check()
    if guard:
        return guard
    data   = request.get_json(force=True, silent=True) or {}
    team   = ow_fire_load(OW_FIRE_TEAM_FILE)
    member = {
        "id":             ow_fire_uid(),
        "property_id":    "ONEWEST",
        "name":           data.get("name", ""),
        "role":           data.get("role", "responder"),
        "contact_number": data.get("contact_number", ""),
        "zone":           data.get("zone", ""),
        "active":         True,
        "created_at":     ow_fire_now(),
    }
    team.insert(0, member)
    ow_fire_save(OW_FIRE_TEAM_FILE, team)
    return ow_fire_json({"success": True, "member": member})


@ow_fire_bp.route("/api/team/<tid>", methods=["DELETE"])
def ow_fire_delete_team(tid):
    guard = ow_fire_auth_check()
    if guard:
        return guard
    team = [m for m in ow_fire_load(OW_FIRE_TEAM_FILE) if m["id"] != tid]
    ow_fire_save(OW_FIRE_TEAM_FILE, team)
    return ow_fire_json({"success": True})


# ═══════════════════════════════════════════════════════════════════════════════
# DRILLS
# ═══════════════════════════════════════════════════════════════════════════════
@ow_fire_bp.route("/api/drills", methods=["GET"])
def ow_fire_get_drills():
    guard = ow_fire_auth_check()
    if guard:
        return guard
    return ow_fire_json(ow_fire_load(OW_FIRE_DRILLS_FILE))


@ow_fire_bp.route("/api/drills", methods=["POST"])
def ow_fire_add_drill():
    guard = ow_fire_auth_check()
    if guard:
        return guard
    data   = request.get_json(force=True, silent=True) or {}
    drills = ow_fire_load(OW_FIRE_DRILLS_FILE)
    drill  = {
        "id":           ow_fire_uid(),
        "property_id":  "ONEWEST",
        "date":         data.get("date", ""),
        "conducted_by": data.get("conducted_by", ""),
        "drill_type":   data.get("drill_type", "evacuation"),
        "participants": data.get("participants", 0),
        "duration":     data.get("duration", ""),
        "score":        data.get("score", ""),
        "remarks":      data.get("remarks", ""),
        "status":       data.get("status", "Scheduled"),
        "created_at":   ow_fire_now(),
    }
    drills.insert(0, drill)
    ow_fire_save(OW_FIRE_DRILLS_FILE, drills)
    return ow_fire_json({"success": True, "drill": drill})


@ow_fire_bp.route("/api/drills/<did>", methods=["PATCH"])
def ow_fire_update_drill(did):
    guard = ow_fire_auth_check()
    if guard:
        return guard
    data   = request.get_json(force=True, silent=True) or {}
    drills = ow_fire_load(OW_FIRE_DRILLS_FILE)
    for d in drills:
        if d["id"] == did:
            d.update({k: v for k, v in data.items() if k != "id"})
            d["updated_at"] = ow_fire_now()
            break
    ow_fire_save(OW_FIRE_DRILLS_FILE, drills)
    return ow_fire_json({"success": True})


# ═══════════════════════════════════════════════════════════════════════════════
# EXPORT — JSON payload for PDF / CSV client-side
# ═══════════════════════════════════════════════════════════════════════════════
@ow_fire_bp.route("/api/export/<module>", methods=["GET"])
def ow_fire_export(module):
    guard = ow_fire_auth_check()
    if guard:
        return guard
    exports = {
        "assets":      (ow_fire_load(OW_FIRE_ASSETS_FILE),
                        ["id","asset_code","asset_type","location","zone_id","capacity",
                         "installation_date","last_inspection_date","next_due_date","status","remarks"]),
        "alarms":      (ow_fire_load(OW_FIRE_ALARMS_FILE),
                        ["id","zone_name","alarm_type","triggered_at","status",
                         "acknowledged_by","resolved_at","remarks"]),
        "inspections": (ow_fire_load(OW_FIRE_INSPECTIONS_FILE),
                        ["id","asset_code","asset_type","location","inspected_by",
                         "inspection_type","status","remarks","created_at"]),
        "maintenance": (ow_fire_load(OW_FIRE_MAINTENANCE_FILE),
                        ["id","asset_code","task_type","description","scheduled_date",
                         "completed_date","status","assigned_to","remarks"]),
        "incidents":   (ow_fire_load(OW_FIRE_INCIDENTS_FILE),
                        ["id","zone_name","severity","description","reported_by",
                         "start_time","end_time","status","actions_taken"]),
        "drills":      (ow_fire_load(OW_FIRE_DRILLS_FILE),
                        ["id","date","drill_type","conducted_by","participants",
                         "duration","score","status","remarks"]),
    }
    if module not in exports:
        return ow_fire_json({"error": "Invalid module"}), 404
    data, cols = exports[module]
    rows = [{c: item.get(c, "") for c in cols} for item in data]
    return ow_fire_json({"columns": cols, "rows": rows, "module": module})


# ═══════════════════════════════════════════════════════════════════════════════
# SERVE MASTER TEMPLATE FILE
# ═══════════════════════════════════════════════════════════════════════════════
@ow_fire_bp.route("/template/download", methods=["GET"])
def ow_fire_template_download():
    """Serve the pre-built multi-sheet Excel master template for ONEWEST."""
    guard = ow_fire_auth_check()
    if guard:
        return guard
    template_path = DATA_DIR / "OW_Fire_Master_Template.xlsx"
    if not template_path.exists():
        # Fallback to SLN template if OW-specific not found
        template_path = DATA_DIR / "SLN_Fire_Master_Template.xlsx"
    if not template_path.exists():
        return ow_fire_json({"error": "Template file not found. Please contact admin."}, 404)
    return send_file(
        str(template_path),
        as_attachment=True,
        download_name="OW_Fire_Master_Template.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )


# ═══════════════════════════════════════════════════════════════════════════════
# REGISTER FUNCTION — called by server.py as ow_fire_register(app, ...)
# Registers the blueprint onto the Flask app.
# ═══════════════════════════════════════════════════════════════════════════════
def ow_fire_register(app, login_required_decorator=None, require_property_decorator=None):
    """
    Registration shim that server.py calls:
        from ow_fire import ow_fire_register
        ow_fire_register(app, login_required, require_property)

    We register the blueprint directly — auth is handled internally
    per-route via ow_fire_auth_check() which never redirects to HTML
    on API calls (prevents the 'Unexpected token <' JSON parse error).
    """
    try:
        app.register_blueprint(ow_fire_bp)
        print("✅ Registered: ow_fire_bp (ONEWEST Fire Fighting Module) at /ow_fire")
    except Exception as e:
        print(f"⚠️  ow_fire_bp registration error: {e}")