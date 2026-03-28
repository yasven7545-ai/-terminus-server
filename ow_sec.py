"""
OW SECURITY MODULE — FLASK ROUTES
ow_sec.py

Prefix: ow_ for all function, route, and file names.
Integrates with main server.py (app Flask instance).
Persistent JSON storage in static/data/ow_sec_*.json

FIX: Uses single <string:key> dispatcher routes instead of a factory loop,
     which caused "overwriting an existing endpoint function" errors in Flask.
"""

from flask import Blueprint, jsonify, request
from pathlib import Path
from datetime import datetime
from functools import wraps
import json
import threading

# ══════════════════════════════════════════════════
# BLUEPRINT
# ══════════════════════════════════════════════════
ow_sec_bp = Blueprint("ow_sec", __name__, url_prefix="")

# ══════════════════════════════════════════════════
# PATHS
# ══════════════════════════════════════════════════
_BASE = Path(__file__).parent.resolve()
_DATA = _BASE / "static" / "data"
_DATA.mkdir(parents=True, exist_ok=True)

def _ow_sec_path(key: str) -> Path:
    return _DATA / f"ow_sec_{key}.json"

# ══════════════════════════════════════════════════
# STORAGE HELPERS
# ══════════════════════════════════════════════════
_ow_sec_lock = threading.Lock()

def ow_sec_load(key: str) -> list:
    p = _ow_sec_path(key)
    try:
        if p.exists():
            with open(p, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data if isinstance(data, list) else []
    except Exception:
        pass
    return []

def ow_sec_save(key: str, data: list) -> None:
    p   = _ow_sec_path(key)
    tmp = p.with_suffix(".tmp")
    with _ow_sec_lock:
        try:
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2, default=str)
            tmp.replace(p)
        except Exception as e:
            print(f"[ow_sec] Save error ({key}): {e}")

def ow_sec_now_str()   -> str: return datetime.now().strftime("%H:%M")
def ow_sec_today_str() -> str: return datetime.now().strftime("%Y-%m-%d")

# ══════════════════════════════════════════════════
# VALID KEYS  (whitelist — prevents arbitrary file access)
# ══════════════════════════════════════════════════
OW_SEC_KEYS = {
    "guards", "patrol", "visitors", "vendors",
    "service", "material", "vehicles", "incidents",
    "latenight", "idcheck", "guests"
}

def _bad_key(key):
    if key not in OW_SEC_KEYS:
        return jsonify({"success": False, "error": f"Unknown module: {key}"}), 400
    return None

# ══════════════════════════════════════════════════
# PAGE ROUTE
# ══════════════════════════════════════════════════
@ow_sec_bp.route("/ow_sec")
@ow_sec_bp.route("/ow_security")
def ow_sec_page():
    for path in [
        _BASE / "templates" / "ow_sec.html",
        _BASE / "static"    / "ow_sec.html",
    ]:
        if path.exists():
            from flask import send_from_directory
            return send_from_directory(str(path.parent), path.name)
    return "ow_sec.html not found — place it in templates/ or static/", 404

# ══════════════════════════════════════════════════
# API — FULL DATA DUMP  (page load)
# ══════════════════════════════════════════════════
@ow_sec_bp.route("/api/ow_sec/data", methods=["GET"])
def ow_sec_get_all():
    result = {k: ow_sec_load(k) for k in OW_SEC_KEYS}
    result["meta"] = {
        "timestamp": datetime.now().isoformat(),
        "property":  "OneWest",
        "module":    "Security",
    }
    return jsonify(result)

# ══════════════════════════════════════════════════
# API — LIVE COUNTERS
# ══════════════════════════════════════════════════
@ow_sec_bp.route("/api/ow_sec/counters", methods=["GET"])
def ow_sec_counters():
    guards    = ow_sec_load("guards")
    incidents = ow_sec_load("incidents")
    visitors  = ow_sec_load("visitors")
    vehicles  = ow_sec_load("vehicles")
    patrol    = ow_sec_load("patrol")
    material  = ow_sec_load("material")
    vendors   = ow_sec_load("vendors")
    done      = sum(1 for p in patrol if p.get("status") == "Completed")
    total     = len(patrol) or 1
    return jsonify({
        "guards_on_duty":    sum(1 for g in guards    if g.get("status") == "On Duty"),
        "open_incidents":    sum(1 for i in incidents  if i.get("status") == "Open"),
        "visitors_inside":   sum(1 for v in visitors   if v.get("status") == "Inside"),
        "vehicles_inside":   sum(1 for v in vehicles   if v.get("status") == "Inside"),
        "missed_patrols":    sum(1 for p in patrol     if p.get("status") == "Missed"),
        "patrol_compliance": round(done / total * 100),
        "material_pending":  sum(1 for m in material   if m.get("status") == "Pending"),
        "vendors_inside":    sum(1 for v in vendors    if not v.get("exit")),
        "timestamp":         datetime.now().isoformat(),
    })

# ══════════════════════════════════════════════════
# API — DAILY SUMMARY
# ══════════════════════════════════════════════════
@ow_sec_bp.route("/api/ow_sec/daily_summary", methods=["GET"])
def ow_sec_daily_summary():
    today = ow_sec_today_str()
    def _t(recs): return [r for r in recs if str(r.get("date", r.get("created_at",""))).startswith(today)]
    guards    = ow_sec_load("guards")
    incidents = ow_sec_load("incidents")
    visitors  = ow_sec_load("visitors")
    patrol    = ow_sec_load("patrol")
    vehicles  = ow_sec_load("vehicles")
    ti        = _t(incidents)
    return jsonify({
        "date":             today,
        "property":         "OneWest",
        "guards_on_duty":   sum(1 for g in guards    if g.get("status") == "On Duty"),
        "incidents_today":  len(ti),
        "open_incidents":   sum(1 for i in incidents  if i.get("status") == "Open"),
        "high_severity":    sum(1 for i in ti         if i.get("severity") == "High"),
        "visitors_today":   len(_t(visitors)),
        "patrol_done":      sum(1 for p in patrol     if p.get("status") == "Completed"),
        "patrol_missed":    sum(1 for p in patrol     if p.get("status") == "Missed"),
        "vehicles_logged":  len(_t(vehicles)),
        "incidents_detail": ti[:10],
    })

# ══════════════════════════════════════════════════
# API — GENERIC CRUD  via single dispatcher routes
#
#  WHY: Using a factory function inside a for-loop causes Flask to see
#  repeated endpoint names (_get, _post …) and raises:
#    "View function mapping is overwriting an existing endpoint function"
#
#  SOLUTION: One named route per HTTP verb, with <string:key> as the
#  module selector. Flask gives each view a unique name automatically.
# ══════════════════════════════════════════════════

@ow_sec_bp.route("/api/ow_sec/<string:key>", methods=["GET"])
def ow_sec_list(key):
    err = _bad_key(key)
    if err: return err
    data = ow_sec_load(key)
    return jsonify({"success": True, "data": data, "count": len(data)})


@ow_sec_bp.route("/api/ow_sec/<string:key>", methods=["POST"])
def ow_sec_add(key):
    err = _bad_key(key)
    if err: return err
    body = request.get_json(force=True, silent=True) or {}
    if not body:
        return jsonify({"success": False, "error": "Empty body"}), 400
    body.setdefault("created_at", datetime.now().isoformat())
    body.setdefault("date",       ow_sec_today_str())
    data = ow_sec_load(key)
    data.insert(0, body)
    ow_sec_save(key, data)
    return jsonify({"success": True, "record": body, "total": len(data)}), 201


@ow_sec_bp.route("/api/ow_sec/<string:key>/<int:idx>", methods=["PUT", "PATCH"])
def ow_sec_update(key, idx):
    err = _bad_key(key)
    if err: return err
    body = request.get_json(force=True, silent=True) or {}
    data = ow_sec_load(key)
    if idx < 0 or idx >= len(data):
        return jsonify({"success": False, "error": "Index out of range"}), 404
    data[idx].update(body)
    data[idx]["updated_at"] = datetime.now().isoformat()
    ow_sec_save(key, data)
    return jsonify({"success": True, "record": data[idx]})


@ow_sec_bp.route("/api/ow_sec/<string:key>/<int:idx>", methods=["DELETE"])
def ow_sec_delete(key, idx):
    err = _bad_key(key)
    if err: return err
    data = ow_sec_load(key)
    if idx < 0 or idx >= len(data):
        return jsonify({"success": False, "error": "Index out of range"}), 404
    removed = data.pop(idx)
    ow_sec_save(key, data)
    return jsonify({"success": True, "removed": removed, "total": len(data)})

# ══════════════════════════════════════════════════
# API — BULK IMPORT  (Excel rows as JSON array)
# ══════════════════════════════════════════════════
@ow_sec_bp.route("/api/ow_sec/import/<string:key>", methods=["POST"])
def ow_sec_bulk_import(key):
    err = _bad_key(key)
    if err: return err
    body = request.get_json(force=True, silent=True)
    if not isinstance(body, list):
        return jsonify({"success": False, "error": "Expected JSON array"}), 400
    now = datetime.now().isoformat()
    for rec in body:
        if isinstance(rec, dict):
            rec.setdefault("created_at", now)
    merged = body + ow_sec_load(key)
    ow_sec_save(key, merged)
    return jsonify({"success": True, "imported": len(body), "total": len(merged)})

# ══════════════════════════════════════════════════
# API — QUICK-ACTION SHORTCUTS
# ══════════════════════════════════════════════════

@ow_sec_bp.route("/api/ow_sec/incidents/<int:idx>/resolve", methods=["POST"])
def ow_sec_resolve_incident(idx):
    body = request.get_json(force=True, silent=True) or {}
    data = ow_sec_load("incidents")
    if idx < 0 or idx >= len(data):
        return jsonify({"success": False, "error": "Not found"}), 404
    data[idx].update({
        "status":      "Closed",
        "resolved_by": body.get("resolved_by", "Security Team"),
        "resolved_at": datetime.now().isoformat(),
    })
    ow_sec_save("incidents", data)
    return jsonify({"success": True, "record": data[idx]})


@ow_sec_bp.route("/api/ow_sec/visitors/<int:idx>/exit", methods=["POST"])
def ow_sec_visitor_exit(idx):
    data = ow_sec_load("visitors")
    if idx < 0 or idx >= len(data):
        return jsonify({"success": False}), 404
    data[idx].update({"exit": ow_sec_now_str(), "status": "Exited"})
    ow_sec_save("visitors", data)
    return jsonify({"success": True})


@ow_sec_bp.route("/api/ow_sec/vendors/<int:idx>/exit", methods=["POST"])
def ow_sec_vendor_exit(idx):
    data = ow_sec_load("vendors")
    if idx < 0 or idx >= len(data):
        return jsonify({"success": False}), 404
    data[idx]["exit"] = ow_sec_now_str()
    ow_sec_save("vendors", data)
    return jsonify({"success": True})


@ow_sec_bp.route("/api/ow_sec/vehicles/<int:idx>/exit", methods=["POST"])
def ow_sec_vehicle_exit(idx):
    data = ow_sec_load("vehicles")
    if idx < 0 or idx >= len(data):
        return jsonify({"success": False}), 404
    data[idx].update({"exit": ow_sec_now_str(), "status": "Exited"})
    ow_sec_save("vehicles", data)
    return jsonify({"success": True})


@ow_sec_bp.route("/api/ow_sec/guards/<int:idx>/checkout", methods=["POST"])
def ow_sec_guard_checkout(idx):
    data = ow_sec_load("guards")
    if idx < 0 or idx >= len(data):
        return jsonify({"success": False}), 404
    data[idx].update({"checkout": ow_sec_now_str(), "status": "Off Duty"})
    ow_sec_save("guards", data)
    return jsonify({"success": True})


@ow_sec_bp.route("/api/ow_sec/material/<int:idx>/approve", methods=["POST"])
def ow_sec_material_approve(idx):
    body = request.get_json(force=True, silent=True) or {}
    data = ow_sec_load("material")
    if idx < 0 or idx >= len(data):
        return jsonify({"success": False}), 404
    data[idx].update({
        "status":      "Approved",
        "approved_by": body.get("approved_by", "Security Supervisor"),
        "approved_at": datetime.now().isoformat(),
    })
    ow_sec_save("material", data)
    return jsonify({"success": True, "record": data[idx]})

# ══════════════════════════════════════════════════
# REGISTER  (called from server.py)
# ══════════════════════════════════════════════════
def ow_sec_register(app):
    """
    Drop-in registration — add ONE line to server.py:

        from ow_sec import ow_sec_register
        ow_sec_register(app)
    """
    app.register_blueprint(ow_sec_bp)
    print("✅ [ow_sec] Security module registered")
    print("   🔒 Page  : /ow_sec  |  /ow_security")
    print("   📡 CRUD  : /api/ow_sec/<module>  (GET · POST · PUT · DELETE)")
    print("   📊 Data  : /api/ow_sec/data")
    print("   📈 Stats : /api/ow_sec/counters")
    return ow_sec_bp

# ══════════════════════════════════════════════════
# STANDALONE TEST  →  python ow_sec.py
# ══════════════════════════════════════════════════
if __name__ == "__main__":
    from flask import Flask
    _app = Flask(__name__, template_folder="templates", static_folder="static")
    _app.secret_key = "ow-sec-dev-2026"
    ow_sec_register(_app)

    # Seed sample data if files don't exist yet
    if not _ow_sec_path("guards").exists():
        ow_sec_save("guards", [
            {"id":"GD-001","name":"Rajesh Kumar","location":"Main Gate","shift":"Day",
             "supervisor":"Suresh Singh","checkin":"08:00","checkout":"","status":"On Duty"},
            {"id":"GD-002","name":"Manoj Yadav","location":"Lobby","shift":"Day",
             "supervisor":"Suresh Singh","checkin":"08:00","checkout":"","status":"On Duty"},
            {"id":"GD-003","name":"Vikram Patil","location":"Parking","shift":"Night",
             "supervisor":"Suresh Singh","checkin":"20:00","checkout":"","status":"On Duty"},
        ])
    if not _ow_sec_path("incidents").exists():
        ow_sec_save("incidents", [
            {"type":"Unauthorized Access","location":"B3 Parking","severity":"High",
             "status":"Open","reported_by":"Rajesh Kumar",
             "date":ow_sec_today_str(),"time":"09:14",
             "description":"Unauthorized vehicle detected in B3 parking."},
            {"type":"Suspicious Vehicle","location":"Gate 2","severity":"Medium",
             "status":"Open","reported_by":"Manoj Yadav",
             "date":ow_sec_today_str(),"time":"10:45",
             "description":"Vehicle parked near Gate 2 for over 2 hours."},
        ])

    print("\n" + "="*60)
    print("🔒  OW SECURITY — STANDALONE TEST  →  http://localhost:5001/ow_sec")
    print("="*60 + "\n")
    _app.run(host="0.0.0.0", port=5001, debug=True)