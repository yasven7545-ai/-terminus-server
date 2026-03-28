"""
TERMINUS MMS — MOBILE API ROUTES  (api_routes.py)
====================================================
JWT-based REST API for mobile applications.
All existing web routes and blueprints are left untouched.

Auth flow:
  POST /mobile/api/login  →  { token, user, role, properties }
  All other endpoints:    Authorization: Bearer <token>

The token payload carries the same session fields that the web
layer stores in Flask-Session, so every downstream helper that
reads session["user"], session["role"], etc. still works when
the request flows through the mobile decorators below.
"""

from flask import Blueprint, request, jsonify, g
from functools import wraps
import json, hmac, hashlib, base64, time, traceback
from datetime import datetime
from pathlib import Path

# ── Blueprint ────────────────────────────────────────────────────────────────
mobile_api = Blueprint("mobile_api", __name__, url_prefix="/mobile/api")

# ── Shared secret for signing tokens (change in production) ──────────────────
_TOKEN_SECRET = "terminus-mobile-jwt-secret-2026"
_TOKEN_TTL    = 86400          # 24 hours


# =====================================================================
# TOKEN HELPERS  (lightweight HMAC-signed JWT — no extra deps needed)
# =====================================================================

def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()

def _b64url_decode(s: str) -> bytes:
    pad = 4 - len(s) % 4
    return base64.urlsafe_b64decode(s + "=" * (pad % 4))

def create_token(payload: dict) -> str:
    """Create a signed token carrying the user payload."""
    header  = _b64url(json.dumps({"alg": "HS256", "typ": "JWT"}).encode())
    payload = dict(payload, iat=int(time.time()), exp=int(time.time()) + _TOKEN_TTL)
    body    = _b64url(json.dumps(payload).encode())
    sig     = _b64url(
        hmac.new(_TOKEN_SECRET.encode(), f"{header}.{body}".encode(), hashlib.sha256).digest()
    )
    return f"{header}.{body}.{sig}"

def verify_token(token: str) -> dict | None:
    """Verify signature + expiry. Returns payload dict or None."""
    try:
        header, body, sig = token.split(".")
        expected = _b64url(
            hmac.new(_TOKEN_SECRET.encode(), f"{header}.{body}".encode(), hashlib.sha256).digest()
        )
        if not hmac.compare_digest(sig, expected):
            return None
        payload = json.loads(_b64url_decode(body))
        if payload.get("exp", 0) < time.time():
            return None
        return payload
    except Exception:
        return None


# =====================================================================
# DECORATORS
# =====================================================================

def mobile_login_required(f):
    """Verify Bearer token; expose payload as g.mobile_user."""
    @wraps(f)
    def wrapper(*args, **kwargs):
        auth = request.headers.get("Authorization", "")
        if not auth.startswith("Bearer "):
            return jsonify({"success": False, "error": "Missing or invalid token"}), 401
        payload = verify_token(auth[7:])
        if not payload:
            return jsonify({"success": False, "error": "Token expired or invalid"}), 401
        g.mobile_user = payload
        return f(*args, **kwargs)
    return wrapper


def mobile_require_property(property_name):
    """Enforce property access on mobile endpoints."""
    def decorator(f):
        @wraps(f)
        @mobile_login_required
        def wrapper(*args, **kwargs):
            bypass = {"admin", "management", "general manager", "property manager"}
            role   = (g.mobile_user.get("role") or "").lower()
            props  = g.mobile_user.get("properties", [])
            if role in bypass or property_name in props:
                return f(*args, **kwargs)
            return jsonify({"success": False, "error": f"No access to {property_name}"}), 403
        return wrapper
    return decorator


# =====================================================================
# USER STORE  (mirrors USERS dict in server.py — single source of truth)
# Imported lazily so this file can be used standalone too.
# =====================================================================

def _get_users():
    try:
        import server as _srv
        return _srv.USERS
    except Exception:
        return {}

def _get_role_modules():
    try:
        import server as _srv
        return _srv.ROLE_MODULES, _srv.PROPERTY_MODULES
    except Exception:
        return {}, {}


# =====================================================================
# 1.  AUTH — LOGIN
# =====================================================================

@mobile_api.route("/login", methods=["POST"])
def mobile_login():
    """
    POST /mobile/api/login
    Body (JSON):  { username, password, property }
    Returns:      { success, token, user, role, properties, active_property }
    """
    data          = request.get_json(force=True) or {}
    username      = (data.get("username") or "").strip()
    password      = (data.get("password") or "").strip()
    property_name = (data.get("property")  or "").strip()

    USERS = _get_users()

    if username not in USERS:
        return jsonify({"success": False, "error": "User not found"}), 401

    user_data = USERS[username]

    if user_data["password"] != password:
        return jsonify({"success": False, "error": "Invalid password"}), 401

    if property_name and property_name not in user_data["properties"]:
        return jsonify({
            "success": False,
            "error": f"No access to {property_name}"
        }), 403

    active_property = property_name or user_data["properties"][0]

    payload = {
        "user":            username,
        "role":            user_data["role"],
        "properties":      user_data["properties"],
        "active_property": active_property,
    }
    token = create_token(payload)

    return jsonify({
        "success":         True,
        "token":           token,
        "user":            username,
        "role":            user_data["role"],
        "properties":      user_data["properties"],
        "active_property": active_property,
    })


# =====================================================================
# 2.  AUTH — TOKEN REFRESH
# =====================================================================

@mobile_api.route("/refresh", methods=["POST"])
@mobile_login_required
def mobile_refresh():
    """Refresh a valid token before it expires."""
    payload = {k: v for k, v in g.mobile_user.items() if k not in ("iat", "exp")}
    return jsonify({"success": True, "token": create_token(payload)})


# =====================================================================
# 3.  USER PROFILE
# =====================================================================

@mobile_api.route("/profile", methods=["GET"])
@mobile_login_required
def mobile_profile():
    """
    GET /mobile/api/profile
    Returns the authenticated user's profile + allowed modules.
    """
    role            = g.mobile_user.get("role", "Technician")
    active_property = g.mobile_user.get("active_property", "SLN Terminus")

    ROLE_MODULES, PROPERTY_MODULES = _get_role_modules()
    role_mods     = ROLE_MODULES.get(role, ROLE_MODULES.get("Technician", []))
    prop_mods     = PROPERTY_MODULES.get(active_property, [])
    full_access   = {"admin", "management", "general manager", "property manager"}
    allowed_mods  = prop_mods if role.lower() in full_access else [m for m in role_mods if m in prop_mods]

    return jsonify({
        "success":         True,
        "username":        g.mobile_user.get("user", ""),
        "role":            role,
        "active_property": active_property,
        "properties":      g.mobile_user.get("properties", []),
        "allowed_modules": allowed_mods,
    })


# =====================================================================
# 4.  PROPERTY STATUS  (mirrors /api/properties/status)
# =====================================================================

@mobile_api.route("/properties/status", methods=["GET"])
@mobile_login_required
def mobile_properties_status():
    """
    GET /mobile/api/properties/status
    Returns live open-WO + alert counts for all properties.
    """
    try:
        BASE_DIR = Path(__file__).parent.resolve()
        WO_JSON  = BASE_DIR / "static" / "data" / "work_orders.json"

        wo_counts    = {p: 0 for p in ["SLN Terminus", "ONEWEST", "The District",
                                        "One Golden Mile", "Nine Hills"]}
        alert_counts = {p: 0 for p in wo_counts}

        if WO_JSON.exists():
            with open(WO_JSON, encoding="utf-8") as f:
                wos = json.load(f).get("work_orders", [])
            open_statuses = {"open", "in-progress", "overdue"}
            for wo in wos:
                prop = wo.get("location", wo.get("property", ""))
                if prop in wo_counts and wo.get("status", "").lower() in open_statuses:
                    wo_counts[prop] += 1

        bd_file = BASE_DIR / "static" / "data" / "breakdown_data.json"
        if bd_file.exists():
            with open(bd_file, encoding="utf-8") as f:
                bd = json.load(f)
            for ticket in bd.get("engineering_breakdowns", []):
                prop = ticket.get("property", "")
                if prop in alert_counts and ticket.get("status") not in ("Resolved", "Closed"):
                    alert_counts[prop] += 1

        properties = [
            {"id": "sln", "name": "SLN Terminus",    "code": "SLN", "type": "Commercial",
             "city": "Hyderabad", "status": "online",   "redirect": "/sln_terminus",
             "open_wo": wo_counts["SLN Terminus"],    "alerts": alert_counts["SLN Terminus"]},
            {"id": "ow",  "name": "ONEWEST",          "code": "OW",  "type": "Commercial",
             "city": "Hyderabad", "status": "online",   "redirect": "/onewest",
             "open_wo": wo_counts["ONEWEST"],          "alerts": alert_counts["ONEWEST"]},
            {"id": "td",  "name": "The District",     "code": "TD",  "type": "Commercial",
             "city": "Hyderabad", "status": "attention","redirect": "/the_district",
             "open_wo": wo_counts["The District"],     "alerts": alert_counts["The District"]},
            {"id": "ogm", "name": "One Golden Mile",  "code": "OGM", "type": "Commercial",
             "city": "Hyderabad", "status": "online",   "redirect": "/ogm",
             "open_wo": wo_counts["One Golden Mile"],  "alerts": alert_counts["One Golden Mile"]},
            {"id": "nh",  "name": "Nine Hills",       "code": "NH",  "type": "Life Science",
             "city": "Hyderabad", "status": "online",   "redirect": "/nine_hills",
             "open_wo": wo_counts["Nine Hills"],       "alerts": alert_counts["Nine Hills"]},
        ]
        return jsonify({"success": True, "properties": properties,
                        "generated_at": datetime.now().isoformat()})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# =====================================================================
# 5.  WORK ORDERS
# =====================================================================

@mobile_api.route("/work_orders", methods=["GET"])
@mobile_login_required
def mobile_work_orders_list():
    """
    GET /mobile/api/work_orders?property=SLN+Terminus&status=open&limit=50
    Returns paginated work-order list.
    """
    try:
        BASE_DIR = Path(__file__).parent.resolve()
        WO_JSON  = BASE_DIR / "static" / "data" / "work_orders.json"

        prop_filter   = request.args.get("property", "").strip()
        status_filter = request.args.get("status",   "").strip().lower()
        limit         = min(int(request.args.get("limit", 100)), 500)
        offset        = int(request.args.get("offset", 0))

        wos = []
        if WO_JSON.exists():
            with open(WO_JSON, encoding="utf-8") as f:
                wos = json.load(f).get("work_orders", [])

        if prop_filter:
            wos = [w for w in wos if w.get("location", w.get("property", "")) == prop_filter]
        if status_filter:
            wos = [w for w in wos if w.get("status", "").lower() == status_filter]

        total = len(wos)
        page  = wos[offset: offset + limit]

        return jsonify({"success": True, "work_orders": page,
                        "total": total, "limit": limit, "offset": offset})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@mobile_api.route("/work_orders/<wo_id>", methods=["GET"])
@mobile_login_required
def mobile_work_order_detail(wo_id):
    """GET /mobile/api/work_orders/<wo_id>"""
    try:
        BASE_DIR = Path(__file__).parent.resolve()
        WO_JSON  = BASE_DIR / "static" / "data" / "work_orders.json"

        if WO_JSON.exists():
            with open(WO_JSON, encoding="utf-8") as f:
                wos = json.load(f).get("work_orders", [])
            for wo in wos:
                if str(wo.get("id")) == str(wo_id):
                    return jsonify({"success": True, "work_order": wo})

        return jsonify({"success": False, "error": "Work order not found"}), 404
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@mobile_api.route("/work_orders/<wo_id>/status", methods=["PATCH"])
@mobile_login_required
def mobile_update_wo_status(wo_id):
    """
    PATCH /mobile/api/work_orders/<wo_id>/status
    Body: { "status": "Completed" }
    """
    try:
        data      = request.get_json(force=True) or {}
        new_status = data.get("status", "").strip()
        if not new_status:
            return jsonify({"success": False, "error": "status required"}), 400

        BASE_DIR = Path(__file__).parent.resolve()
        WO_JSON  = BASE_DIR / "static" / "data" / "work_orders.json"

        if not WO_JSON.exists():
            return jsonify({"success": False, "error": "Work orders data not found"}), 404

        with open(WO_JSON, encoding="utf-8") as f:
            data_store = json.load(f)

        updated = False
        for wo in data_store.get("work_orders", []):
            if str(wo.get("id")) == str(wo_id):
                wo["status"]    = new_status
                wo["updatedAt"] = datetime.now().isoformat()
                wo["updatedBy"] = g.mobile_user.get("user", "mobile")
                updated = True
                break

        if not updated:
            return jsonify({"success": False, "error": "Work order not found"}), 404

        with open(WO_JSON, "w", encoding="utf-8") as f:
            json.dump(data_store, f, indent=2)

        return jsonify({"success": True, "id": wo_id, "status": new_status})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# =====================================================================
# 6.  ISSUES / DAILY LOG
# =====================================================================

@mobile_api.route("/issues", methods=["GET"])
@mobile_login_required
def mobile_issues_list():
    """
    GET /mobile/api/issues?property=SLN+Terminus&status=open&limit=50
    """
    try:
        BASE_DIR     = Path(__file__).parent.resolve()
        issues_file  = BASE_DIR / "static" / "data" / "issues.json"

        prop_filter   = request.args.get("property", "").strip()
        status_filter = request.args.get("status",   "").strip().lower()
        limit         = min(int(request.args.get("limit", 100)), 500)
        offset        = int(request.args.get("offset", 0))

        issues = []
        if issues_file.exists():
            with open(issues_file, encoding="utf-8") as f:
                issues = json.load(f)

        if isinstance(issues, dict):
            issues = issues.get("issues", [])

        if prop_filter:
            issues = [i for i in issues if i.get("property", i.get("location", "")) == prop_filter]
        if status_filter:
            issues = [i for i in issues if i.get("status", "").lower() == status_filter]

        total = len(issues)
        return jsonify({"success": True, "issues": issues[offset: offset + limit],
                        "total": total, "limit": limit, "offset": offset})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# =====================================================================
# 7.  PPM ASSETS  (mirrors /api/ppm/assets)
# =====================================================================

@mobile_api.route("/ppm/assets", methods=["GET"])
@mobile_login_required
def mobile_ppm_assets():
    """GET /mobile/api/ppm/assets?location=<loc>"""
    try:
        import pandas as pd
        BASE_DIR     = Path(__file__).parent.resolve()
        ASSETS_XLSX  = BASE_DIR / "static" / "data" / "Assets.xlsx"
        location_filter = request.args.get("location", "all").strip()

        if not ASSETS_XLSX.exists():
            return jsonify({"assets": [], "total": 0})

        df = pd.read_excel(ASSETS_XLSX, engine="openpyxl")
        assets = []
        for _, row in df.iterrows():
            asset_code = str(row.get("Asset Code", "")).strip()
            if not asset_code or asset_code.lower() in ("nan", "none", ""):
                continue
            asset = {
                "id":          asset_code,
                "name":        str(row.get("Asset Name", "Unknown Asset")).strip(),
                "category":    str(row.get("In-House/Vendor", "General")).strip(),
                "location":    str(row.get("Location", "Unknown")).strip(),
                "lastService": str(row.get("Last Service", "")).strip(),
                "nextDueDate": str(row.get("nextDueDate", "")).strip(),
                "colorCode":   "Green",
            }
            assets.append(asset)

        if location_filter not in ("all", ""):
            assets = [a for a in assets if a.get("location", "").strip() == location_filter]

        return jsonify({"success": True, "assets": assets, "total": len(assets)})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# =====================================================================
# 8.  GM TASKS
# =====================================================================

def _load_gm_tasks_mobile():
    BASE_DIR   = Path(__file__).parent.resolve()
    tasks_file = BASE_DIR / "static" / "data" / "gm_tasks.json"
    if tasks_file.exists():
        with open(tasks_file, encoding="utf-8") as f:
            return json.load(f)
    return []

def _save_gm_tasks_mobile(tasks):
    BASE_DIR   = Path(__file__).parent.resolve()
    tasks_file = BASE_DIR / "static" / "data" / "gm_tasks.json"
    tasks_file.parent.mkdir(parents=True, exist_ok=True)
    with open(tasks_file, "w", encoding="utf-8") as f:
        json.dump(tasks, f, indent=2)


@mobile_api.route("/gm_tasks", methods=["GET"])
@mobile_login_required
def mobile_gm_tasks_list():
    """GET /mobile/api/gm_tasks?site=<site>&status=<status>"""
    try:
        tasks         = _load_gm_tasks_mobile()
        site_filter   = request.args.get("site",   "").strip()
        status_filter = request.args.get("status", "").strip()

        if site_filter:
            tasks = [t for t in tasks if t.get("site", "") == site_filter]
        if status_filter:
            tasks = [t for t in tasks if t.get("status", "").lower() == status_filter.lower()]

        return jsonify({"success": True, "tasks": tasks, "total": len(tasks)})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@mobile_api.route("/gm_tasks", methods=["POST"])
@mobile_login_required
def mobile_gm_tasks_add():
    """POST /mobile/api/gm_tasks  — create a new GM task."""
    try:
        task = request.get_json(force=True) or {}
        if not task.get("description"):
            return jsonify({"success": False, "error": "description required"}), 400

        task.setdefault("id",       f"task_{int(datetime.now().timestamp()*1000)}")
        task.setdefault("status",   "Open")
        task.setdefault("priority", "Medium")
        task.setdefault("date",     datetime.now().strftime("%Y-%m-%d"))
        task["updatedAt"] = datetime.now().isoformat()
        task["createdBy"] = g.mobile_user.get("user", "mobile")

        tasks = _load_gm_tasks_mobile()
        tasks.insert(0, task)
        _save_gm_tasks_mobile(tasks)

        return jsonify({"success": True, "task": task, "total": len(tasks)}), 201
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@mobile_api.route("/gm_tasks/<task_id>", methods=["PATCH"])
@mobile_login_required
def mobile_gm_tasks_update(task_id):
    """PATCH /mobile/api/gm_tasks/<task_id>  — update fields."""
    try:
        updates = request.get_json(force=True) or {}
        tasks   = _load_gm_tasks_mobile()
        updated = False
        for t in tasks:
            if t.get("id") == task_id:
                t.update({k: v for k, v in updates.items() if k not in ("id",)})
                t["updatedAt"] = datetime.now().isoformat()
                updated = True
                break

        if not updated:
            return jsonify({"success": False, "error": "Task not found"}), 404

        _save_gm_tasks_mobile(tasks)
        return jsonify({"success": True, "id": task_id})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# =====================================================================
# 9.  DASHBOARD SUMMARY  (single aggregated call for mobile home screen)
# =====================================================================

@mobile_api.route("/dashboard/summary", methods=["GET"])
@mobile_login_required
def mobile_dashboard_summary():
    """
    GET /mobile/api/dashboard/summary
    Returns open WO counts, overdue counts, and alert counts per property
    — a single lightweight call to hydrate the mobile home screen.
    """
    try:
        BASE_DIR = Path(__file__).parent.resolve()
        WO_JSON  = BASE_DIR / "static" / "data" / "work_orders.json"

        summary = {
            "open_work_orders": 0,
            "overdue_work_orders": 0,
            "total_alerts": 0,
            "generated_at": datetime.now().isoformat(),
        }

        if WO_JSON.exists():
            with open(WO_JSON, encoding="utf-8") as f:
                wos = json.load(f).get("work_orders", [])
            active_property = g.mobile_user.get("active_property")
            for wo in wos:
                prop   = wo.get("location", wo.get("property", ""))
                status = wo.get("status", "").lower()
                if active_property and prop != active_property:
                    continue
                if status in ("open", "in-progress"):
                    summary["open_work_orders"] += 1
                if status == "overdue":
                    summary["overdue_work_orders"] += 1

        bd_file = BASE_DIR / "static" / "data" / "breakdown_data.json"
        if bd_file.exists():
            with open(bd_file, encoding="utf-8") as f:
                bd = json.load(f)
            active_property = g.mobile_user.get("active_property")
            for ticket in bd.get("engineering_breakdowns", []):
                if ticket.get("status") in ("Resolved", "Closed"):
                    continue
                if active_property and ticket.get("property") != active_property:
                    continue
                summary["total_alerts"] += 1

        return jsonify({"success": True, "summary": summary})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# =====================================================================
# 10. HEALTH CHECK
# =====================================================================

@mobile_api.route("/health", methods=["GET"])
def mobile_health():
    """GET /mobile/api/health  — unauthenticated liveness probe."""
    return jsonify({
        "status":    "ok",
        "service":   "Terminus MMS Mobile API",
        "timestamp": datetime.now().isoformat(),
    })
