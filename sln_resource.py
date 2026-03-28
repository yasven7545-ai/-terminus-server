"""
SLN TERMINUS — WORKFORCE & RESOURCE MANAGEMENT MODULE
sln_resource.py  ·  Flask Blueprint
Routes:
  GET  /sln_resource_mgmt                  → Serve the HTML dashboard
  GET  /api/resource/summary               → KPI summary counters (JSON)
  GET  /api/resource/staff                 → All staff records (JSON)
  POST /api/resource/staff/add             → Add / update a staff record
  GET  /api/resource/attendance            → Attendance records (JSON)
  POST /api/resource/attendance/import     → Bulk import attendance via uploaded Excel/CSV
  GET  /api/resource/vendor                → Vendor compliance data (JSON)
  POST /api/resource/vendor/update         → Update a vendor record
  GET  /api/resource/tasks                 → Task execution records (JSON)
  POST /api/resource/tasks/add             → Add task record
  GET  /api/resource/cost                  → Cost & efficiency data (JSON)
  GET  /api/resource/kpi                   → KPI report data (JSON)
  GET  /api/resource/alerts                → Active alerts (JSON)
  POST /api/resource/upload                → Upload Excel/CSV for any table
  GET  /api/resource/export/excel          → Download full Excel report
  GET  /api/resource/export/template/<t>   → Download blank import template
"""

from flask import (
    Blueprint, render_template, request, jsonify,
    session, send_file, abort
)
from pathlib import Path
from datetime import datetime, date
from functools import wraps
import json
import io
import os

# Optional: pandas + openpyxl for richer Excel handling
try:
    import pandas as pd
    import openpyxl
    from openpyxl.styles import Font, PatternFill, Alignment
    _HAS_OPENPYXL = True
except ImportError:
    _HAS_OPENPYXL = False

# ── Blueprint ─────────────────────────────────────────────────────────────────
sln_resource_bp = Blueprint(
    "sln_resource", __name__,
    template_folder="templates",
    url_prefix=""
)

# ── Paths ─────────────────────────────────────────────────────────────────────
BASE_DIR     = Path(__file__).parent.resolve()
DATA_DIR     = BASE_DIR / "static" / "data"
RESOURCE_DIR = DATA_DIR / "resource_mgmt"
RESOURCE_DIR.mkdir(parents=True, exist_ok=True)

STAFF_FILE      = RESOURCE_DIR / "staff.json"
ATTENDANCE_FILE = RESOURCE_DIR / "attendance.json"
VENDOR_FILE     = RESOURCE_DIR / "vendors.json"
TASKS_FILE      = RESOURCE_DIR / "tasks.json"
COST_FILE       = RESOURCE_DIR / "cost.json"
KPI_FILE        = RESOURCE_DIR / "kpi.json"
ALERTS_FILE     = RESOURCE_DIR / "alerts.json"


# ── Auth guard (reuse server.py session pattern) ──────────────────────────────
def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user" not in session:
            return jsonify({"error": "Unauthorized", "redirect": "/login"}), 401
        return f(*args, **kwargs)
    return decorated


# ── JSON helpers ──────────────────────────────────────────────────────────────
def _load(filepath: Path, default=None):
    if default is None:
        default = []
    try:
        if filepath.exists():
            with open(filepath, encoding="utf-8") as f:
                return json.load(f)
    except Exception as e:
        print(f"⚠️  [resource] load error {filepath.name}: {e}")
    return default


def _save(filepath: Path, data):
    try:
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"⚠️  [resource] save error {filepath.name}: {e}")
        return False


# ── Seed defaults if files are empty ─────────────────────────────────────────
def _seed_defaults():
    """Populate JSON files with sample data if they don't exist or are empty."""

    if not STAFF_FILE.exists() or os.path.getsize(STAFF_FILE) < 5:
        staff = [
            {"id":"EMP-001","name":"Ravi Kumar","function":"Housekeeping","zone":"Tower A","shift":"Morning (6AM–2PM)","vendor":"CleanPro Services","contract":"VND-2026-001","status":"Present","joined":"2024-01-15"},
            {"id":"EMP-002","name":"Suresh Babu","function":"Security","zone":"Main Gate","shift":"Evening (2PM–10PM)","vendor":"SecureGuard Ltd","contract":"VND-2026-002","status":"Present","joined":"2023-06-01"},
            {"id":"EMP-003","name":"Anitha Devi","function":"Housekeeping","zone":"Tower B","shift":"Morning (6AM–2PM)","vendor":"CleanPro Services","contract":"VND-2026-001","status":"Absent","joined":"2024-03-01"},
            {"id":"EMP-004","name":"Mohammed Aziz","function":"Maintenance","zone":"Plant Room","shift":"Morning (6AM–2PM)","vendor":"TechServ FM","contract":"VND-2026-003","status":"Present","joined":"2023-09-15"},
            {"id":"EMP-005","name":"Priya Reddy","function":"Admin Support","zone":"Management Office","shift":"Morning (6AM–2PM)","vendor":"HireFleet India","contract":"VND-2026-004","status":"Present","joined":"2025-01-10"},
            {"id":"EMP-006","name":"Naresh Singh","function":"Fire & Safety","zone":"All Floors","shift":"Night (10PM–6AM)","vendor":"SafetyFirst Corp","contract":"VND-2026-005","status":"Present","joined":"2023-11-20"},
            {"id":"EMP-007","name":"Lakshmi Narayan","function":"Security","zone":"Parking Level","shift":"Night (10PM–6AM)","vendor":"SecureGuard Ltd","contract":"VND-2026-002","status":"Late","joined":"2024-07-01"},
            {"id":"EMP-008","name":"Vijay Sharma","function":"Housekeeping","zone":"Basement","shift":"Evening (2PM–10PM)","vendor":"CleanPro Services","contract":"VND-2026-001","status":"Present","joined":"2024-02-20"},
        ]
        _save(STAFF_FILE, staff)

    if not VENDOR_FILE.exists() or os.path.getsize(VENDOR_FILE) < 5:
        vendors = [
            {"id":"VND-001","name":"CleanPro Services","function":"Housekeeping","contracted":45,"deployed":40,"gap":5,"compliance":89,"sla":"Partial","last_verified":str(date.today()),"contact":"cleanpro@example.com"},
            {"id":"VND-002","name":"SecureGuard Ltd","function":"Security","contracted":32,"deployed":32,"gap":0,"compliance":100,"sla":"Met","last_verified":str(date.today()),"contact":"secure@example.com"},
            {"id":"VND-003","name":"TechServ FM","function":"Maintenance","contracted":18,"deployed":15,"gap":3,"compliance":83,"sla":"Partial","last_verified":str(date.today()),"contact":"tech@example.com"},
            {"id":"VND-004","name":"SafetyFirst Corp","function":"Fire & Safety","contracted":8,"deployed":8,"gap":0,"compliance":100,"sla":"Met","last_verified":str(date.today()),"contact":"safety@example.com"},
            {"id":"VND-005","name":"HireFleet India","function":"Admin Support","contracted":12,"deployed":9,"gap":3,"compliance":75,"sla":"Breach","last_verified":str(date.today()),"contact":"hire@example.com"},
            {"id":"VND-006","name":"GreenGarden FM","function":"Landscaping","contracted":6,"deployed":5,"gap":1,"compliance":83,"sla":"Partial","last_verified":str(date.today()),"contact":"green@example.com"},
        ]
        _save(VENDOR_FILE, vendors)

    if not ATTENDANCE_FILE.exists() or os.path.getsize(ATTENDANCE_FILE) < 5:
        today = str(date.today())
        attendance = [
            {"name":"Ravi Kumar","function":"Housekeeping","date":today,"checkin":"06:02","checkout":"14:05","shift":"Morning","status":"Present","remarks":"On time"},
            {"name":"Suresh Babu","function":"Security","date":today,"checkin":"14:15","checkout":"22:00","shift":"Evening","status":"Late","remarks":"15 min late"},
            {"name":"Anitha Devi","function":"Housekeeping","date":today,"checkin":"—","checkout":"—","shift":"Morning","status":"Absent","remarks":"No call out"},
            {"name":"Mohammed Aziz","function":"Maintenance","date":today,"checkin":"06:00","checkout":"14:10","shift":"Morning","status":"Present","remarks":""},
            {"name":"Priya Reddy","function":"Admin Support","date":today,"checkin":"09:05","checkout":"18:00","shift":"Morning","status":"Present","remarks":""},
            {"name":"Naresh Singh","function":"Fire & Safety","date":today,"checkin":"22:00","checkout":"06:00","shift":"Night","status":"Present","remarks":""},
            {"name":"Lakshmi Narayan","function":"Security","date":today,"checkin":"22:28","checkout":"—","shift":"Night","status":"Late","remarks":"28 min late"},
            {"name":"Vijay Sharma","function":"Housekeeping","date":today,"checkin":"14:00","checkout":"22:00","shift":"Evening","status":"Present","remarks":""},
        ]
        _save(ATTENDANCE_FILE, attendance)

    if not KPI_FILE.exists() or os.path.getsize(KPI_FILE) < 5:
        kpis = [
            {"metric":"Attendance %","target":"95%","actual":"93%","variance":"-2%","period":"Mar 2026","status":"Near Target"},
            {"metric":"Productivity (Tasks/Staff)","target":"4.0","actual":"3.86","variance":"-0.14","period":"Mar 2026","status":"Near Target"},
            {"metric":"Cost per Manpower Unit (₹)","target":"₹1,800","actual":"₹1,818","variance":"+₹18","period":"Mar 2026","status":"Within Budget"},
            {"metric":"Vendor Compliance %","target":"95%","actual":"87%","variance":"-8%","period":"Mar 2026","status":"Below Target"},
            {"metric":"Shift Coverage %","target":"100%","actual":"97%","variance":"-3%","period":"Mar 2026","status":"Near Target"},
            {"metric":"SLA Adherence %","target":"95%","actual":"89%","variance":"-6%","period":"Mar 2026","status":"Below Target"},
            {"metric":"Overtime Hours","target":"<200h","actual":"186h","variance":"-14h","period":"Mar 2026","status":"On Target"},
            {"metric":"Late Reporting Incidents","target":"<5","actual":"8","variance":"+3","period":"Mar 2026","status":"Exceeds Limit"},
        ]
        _save(KPI_FILE, kpis)

    if not ALERTS_FILE.exists() or os.path.getsize(ALERTS_FILE) < 5:
        alerts = [
            {"type":"critical","title":"Staff Shortage — Tower A Housekeeping","desc":"Deployed 20/22 planned. Gap of 2 staff since morning shift.","time":datetime.now().strftime("%H:%M"),"dismissed":False},
            {"type":"critical","title":"Vendor Under-Deployment — HireFleet India","desc":"Admin support: 9/12 contracted staff deployed. SLA breach risk.","time":"08:45","dismissed":False},
            {"type":"warning","title":"Late Reporting — 2 Security Staff","desc":"Suresh Babu & Lakshmi Narayan checked in late today.","time":"14:28","dismissed":False},
            {"type":"warning","title":"Vendor Compliance Drop — HireFleet India","desc":"Compliance down to 75% this week. Review required.","time":"09:00","dismissed":False},
            {"type":"info","title":"Shift Handover Pending — Plant Room","desc":"Maintenance shift handover not logged for evening shift.","time":"14:00","dismissed":False},
        ]
        _save(ALERTS_FILE, alerts)


# ── ROUTES ────────────────────────────────────────────────────────────────────

@sln_resource_bp.route("/sln_resource_mgmt")
@login_required
def sln_resource_dashboard():
    """Serve the Workforce & Resource Management HTML dashboard."""
    return render_template("sln_resource_mgmt.html")


# ── API: Summary KPIs ─────────────────────────────────────────────────────────
@sln_resource_bp.route("/api/resource/summary")
@login_required
def api_resource_summary():
    """Return KPI summary counters for the overview cards."""
    staff      = _load(STAFF_FILE)
    attendance = _load(ATTENDANCE_FILE)
    vendors    = _load(VENDOR_FILE)
    alerts     = _load(ALERTS_FILE)

    today = str(date.today())
    today_att  = [a for a in attendance if a.get("date") == today]
    present    = sum(1 for a in today_att if a.get("status") == "Present")
    absent     = sum(1 for a in today_att if a.get("status") == "Absent")
    late       = sum(1 for a in today_att if a.get("status") == "Late")
    total_att  = len(today_att) or 1

    avg_compliance = (sum(v.get("compliance", 0) for v in vendors) / max(len(vendors), 1))

    active_alerts  = sum(1 for a in alerts if not a.get("dismissed", False))

    return jsonify({
        "planned":          248,
        "actual_deployed":  present + late,
        "attendance_pct":   round((present + late) / total_att * 100, 1),
        "absent":           absent,
        "late":             late,
        "vendor_compliance": round(avg_compliance, 1),
        "under_deployed_vendors": sum(1 for v in vendors if v.get("gap", 0) > 0),
        "active_alerts":    active_alerts,
        "tasks_completed":  892,
        "productivity":     3.86,
        "monthly_cost_lakh": 4.2,
        "cost_per_unit":    1818,
    })


# ── API: Staff ────────────────────────────────────────────────────────────────
@sln_resource_bp.route("/api/resource/staff", methods=["GET"])
@login_required
def api_resource_staff_get():
    return jsonify(_load(STAFF_FILE))


@sln_resource_bp.route("/api/resource/staff/add", methods=["POST"])
@login_required
def api_resource_staff_add():
    data = request.get_json(force=True) or {}
    staff = _load(STAFF_FILE)

    # Check if update (same ID) or new record
    existing_ids = {s["id"]: i for i, s in enumerate(staff)}
    new_id = data.get("id") or f"EMP-{str(len(staff)+1).zfill(3)}"

    record = {
        "id":       new_id,
        "name":     data.get("name", "").strip(),
        "function": data.get("function", ""),
        "zone":     data.get("zone", ""),
        "shift":    data.get("shift", "Morning"),
        "vendor":   data.get("vendor", ""),
        "contract": data.get("contract", ""),
        "status":   data.get("status", "Present"),
        "remarks":  data.get("remarks", ""),
        "updatedAt": datetime.now().isoformat(),
    }
    if not record["name"]:
        return jsonify({"success": False, "error": "Staff name required"}), 400

    if new_id in existing_ids:
        staff[existing_ids[new_id]] = record
    else:
        record["joined"] = str(date.today())
        staff.insert(0, record)

    _save(STAFF_FILE, staff)
    return jsonify({"success": True, "record": record, "total": len(staff)})


# ── API: Attendance ───────────────────────────────────────────────────────────
@sln_resource_bp.route("/api/resource/attendance", methods=["GET"])
@login_required
def api_resource_attendance():
    filter_date = request.args.get("date")
    records = _load(ATTENDANCE_FILE)
    if filter_date:
        records = [r for r in records if r.get("date") == filter_date]
    return jsonify(records)


@sln_resource_bp.route("/api/resource/attendance/import", methods=["POST"])
@login_required
def api_resource_attendance_import():
    """
    Bulk-import attendance records from an uploaded Excel / CSV file.
    Expects multipart/form-data with key 'file'.
    """
    if not _HAS_OPENPYXL:
        return jsonify({"success": False, "error": "openpyxl not installed — Excel import unavailable"}), 400

    uploaded = request.files.get("file")
    if not uploaded:
        return jsonify({"success": False, "error": "No file received"}), 400

    try:
        import tempfile, shutil
        suffix = Path(uploaded.filename).suffix.lower()
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            uploaded.save(tmp.name)
            tmp_path = tmp.name

        if suffix in (".xlsx", ".xls"):
            df = pd.read_excel(tmp_path)
        elif suffix == ".csv":
            df = pd.read_csv(tmp_path)
        else:
            return jsonify({"success": False, "error": "Unsupported file type"}), 400

        os.unlink(tmp_path)

        # Normalize columns
        df.columns = [str(c).strip().lower().replace(" ", "_") for c in df.columns]
        col_map = {"name":"name","function":"function","date":"date","check-in":"checkin","check_in":"checkin","checkin":"checkin","check-out":"checkout","check_out":"checkout","checkout":"checkout","shift":"shift","status":"status","remarks":"remarks"}
        records_in = df.rename(columns=col_map).to_dict("records")
        existing = _load(ATTENDANCE_FILE)

        imported = 0
        for row in records_in:
            record = {
                "name":     str(row.get("name","")).strip(),
                "function": str(row.get("function","")).strip(),
                "date":     str(row.get("date", str(date.today()))).strip(),
                "checkin":  str(row.get("checkin","—")).strip(),
                "checkout": str(row.get("checkout","—")).strip(),
                "shift":    str(row.get("shift","Morning")).strip(),
                "status":   str(row.get("status","Present")).strip(),
                "remarks":  str(row.get("remarks","")).strip(),
                "importedAt": datetime.now().isoformat(),
            }
            if record["name"]:
                existing.append(record)
                imported += 1

        _save(ATTENDANCE_FILE, existing)
        return jsonify({"success": True, "imported": imported, "total": len(existing)})

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# ── API: Vendor ───────────────────────────────────────────────────────────────
@sln_resource_bp.route("/api/resource/vendor", methods=["GET"])
@login_required
def api_resource_vendor():
    return jsonify(_load(VENDOR_FILE))


@sln_resource_bp.route("/api/resource/vendor/update", methods=["POST"])
@login_required
def api_resource_vendor_update():
    data    = request.get_json(force=True) or {}
    vendors = _load(VENDOR_FILE)
    vid     = data.get("id")
    if not vid:
        return jsonify({"success": False, "error": "Vendor ID required"}), 400

    for v in vendors:
        if v.get("id") == vid:
            v.update({k: data[k] for k in data if k != "id"})
            v["last_verified"] = str(date.today())
            break
    else:
        vendors.insert(0, {**data, "last_verified": str(date.today())})

    _save(VENDOR_FILE, vendors)
    return jsonify({"success": True})


# ── API: Tasks ────────────────────────────────────────────────────────────────
@sln_resource_bp.route("/api/resource/tasks", methods=["GET"])
@login_required
def api_resource_tasks():
    return jsonify(_load(TASKS_FILE))


@sln_resource_bp.route("/api/resource/tasks/add", methods=["POST"])
@login_required
def api_resource_tasks_add():
    data  = request.get_json(force=True) or {}
    tasks = _load(TASKS_FILE)
    task  = {
        "id":       f"TASK-{int(datetime.now().timestamp()*1000)}",
        "type":     data.get("type",""),
        "assigned": data.get("assigned",""),
        "area":     data.get("area",""),
        "start":    data.get("start",""),
        "end":      data.get("end",""),
        "duration": data.get("duration",""),
        "coverage": data.get("coverage",""),
        "status":   data.get("status","Pending"),
        "addedAt":  datetime.now().isoformat(),
    }
    tasks.insert(0, task)
    _save(TASKS_FILE, tasks)
    return jsonify({"success": True, "task": task})


# ── API: Cost ─────────────────────────────────────────────────────────────────
@sln_resource_bp.route("/api/resource/cost", methods=["GET"])
@login_required
def api_resource_cost():
    cost = _load(COST_FILE)
    if not cost:
        cost = [
            {"property":"SLN Terminus — Tower A","function":"Housekeeping","count":22,"base":110000,"overtime":8000,"total":118000,"perUnit":5364,"efficiency":91},
            {"property":"SLN Terminus — Tower B","function":"Housekeeping","count":18,"base":90000,"overtime":5500,"total":95500,"perUnit":5306,"efficiency":88},
            {"property":"SLN Terminus — Common","function":"Security","count":32,"base":160000,"overtime":12000,"total":172000,"perUnit":5375,"efficiency":94},
            {"property":"SLN Terminus — Plant","function":"Maintenance","count":15,"base":75000,"overtime":9000,"total":84000,"perUnit":5600,"efficiency":79},
            {"property":"SLN Terminus — Fire","function":"Fire & Safety","count":8,"base":40000,"overtime":2000,"total":42000,"perUnit":5250,"efficiency":96},
            {"property":"SLN Terminus — Admin","function":"Admin Support","count":9,"base":45000,"overtime":1500,"total":46500,"perUnit":5167,"efficiency":72},
        ]
        _save(COST_FILE, cost)
    return jsonify(cost)


# ── API: KPI ──────────────────────────────────────────────────────────────────
@sln_resource_bp.route("/api/resource/kpi", methods=["GET"])
@login_required
def api_resource_kpi():
    return jsonify(_load(KPI_FILE))


# ── API: Alerts ───────────────────────────────────────────────────────────────
@sln_resource_bp.route("/api/resource/alerts", methods=["GET"])
@login_required
def api_resource_alerts():
    alerts = _load(ALERTS_FILE)
    return jsonify([a for a in alerts if not a.get("dismissed", False)])


@sln_resource_bp.route("/api/resource/alerts/dismiss", methods=["POST"])
@login_required
def api_resource_alerts_dismiss():
    data   = request.get_json(force=True) or {}
    idx    = data.get("index")
    alerts = _load(ALERTS_FILE)
    if idx == "all":
        for a in alerts:
            a["dismissed"] = True
    elif isinstance(idx, int) and 0 <= idx < len(alerts):
        alerts[idx]["dismissed"] = True
    _save(ALERTS_FILE, alerts)
    return jsonify({"success": True})


# ── API: Generic Upload ───────────────────────────────────────────────────────
@sln_resource_bp.route("/api/resource/upload", methods=["POST"])
@login_required
def api_resource_upload():
    """
    Generic data upload endpoint.
    Form fields: file (xlsx/csv), table (staff|attendance|vendor|tasks)
    """
    if not _HAS_OPENPYXL:
        return jsonify({"success": False, "error": "pandas/openpyxl not installed"}), 400

    uploaded = request.files.get("file")
    table    = request.form.get("table", "attendance")
    if not uploaded:
        return jsonify({"success": False, "error": "No file"}), 400

    try:
        suffix = Path(uploaded.filename).suffix.lower()
        raw    = uploaded.read()
        if suffix in (".xlsx", ".xls"):
            df = pd.read_excel(io.BytesIO(raw))
        elif suffix == ".csv":
            df = pd.read_csv(io.BytesIO(raw))
        else:
            return jsonify({"success": False, "error": "Unsupported type"}), 400

        records = df.to_dict("records")
        target_map = {
            "staff":      STAFF_FILE,
            "attendance": ATTENDANCE_FILE,
            "vendor":     VENDOR_FILE,
            "tasks":      TASKS_FILE,
        }
        dest = target_map.get(table, ATTENDANCE_FILE)
        existing = _load(dest)
        for r in records:
            r["importedAt"] = datetime.now().isoformat()
            existing.append(r)
        _save(dest, existing)
        return jsonify({"success": True, "imported": len(records), "total": len(existing)})

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# ── API: Export Excel ─────────────────────────────────────────────────────────
@sln_resource_bp.route("/api/resource/export/excel", methods=["GET"])
@login_required
def api_resource_export_excel():
    """Build and stream a multi-sheet Excel workbook."""
    if not _HAS_OPENPYXL:
        return jsonify({"error": "openpyxl not installed"}), 400

    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        # Staff sheet
        staff = _load(STAFF_FILE)
        if staff:
            pd.DataFrame(staff).to_excel(writer, sheet_name="Staff Deployment", index=False)

        # Attendance sheet
        att = _load(ATTENDANCE_FILE)
        if att:
            pd.DataFrame(att).to_excel(writer, sheet_name="Attendance", index=False)

        # Vendor sheet
        vendors = _load(VENDOR_FILE)
        if vendors:
            pd.DataFrame(vendors).to_excel(writer, sheet_name="Vendor Compliance", index=False)

        # KPI sheet
        kpi = _load(KPI_FILE)
        if kpi:
            pd.DataFrame(kpi).to_excel(writer, sheet_name="KPI Report", index=False)

        # Cost sheet
        cost = _load(COST_FILE)
        if cost:
            pd.DataFrame(cost).to_excel(writer, sheet_name="Cost Analysis", index=False)

    output.seek(0)
    fname = f"SLN_Workforce_Report_{date.today()}.xlsx"
    return send_file(
        output,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        as_attachment=True,
        download_name=fname
    )


# ── API: Download Blank Template ──────────────────────────────────────────────
@sln_resource_bp.route("/api/resource/export/template/<string:ttype>", methods=["GET"])
@login_required
def api_resource_export_template(ttype):
    """Return a blank Excel template for staff / attendance / vendor."""
    if not _HAS_OPENPYXL:
        return jsonify({"error": "openpyxl not installed"}), 400

    templates = {
        "attendance": {
            "columns": ["Name","Function","Zone","Date","Check-In","Check-Out","Shift","Status","Remarks"],
            "sample":  [["John Doe","Housekeeping","Tower A",str(date.today()),"06:00","14:00","Morning","Present",""]]
        },
        "deployment": {
            "columns": ["Staff Name","Staff ID","Property","Zone","Role/Function","Vendor","Contract Ref","Shift","Status"],
            "sample":  [["John Doe","EMP-001","SLN Terminus","Tower A","Housekeeping","CleanPro Services","VND-001","Morning","Present"]]
        },
        "vendor": {
            "columns": ["Vendor Name","Function","Contracted Count","Deployed Count","Gap","Compliance %","SLA Status","Last Verified"],
            "sample":  [["CleanPro Services","Housekeeping","45","40","5","89%","Partial",str(date.today())]]
        },
        "staff": {
            "columns": ["Full Name","Staff ID","Function","Zone","Shift","Vendor","Contract Ref","Status","Remarks"],
            "sample":  [["John Doe","EMP-001","Housekeeping","Tower A","Morning","CleanPro Services","VND-001","Present",""]]
        }
    }

    spec = templates.get(ttype)
    if not spec:
        abort(404)

    df = pd.DataFrame([spec["sample"][0]], columns=spec["columns"])
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="Template", index=False)
    output.seek(0)
    return send_file(
        output,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        as_attachment=True,
        download_name=f"SLN_resource_{ttype}_template.xlsx"
    )


# ── Initialization ────────────────────────────────────────────────────────────
def register_resource_module(app):
    """
    Call this from server.py to register the resource management blueprint.

    Usage in server.py:
        from sln_resource import register_resource_module
        register_resource_module(app)
    """
    _seed_defaults()
    app.register_blueprint(sln_resource_bp)
    print("✅ [sln_resource] Workforce & Resource Management module registered")
    print("   → Route: /sln_resource_mgmt")
    print("   → API:   /api/resource/*")