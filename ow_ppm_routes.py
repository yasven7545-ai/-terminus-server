"""
OW PPM ROUTES — ONEWEST Planned Preventive Maintenance
Handles: inhouse_ppm + vendor_ppm sheets from Asset.xls
All routes prefixed with ow_
ADD to server.py: safe_register("ow_ppm_routes", "ow_ppm_bp", url_prefix="/ow_api")
"""

from flask import Blueprint, request, jsonify, session, send_file
from pathlib import Path
from datetime import datetime
import pandas as pd
import json
import io
import os
from werkzeug.utils import secure_filename

ow_ppm_bp = Blueprint("ow_ppm_bp", __name__)

# ─────────────────────────────────────────────────────────────────
# PATHS
# ─────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).parent.resolve()
OW_DIR   = BASE_DIR / "static" / "data" / "OW"
OW_ASSETS_XLS        = OW_DIR / "Asset.xls"
OW_ASSETS_XLSX       = OW_DIR / "Asset.xlsx"
OW_WORK_ORDERS_JSON  = OW_DIR / "work_orders.json"
OW_AMC_JSON          = OW_DIR / "amc_contracts.json"
OW_AMC_DOCS_DIR      = BASE_DIR / "uploads" / "OW" / "amc_docs"
OW_PPM_WO_UPLOADS    = BASE_DIR / "uploads" / "OW" / "ppm"

for _d in [OW_DIR, OW_AMC_DOCS_DIR, OW_PPM_WO_UPLOADS]:
    _d.mkdir(parents=True, exist_ok=True)

SHEET_INHOUSE = "inhouse_ppm"
SHEET_VENDOR  = "vendor_ppm"

ALLOWED_DOC_EXT = {"pdf", "doc", "docx", "jpg", "jpeg", "png"}


# ─────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────
def ow_load_sheet(sheet_name: str) -> list:
    """
    Read a sheet from Asset.xls / Asset.xlsx.
    sheet_name is the CANONICAL name (SHEET_INHOUSE / SHEET_VENDOR).
    We auto-resolve the actual tab name via _SHEET_ALIASES so files with
    non-standard tab names still load correctly after import.
    """
    candidates = [
        (OW_ASSETS_XLS,  "xlrd"),
        (OW_ASSETS_XLSX, "openpyxl"),
    ]
    df = None
    for path, engine in candidates:
        if not path.exists():
            continue
        try:
            # Try to discover the actual sheet name in this file
            xl = pd.ExcelFile(str(path), engine=engine)
            actual = sheet_name  # default: use as-is
            for s in xl.sheet_names:
                if _SHEET_ALIASES.get(s.lower().strip()) == sheet_name:
                    actual = s
                    break
            df = pd.read_excel(str(path), sheet_name=actual, engine=engine)
            break
        except Exception as e:
            print(f"\u26a0\ufe0f  ow_load_sheet('{sheet_name}') \u2014 {path.name} [{engine}]: {e}")
            continue
    if df is None:
        return []

    assets = []
    for _, row in df.iterrows():
        asset_code = str(row.get("Asset Code", "")).strip()
        if not asset_code or asset_code.lower() in ("nan", "none", ""):
            continue

        # Department / Trade
        dept = (
            str(row.get("Department", row.get("Trade", row.get("Category", "General")))).strip()
        )

        assets.append({
            "id":          asset_code,
            "asset_code":  asset_code,
            "name":        str(row.get("Asset Name", "Unknown Asset")).strip(),
            "asset_name":  str(row.get("Asset Name", "Unknown Asset")).strip(),
            "department":  dept,
            "trade":       dept,
            "category":    dept,
            "location":    str(row.get("Location", "Unknown")).strip(),
            "lastService": str(row.get("Last Service", "")).strip(),
            "last_service":str(row.get("Last Service", "")).strip(),
            "nextDueDate": str(row.get("nextDueDate", row.get("Next Due Date", ""))).strip(),
            "next_due":    str(row.get("nextDueDate", row.get("Next Due Date", ""))).strip(),
            "ppm_type":    sheet_name.replace("_ppm", ""),
            "property":    "ONEWEST",
        })
    return assets


def ow_load_work_orders() -> list:
    """Load all work orders from JSON."""
    if not OW_WORK_ORDERS_JSON.exists():
        return []
    with open(OW_WORK_ORDERS_JSON, "r", encoding="utf-8") as f:
        return json.load(f).get("work_orders", [])


def ow_save_work_orders(wos: list):
    OW_DIR.mkdir(parents=True, exist_ok=True)
    with open(OW_WORK_ORDERS_JSON, "w", encoding="utf-8") as f:
        json.dump({"work_orders": wos, "last_updated": datetime.now().isoformat()}, f, indent=2)


def ow_require_onewest(fn):
    """Decorator: require ONEWEST property access."""
    from functools import wraps
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if "user" not in session:
            return jsonify({"success": False, "error": "Not authenticated"}), 401
        role = session.get("role", "")
        if role not in ("admin", "Admin"):
            props = session.get("properties", [])
            if "ONEWEST" not in props:
                return jsonify({"success": False, "error": "No access to ONEWEST"}), 403
        return fn(*args, **kwargs)
    return wrapper


# ─────────────────────────────────────────────────────────────────
# 1. ASSETS API — supports ?sheet=inhouse_ppm | vendor_ppm | all
# ─────────────────────────────────────────────────────────────────
@ow_ppm_bp.route("/ppm/assets")
@ow_require_onewest
def ow_ppm_get_assets():
    """
    GET /ow_api/ppm/assets?sheet=inhouse_ppm|vendor_ppm|all
    Returns assets from the specified sheet in Asset.xls
    """
    sheet    = request.args.get("sheet", "all")
    location = request.args.get("location", "all")
    dept     = request.args.get("department", "all")

    if sheet == "inhouse_ppm":
        assets = ow_load_sheet(SHEET_INHOUSE)
    elif sheet == "vendor_ppm":
        assets = ow_load_sheet(SHEET_VENDOR)
    else:  # all
        assets = ow_load_sheet(SHEET_INHOUSE) + ow_load_sheet(SHEET_VENDOR)

    # Filters
    if location != "all":
        assets = [a for a in assets if a.get("location", "").strip() == location.strip()]
    if dept != "all":
        assets = [a for a in assets if (a.get("department") or a.get("trade") or a.get("category") or "") == dept]

    print(f"✅ OW PPM assets — sheet={sheet} → {len(assets)} records")
    return jsonify({"assets": assets, "total": len(assets), "sheet": sheet, "property": "ONEWEST"})


# ─────────────────────────────────────────────────────────────────
# 2. PPM TYPE STATS (inhouse vs vendor counters)
# ─────────────────────────────────────────────────────────────────
@ow_ppm_bp.route("/ppm/type-stats")
@ow_require_onewest
def ow_ppm_type_stats():
    ih = ow_load_sheet(SHEET_INHOUSE)
    vd = ow_load_sheet(SHEET_VENDOR)
    wos = ow_load_work_orders()
    today = datetime.now().date()

    def _count_wo(ppm_type):
        lst = [w for w in wos if (w.get("ppm_type") or "inhouse") == ppm_type]
        open_c = sum(1 for w in lst if (w.get("status") or "open").lower() not in ("completed", "closed"))
        overdue_c = 0
        for w in lst:
            st = (w.get("status") or "open").lower()
            if st in ("completed", "closed"):
                continue
            try:
                dd = datetime.strptime(w.get("due_date", "")[:10], "%Y-%m-%d").date()
                if dd < today:
                    overdue_c += 1
            except Exception:
                pass
        return open_c, overdue_c

    ih_open, ih_overdue = _count_wo("inhouse")
    vd_open, vd_overdue = _count_wo("vendor")

    return jsonify({
        "inhouse": {"assets": len(ih), "open_wos": ih_open, "overdue": ih_overdue},
        "vendor":  {"assets": len(vd), "open_wos": vd_open, "overdue": vd_overdue},
        "property": "ONEWEST",
    })


# ─────────────────────────────────────────────────────────────────
# 3. DASHBOARD STATS
# ─────────────────────────────────────────────────────────────────
@ow_ppm_bp.route("/ppm/dashboard/stats")
@ow_require_onewest
def ow_ppm_dashboard_stats():
    wos = ow_load_work_orders()
    today = datetime.now().date()

    total_wo     = len(wos)
    completed_wo = sum(1 for w in wos if (w.get("status") or "").lower() in ("completed", "closed"))
    pending_wo   = total_wo - completed_wo
    overdue_wo   = 0

    for wo in wos:
        status = (wo.get("status") or "").lower()
        if status in ("completed", "closed"):
            continue
        try:
            dd = datetime.strptime(wo.get("due_date", "")[:10], "%Y-%m-%d").date()
            if dd < today:
                overdue_wo += 1
        except Exception:
            pass

    # Asset count (both sheets)
    asset_count = len(ow_load_sheet(SHEET_INHOUSE)) + len(ow_load_sheet(SHEET_VENDOR))
    compliance  = round(completed_wo / total_wo * 100, 1) if total_wo > 0 else 0.0

    return jsonify({
        "total_assets":    asset_count,
        "pending_ppm":     pending_wo,
        "completed_ppm":   completed_wo,
        "ppm_overdue":     overdue_wo,
        "compliance_rate": compliance,
        "property":        "ONEWEST",
    })


# ─────────────────────────────────────────────────────────────────
# 4. WORK ORDERS
# ─────────────────────────────────────────────────────────────────
@ow_ppm_bp.route("/ppm/workorders")
@ow_require_onewest
def ow_ppm_get_workorders():
    wos = ow_load_work_orders()
    status_filter = request.args.get("status", "all").lower()
    if status_filter != "all":
        wos = [w for w in wos if (w.get("status") or "").lower() == status_filter]

    formatted = [{
        "WO ID":        wo.get("work_order_id", "N/A"),
        "Asset":        wo.get("asset_name", "Unknown"),
        "Location":     wo.get("location", "Unknown"),
        "Due Date":     wo.get("due_date", "N/A"),
        "Priority":     wo.get("priority", "Medium"),
        "Status":       wo.get("status", "open"),
        "work_order_id": wo.get("work_order_id", ""),
        "asset_id":     wo.get("asset_id", ""),
        "asset_name":   wo.get("asset_name", ""),
        "location":     wo.get("location", ""),
        "due_date":     wo.get("due_date", ""),
        "priority":     wo.get("priority", "Medium"),
        "status":       wo.get("status", "open"),
        "ppm_type":     wo.get("ppm_type", "inhouse"),
        "assigned_to":  wo.get("assigned_to", ""),
        "supervisor":   wo.get("supervisor", ""),
        "checklist":    wo.get("checklist", []),
        "images":       wo.get("images", []),
        "closed_at":    wo.get("closed_at", ""),
        "closed_by":    wo.get("closed_by", ""),
        "approval_notes": wo.get("approval_notes", ""),
        "technician_notes": wo.get("technician_notes", ""),
        "created_at":   wo.get("created_at", ""),
        "property":     "ONEWEST",
    } for wo in wos]

    return jsonify({"work_orders": formatted, "total": len(formatted), "property": "ONEWEST", "success": True})


# ─────────────────────────────────────────────────────────────────
# 5. WORK ORDERS BY DATE (Calendar)
# ─────────────────────────────────────────────────────────────────
@ow_ppm_bp.route("/workorders/by-date")
@ow_require_onewest
def ow_workorders_by_date():
    date_str = request.args.get("date", datetime.now().strftime("%Y-%m-%d"))
    wos = ow_load_work_orders()
    filtered = [w for w in wos if w.get("due_date", "")[:10] == date_str]
    return jsonify({"work_orders": filtered, "date": date_str, "total": len(filtered), "property": "ONEWEST"})


# ─────────────────────────────────────────────────────────────────
# 6. CALENDAR DATA (grouped by due date)
# ─────────────────────────────────────────────────────────────────
@ow_ppm_bp.route("/ppm/calendar")
@ow_require_onewest
def ow_ppm_calendar():
    year  = int(request.args.get("year",  datetime.now().year))
    month = int(request.args.get("month", datetime.now().month))

    all_assets = ow_load_sheet(SHEET_INHOUSE) + ow_load_sheet(SHEET_VENDOR)
    calendar_data = {}

    for asset in all_assets:
        next_due = asset.get("nextDueDate") or asset.get("next_due") or ""
        if not next_due or next_due.lower() in ("nan", "none", ""):
            continue
        try:
            from dateutil.parser import parse as dp
            dt = dp(next_due)
            if dt.year == year and dt.month == month:
                key = dt.strftime("%Y-%m-%d")
                if key not in calendar_data:
                    calendar_data[key] = []
                calendar_data[key].append({
                    "id":          asset["id"],
                    "name":        asset["name"],
                    "location":    asset["location"],
                    "lastService": asset.get("lastService", ""),
                    "ppm_type":    asset.get("ppm_type", "inhouse"),
                    "department":  asset.get("department", "General"),
                })
        except Exception:
            pass

    return jsonify({"calendar": calendar_data, "year": year, "month": month, "property": "ONEWEST"})


# ─────────────────────────────────────────────────────────────────
# 7. CREATE WORK ORDER
# ─────────────────────────────────────────────────────────────────
@ow_ppm_bp.route("/workflow/create", methods=["POST"])
@ow_require_onewest
def ow_workflow_create():
    data       = request.get_json() or {}
    asset_id   = data.get("assetId", "")
    asset_name = data.get("assetName", "Manual WO")
    location   = data.get("location", "ONEWEST")
    due_date   = data.get("dueDate", datetime.now().strftime("%Y-%m-%d"))
    ppm_type   = data.get("ppmType", "inhouse")

    # Determine asset type for checklist
    name_lower = asset_name.lower()
    if   "dg" in name_lower or "generator" in name_lower: asset_type = "dg"
    elif "elevator" in name_lower or "lift" in name_lower: asset_type = "elevator"
    elif "chiller" in name_lower or "hvac" in name_lower:  asset_type = "chiller"
    elif "fire" in name_lower:                              asset_type = "fire"
    elif "pump" in name_lower:                              asset_type = "pump"
    elif "electrical" in name_lower or "panel" in name_lower: asset_type = "electrical"
    else:                                                   asset_type = "default"

    checklists = {
        "dg":         ["Check fuel level", "Inspect battery", "Verify coolant level", "Check engine oil", "Test ATS switchover", "Inspect exhaust system", "Check coolant temperature"],
        "elevator":   ["Inspect door operation", "Check emergency stop", "Verify leveling accuracy", "Inspect machine room", "Test emergency lighting", "Check safety devices", "Lubricate guide rails"],
        "chiller":    ["Check refrigerant pressure", "Inspect condenser coils", "Verify compressor oil level", "Check electrical connections", "Inspect for refrigerant leaks", "Clean strainer/filter"],
        "fire":       ["Test alarm panel", "Check sprinkler heads", "Verify extinguisher pressure", "Test smoke detectors", "Check hydrant pressure", "Inspect fire pump"],
        "pump":       ["Check discharge pressure", "Inspect mechanical seal", "Verify suction pressure", "Check motor current", "Inspect coupling", "Check bearing temperature"],
        "electrical": ["Check panel board", "Test MCB operation", "Verify earthing connection", "Check cable insulation", "Inspect bus bar", "Verify voltage levels"],
        "default":    ["Visual inspection", "Check for abnormal noise/vibration", "Verify safety guards", "Inspect for leaks", "Test emergency stop", "Verify control panel operation"],
    }
    cl_items = checklists.get(asset_type, checklists["default"])
    checklist = [{"id": f"{asset_type}_{i+1}", "text": item, "required": i < 4, "completed": False, "comments": ""} for i, item in enumerate(cl_items)]

    priority = "High" if any(k in name_lower for k in ["fire", "dg", "generator", "transformer", "hv", "elevator", "pump"]) else "Medium"

    wos = ow_load_work_orders()
    wo_id = f"OW-PPM-{datetime.now().strftime('%Y-%m')}-{str(len(wos)+1).zfill(4)}"

    new_wo = {
        "work_order_id":     wo_id,
        "asset_id":          asset_id,
        "asset_name":        asset_name,
        "location":          location,
        "due_date":          due_date,
        "priority":          priority,
        "status":            "open",
        "ppm_type":          ppm_type,
        "property":          "ONEWEST",
        "created_at":        datetime.now().isoformat(),
        "assigned_to":       "",
        "supervisor":        "",
        "checklist":         checklist,
        "images":            [],
        "technician_notes":  "",
        "approval_notes":    "",
    }

    wos.append(new_wo)
    ow_save_work_orders(wos)
    print(f"✅ OW WO Created: {wo_id} — {asset_name} [{ppm_type}]")
    return jsonify({"success": True, "work_order_id": wo_id, "message": "Work order created"})


# ─────────────────────────────────────────────────────────────────
# 8. SAVE CHECKLIST PROGRESS
# ─────────────────────────────────────────────────────────────────
@ow_ppm_bp.route("/workflow/save-checklist", methods=["POST"])
@ow_require_onewest
def ow_workflow_save_checklist():
    data  = request.get_json() or {}
    wo_id = data.get("workOrderId", "")
    wos   = ow_load_work_orders()
    updated = False
    for wo in wos:
        if wo.get("work_order_id") == wo_id:
            wo["checklist"]         = data.get("checklist", wo.get("checklist", []))
            wo["technician_notes"]  = data.get("technician_notes", "")
            wo["status"]            = data.get("status", wo.get("status", "in-progress"))
            updated = True
            break
    if not updated:
        return jsonify({"success": False, "error": "Work order not found"}), 404
    ow_save_work_orders(wos)
    return jsonify({"success": True, "message": "Checklist saved"})


# ─────────────────────────────────────────────────────────────────
# 9. CLOSE WORK ORDER (supervisor approval)
# ─────────────────────────────────────────────────────────────────
@ow_ppm_bp.route("/workflow/close", methods=["POST"])
@ow_require_onewest
def ow_workflow_close():
    data           = request.get_json() or {}
    wo_id          = data.get("workOrderId", "")
    approval_notes = data.get("approvalNotes", "")
    supervisor_ok  = data.get("supervisorApproval", False)
    technician     = data.get("technician", "")
    images         = data.get("images", [])
    checklist      = data.get("checklist", [])

    if not supervisor_ok:
        return jsonify({"success": False, "error": "Supervisor approval required"}), 400

    # Save any base64 images to disk — keeps work_orders.json lean
    saved_image_paths = []
    for img in images:
        try:
            if isinstance(img, str) and img.startswith("data:"):
                header, b64data = img.split(",", 1)
                ext_match = header.split("/")[-1].split(";")[0]  # e.g. "jpeg"
                ext_match = ext_match if ext_match in ("jpg", "jpeg", "png", "webp") else "jpg"
                import base64
                img_bytes = base64.b64decode(b64data)
                img_fn = f"{wo_id}_{datetime.now().strftime('%H%M%S%f')}_{len(saved_image_paths)}.{ext_match}"
                img_path = OW_PPM_WO_UPLOADS / img_fn
                OW_PPM_WO_UPLOADS.mkdir(parents=True, exist_ok=True)
                img_path.write_bytes(img_bytes)
                saved_image_paths.append(f"/uploads/OW/ppm/{img_fn}")
            elif isinstance(img, str) and img.startswith("/uploads/"):
                saved_image_paths.append(img)  # already a URL reference
        except Exception as e:
            print(f"⚠️  OW WO image save failed: {e}")

    wos = ow_load_work_orders()
    updated = False
    for wo in wos:
        if wo.get("work_order_id") == wo_id:
            wo["status"]         = "completed"
            wo["closed_at"]      = datetime.now().isoformat()
            wo["approval_notes"] = approval_notes
            wo["technician"]     = technician
            wo["images"]         = saved_image_paths  # store paths, not base64
            wo["checklist"]      = checklist
            wo["closed_by"]      = session.get("user", "supervisor")
            updated = True
            break

    if not updated:
        return jsonify({"success": False, "error": "Work order not found"}), 404

    ow_save_work_orders(wos)
    print(f"✅ OW WO Closed: {wo_id} by {session.get('user')}")
    return jsonify({"success": True, "message": f"Work order {wo_id} closed successfully"})


# ─────────────────────────────────────────────────────────────────
# 10. EXPORT WORK ORDERS (Excel)
# ─────────────────────────────────────────────────────────────────
@ow_ppm_bp.route("/ppm/workorders/export")
@ow_require_onewest
def ow_ppm_export_workorders():
    wos = ow_load_work_orders()
    if not wos:
        return jsonify({"error": "No work orders to export"}), 404

    rows = [{
        "WO ID":          wo.get("work_order_id", ""),
        "Asset":          wo.get("asset_name", ""),
        "Location":       wo.get("location", ""),
        "Due Date":       wo.get("due_date", ""),
        "Priority":       wo.get("priority", ""),
        "Status":         wo.get("status", ""),
        "PPM Type":       wo.get("ppm_type", "inhouse"),
        "Assigned To":    wo.get("assigned_to", ""),
        "Supervisor":     wo.get("supervisor", ""),
        "Created At":     wo.get("created_at", ""),
        "Closed At":      wo.get("closed_at", ""),
        "Approval Notes": wo.get("approval_notes", ""),
        "Property":       "ONEWEST",
    } for wo in wos]

    df = pd.DataFrame(rows)
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as w:
        df.to_excel(w, index=False, sheet_name="ONEWEST Work Orders")
    buf.seek(0)
    fn = f"ONEWEST_WorkOrders_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    return send_file(buf, mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                     as_attachment=True, download_name=fn)


# ─────────────────────────────────────────────────────────────────
# 11. IMPORT / UPLOAD ASSET EXCEL
# ─────────────────────────────────────────────────────────────────
# Sheet name aliases — maps any reasonable tab name → canonical key
_SHEET_ALIASES = {
    SHEET_INHOUSE:  SHEET_INHOUSE,   # "inhouse_ppm"
    "inhouse":      SHEET_INHOUSE,
    "in-house":     SHEET_INHOUSE,
    "in house":     SHEET_INHOUSE,
    "inhouse ppm":  SHEET_INHOUSE,
    "in-house ppm": SHEET_INHOUSE,
    "ppm inhouse":  SHEET_INHOUSE,
    "sheet1":       SHEET_INHOUSE,   # common default name
    "assets":       SHEET_INHOUSE,
    SHEET_VENDOR:   SHEET_VENDOR,    # "vendor_ppm"
    "vendor":       SHEET_VENDOR,
    "vendor ppm":   SHEET_VENDOR,
    "ppm vendor":   SHEET_VENDOR,
    "amc":          SHEET_VENDOR,
    "sheet2":       SHEET_VENDOR,    # common default name
}

def _resolve_sheets(file_bytes: bytes, engine: str) -> dict:
    """
    Open the workbook, try to find inhouse + vendor sheets by name or alias.
    Returns {canonical_key: actual_sheet_name_in_file}
    """
    xl = pd.ExcelFile(io.BytesIO(file_bytes), engine=engine)
    actual_sheets = xl.sheet_names  # list of names as they appear in the file
    resolved = {}
    for actual in actual_sheets:
        key = _SHEET_ALIASES.get(actual.lower().strip())
        if key and key not in resolved:
            resolved[key] = actual
    # Fallback: if only ONE sheet exists, treat it as inhouse
    if not resolved and len(actual_sheets) >= 1:
        resolved[SHEET_INHOUSE] = actual_sheets[0]
    if SHEET_INHOUSE in resolved and SHEET_VENDOR not in resolved and len(actual_sheets) >= 2:
        # second sheet that wasn't matched → vendor
        for s in actual_sheets:
            if s != resolved[SHEET_INHOUSE]:
                resolved[SHEET_VENDOR] = s
                break
    return resolved, actual_sheets


@ow_ppm_bp.route("/ppm/import-excel", methods=["POST"])
@ow_require_onewest
def ow_ppm_import_excel():
    try:
        file = request.files.get("file")
        if not file or not file.filename:
            return jsonify({"status": "error", "message": "No file uploaded"}), 400

        ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
        if ext not in ("xls", "xlsx"):
            return jsonify({"status": "error", "message": "Only .xlsx or .xls files are accepted"}), 400

        OW_DIR.mkdir(parents=True, exist_ok=True)

        # Read into memory first — avoids holding request open during disk ops
        file_bytes = file.read()
        engine = "openpyxl" if ext == "xlsx" else "xlrd"

        # Resolve sheet names before saving (gives clearer errors if file is corrupt)
        try:
            sheet_map, all_sheets = _resolve_sheets(file_bytes, engine)
        except Exception as e:
            return jsonify({
                "status": "error",
                "message": f"Could not read Excel file — is it corrupt or password-protected? ({e})"
            }), 422

        if not sheet_map:
            return jsonify({
                "status": "error",
                "message": (
                    f"No usable sheets found. Your file has: {all_sheets}. "
                    f"Rename a sheet to '{SHEET_INHOUSE}' and/or '{SHEET_VENDOR}' and re-upload."
                )
            }), 422

        # Correct target path per extension
        target = OW_ASSETS_XLSX if ext == "xlsx" else OW_ASSETS_XLS

        # Remove existing locked/read-only file before writing
        for old_f in [OW_ASSETS_XLS, OW_ASSETS_XLSX]:
            if old_f.exists():
                try:
                    os.chmod(str(old_f), 0o666)
                    old_f.unlink()
                except Exception as e:
                    print(f"\u26a0\ufe0f  Could not remove {old_f.name}: {e}")

        # Atomic write: temp file → rename
        import tempfile, shutil
        tmp_fd, tmp_path = tempfile.mkstemp(suffix=f".{ext}", dir=str(OW_DIR))
        try:
            with os.fdopen(tmp_fd, "wb") as tmp_f:
                tmp_f.write(file_bytes)
            os.chmod(tmp_path, 0o666)
            shutil.move(tmp_path, str(target))
        except Exception:
            try: os.unlink(tmp_path)
            except Exception: pass
            raise

        # Count records using resolved sheet names
        count = 0
        sheets_found = []
        for canonical, actual in sheet_map.items():
            try:
                df = pd.read_excel(str(target), sheet_name=actual, engine=engine)
                sheet_count = int(df["Asset Code"].notna().sum()) if "Asset Code" in df.columns else len(df)
                count += sheet_count
                label = actual if actual == canonical else f"{actual}\u2192{canonical}"
                sheets_found.append(f"{label}({sheet_count})")
                # If the actual name differs from canonical, note it in server log
                if actual != canonical:
                    print(f"\u2139\ufe0f  OW import: sheet '{actual}' mapped to '{canonical}'")
            except Exception as e:
                print(f"\u26a0\ufe0f  OW import — sheet '{actual}' skipped: {e}")

        msg = f"Synced {count} ONEWEST assets \u2014 " + ", ".join(sheets_found)
        print(f"\u2705 OW Assets imported: {msg} from {file.filename}")
        return jsonify({"status": "success", "message": msg, "count": count})

    except PermissionError as e:
        msg = (
            f"Permission denied: {getattr(e, 'filename', None) or 'asset file'}. "
            "Close the file in Excel if open, or check folder write permissions."
        )
        print(f"\u274c OW import PermissionError: {e}")
        return jsonify({"status": "error", "message": msg}), 500

    except Exception as e:
        import traceback
        print(f"\u274c OW import-excel error: {traceback.format_exc()}")
        return jsonify({"status": "error", "message": f"Import failed: {str(e)}"}), 500


@ow_ppm_bp.route("/ppm/import-excel/info", methods=["POST"])
@ow_require_onewest
def ow_ppm_import_excel_info():
    """Preview sheet names in an uploaded file without saving it."""
    file = request.files.get("file")
    if not file or not file.filename:
        return jsonify({"status": "error", "message": "No file"}), 400
    ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    if ext not in ("xls", "xlsx"):
        return jsonify({"status": "error", "message": "Only .xls/.xlsx accepted"}), 400
    try:
        engine = "openpyxl" if ext == "xlsx" else "xlrd"
        file_bytes = file.read()
        sheet_map, all_sheets = _resolve_sheets(file_bytes, engine)
        return jsonify({
            "sheets_in_file": all_sheets,
            "resolved": {k: v for k, v in sheet_map.items()},
            "ready": bool(sheet_map),
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 422


# ─────────────────────────────────────────────────────────────────
# 12. BULK UPLOAD WORK ORDERS (Excel / CSV)
# ─────────────────────────────────────────────────────────────────
@ow_ppm_bp.route("/ppm/bulk-upload", methods=["POST"])
@ow_require_onewest
def ow_ppm_bulk_upload():
    file = request.files.get("file")
    if not file:
        return jsonify({"status": "error", "message": "No file uploaded"}), 400

    try:
        ext = file.filename.rsplit(".", 1)[-1].lower()
        if ext == "csv":
            import csv, io as _io
            content = file.read().decode("utf-8")
            reader = csv.DictReader(_io.StringIO(content))
            rows = list(reader)
        else:
            # Read stream into bytes first — file streams can't be seeked by pandas
            file_bytes = file.read()
            engine = "openpyxl" if ext == "xlsx" else "xlrd"
            df = pd.read_excel(io.BytesIO(file_bytes), engine=engine)
            rows = df.to_dict(orient="records")

        wos = ow_load_work_orders()
        created = 0
        for row in rows:
            asset_id   = str(row.get("Asset Code", row.get("asset_id", ""))).strip()
            asset_name = str(row.get("Asset Name", row.get("asset_name", "Unknown"))).strip()
            location   = str(row.get("Location", row.get("location", "ONEWEST"))).strip()
            due_date   = str(row.get("Due Date", row.get("due_date", datetime.now().strftime("%Y-%m-%d")))).strip()
            ppm_type   = str(row.get("PPM Type", row.get("ppm_type", "inhouse"))).strip().lower()

            if not asset_name or asset_name.lower() in ("nan", "none"):
                continue

            wo_id = f"OW-PPM-{datetime.now().strftime('%Y-%m')}-{str(len(wos)+created+1).zfill(4)}"
            wos.append({
                "work_order_id": wo_id,
                "asset_id":      asset_id,
                "asset_name":    asset_name,
                "location":      location,
                "due_date":      due_date,
                "priority":      "Medium",
                "status":        "open",
                "ppm_type":      ppm_type,
                "property":      "ONEWEST",
                "created_at":    datetime.now().isoformat(),
                "checklist":     [],
                "images":        [],
            })
            created += 1

        ow_save_work_orders(wos)
        return jsonify({"status": "success", "message": f"Created {created} work orders", "count": created})

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


# ─────────────────────────────────────────────────────────────────
# 13. AMC CONTRACTS
# ─────────────────────────────────────────────────────────────────
@ow_ppm_bp.route("/amc/contracts")
@ow_require_onewest
def ow_amc_contracts():
    if not OW_AMC_JSON.exists():
        return jsonify({"contracts": [], "total": 0, "property": "ONEWEST"})
    with open(OW_AMC_JSON, "r", encoding="utf-8") as f:
        data = json.load(f)
    contracts = data.get("contracts", [])
    sf = request.args.get("status", "all").lower()
    if sf != "all":
        contracts = [c for c in contracts if (c.get("status") or "active").lower() == sf]
    return jsonify({"contracts": contracts, "total": len(contracts), "property": "ONEWEST", "success": True})


@ow_ppm_bp.route("/amc/update", methods=["POST"])
@ow_require_onewest
def ow_amc_update():
    data        = request.get_json() or {}
    contract_id = data.get("contract_id", "")
    amc_data    = {"contracts": [], "last_updated": ""}
    if OW_AMC_JSON.exists():
        with open(OW_AMC_JSON, "r", encoding="utf-8") as f:
            amc_data = json.load(f)
    contracts = amc_data.get("contracts", [])
    found = False
    for i, c in enumerate(contracts):
        if c.get("contract_id") == contract_id:
            contracts[i] = {**c, **data, "updated_at": datetime.now().isoformat()}
            found = True
            break
    if not found:
        data["created_at"] = datetime.now().isoformat()
        contracts.append(data)
    amc_data["contracts"]    = contracts
    amc_data["last_updated"] = datetime.now().isoformat()
    OW_DIR.mkdir(parents=True, exist_ok=True)
    with open(OW_AMC_JSON, "w", encoding="utf-8") as f:
        json.dump(amc_data, f, indent=2)
    return jsonify({"success": True, "message": "AMC contract saved"})


@ow_ppm_bp.route("/amc/contracts/export")
@ow_require_onewest
def ow_amc_export():
    contracts = []
    if OW_AMC_JSON.exists():
        with open(OW_AMC_JSON, "r", encoding="utf-8") as f:
            contracts = json.load(f).get("contracts", [])
    if not contracts:
        return jsonify({"error": "No contracts to export"}), 404
    df  = pd.DataFrame(contracts)
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as w:
        df.to_excel(w, index=False, sheet_name="ONEWEST AMC")
    buf.seek(0)
    fn = f"ONEWEST_AMC_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    return send_file(buf, mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                     as_attachment=True, download_name=fn)


# ─────────────────────────────────────────────────────────────────
# 14. AMC DOCUMENT UPLOAD
# ─────────────────────────────────────────────────────────────────
@ow_ppm_bp.route("/amc/upload-doc", methods=["POST"])
@ow_require_onewest
def ow_amc_upload_doc():
    files = request.files.getlist("file")
    if not files:
        return jsonify({"success": False, "error": "No file uploaded"}), 400
    saved = []
    for f in files:
        ext = f.filename.rsplit(".", 1)[-1].lower() if "." in f.filename else ""
        if ext not in ALLOWED_DOC_EXT:
            continue
        fn = secure_filename(f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{f.filename}")
        f.save(str(OW_AMC_DOCS_DIR / fn))
        saved.append({"filename": fn, "url": f"/uploads/OW/amc_docs/{fn}"})
    return jsonify({"success": True, "files": saved, "count": len(saved)})


# ─────────────────────────────────────────────────────────────────
# 15. TECHNICIANS & SUPERVISORS
# ─────────────────────────────────────────────────────────────────
@ow_ppm_bp.route("/technicians")
@ow_require_onewest
def ow_ppm_technicians():
    f = OW_DIR / "technicians.json"
    if not f.exists():
        return jsonify({"technicians": []})
    with open(f, "r", encoding="utf-8") as fp:
        return jsonify(json.load(fp))


@ow_ppm_bp.route("/supervisors")
@ow_require_onewest
def ow_ppm_supervisors():
    f = OW_DIR / "supervisors.json"
    if not f.exists():
        return jsonify({"supervisors": []})
    with open(f, "r", encoding="utf-8") as fp:
        return jsonify(json.load(fp))


# ─────────────────────────────────────────────────────────────────
# 16. DAILY MAIL TRIGGER
# ─────────────────────────────────────────────────────────────────
@ow_ppm_bp.route("/trigger-daily-mail", methods=["POST"])
@ow_require_onewest
def ow_trigger_daily_mail():
    """Manual trigger for daily PPM email."""
    try:
        # Import from main server to re-use existing mailer
        import importlib, sys
        # Try to call the function if available in main module
        if "ow_send_daily_ppm_mail" in dir(sys.modules.get("__main__")):
            result = sys.modules["__main__"].ow_send_daily_ppm_mail()
            return jsonify(result)
        # Fallback: basic notification
        wos = ow_load_work_orders()
        today_str = datetime.now().strftime("%Y-%m-%d")
        today_wos = [w for w in wos if w.get("due_date", "")[:10] == today_str and
                     (w.get("status") or "").lower() not in ("completed", "closed")]
        return jsonify({"success": True, "wo_count": len(today_wos), "message": f"Daily mail trigger — {len(today_wos)} WOs today"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500