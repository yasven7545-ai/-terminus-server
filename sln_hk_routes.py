"""
SLN HOUSEKEEPING MODULE — ROUTES
Blueprint: sln_hk_bp
Prefix:    /sln_hk
─────────────────────────────────────────────────────────────────────────────
FEATURES
  • Dashboard + KPI
  • Tasks          – CRUD + photo upload per task
  • Checklist      – daily checklist items CRUD
  • Zones          – status cycle (Pending → In Progress → Cleaned) + photo
  • Staff          – full directory CRUD (name / role / shift / contact / photo)
  • Inventory      – Excel import + manual CRUD + stock movement
  • SOW            – Scope-of-Work table
  • Schedules      – shift schedules CRUD
  • Washroom       – location checklist + log
  • Pest Control   – CRUD
  • Training       – CRUD + photo / document upload
  • Charts         – aggregated data endpoint
  • Export         – full XLSX dump
─────────────────────────────────────────────────────────────────────────────
"""

from flask import (Blueprint, render_template, request, jsonify,
                   session, redirect, url_for, send_file, abort)
from functools import wraps
from pathlib import Path
from datetime import datetime
from werkzeug.utils import secure_filename
import json, os, io

# ── optional Excel support ────────────────────────────────────────────────────
try:
    import pandas as pd
    import openpyxl
    EXCEL_OK = True
except ImportError:
    EXCEL_OK = False

# ─────────────────────────────────────────────────────────────────────────────
# BLUEPRINT & PATHS
# ─────────────────────────────────────────────────────────────────────────────
sln_hk_bp = Blueprint("sln_hk", __name__,
                       url_prefix="/sln_hk",
                       template_folder="templates",
                       static_folder="static")

BASE_DIR   = Path(__file__).parent.resolve()
DATA_DIR   = BASE_DIR / "static" / "data" / "sln_hk"

# Upload roots
UPLOAD_ROOT   = BASE_DIR / "uploads" / "sln_hk"
TASK_PHOTOS   = UPLOAD_ROOT / "task_photos"
ZONE_PHOTOS   = UPLOAD_ROOT / "zone_photos"
TRAINING_DOCS = UPLOAD_ROOT / "training"
STAFF_PHOTOS  = UPLOAD_ROOT / "staff_photos"

for _d in [DATA_DIR, TASK_PHOTOS, ZONE_PHOTOS, TRAINING_DOCS, STAFF_PHOTOS]:
    _d.mkdir(parents=True, exist_ok=True)

# ── JSON data files ────────────────────────────────────────────────────────
HK_TASKS_FILE      = DATA_DIR / "hk_tasks.json"
HK_CHECKLIST_FILE  = DATA_DIR / "hk_checklist.json"
HK_ZONES_FILE      = DATA_DIR / "hk_zones.json"
HK_STAFF_FILE      = DATA_DIR / "hk_staff.json"
HK_INVENTORY_FILE  = DATA_DIR / "hk_inventory.json"
HK_SOW_FILE        = DATA_DIR / "hk_sow.json"
HK_SCHEDULES_FILE  = DATA_DIR / "hk_schedules.json"
HK_WC_FILE         = DATA_DIR / "hk_wc.json"
HK_PEST_FILE       = DATA_DIR / "hk_pest.json"
HK_TRAINING_FILE   = DATA_DIR / "hk_training.json"

# ── Allowed extensions ────────────────────────────────────────────────────
ALLOWED_IMG  = {"png", "jpg", "jpeg", "gif", "webp"}
ALLOWED_DOCS = {"pdf", "doc", "docx", "png", "jpg", "jpeg"}

# ─────────────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────────────
def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if "user" not in session:
            if request.path.startswith("/sln_hk/api/"):
                return jsonify({"success": False, "error": "Not authenticated"}), 401
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return wrapper


def _load(path: Path, default=None):
    """Load JSON file, returning default on missing / corrupt."""
    if default is None:
        default = []
    try:
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return default


def _save(path: Path, data):
    """Atomically save JSON."""
    tmp = path.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False, default=str)
    tmp.replace(path)


def _next_id(records: list, prefix: str) -> str:
    """Generate next sequential ID with prefix, e.g. HKT-001."""
    nums = []
    for r in records:
        for key in ("Task_ID", "Zone_ID", "Staff_ID", "Item_ID",
                    "Pest_ID", "Training_ID", "Sow_ID", "Schedule_ID",
                    "WC_Log_ID", "Checklist_ID"):
            val = r.get(key, "")
            if val.startswith(prefix):
                try:
                    nums.append(int(val.replace(prefix, "").lstrip("-")))
                except ValueError:
                    pass
    nxt = max(nums, default=0) + 1
    return f"{prefix}{nxt:03d}"


def _allowed_img(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_IMG


def _allowed_doc(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_DOCS


def _save_upload(file, folder: Path, allowed_fn) -> str | None:
    """Save an uploaded FileStorage to folder. Returns filename or None."""
    if not file or not file.filename:
        return None
    if not allowed_fn(file.filename):
        return None
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe = f"{ts}_{secure_filename(file.filename)}"
    file.save(str(folder / safe))
    return safe


# ─────────────────────────────────────────────────────────────────────────────
# DASHBOARD
# ─────────────────────────────────────────────────────────────────────────────
@sln_hk_bp.route("/")
@sln_hk_bp.route("/dashboard")
@login_required
def sln_hk_dashboard():
    return render_template("sln_hk.html")


# ─────────────────────────────────────────────────────────────────────────────
# KPI
# ─────────────────────────────────────────────────────────────────────────────
@sln_hk_bp.route("/api/sln_hk_kpi")
@login_required
def sln_hk_kpi():
    tasks     = _load(HK_TASKS_FILE)
    zones     = _load(HK_ZONES_FILE)
    inventory = _load(HK_INVENTORY_FILE)
    wc_logs   = _load(HK_WC_FILE)
    pest      = _load(HK_PEST_FILE)
    training  = _load(HK_TRAINING_FILE)

    today = datetime.now().strftime("%Y-%m-%d")

    total     = len(tasks)
    completed = sum(1 for t in tasks if t.get("Status") == "Completed")
    pending   = sum(1 for t in tasks if t.get("Status") == "Pending")
    in_prog   = sum(1 for t in tasks if t.get("Status") == "In Progress")
    today_t   = sum(1 for t in tasks if t.get("Date", "") == today)
    rate      = round(completed / total * 100) if total else 0

    total_zones   = len(zones)
    cleaned_zones = sum(1 for z in zones if z.get("Status") == "Cleaned")

    low_stock = sum(1 for i in inventory
                    if float(i.get("Current_Stock", 0) or 0)
                    < float(i.get("Min_Stock", 1) or 1))

    wc_today = sum(1 for w in wc_logs if w.get("Date", "") == today)

    pest_dates = [p.get("Next_Due") for p in pest if p.get("Next_Due")]
    pest_due   = min(pest_dates) if pest_dates else None

    # Zone type summary
    zone_types = {}
    for z in zones:
        zt = z.get("Zone_Type", "Other")
        if zt not in zone_types:
            zone_types[zt] = {"total": 0, "cleaned": 0, "pending": 0, "inprog": 0}
        zone_types[zt]["total"] += 1
        s = z.get("Status", "Pending")
        if s == "Cleaned":    zone_types[zt]["cleaned"] += 1
        elif s == "Pending":  zone_types[zt]["pending"] += 1
        else:                  zone_types[zt]["inprog"]  += 1

    return jsonify({
        "total_tasks": total, "today_tasks": today_t,
        "completed": completed, "pending": pending, "in_progress": in_prog,
        "completion_rate": rate,
        "total_zones": total_zones, "cleaned_zones": cleaned_zones,
        "low_stock_items": low_stock,
        "wc_today": wc_today,
        "pest_next_due": pest_due,
        "training_total": len(training),
        "zone_summary": zone_types,
    })


# ─────────────────────────────────────────────────────────────────────────────
# TASKS  (CRUD + photo upload)
# ─────────────────────────────────────────────────────────────────────────────
@sln_hk_bp.route("/api/sln_hk_tasks", methods=["GET"])
@login_required
def hk_get_tasks():
    return jsonify(_load(HK_TASKS_FILE))


@sln_hk_bp.route("/api/sln_hk_tasks", methods=["POST"])
@login_required
def hk_add_task():
    """
    Accepts multipart/form-data  OR  application/json.
    Photo field name: photo
    """
    tasks = _load(HK_TASKS_FILE)

    # ── parse body ────────────────────────────────────────────────────────
    if request.content_type and "multipart" in request.content_type:
        d = request.form
    else:
        d = request.get_json(silent=True) or {}

    tid = _next_id(tasks, "HKT-")

    # ── photo ─────────────────────────────────────────────────────────────
    photo_file = request.files.get("photo")
    photo_name = _save_upload(photo_file, TASK_PHOTOS, _allowed_img)

    task = {
        "Task_ID":     tid,
        "Date":        d.get("date", datetime.now().strftime("%Y-%m-%d")),
        "Zone_ID":     d.get("zone_id", ""),
        "Zone_Name":   d.get("zone_name", ""),
        "Zone_Type":   d.get("zone_type", ""),
        "Floor_Level": d.get("floor_level", ""),
        "Task_Type":   d.get("task_type", ""),
        "Priority":    d.get("priority", "Medium"),
        "Status":      d.get("status", "Pending"),
        "Assigned_To": d.get("assigned_to", ""),
        "Remarks":     d.get("remarks", ""),
        "Photo":       photo_name or "",
        "Created_At":  datetime.now().isoformat(),
    }
    tasks.append(task)
    _save(HK_TASKS_FILE, tasks)
    return jsonify({"success": True, "task_id": tid})


@sln_hk_bp.route("/api/sln_hk_tasks/<task_id>", methods=["PUT"])
@login_required
def hk_update_task(task_id):
    tasks = _load(HK_TASKS_FILE)
    body  = request.get_json(silent=True) or {}
    for t in tasks:
        if t.get("Task_ID") == task_id:
            for k, v in body.items():
                t[k] = v
            t["Updated_At"] = datetime.now().isoformat()
            _save(HK_TASKS_FILE, tasks)
            return jsonify({"success": True})
    return jsonify({"success": False, "error": "Not found"}), 404


@sln_hk_bp.route("/api/sln_hk_tasks/<task_id>", methods=["DELETE"])
@login_required
def hk_delete_task(task_id):
    tasks = _load(HK_TASKS_FILE)
    new   = [t for t in tasks if t.get("Task_ID") != task_id]
    _save(HK_TASKS_FILE, new)
    return jsonify({"success": True})


# ── Task photo upload (standalone endpoint for existing tasks) ────────────
@sln_hk_bp.route("/api/sln_hk_tasks/<task_id>/photo", methods=["POST"])
@login_required
def hk_upload_task_photo(task_id):
    tasks = _load(HK_TASKS_FILE)
    photo_file = request.files.get("photo")
    if not photo_file:
        return jsonify({"success": False, "error": "No file"}), 400
    photo_name = _save_upload(photo_file, TASK_PHOTOS, _allowed_img)
    if not photo_name:
        return jsonify({"success": False, "error": "Invalid file type"}), 400
    for t in tasks:
        if t.get("Task_ID") == task_id:
            t["Photo"] = photo_name
            t["Updated_At"] = datetime.now().isoformat()
            _save(HK_TASKS_FILE, tasks)
            return jsonify({"success": True, "photo": photo_name})
    return jsonify({"success": False, "error": "Task not found"}), 404


# ── Serve task photos ─────────────────────────────────────────────────────
@sln_hk_bp.route("/uploads/task_photos/<filename>")
@login_required
def serve_task_photo(filename):
    return send_file(TASK_PHOTOS / secure_filename(filename))


# ─────────────────────────────────────────────────────────────────────────────
# CHECKLIST
# ─────────────────────────────────────────────────────────────────────────────
@sln_hk_bp.route("/api/sln_hk_checklist", methods=["GET"])
@login_required
def hk_get_checklist():
    return jsonify(_load(HK_CHECKLIST_FILE))


@sln_hk_bp.route("/api/sln_hk_checklist", methods=["POST"])
@login_required
def hk_add_checklist():
    items = _load(HK_CHECKLIST_FILE)
    d     = request.get_json(silent=True) or {}
    cid   = _next_id(items, "HKC-")
    items.append({
        "Checklist_ID": cid,
        "Task":         d.get("task", ""),
        "Category":     d.get("category", "General"),
        "Frequency":    d.get("frequency", "Daily"),
        "Status":       d.get("status", "Pending"),
        "Assigned_To":  d.get("assigned_to", ""),
        "Time":         d.get("time", ""),
        "Remarks":      d.get("remarks", ""),
        "Created_At":   datetime.now().isoformat(),
    })
    _save(HK_CHECKLIST_FILE, items)
    return jsonify({"success": True, "checklist_id": cid})


@sln_hk_bp.route("/api/sln_hk_checklist/<cid>", methods=["PUT"])
@login_required
def hk_update_checklist(cid):
    items = _load(HK_CHECKLIST_FILE)
    body  = request.get_json(silent=True) or {}
    for item in items:
        if item.get("Checklist_ID") == cid:
            item.update(body)
            _save(HK_CHECKLIST_FILE, items)
            return jsonify({"success": True})
    return jsonify({"success": False, "error": "Not found"}), 404


@sln_hk_bp.route("/api/sln_hk_checklist/<cid>", methods=["DELETE"])
@login_required
def hk_delete_checklist(cid):
    items = _load(HK_CHECKLIST_FILE)
    _save(HK_CHECKLIST_FILE, [i for i in items if i.get("Checklist_ID") != cid])
    return jsonify({"success": True})


# ─────────────────────────────────────────────────────────────────────────────
# ZONES  (status cycle + photo upload)
# ─────────────────────────────────────────────────────────────────────────────
@sln_hk_bp.route("/api/sln_hk_zones", methods=["GET"])
@login_required
def hk_get_zones():
    return jsonify(_load(HK_ZONES_FILE))


@sln_hk_bp.route("/api/sln_hk_zones", methods=["POST"])
@login_required
def hk_add_zone():
    zones = _load(HK_ZONES_FILE)
    d     = request.get_json(silent=True) or {}
    zid   = _next_id(zones, "HKZ-")
    zones.append({
        "Zone_ID":       zid,
        "Zone_Name":     d.get("zone_name", ""),
        "Zone_Type":     d.get("zone_type", ""),
        "Floor_Level":   d.get("floor_level", ""),
        "Area_Category": d.get("area_category", ""),
        "Area_sqft":     d.get("area_sqft", ""),
        "Status":        "Pending",
        "Last_Cleaned":  "",
        "Photo":         "",
        "Created_At":    datetime.now().isoformat(),
    })
    _save(HK_ZONES_FILE, zones)
    return jsonify({"success": True, "zone_id": zid})


@sln_hk_bp.route("/api/sln_hk_zones/<zone_id>", methods=["PUT"])
@login_required
def hk_update_zone(zone_id):
    zones = _load(HK_ZONES_FILE)
    body  = request.get_json(silent=True) or {}
    for z in zones:
        if z.get("Zone_ID") == zone_id:
            if "status" in body:
                z["Status"] = body["status"]
                if body["status"] == "Cleaned":
                    z["Last_Cleaned"] = datetime.now().strftime("%Y-%m-%d %H:%M")
            for k, v in body.items():
                if k not in ("status",):
                    z[k] = v
            _save(HK_ZONES_FILE, zones)
            return jsonify({"success": True})
    return jsonify({"success": False, "error": "Not found"}), 404


@sln_hk_bp.route("/api/sln_hk_zones/<zone_id>", methods=["DELETE"])
@login_required
def hk_delete_zone(zone_id):
    zones = _load(HK_ZONES_FILE)
    _save(HK_ZONES_FILE, [z for z in zones if z.get("Zone_ID") != zone_id])
    return jsonify({"success": True})


# ── Zone photo upload ─────────────────────────────────────────────────────
@sln_hk_bp.route("/api/sln_hk_zones/<zone_id>/photo", methods=["POST"])
@login_required
def hk_upload_zone_photo(zone_id):
    zones = _load(HK_ZONES_FILE)
    photo_file = request.files.get("photo")
    if not photo_file:
        return jsonify({"success": False, "error": "No file"}), 400
    photo_name = _save_upload(photo_file, ZONE_PHOTOS, _allowed_img)
    if not photo_name:
        return jsonify({"success": False, "error": "Invalid file type"}), 400
    for z in zones:
        if z.get("Zone_ID") == zone_id:
            z["Photo"] = photo_name
            z["Updated_At"] = datetime.now().isoformat()
            _save(HK_ZONES_FILE, zones)
            return jsonify({"success": True, "photo": photo_name})
    return jsonify({"success": False, "error": "Zone not found"}), 404


@sln_hk_bp.route("/uploads/zone_photos/<filename>")
@login_required
def serve_zone_photo(filename):
    return send_file(ZONE_PHOTOS / secure_filename(filename))


# ─────────────────────────────────────────────────────────────────────────────
# STAFF DIRECTORY  (full CRUD + photo upload)
# ─────────────────────────────────────────────────────────────────────────────
@sln_hk_bp.route("/api/sln_hk_staff", methods=["GET"])
@login_required
def hk_get_staff():
    return jsonify(_load(HK_STAFF_FILE))


@sln_hk_bp.route("/api/sln_hk_staff", methods=["POST"])
@login_required
def hk_add_staff():
    """
    Accepts multipart/form-data  OR  application/json.
    Photo field name: photo
    """
    staff = _load(HK_STAFF_FILE)

    if request.content_type and "multipart" in request.content_type:
        d = request.form
    else:
        d = request.get_json(silent=True) or {}

    sid = _next_id(staff, "HKS-")

    photo_file = request.files.get("photo")
    photo_name = _save_upload(photo_file, STAFF_PHOTOS, _allowed_img)

    staff.append({
        "Staff_ID":    sid,
        "Name":        d.get("name", ""),
        "Role":        d.get("role", ""),
        "Shift":       d.get("shift", ""),
        "Contact":     d.get("contact", ""),
        "Email":       d.get("email", ""),
        "Join_Date":   d.get("join_date", ""),
        "Status":      d.get("status", "Active"),
        "Supervisor":  d.get("supervisor", ""),
        "Remarks":     d.get("remarks", ""),
        "Photo":       photo_name or "",
        "Created_At":  datetime.now().isoformat(),
    })
    _save(HK_STAFF_FILE, staff)
    return jsonify({"success": True, "staff_id": sid})


@sln_hk_bp.route("/api/sln_hk_staff/<sid>", methods=["PUT"])
@login_required
def hk_update_staff(sid):
    """Supports multipart (with optional photo replacement) or JSON."""
    staff = _load(HK_STAFF_FILE)

    if request.content_type and "multipart" in request.content_type:
        d = request.form
        photo_file = request.files.get("photo")
        photo_name = _save_upload(photo_file, STAFF_PHOTOS, _allowed_img)
    else:
        d = request.get_json(silent=True) or {}
        photo_name = None

    updatable = ("name", "role", "shift", "contact", "email",
                 "join_date", "status", "supervisor", "remarks")

    for s in staff:
        if s.get("Staff_ID") == sid:
            for k in updatable:
                if k in d:
                    s[k.title().replace("_", "")] = d[k]
                    s[k.capitalize()] = d[k]  # try both cases
            # proper key mapping
            field_map = {
                "name": "Name", "role": "Role", "shift": "Shift",
                "contact": "Contact", "email": "Email",
                "join_date": "Join_Date", "status": "Status",
                "supervisor": "Supervisor", "remarks": "Remarks",
            }
            for form_k, json_k in field_map.items():
                if form_k in d:
                    s[json_k] = d[form_k]

            if photo_name:
                s["Photo"] = photo_name
            s["Updated_At"] = datetime.now().isoformat()
            _save(HK_STAFF_FILE, staff)
            return jsonify({"success": True})
    return jsonify({"success": False, "error": "Not found"}), 404


@sln_hk_bp.route("/api/sln_hk_staff/<sid>", methods=["DELETE"])
@login_required
def hk_delete_staff(sid):
    staff = _load(HK_STAFF_FILE)
    _save(HK_STAFF_FILE, [s for s in staff if s.get("Staff_ID") != sid])
    return jsonify({"success": True})


@sln_hk_bp.route("/uploads/staff_photos/<filename>")
@login_required
def serve_staff_photo(filename):
    return send_file(STAFF_PHOTOS / secure_filename(filename))


# ─────────────────────────────────────────────────────────────────────────────
# INVENTORY
# ─────────────────────────────────────────────────────────────────────────────
@sln_hk_bp.route("/api/sln_hk_inventory", methods=["GET"])
@login_required
def hk_get_inventory():
    return jsonify(_load(HK_INVENTORY_FILE))


@sln_hk_bp.route("/api/sln_hk_inventory", methods=["POST"])
@login_required
def hk_add_inventory():
    items = _load(HK_INVENTORY_FILE)
    d     = request.get_json(silent=True) or {}
    iid   = _next_id(items, "HKI-")
    items.append({
        "Item_ID":       iid,
        "Item_Name":     d.get("item_name", ""),
        "Category":      d.get("category", ""),
        "Unit":          d.get("unit", ""),
        "Current_Stock": float(d.get("current_stock", 0)),
        "Min_Stock":     float(d.get("min_stock", 0)),
        "Supplier":      d.get("supplier", ""),
        "Last_Updated":  datetime.now().strftime("%Y-%m-%d"),
        "Remarks":       d.get("remarks", ""),
        "Created_At":    datetime.now().isoformat(),
    })
    _save(HK_INVENTORY_FILE, items)
    return jsonify({"success": True, "item_id": iid})


@sln_hk_bp.route("/api/sln_hk_inventory/<iid>", methods=["PUT"])
@login_required
def hk_update_inventory(iid):
    items = _load(HK_INVENTORY_FILE)
    body  = request.get_json(silent=True) or {}
    for i in items:
        if i.get("Item_ID") == iid:
            i.update(body)
            i["Last_Updated"] = datetime.now().strftime("%Y-%m-%d")
            _save(HK_INVENTORY_FILE, items)
            return jsonify({"success": True})
    return jsonify({"success": False, "error": "Not found"}), 404


@sln_hk_bp.route("/api/sln_hk_inventory/<iid>", methods=["DELETE"])
@login_required
def hk_delete_inventory(iid):
    items = _load(HK_INVENTORY_FILE)
    _save(HK_INVENTORY_FILE, [i for i in items if i.get("Item_ID") != iid])
    return jsonify({"success": True})


# ── Inventory Excel upload ────────────────────────────────────────────────
@sln_hk_bp.route("/api/sln_hk_inventory/upload", methods=["POST"])
@login_required
def hk_upload_inventory():
    if not EXCEL_OK:
        return jsonify({"success": False, "error": "pandas/openpyxl not installed"}), 500
    f = request.files.get("file")
    if not f:
        return jsonify({"success": False, "error": "No file"}), 400
    try:
        df = pd.read_excel(f)
        items   = _load(HK_INVENTORY_FILE)
        added   = 0
        for _, row in df.iterrows():
            iid = _next_id(items, "HKI-")
            items.append({
                "Item_ID":       iid,
                "Item_Name":     str(row.get("Item_Name", row.get("item_name", ""))).strip(),
                "Category":      str(row.get("Category", "")).strip(),
                "Unit":          str(row.get("Unit", "")).strip(),
                "Current_Stock": float(row.get("Current_Stock", row.get("current_stock", 0)) or 0),
                "Min_Stock":     float(row.get("Min_Stock", row.get("min_stock", 0)) or 0),
                "Supplier":      str(row.get("Supplier", "")).strip(),
                "Last_Updated":  datetime.now().strftime("%Y-%m-%d"),
                "Remarks":       str(row.get("Remarks", "")).strip(),
                "Created_At":    datetime.now().isoformat(),
            })
            added += 1
        _save(HK_INVENTORY_FILE, items)
        return jsonify({"success": True, "added": added})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# ─────────────────────────────────────────────────────────────────────────────
# SOW  (Scope of Work)
# ─────────────────────────────────────────────────────────────────────────────
@sln_hk_bp.route("/api/sln_hk_sow", methods=["GET"])
@login_required
def hk_get_sow():
    return jsonify(_load(HK_SOW_FILE))


@sln_hk_bp.route("/api/sln_hk_sow", methods=["POST"])
@login_required
def hk_add_sow():
    sow = _load(HK_SOW_FILE)
    d   = request.get_json(silent=True) or {}
    sid = _next_id(sow, "HKW-")
    sow.append({
        "Sow_ID":    sid,
        "Task":      d.get("task", ""),
        "Area":      d.get("area", ""),
        "Frequency": d.get("frequency", "Daily"),
        "Method":    d.get("method", ""),
        "Chemical":  d.get("chemical", ""),
        "Equipment": d.get("equipment", ""),
        "Remarks":   d.get("remarks", ""),
        "Created_At": datetime.now().isoformat(),
    })
    _save(HK_SOW_FILE, sow)
    return jsonify({"success": True, "sow_id": sid})


@sln_hk_bp.route("/api/sln_hk_sow/<sid>", methods=["DELETE"])
@login_required
def hk_delete_sow(sid):
    sow = _load(HK_SOW_FILE)
    _save(HK_SOW_FILE, [s for s in sow if s.get("Sow_ID") != sid])
    return jsonify({"success": True})


# ─────────────────────────────────────────────────────────────────────────────
# SCHEDULES
# ─────────────────────────────────────────────────────────────────────────────
@sln_hk_bp.route("/api/sln_hk_schedules", methods=["GET"])
@login_required
def hk_get_schedules():
    return jsonify(_load(HK_SCHEDULES_FILE))


@sln_hk_bp.route("/api/sln_hk_schedules", methods=["POST"])
@login_required
def hk_add_schedule():
    scheds = _load(HK_SCHEDULES_FILE)
    d      = request.get_json(silent=True) or {}
    sid    = _next_id(scheds, "HKSch-")
    scheds.append({
        "Schedule_ID": sid,
        "Staff_Name":  d.get("staff_name", ""),
        "Shift":       d.get("shift", ""),
        "Start_Time":  d.get("start_time", ""),
        "End_Time":    d.get("end_time", ""),
        "Zone":        d.get("zone", ""),
        "Day":         d.get("day", ""),
        "Remarks":     d.get("remarks", ""),
        "Created_At":  datetime.now().isoformat(),
    })
    _save(HK_SCHEDULES_FILE, scheds)
    return jsonify({"success": True, "schedule_id": sid})


@sln_hk_bp.route("/api/sln_hk_schedules/<sid>", methods=["DELETE"])
@login_required
def hk_delete_schedule(sid):
    scheds = _load(HK_SCHEDULES_FILE)
    _save(HK_SCHEDULES_FILE, [s for s in scheds if s.get("Schedule_ID") != sid])
    return jsonify({"success": True})


# ─────────────────────────────────────────────────────────────────────────────
# WASHROOM CHECKLIST
# ─────────────────────────────────────────────────────────────────────────────
@sln_hk_bp.route("/api/sln_hk_wc", methods=["GET"])
@login_required
def hk_get_wc():
    return jsonify(_load(HK_WC_FILE))


@sln_hk_bp.route("/api/sln_hk_wc", methods=["POST"])
@login_required
def hk_add_wc():
    logs = _load(HK_WC_FILE)
    d    = request.get_json(silent=True) or {}
    lid  = _next_id(logs, "HKWC-")
    logs.append({
        "WC_Log_ID":  lid,
        "Location":   d.get("location", ""),
        "Floor":      d.get("floor", ""),
        "Gender":     d.get("gender", ""),
        "Date":       d.get("date", datetime.now().strftime("%Y-%m-%d")),
        "Time":       d.get("time", datetime.now().strftime("%H:%M")),
        "Checked_By": d.get("checked_by", ""),
        "Items":      d.get("items", {}),
        "Remarks":    d.get("remarks", ""),
        "Created_At": datetime.now().isoformat(),
    })
    _save(HK_WC_FILE, logs)
    return jsonify({"success": True, "wc_log_id": lid})


@sln_hk_bp.route("/api/sln_hk_wc/<lid>", methods=["DELETE"])
@login_required
def hk_delete_wc(lid):
    logs = _load(HK_WC_FILE)
    _save(HK_WC_FILE, [l for l in logs if l.get("WC_Log_ID") != lid])
    return jsonify({"success": True})


# ─────────────────────────────────────────────────────────────────────────────
# PEST CONTROL
# ─────────────────────────────────────────────────────────────────────────────
@sln_hk_bp.route("/api/sln_hk_pest", methods=["GET"])
@login_required
def hk_get_pest():
    return jsonify(_load(HK_PEST_FILE))


@sln_hk_bp.route("/api/sln_hk_pest", methods=["POST"])
@login_required
def hk_add_pest():
    pest = _load(HK_PEST_FILE)
    d    = request.get_json(silent=True) or {}
    pid  = _next_id(pest, "HKP-")
    pest.append({
        "Pest_ID":        pid,
        "Date":           d.get("date", ""),
        "Contractor":     d.get("contractor", ""),
        "Contact":        d.get("contact", ""),
        "Treatment_Type": d.get("treatment_type", ""),
        "Areas_Covered":  d.get("areas_covered", ""),
        "Chemical_Used":  d.get("chemical_used", ""),
        "Dosage":         d.get("dosage", ""),
        "Next_Due":       d.get("next_due", ""),
        "Status":         d.get("status", "Scheduled"),
        "Remarks":        d.get("remarks", ""),
        "Created_At":     datetime.now().isoformat(),
    })
    _save(HK_PEST_FILE, pest)
    return jsonify({"success": True, "pest_id": pid})


@sln_hk_bp.route("/api/sln_hk_pest/<pid>", methods=["DELETE"])
@login_required
def hk_delete_pest(pid):
    pest = _load(HK_PEST_FILE)
    _save(HK_PEST_FILE, [p for p in pest if p.get("Pest_ID") != pid])
    return jsonify({"success": True})


# ─────────────────────────────────────────────────────────────────────────────
# TRAINING  (CRUD + photo + document upload)
# ─────────────────────────────────────────────────────────────────────────────
@sln_hk_bp.route("/api/sln_hk_training", methods=["GET"])
@login_required
def hk_get_training():
    return jsonify(_load(HK_TRAINING_FILE))


@sln_hk_bp.route("/api/sln_hk_training", methods=["POST"])
@login_required
def hk_add_training():
    """
    Accepts multipart/form-data  OR  application/json.
    Photo field:    photo
    Document field: document  (PDF / Word)
    """
    training = _load(HK_TRAINING_FILE)

    if request.content_type and "multipart" in request.content_type:
        d = request.form
    else:
        d = request.get_json(silent=True) or {}

    tid = _next_id(training, "HKTrn-")

    # ── photo ─────────────────────────────────────────────────────────────
    photo_file = request.files.get("photo")
    photo_name = _save_upload(photo_file, TRAINING_DOCS, _allowed_img)

    # ── document ──────────────────────────────────────────────────────────
    doc_file  = request.files.get("document")
    doc_name  = _save_upload(doc_file, TRAINING_DOCS, _allowed_doc)

    training.append({
        "Training_ID":   tid,
        "Date":          d.get("date", ""),
        "Topic":         d.get("topic", ""),
        "Trainer":       d.get("trainer", ""),
        "Attendees":     d.get("attendees", ""),
        "Duration_hrs":  d.get("duration_hrs", ""),
        "Venue":         d.get("venue", ""),
        "Status":        d.get("status", "Scheduled"),
        "Remarks":       d.get("remarks", ""),
        "Photo":         photo_name or "",
        "Document":      doc_name   or "",
        "Created_At":    datetime.now().isoformat(),
    })
    _save(HK_TRAINING_FILE, training)
    return jsonify({"success": True, "training_id": tid})


@sln_hk_bp.route("/api/sln_hk_training/<tid>", methods=["PUT"])
@login_required
def hk_update_training(tid):
    training = _load(HK_TRAINING_FILE)

    if request.content_type and "multipart" in request.content_type:
        d = request.form
        photo_file = request.files.get("photo")
        photo_name = _save_upload(photo_file, TRAINING_DOCS, _allowed_img)
        doc_file   = request.files.get("document")
        doc_name   = _save_upload(doc_file, TRAINING_DOCS, _allowed_doc)
    else:
        d = request.get_json(silent=True) or {}
        photo_name = None
        doc_name   = None

    field_map = {
        "date": "Date", "topic": "Topic", "trainer": "Trainer",
        "attendees": "Attendees", "duration_hrs": "Duration_hrs",
        "venue": "Venue", "status": "Status", "remarks": "Remarks",
    }
    for t in training:
        if t.get("Training_ID") == tid:
            for fk, jk in field_map.items():
                if fk in d:
                    t[jk] = d[fk]
            if photo_name:
                t["Photo"] = photo_name
            if doc_name:
                t["Document"] = doc_name
            t["Updated_At"] = datetime.now().isoformat()
            _save(HK_TRAINING_FILE, training)
            return jsonify({"success": True})
    return jsonify({"success": False, "error": "Not found"}), 404


@sln_hk_bp.route("/api/sln_hk_training/<tid>", methods=["DELETE"])
@login_required
def hk_delete_training(tid):
    training = _load(HK_TRAINING_FILE)
    _save(HK_TRAINING_FILE, [t for t in training if t.get("Training_ID") != tid])
    return jsonify({"success": True})


# ── Upload to existing training session ──────────────────────────────────
@sln_hk_bp.route("/api/sln_hk_training/<tid>/upload", methods=["POST"])
@login_required
def hk_upload_training_file(tid):
    """
    Upload photo or document to an existing training session.
    field: photo  →  image
    field: document  →  PDF/doc
    """
    training = _load(HK_TRAINING_FILE)
    updated  = False

    photo_file = request.files.get("photo")
    if photo_file:
        pn = _save_upload(photo_file, TRAINING_DOCS, _allowed_img)
        if pn:
            for t in training:
                if t.get("Training_ID") == tid:
                    t["Photo"] = pn
                    updated = True

    doc_file = request.files.get("document")
    if doc_file:
        dn = _save_upload(doc_file, TRAINING_DOCS, _allowed_doc)
        if dn:
            for t in training:
                if t.get("Training_ID") == tid:
                    t["Document"] = dn
                    updated = True

    if updated:
        for t in training:
            if t.get("Training_ID") == tid:
                t["Updated_At"] = datetime.now().isoformat()
        _save(HK_TRAINING_FILE, training)
        return jsonify({"success": True})

    return jsonify({"success": False, "error": "No valid file uploaded or session not found"}), 400


# ── Serve training uploads ────────────────────────────────────────────────
@sln_hk_bp.route("/uploads/training/<filename>")
@login_required
def serve_training_file(filename):
    return send_file(TRAINING_DOCS / secure_filename(filename))


# ─────────────────────────────────────────────────────────────────────────────
# CHART DATA
# ─────────────────────────────────────────────────────────────────────────────
@sln_hk_bp.route("/api/sln_hk_chart_data")
@login_required
def hk_chart_data():
    tasks = _load(HK_TASKS_FILE)
    zones = _load(HK_ZONES_FILE)

    # Task bar chart — last 7 distinct dates
    date_map: dict = {}
    for t in tasks:
        d = t.get("Date", "")[:10]
        if not d:
            continue
        if d not in date_map:
            date_map[d] = {"Completed": 0, "Pending": 0, "In Progress": 0}
        s = t.get("Status", "Pending")
        date_map[d][s] = date_map[d].get(s, 0) + 1

    labels = sorted(date_map.keys())[-7:]
    completed  = [date_map[l]["Completed"]   for l in labels]
    pending    = [date_map[l]["Pending"]      for l in labels]
    in_progress= [date_map[l]["In Progress"]  for l in labels]

    # Zone donut
    z_cleaned = sum(1 for z in zones if z.get("Status") == "Cleaned")
    z_pending = sum(1 for z in zones if z.get("Status") == "Pending")
    z_inprog  = sum(1 for z in zones if z.get("Status") == "In Progress")

    return jsonify({
        "task_labels":  labels,
        "completed":    completed,
        "pending":      pending,
        "in_progress":  in_progress,
        "zone_cleaned": z_cleaned,
        "zone_pending": z_pending,
        "zone_inprog":  z_inprog,
    })


# ─────────────────────────────────────────────────────────────────────────────
# EXPORT  (full XLSX dump)
# ─────────────────────────────────────────────────────────────────────────────
@sln_hk_bp.route("/api/sln_hk_export")
@login_required
def hk_export():
    if not EXCEL_OK:
        return jsonify({"error": "pandas/openpyxl not available"}), 500
    try:
        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine="openpyxl") as writer:
            sheets = {
                "Tasks":     _load(HK_TASKS_FILE),
                "Checklist": _load(HK_CHECKLIST_FILE),
                "Zones":     _load(HK_ZONES_FILE),
                "Staff":     _load(HK_STAFF_FILE),
                "Inventory": _load(HK_INVENTORY_FILE),
                "SOW":       _load(HK_SOW_FILE),
                "Schedules": _load(HK_SCHEDULES_FILE),
                "WC_Logs":   _load(HK_WC_FILE),
                "Pest":      _load(HK_PEST_FILE),
                "Training":  _load(HK_TRAINING_FILE),
            }
            for sheet_name, data in sheets.items():
                if data:
                    pd.DataFrame(data).to_excel(writer, sheet_name=sheet_name, index=False)
                else:
                    pd.DataFrame().to_excel(writer, sheet_name=sheet_name, index=False)
        buf.seek(0)
        fname = f"SLN_HK_Export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        return send_file(buf, mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                         as_attachment=True, download_name=fname)
    except Exception as e:
        return jsonify({"error": str(e)}), 500