"""
BREAKDOWN ROUTES — Command Center Operational Modules
Handles:
  • Engineering Breakdown  — fault logging, RCA, SLA tracking
  • Flying Squad           — rapid dispatch, incident management
  • Workshop               — repair queue, spare parts, work orders

Blueprint: breakdown_bp   |   URL prefix: /api/breakdown
JSON store:  static/data/breakdown_data.json
"""

from flask import Blueprint, request, jsonify, session
from functools import wraps
from pathlib import Path
from datetime import datetime
import json
import os

breakdown_bp = Blueprint("breakdown_bp", __name__, url_prefix="/api/breakdown")

# ── Storage path ──────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).parent.resolve()
DATA_DIR  = BASE_DIR / "static" / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
BREAKDOWN_FILE = DATA_DIR / "breakdown_data.json"

# ── Properties & systems (mirrors server.py USERS list) ──────────────────────
PROPERTIES = [
    "SLN Terminus",
    "ONEWEST",
    "The District",
    "One Golden Mile",
    "Nine Hills",
]

SYSTEMS = [
    "HVAC",
    "Electrical",
    "Plumbing",
    "Elevators",
    "Fire Safety",
    "BMS / IoT",
    "Mechanical",
    "Civil / Structural",
    "Security / CCTV",
    "Other",
]

SEVERITIES    = ["Critical", "High", "Medium", "Low"]
EB_STATUSES   = ["Open", "In-Progress", "Escalated", "Resolved", "Closed"]
FS_STATUSES   = ["Dispatched", "En-Route", "On-Site", "Resolved", "Escalated", "Closed"]
WS_STATUSES   = ["Received", "Diagnosis", "Awaiting Parts", "Repair", "Testing", "Closed"]
PRIORITIES    = ["Critical", "High", "Medium", "Low"]

# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────
def _load() -> dict:
    """Load all breakdown data from JSON store."""
    if BREAKDOWN_FILE.exists():
        try:
            with open(BREAKDOWN_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {
        "engineering_breakdowns": [],
        "flying_squad_incidents": [],
        "workshop_jobs": [],
        "meta": {"last_updated": datetime.now().isoformat()}
    }


def _save(data: dict):
    """Persist breakdown data to JSON store."""
    data["meta"] = {"last_updated": datetime.now().isoformat()}
    with open(BREAKDOWN_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def _new_id(prefix: str, items: list) -> str:
    """Generate a zero-padded sequential ID."""
    today = datetime.now().strftime("%Y%m%d")
    seq   = len([i for i in items if today in i.get("id", "")]) + 1
    return f"{prefix}-{today}-{str(seq).zfill(3)}"


def _login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if "user" not in session:
            return jsonify({"success": False, "error": "Not authenticated"}), 401
        return f(*args, **kwargs)
    return wrapper


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


# ─────────────────────────────────────────────────────────────────────────────
# ── 1. ENGINEERING BREAKDOWN ─────────────────────────────────────────────────
# ─────────────────────────────────────────────────────────────────────────────

@breakdown_bp.route("/engineering", methods=["GET"])
@_login_required
def list_engineering():
    """GET /api/breakdown/engineering  — list all / filter by property, status, severity"""
    data   = _load()
    items  = data.get("engineering_breakdowns", [])

    prop     = request.args.get("property")
    status   = request.args.get("status")
    severity = request.args.get("severity")
    limit    = int(request.args.get("limit", 100))

    if prop:
        items = [i for i in items if i.get("property") == prop]
    if status:
        items = [i for i in items if i.get("status") == status]
    if severity:
        items = [i for i in items if i.get("severity") == severity]

    items = items[-limit:][::-1]          # most recent first
    return jsonify({"success": True, "items": items, "total": len(items)})


@breakdown_bp.route("/engineering", methods=["POST"])
@_login_required
def create_engineering():
    """POST /api/breakdown/engineering  — log a new engineering breakdown / fault"""
    body = request.get_json(force=True) or {}

    required = ["property", "system", "severity", "description"]
    missing  = [k for k in required if not body.get(k)]
    if missing:
        return jsonify({"success": False, "error": f"Missing: {', '.join(missing)}"}), 400

    data  = _load()
    items = data.setdefault("engineering_breakdowns", [])

    ticket = {
        "id":             _new_id("EB", items),
        "type":           "Engineering Breakdown",
        "property":       body["property"],
        "system":         body["system"],
        "severity":       body["severity"],
        "description":    body["description"],
        "location":       body.get("location", ""),
        "floor":          body.get("floor", ""),
        "fault_source":   body.get("fault_source", "Manual"),       # IoT / Manual / Inspection
        "assigned_to":    body.get("assigned_to", ""),
        "status":         "Open",
        "downtime_start": body.get("downtime_start", _now_iso()),
        "downtime_end":   None,
        "downtime_mins":  None,
        "rca":            body.get("rca", ""),
        "corrective_action": body.get("corrective_action", ""),
        "escalated_to":   None,            # "Flying Squad" | "Workshop" | None
        "sla_breach":     False,
        "sla_target_mins": _sla_target(body["severity"]),
        "photos":         body.get("photos", []),
        "comments":       [],
        "logged_by":      session.get("user", "—"),
        "logged_at":      _now_iso(),
        "updated_at":     _now_iso(),
    }

    items.append(ticket)
    _save(data)
    return jsonify({"success": True, "ticket": ticket}), 201


@breakdown_bp.route("/engineering/<ticket_id>", methods=["PATCH"])
@_login_required
def update_engineering(ticket_id):
    """PATCH /api/breakdown/engineering/<id>  — update status, add RCA, escalate, close"""
    body  = request.get_json(force=True) or {}
    data  = _load()
    items = data.get("engineering_breakdowns", [])

    ticket = next((i for i in items if i["id"] == ticket_id), None)
    if not ticket:
        return jsonify({"success": False, "error": "Ticket not found"}), 404

    # Updatable fields
    for field in ["status", "assigned_to", "rca", "corrective_action",
                  "escalated_to", "floor", "location", "severity"]:
        if field in body:
            ticket[field] = body[field]

    # Auto-calculate downtime on close / resolve
    if body.get("status") in ("Resolved", "Closed") and not ticket.get("downtime_end"):
        ticket["downtime_end"]  = _now_iso()
        start = datetime.fromisoformat(ticket["downtime_start"])
        end   = datetime.fromisoformat(ticket["downtime_end"])
        ticket["downtime_mins"] = int((end - start).total_seconds() / 60)
        sla_t = ticket.get("sla_target_mins", 240)
        ticket["sla_breach"]    = ticket["downtime_mins"] > sla_t

    # Append comment if provided
    if body.get("comment"):
        ticket.setdefault("comments", []).append({
            "by":   session.get("user", "—"),
            "at":   _now_iso(),
            "text": body["comment"],
        })

    ticket["updated_at"] = _now_iso()
    _save(data)
    return jsonify({"success": True, "ticket": ticket})


# ─────────────────────────────────────────────────────────────────────────────
# ── 2. FLYING SQUAD ──────────────────────────────────────────────────────────
# ─────────────────────────────────────────────────────────────────────────────

@breakdown_bp.route("/flying_squad", methods=["GET"])
@_login_required
def list_flying_squad():
    data  = _load()
    items = data.get("flying_squad_incidents", [])

    prop   = request.args.get("property")
    status = request.args.get("status")
    limit  = int(request.args.get("limit", 100))

    if prop:
        items = [i for i in items if i.get("property") == prop]
    if status:
        items = [i for i in items if i.get("status") == status]

    items = items[-limit:][::-1]
    return jsonify({"success": True, "items": items, "total": len(items)})


@breakdown_bp.route("/flying_squad", methods=["POST"])
@_login_required
def create_flying_squad():
    """POST — dispatch flying squad for an incident"""
    body    = request.get_json(force=True) or {}
    missing = [k for k in ["property", "severity", "description"] if not body.get(k)]
    if missing:
        return jsonify({"success": False, "error": f"Missing: {', '.join(missing)}"}), 400

    data  = _load()
    items = data.setdefault("flying_squad_incidents", [])

    incident = {
        "id":              _new_id("FS", items),
        "type":            "Flying Squad",
        "property":        body["property"],
        "system":          body.get("system", "General"),
        "severity":        body["severity"],
        "description":     body["description"],
        "location":        body.get("location", ""),
        "floor":           body.get("floor", ""),
        "team_assigned":   body.get("team_assigned", ""),
        "vehicle_no":      body.get("vehicle_no", ""),
        "dispatch_time":   _now_iso(),
        "arrival_time":    None,
        "resolution_time": None,
        "eta_mins":        body.get("eta_mins", None),
        "status":          "Dispatched",
        "resolution_note": "",
        "escalated_to_eb": False,
        "escalated_to_ws": False,
        "sla_target_mins": _sla_target(body["severity"]),
        "sla_breach":      False,
        "comments":        [],
        "linked_eb_id":    body.get("linked_eb_id", None),
        "logged_by":       session.get("user", "—"),
        "logged_at":       _now_iso(),
        "updated_at":      _now_iso(),
    }

    items.append(incident)
    _save(data)
    return jsonify({"success": True, "incident": incident}), 201


@breakdown_bp.route("/flying_squad/<incident_id>", methods=["PATCH"])
@_login_required
def update_flying_squad(incident_id):
    body  = request.get_json(force=True) or {}
    data  = _load()
    items = data.get("flying_squad_incidents", [])
    inc   = next((i for i in items if i["id"] == incident_id), None)
    if not inc:
        return jsonify({"success": False, "error": "Incident not found"}), 404

    for field in ["status", "team_assigned", "vehicle_no", "arrival_time",
                  "resolution_note", "eta_mins", "escalated_to_eb", "escalated_to_ws"]:
        if field in body:
            inc[field] = body[field]

    # Mark resolution time automatically
    if body.get("status") in ("Resolved", "Closed") and not inc.get("resolution_time"):
        inc["resolution_time"] = _now_iso()
        start = datetime.fromisoformat(inc["dispatch_time"])
        end   = datetime.fromisoformat(inc["resolution_time"])
        total = int((end - start).total_seconds() / 60)
        inc["sla_breach"] = total > inc.get("sla_target_mins", 120)

    if body.get("comment"):
        inc.setdefault("comments", []).append({
            "by": session.get("user", "—"), "at": _now_iso(), "text": body["comment"]
        })

    inc["updated_at"] = _now_iso()
    _save(data)
    return jsonify({"success": True, "incident": inc})


# ─────────────────────────────────────────────────────────────────────────────
# ── 3. WORKSHOP ──────────────────────────────────────────────────────────────
# ─────────────────────────────────────────────────────────────────────────────

@breakdown_bp.route("/workshop", methods=["GET"])
@_login_required
def list_workshop():
    data  = _load()
    items = data.get("workshop_jobs", [])

    prop   = request.args.get("property")
    status = request.args.get("status")
    limit  = int(request.args.get("limit", 100))

    if prop:
        items = [i for i in items if i.get("property") == prop]
    if status:
        items = [i for i in items if i.get("status") == status]

    items = items[-limit:][::-1]
    return jsonify({"success": True, "items": items, "total": len(items)})


@breakdown_bp.route("/workshop", methods=["POST"])
@_login_required
def create_workshop():
    """POST — create a workshop repair job"""
    body    = request.get_json(force=True) or {}
    missing = [k for k in ["property", "asset_description", "fault_description"] if not body.get(k)]
    if missing:
        return jsonify({"success": False, "error": f"Missing: {', '.join(missing)}"}), 400

    data  = _load()
    items = data.setdefault("workshop_jobs", [])

    job = {
        "id":                _new_id("WS", items),
        "type":              "Workshop",
        "property":          body["property"],
        "asset_description": body["asset_description"],
        "asset_id":          body.get("asset_id", ""),
        "fault_description": body["fault_description"],
        "priority":          body.get("priority", "Medium"),
        "technician":        body.get("technician", ""),
        "spare_parts":       body.get("spare_parts", []),      # [{name, qty, unit_cost}]
        "status":            "Received",
        "received_at":       _now_iso(),
        "diagnosis":         body.get("diagnosis", ""),
        "repair_notes":      body.get("repair_notes", ""),
        "tat_target_hours":  body.get("tat_target_hours", 48),
        "completed_at":      None,
        "tat_hours":         None,
        "qc_passed":         None,
        "returned_to_service": False,
        "linked_eb_id":      body.get("linked_eb_id", None),
        "linked_fs_id":      body.get("linked_fs_id", None),
        "comments":          [],
        "logged_by":         session.get("user", "—"),
        "logged_at":         _now_iso(),
        "updated_at":        _now_iso(),
    }

    items.append(job)
    _save(data)
    return jsonify({"success": True, "job": job}), 201


@breakdown_bp.route("/workshop/<job_id>", methods=["PATCH"])
@_login_required
def update_workshop(job_id):
    body  = request.get_json(force=True) or {}
    data  = _load()
    items = data.get("workshop_jobs", [])
    job   = next((i for i in items if i["id"] == job_id), None)
    if not job:
        return jsonify({"success": False, "error": "Job not found"}), 404

    for field in ["status", "technician", "diagnosis", "repair_notes",
                  "spare_parts", "qc_passed", "returned_to_service", "tat_target_hours"]:
        if field in body:
            job[field] = body[field]

    if body.get("status") == "Closed" and not job.get("completed_at"):
        job["completed_at"] = _now_iso()
        start = datetime.fromisoformat(job["received_at"])
        end   = datetime.fromisoformat(job["completed_at"])
        job["tat_hours"] = round((end - start).total_seconds() / 3600, 1)

    if body.get("comment"):
        job.setdefault("comments", []).append({
            "by": session.get("user", "—"), "at": _now_iso(), "text": body["comment"]
        })

    job["updated_at"] = _now_iso()
    _save(data)
    return jsonify({"success": True, "job": job})


# ─────────────────────────────────────────────────────────────────────────────
# ── 4. CROSS-MODULE: UNIFIED LOG & DASHBOARD STATS ───────────────────────────
# ─────────────────────────────────────────────────────────────────────────────

@breakdown_bp.route("/log", methods=["POST"])
@_login_required
def unified_log():
    """
    POST /api/breakdown/log
    Single endpoint used by the "Log Breakdown / Issue" modal in the UI.
    Routes to correct module based on 'module' field:
      engineering | flying_squad | workshop
    """
    body   = request.get_json(force=True) or {}
    module = body.get("module", "engineering")

    if module == "flying_squad":
        with breakdown_bp.open_resource(""):
            pass
        # Re-use internal create logic
        from flask import current_app
        with current_app.test_request_context(
            "/api/breakdown/flying_squad",
            method="POST",
            json=body,
            headers={"Content-Type": "application/json"},
        ):
            # Simpler: just call the function directly
            pass
        # Direct call
        return create_flying_squad.__wrapped__(body) if hasattr(create_flying_squad, "__wrapped__") else _route_log(module, body)
    elif module == "workshop":
        return _route_log(module, body)
    else:
        return _route_log("engineering", body)


def _route_log(module: str, body: dict):
    """Internal dispatcher without HTTP overhead."""
    data  = _load()

    if module == "flying_squad":
        items = data.setdefault("flying_squad_incidents", [])
        missing = [k for k in ["property", "severity", "description"] if not body.get(k)]
        if missing:
            return jsonify({"success": False, "error": f"Missing: {', '.join(missing)}"}), 400
        record = {
            "id": _new_id("FS", items),
            "type": "Flying Squad",
            "property": body["property"],
            "system": body.get("system", "General"),
            "severity": body["severity"],
            "description": body["description"],
            "location": body.get("location", ""),
            "floor": body.get("floor", ""),
            "team_assigned": body.get("team_assigned", ""),
            "vehicle_no": body.get("vehicle_no", ""),
            "dispatch_time": _now_iso(),
            "arrival_time": None,
            "resolution_time": None,
            "eta_mins": body.get("eta_mins"),
            "status": "Dispatched",
            "resolution_note": "",
            "escalated_to_eb": False,
            "escalated_to_ws": False,
            "sla_target_mins": _sla_target(body["severity"]),
            "sla_breach": False,
            "comments": [],
            "linked_eb_id": body.get("linked_eb_id"),
            "logged_by": session.get("user", "—"),
            "logged_at": _now_iso(),
            "updated_at": _now_iso(),
        }
        items.append(record)
        _save(data)
        return jsonify({"success": True, "id": record["id"], "type": "Flying Squad", "record": record}), 201

    elif module == "workshop":
        items = data.setdefault("workshop_jobs", [])
        missing = [k for k in ["property", "asset_description", "fault_description"] if not body.get(k)]
        if missing:
            return jsonify({"success": False, "error": f"Missing: {', '.join(missing)}"}), 400
        record = {
            "id": _new_id("WS", items),
            "type": "Workshop",
            "property": body["property"],
            "asset_description": body["asset_description"],
            "asset_id": body.get("asset_id", ""),
            "fault_description": body["fault_description"],
            "priority": body.get("priority", "Medium"),
            "technician": body.get("technician", ""),
            "spare_parts": body.get("spare_parts", []),
            "status": "Received",
            "received_at": _now_iso(),
            "diagnosis": body.get("diagnosis", ""),
            "repair_notes": body.get("repair_notes", ""),
            "tat_target_hours": body.get("tat_target_hours", 48),
            "completed_at": None,
            "tat_hours": None,
            "qc_passed": None,
            "returned_to_service": False,
            "linked_eb_id": body.get("linked_eb_id"),
            "linked_fs_id": body.get("linked_fs_id"),
            "comments": [],
            "logged_by": session.get("user", "—"),
            "logged_at": _now_iso(),
            "updated_at": _now_iso(),
        }
        items.append(record)
        _save(data)
        return jsonify({"success": True, "id": record["id"], "type": "Workshop", "record": record}), 201

    else:  # engineering
        items = data.setdefault("engineering_breakdowns", [])
        missing = [k for k in ["property", "system", "severity", "description"] if not body.get(k)]
        if missing:
            return jsonify({"success": False, "error": f"Missing: {', '.join(missing)}"}), 400
        record = {
            "id": _new_id("EB", items),
            "type": "Engineering Breakdown",
            "property": body["property"],
            "system": body["system"],
            "severity": body["severity"],
            "description": body["description"],
            "location": body.get("location", ""),
            "floor": body.get("floor", ""),
            "fault_source": body.get("fault_source", "Manual"),
            "assigned_to": body.get("assigned_to", ""),
            "status": "Open",
            "downtime_start": body.get("downtime_start", _now_iso()),
            "downtime_end": None,
            "downtime_mins": None,
            "rca": body.get("rca", ""),
            "corrective_action": body.get("corrective_action", ""),
            "escalated_to": None,
            "sla_breach": False,
            "sla_target_mins": _sla_target(body["severity"]),
            "photos": body.get("photos", []),
            "comments": [],
            "logged_by": session.get("user", "—"),
            "logged_at": _now_iso(),
            "updated_at": _now_iso(),
        }
        items.append(record)
        _save(data)
        return jsonify({"success": True, "id": record["id"], "type": "Engineering Breakdown", "record": record}), 201


@breakdown_bp.route("/dashboard_stats", methods=["GET"])
@_login_required
def dashboard_stats():
    """GET /api/breakdown/dashboard_stats — aggregated KPIs for Command Center"""
    data = _load()
    prop = request.args.get("property")

    def _filter(items):
        return [i for i in items if i.get("property") == prop] if prop else items

    eb  = _filter(data.get("engineering_breakdowns", []))
    fs  = _filter(data.get("flying_squad_incidents", []))
    ws  = _filter(data.get("workshop_jobs", []))

    def _open(items, statuses):
        return [i for i in items if i.get("status") not in statuses]

    eb_open   = [i for i in eb if i.get("status") not in ("Resolved", "Closed")]
    eb_crit   = [i for i in eb_open if i.get("severity") == "Critical"]
    fs_active = [i for i in fs if i.get("status") not in ("Resolved", "Closed")]
    ws_active = [i for i in ws if i.get("status") not in ("Closed",)]

    # SLA breach count
    sla_breaches = sum(1 for i in eb + fs if i.get("sla_breach"))

    # Average downtime of closed EB tickets
    closed_eb = [i for i in eb if i.get("downtime_mins") is not None]
    avg_downtime = (
        round(sum(i["downtime_mins"] for i in closed_eb) / len(closed_eb))
        if closed_eb else 0
    )

    return jsonify({
        "success": True,
        "engineering": {
            "total": len(eb),
            "open": len(eb_open),
            "critical_open": len(eb_crit),
            "avg_downtime_mins": avg_downtime,
        },
        "flying_squad": {
            "total": len(fs),
            "active": len(fs_active),
        },
        "workshop": {
            "total": len(ws),
            "active": len(ws_active),
        },
        "sla_breaches": sla_breaches,
        "meta": data.get("meta", {}),
    })


@breakdown_bp.route("/config", methods=["GET"])
@_login_required
def get_config():
    """Return dropdown options for the log form."""
    return jsonify({
        "properties": PROPERTIES,
        "systems":    SYSTEMS,
        "severities": SEVERITIES,
        "eb_statuses": EB_STATUSES,
        "fs_statuses": FS_STATUSES,
        "ws_statuses": WS_STATUSES,
        "priorities": PRIORITIES,
    })


# ─────────────────────────────────────────────────────────────────────────────
# SLA target (minutes) by severity
# ─────────────────────────────────────────────────────────────────────────────
def _sla_target(severity: str) -> int:
    return {"Critical": 60, "High": 120, "Medium": 240, "Low": 480}.get(severity, 240)