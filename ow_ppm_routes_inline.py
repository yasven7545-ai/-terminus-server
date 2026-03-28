"""
ONEWEST PPM ROUTES (INLINE)
ONEWEST PPM assets, work orders (create/close/export/by-date/calendar),
AMC contracts, inventory, technicians/supervisors, daily mail scheduler.
"""
from flask import Blueprint, request, jsonify, session, send_file, render_template, send_from_directory
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr
import json
import traceback
import pandas as pd
import io
import re as _re

from decorators import login_required, require_property
from config import BASE_DIR, _smtp_send, SENDER_EMAIL
from werkzeug.utils import secure_filename

ow_ppm_bp = Blueprint("ow_ppm", __name__)

# ── ONEWEST data paths ────────────────────────────────────────────────────────
OW_DIR              = BASE_DIR / "static" / "data" / "OW"
OW_ASSETS_XLS       = OW_DIR / "Asset.xls"
OW_ASSETS_XLSX      = OW_DIR / "Asset.xlsx"
OW_WORK_ORDERS_JSON = OW_DIR / "work_orders.json"
OW_AMC_JSON         = OW_DIR / "amc_contracts.json"
OW_PPM_WO_UPLOADS   = BASE_DIR / "uploads" / "OW" / "ppm"
OW_INVENTORY_XLSX   = BASE_DIR / "static" / "data" / "ow_store_master.xlsx"
OW_INVENTORY_ALERTS = BASE_DIR / "static" / "data" / "ow_inventory_alerts.json"
OW_INVENTORY_DIR    = BASE_DIR / "static" / "data" / "OW" / "inventory"
OW_TECHNICIANS_JSON = OW_DIR / "technicians.json"
OW_SUPERVISORS_JSON = OW_DIR / "supervisors.json"

OW_EMAIL_RECEIVERS = [
    "maintenance.slnterminus@gmail.com",
    "yasven7545@gmail.com",
    "engineering@terminus-global.com",
]

# ── Ensure directories ────────────────────────────────────────────────────────
for _d in [OW_DIR, OW_PPM_WO_UPLOADS, OW_INVENTORY_DIR, OW_INVENTORY_ALERTS.parent]:
    _d.mkdir(parents=True, exist_ok=True)

if not OW_INVENTORY_ALERTS.exists():
    with open(OW_INVENTORY_ALERTS, "w") as _f:
        json.dump({"alerts": [], "last_updated": datetime.now().isoformat()}, _f, indent=2)

# ── Write authoritative staff data on startup ─────────────────────────────────
_OW_TECHS = {
    "technicians": [
        {"id": "T001", "name": "Jagadish",    "phone": "+919666942315", "specialization": "Supervisor"},
        {"id": "T002", "name": "Sri Ram",     "phone": "+919989668311", "specialization": "Supervisor"},
        {"id": "T003", "name": "Ameer",       "phone": "+919000564662", "specialization": "Supervisor"},
        {"id": "T004", "name": "Rakesh",      "phone": "+917730834084", "specialization": "Supervisor"},
        {"id": "T005", "name": "Raghavendra", "phone": "+918008883537", "specialization": "BMS"},
        {"id": "T006", "name": "Shiva",       "phone": "+918885637165", "specialization": "BMS"},
        {"id": "T007", "name": "Tanmaya",     "phone": "+917077689216", "specialization": "BMS"},
        {"id": "T008", "name": "Raviteja",    "phone": "+919652607622", "specialization": "Electrical"},
        {"id": "T009", "name": "Nagendra",    "phone": "+919347324744", "specialization": "Electrical"},
        {"id": "T010", "name": "Yeshwanth",   "phone": "+919502856581", "specialization": "Electrical"},
        {"id": "T011", "name": "Hakim",       "phone": "+918083360242", "specialization": "Electrical"},
        {"id": "T012", "name": "Sai pawan",   "phone": "+917013987434", "specialization": "Electrical"},
        {"id": "T013", "name": "Nikhil",      "phone": "+917093979479", "specialization": "Asst Technician"},
        {"id": "T014", "name": "Vijay",       "phone": "+916304725703", "specialization": "Asst Technician"},
        {"id": "T015", "name": "Karthik",     "phone": "+919553174565", "specialization": "Asst Technician"},
        {"id": "T016", "name": "Ilyas",       "phone": "+919347732552", "specialization": "HVAC"},
        {"id": "T017", "name": "Sai",         "phone": "+917794057118", "specialization": "HVAC"},
        {"id": "T018", "name": "Venu",        "phone": "+919618670499", "specialization": "HVAC"},
        {"id": "T019", "name": "Bharath",     "phone": "+918106869682", "specialization": "HVAC"},
        {"id": "T020", "name": "Ismail",      "phone": "+919154223362", "specialization": "HVAC"},
        {"id": "T021", "name": "Bipin",       "phone": "+919121261604", "specialization": "Plumber"},
        {"id": "T027", "name": "Bichitra",    "phone": "+917732040540", "specialization": "Plumber"},
        {"id": "T022", "name": "Sudarshan",   "phone": "+917036994079", "specialization": "Plumber"},
        {"id": "T023", "name": "Srikanth",    "phone": "+917749090745", "specialization": "Plumber"},
        {"id": "T024", "name": "Tapan",       "phone": "+916380896010", "specialization": "Plumber"},
        {"id": "T025", "name": "Rohith",      "phone": "+919948351383", "specialization": "Painter"},
        {"id": "T026", "name": "Laxman",      "phone": "+917995751392", "specialization": "Carpenter"},
    ]
}
_OW_SUPS = {
    "supervisors": [
        {"id": "S001", "name": "Anil Kumar",   "phone": "+919876543220", "email": "anil@onewest.com"},
        {"id": "S002", "name": "Ravi Shankar", "phone": "+919876543221", "email": "ravi@onewest.com"},
    ]
}
with open(OW_TECHNICIANS_JSON, "w", encoding="utf-8") as _owf:
    json.dump(_OW_TECHS, _owf, indent=2)
with open(OW_SUPERVISORS_JSON, "w", encoding="utf-8") as _owf:
    json.dump(_OW_SUPS, _owf, indent=2)


# ═════════════════════════════════════════════════════════════════════════════
# ASSETS
# ═════════════════════════════════════════════════════════════════════════════

@ow_ppm_bp.route("/ow_api/ppm/assets")
@login_required
@require_property("ONEWEST")
def ow_api_ppm_assets():
    """ONEWEST PPM assets — reads BOTH inhouse_ppm + vendor_ppm sheets."""
    try:
        location_filter = request.args.get("location", "all")
        candidates = [(OW_ASSETS_XLS, "xlrd"), (OW_ASSETS_XLSX, "openpyxl")]
        sheets_loaded = []
        for fpath, engine in candidates:
            if not fpath.exists():
                continue
            try:
                xl = pd.ExcelFile(str(fpath), engine=engine)
                for sheet_canon, ppm_type in [("inhouse_ppm", "inhouse"), ("vendor_ppm", "vendor")]:
                    actual = next((s for s in xl.sheet_names if s.lower().strip() == sheet_canon), None)
                    if actual is None:
                        actual = next((s for s in xl.sheet_names if ppm_type in s.lower()), None)
                    if actual is None:
                        continue
                    try:
                        df = pd.read_excel(str(fpath), sheet_name=actual, engine=engine)
                        sheets_loaded.append((df, ppm_type))
                    except Exception as se:
                        print(f"⚠️ Sheet '{actual}' error: {se}")
                if sheets_loaded:
                    break
            except Exception as e:
                print(f"⚠️ Cannot open {fpath.name}: {e}")

        if not sheets_loaded:
            return jsonify({"assets": [], "total": 0, "property": "ONEWEST"})

        assets = []
        for df, ppm_type in sheets_loaded:
            for _, row in df.iterrows():
                ac  = str(row.get("Equipment No.", row.get("Asset Code", ""))).strip()
                if not ac or ac.lower() in ("nan", "none", ""):
                    continue
                an  = str(row.get("Equipment Name", row.get("Asset Name", "Unknown Asset"))).strip()
                dept = str(row.get("Trade", row.get("Department", row.get("Category", "General")))).strip()
                if dept.lower() in ("nan", "none", ""): dept = "General"
                loc  = str(row.get("Location", "Unknown")).strip()
                if loc.lower()  in ("nan", "none", ""): loc  = "Unknown"
                ls   = str(row.get("Last Service", "")).strip()
                if ls.lower()   in ("nan", "none"):     ls   = ""
                nd   = str(row.get("Next DueDate", row.get("Next Due Date", ""))).strip()
                if nd.lower()   in ("nan", "none"):     nd   = ""
                assets.append({
                    "id": ac, "asset_code": ac, "name": an, "asset_name": an,
                    "department": dept, "trade": dept, "category": dept, "location": loc,
                    "lastService": ls, "last_service": ls, "nextDueDate": nd, "next_due": nd,
                    "ppm_type": ppm_type, "property": "ONEWEST",
                })

        if location_filter != "all":
            assets = [a for a in assets if a.get("location", "").strip() == location_filter.strip()]

        return jsonify({"assets": assets, "total": len(assets), "property": "ONEWEST"})
    except Exception as e:
        traceback.print_exc()
        return jsonify({"assets": [], "total": 0}), 500


@ow_ppm_bp.route("/ow_api/ppm/import-excel", methods=["POST"])
@login_required
@require_property("ONEWEST")
def ow_api_ppm_import_excel():
    try:
        file = request.files.get("file")
        if not file:
            return jsonify({"status": "error", "message": "No file uploaded"}), 400
        OW_DIR.mkdir(parents=True, exist_ok=True)
        file.save(OW_ASSETS_XLSX)
        df    = pd.read_excel(OW_ASSETS_XLSX)
        count = len([_ for _, row in df.iterrows()
                     if pd.notna(row.get("Asset Code")) and str(row.get("Asset Code")).strip()])
        return jsonify({"status": "success", "message": f"Successfully synced {count} ONEWEST assets", "count": count})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


# ═════════════════════════════════════════════════════════════════════════════
# WORK ORDERS
# ═════════════════════════════════════════════════════════════════════════════

@ow_ppm_bp.route("/ow_api/ppm/dashboard/stats")
@login_required
@require_property("ONEWEST")
def ow_api_ppm_dashboard_stats():
    try:
        wo_data = {"work_orders": []}
        if OW_WORK_ORDERS_JSON.exists():
            with open(OW_WORK_ORDERS_JSON, "r", encoding="utf-8") as f:
                wo_data = json.load(f)
        work_orders  = wo_data.get("work_orders", [])
        today        = datetime.now().date()
        total_wo     = len(work_orders)
        completed_wo = len([w for w in work_orders if (w.get("status","") or "").lower() in ("completed","closed")])
        pending_wo   = total_wo - completed_wo
        overdue_wo   = 0
        for wo in work_orders:
            if (wo.get("status","") or "").lower() in ("completed","closed"):
                continue
            try:
                if datetime.strptime(wo.get("due_date","")[:10], "%Y-%m-%d").date() < today:
                    overdue_wo += 1
            except Exception:
                pass
        asset_count = 0
        for _fp, _eng in [(OW_ASSETS_XLS, "xlrd"), (OW_ASSETS_XLSX, "openpyxl")]:
            if not _fp.exists(): continue
            try:
                _xl = pd.ExcelFile(str(_fp), engine=_eng)
                for _sh in _xl.sheet_names:
                    _df = pd.read_excel(str(_fp), sheet_name=_sh, engine=_eng)
                    for _col in ("Equipment No.", "Asset Code"):
                        if _col in _df.columns:
                            asset_count += int(_df[_col].dropna().astype(str).str.strip().str.len().gt(0).sum())
                            break
                break
            except Exception:
                pass
        compliance = round((completed_wo / total_wo * 100), 1) if total_wo else 0.0
        return jsonify({"total_assets": asset_count, "pending_ppm": pending_wo,
                        "completed_ppm": completed_wo, "ppm_overdue": overdue_wo,
                        "compliance_rate": compliance, "property": "ONEWEST"})
    except Exception as e:
        return jsonify({"total_assets": 0,"pending_ppm": 0,"completed_ppm": 0,
                        "ppm_overdue": 0,"compliance_rate": 0}), 500


@ow_ppm_bp.route("/ow_api/ppm/workorders")
@login_required
@require_property("ONEWEST")
def ow_api_ppm_workorders():
    try:
        if not OW_WORK_ORDERS_JSON.exists():
            return jsonify({"work_orders": [], "total": 0, "property": "ONEWEST"})
        with open(OW_WORK_ORDERS_JSON, "r", encoding="utf-8") as f:
            data = json.load(f)
        work_orders   = data.get("work_orders", [])
        status_filter = request.args.get("status", "all").lower()
        if status_filter != "all":
            work_orders = [w for w in work_orders if (w.get("status","") or "").lower() == status_filter]
        _tod = datetime.now().date()
        formatted = []
        for wo in work_orders:
            _rst = (wo.get("status","") or "open").lower()
            _est = _rst
            if _rst not in ("completed","closed"):
                try:
                    if datetime.strptime(wo.get("due_date","")[:10],"%Y-%m-%d").date() < _tod:
                        _est = "overdue"
                except Exception:
                    pass
            formatted.append({
                "WO ID": wo.get("work_order_id","N/A"), "Asset": wo.get("asset_name","Unknown Asset"),
                "Location": wo.get("location","Unknown"), "Due Date": wo.get("due_date","N/A"),
                "Priority": wo.get("priority","Medium"), "Status": _est, "status": _est,
                "raw_status": _rst, "created_at": wo.get("created_at", datetime.now().isoformat()),
                "assigned_to": wo.get("assigned_to",""), "supervisor": wo.get("supervisor",""),
                "checklist": wo.get("checklist",[]), "images": wo.get("images",[]),
                "asset_id": wo.get("asset_id",""), "work_order_id": wo.get("work_order_id",""),
                "asset_name": wo.get("asset_name",""), "location": wo.get("location",""),
                "due_date": wo.get("due_date",""), "priority": wo.get("priority","Medium"),
                "ppm_type": wo.get("ppm_type","inhouse"), "closed_by": wo.get("closed_by",""),
                "closed_at": wo.get("closed_at",""), "technician": wo.get("technician",""),
                "approval_notes": wo.get("approval_notes",""), "property": "ONEWEST",
            })
        return jsonify({"work_orders": formatted, "total": len(formatted),
                        "property": "ONEWEST", "success": True})
    except Exception as e:
        return jsonify({"work_orders":[],"total":0,"success":False,"error":str(e)}), 500


@ow_ppm_bp.route("/ow_api/workorders/by-date")
@login_required
@require_property("ONEWEST")
def ow_api_workorders_by_date():
    try:
        date_str = request.args.get("date", datetime.now().strftime("%Y-%m-%d"))
        if not OW_WORK_ORDERS_JSON.exists():
            return jsonify({"work_orders": [], "date": date_str, "property": "ONEWEST"})
        with open(OW_WORK_ORDERS_JSON, "r", encoding="utf-8") as f:
            data = json.load(f)
        filtered = [w for w in data.get("work_orders",[]) if w.get("due_date","")[:10] == date_str]
        return jsonify({"work_orders": filtered, "date": date_str, "total": len(filtered), "property": "ONEWEST"})
    except Exception as e:
        return jsonify({"work_orders":[], "error":str(e)}), 500


@ow_ppm_bp.route("/ow_api/workflow/create", methods=["POST"])
@login_required
@require_property("ONEWEST")
def ow_api_workflow_create():
    try:
        data       = request.get_json()
        asset_id   = data.get("assetId", "")
        asset_name = data.get("assetName", "Unknown Asset")
        location   = data.get("location", "Unknown")
        due_date   = data.get("dueDate", "")
        asset_type = data.get("assetType", "default")

        try:
            if "/" in due_date:
                p = due_date.split("/")
                m, d, y = int(p[0]), int(p[1]), int(p[2])
                if y < 100: y += 2000
                due_date = f"{y}-{m:02d}-{d:02d}"
            elif "-" in due_date and len(due_date) == 10:
                pass
            else:
                due_date = datetime.now().strftime("%Y-%m-%d")
        except Exception:
            due_date = datetime.now().strftime("%Y-%m-%d")

        if asset_id and OW_ASSETS_XLSX.exists():
            try:
                df  = pd.read_excel(OW_ASSETS_XLSX)
                row = df[df["Asset Code"] == asset_id]
                if not row.empty:
                    asset_name = str(row.iloc[0]["Asset Name"]).strip() or asset_name
                    location   = str(row.iloc[0]["Location"]).strip()  or location
            except Exception:
                pass

        name_lower = asset_name.lower()
        priority   = "High" if any(k in name_lower for k in ("fire","dg","generator","transformer","hv","elevator")) else "Medium"

        wo_data = {"work_orders": [], "last_updated": ""}
        if OW_WORK_ORDERS_JSON.exists():
            with open(OW_WORK_ORDERS_JSON, "r", encoding="utf-8") as f:
                wo_data = json.load(f)

        existing_wos = wo_data.get("work_orders", [])
        today        = datetime.now()
        wo_id        = f"OW-PPM-{today.strftime('%Y-%m')}-{str(len(existing_wos)+1).zfill(4)}"

        checklists = {
            "dg":       ["Check fuel level","Inspect battery","Verify coolant","Check oil","Test ATS","Inspect exhaust"],
            "elevator": ["Inspect door operation","Check emergency stop","Verify leveling","Inspect machine room","Test emergency lighting"],
            "chiller":  ["Check refrigerant pressure","Inspect condenser","Verify compressor oil","Check connections","Inspect for leaks"],
            "fire":     ["Test alarm panel","Check sprinklers","Verify extinguishers","Test smoke detectors","Check hydrant pressure"],
            "default":  ["Visual inspection","Check for noise/vibration","Verify safety guards","Inspect for leaks","Test emergency stop","Verify control panel"],
        }
        cl_items  = checklists.get(asset_type, checklists["default"])
        checklist = [{"id": f"{asset_type}_{i+1}", "text": item, "required": i < 4, "completed": False, "comments": ""}
                     for i, item in enumerate(cl_items)]

        new_wo = {
            "work_order_id": wo_id, "asset_id": asset_id, "asset_name": asset_name,
            "location": location, "due_date": due_date, "priority": priority,
            "status": "open", "property": "ONEWEST", "created_at": today.isoformat(),
            "assigned_to": "", "supervisor": "", "checklist": checklist,
            "images": [], "technician_notes": "", "approval_notes": "",
        }
        existing_wos.append(new_wo)
        wo_data["work_orders"]  = existing_wos
        wo_data["last_updated"] = today.isoformat()
        with open(OW_WORK_ORDERS_JSON, "w", encoding="utf-8") as f:
            json.dump(wo_data, f, indent=2)
        return jsonify({"success": True, "work_order_id": wo_id, "message": "ONEWEST work order created"})
    except Exception as e:
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500


@ow_ppm_bp.route("/ow_api/workflow/close", methods=["POST"])
@login_required
@require_property("ONEWEST")
def ow_api_workflow_close():
    try:
        data           = request.get_json()
        wo_id          = data.get("workOrderId", "")
        approval_notes = data.get("approvalNotes", "")
        supervisor_ok  = data.get("supervisorApproval", False)
        technician     = data.get("technician", "")
        images         = data.get("images", [])
        checklist      = data.get("checklist", [])

        if not supervisor_ok:
            return jsonify({"success": False, "error": "Supervisor approval required"}), 400
        if not OW_WORK_ORDERS_JSON.exists():
            return jsonify({"success": False, "error": "Work orders file not found"}), 404

        with open(OW_WORK_ORDERS_JSON, "r", encoding="utf-8") as f:
            wo_data = json.load(f)

        updated = False
        for wo in wo_data.get("work_orders", []):
            if wo.get("work_order_id") == wo_id:
                wo.update({"status": "completed", "closed_at": datetime.now().isoformat(),
                            "approval_notes": approval_notes, "technician": technician,
                            "images": images, "checklist": checklist,
                            "closed_by": session.get("user", "unknown")})
                updated = True
                break

        if not updated:
            return jsonify({"success": False, "error": "Work order not found"}), 404

        wo_data["last_updated"] = datetime.now().isoformat()
        with open(OW_WORK_ORDERS_JSON, "w", encoding="utf-8") as f:
            json.dump(wo_data, f, indent=2)
        return jsonify({"success": True, "message": f"Work order {wo_id} closed successfully"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@ow_ppm_bp.route("/ow_api/ppm/workorders/export")
@login_required
@require_property("ONEWEST")
def ow_api_ppm_workorders_export():
    try:
        wo_data = {"work_orders": []}
        if OW_WORK_ORDERS_JSON.exists():
            with open(OW_WORK_ORDERS_JSON, "r", encoding="utf-8") as f:
                wo_data = json.load(f)
        work_orders = wo_data.get("work_orders", [])
        if not work_orders:
            return jsonify({"error": "No work orders to export"}), 404
        rows = [{"WO ID": w.get("work_order_id",""), "Asset": w.get("asset_name",""),
                 "Location": w.get("location",""), "Due Date": w.get("due_date",""),
                 "Priority": w.get("priority",""), "Status": w.get("status",""),
                 "Assigned To": w.get("assigned_to",""), "Supervisor": w.get("supervisor",""),
                 "Created At": w.get("created_at",""), "Closed At": w.get("closed_at",""),
                 "Approval Notes": w.get("approval_notes",""), "Property": "ONEWEST"} for w in work_orders]
        df  = pd.DataFrame(rows)
        out = io.BytesIO()
        with pd.ExcelWriter(out, engine="openpyxl") as writer:
            df.to_excel(writer, index=False, sheet_name="ONEWEST Work Orders")
        out.seek(0)
        filename = f"ONEWEST_WorkOrders_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        return send_file(out, mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                         as_attachment=True, download_name=filename)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@ow_ppm_bp.route("/ow_api/ppm/calendar")
@login_required
@require_property("ONEWEST")
def ow_api_ppm_calendar():
    try:
        year  = int(request.args.get("year",  datetime.now().year))
        month = int(request.args.get("month", datetime.now().month))
        if not OW_ASSETS_XLSX.exists():
            return jsonify({"calendar": {}, "property": "ONEWEST"})
        df = pd.read_excel(OW_ASSETS_XLSX, engine="openpyxl")
        calendar_data = {}
        for _, row in df.iterrows():
            ac  = str(row.get("Asset Code","")).strip()
            if not ac or ac.lower() in ("nan","none",""): continue
            nd  = str(row.get("nextDueDate","")).strip()
            if not nd or nd.lower() in ("nan","none",""): continue
            try:
                from dateutil.parser import parse as _parse
                due_dt = _parse(nd)
                if due_dt.year == year and due_dt.month == month:
                    dk = due_dt.strftime("%Y-%m-%d")
                    calendar_data.setdefault(dk, []).append({
                        "id": ac, "name": str(row.get("Asset Name","")).strip(),
                        "location": str(row.get("Location","")).strip(),
                        "lastService": str(row.get("Last Service","")).strip(),
                    })
            except Exception:
                pass
        return jsonify({"calendar": calendar_data, "year": year, "month": month, "property": "ONEWEST"})
    except Exception as e:
        return jsonify({"calendar": {}, "error": str(e)}), 500


# ═════════════════════════════════════════════════════════════════════════════
# AMC CONTRACTS
# ═════════════════════════════════════════════════════════════════════════════

@ow_ppm_bp.route("/ow_api/amc/contracts")
@login_required
@require_property("ONEWEST")
def ow_api_amc_contracts():
    try:
        if not OW_AMC_JSON.exists():
            return jsonify({"contracts": [], "total": 0, "property": "ONEWEST"})
        with open(OW_AMC_JSON, "r", encoding="utf-8") as f:
            data = json.load(f)
        contracts = data.get("contracts", [])
        sf = request.args.get("status", "all").lower()
        if sf != "all":
            contracts = [c for c in contracts if (c.get("status","") or "").lower() == sf]
        return jsonify({"contracts": contracts, "total": len(contracts), "property": "ONEWEST", "success": True})
    except Exception as e:
        return jsonify({"contracts": [], "error": str(e)}), 500


@ow_ppm_bp.route("/ow_api/amc/contracts/export")
@login_required
@require_property("ONEWEST")
def ow_api_amc_contracts_export():
    try:
        contracts = []
        if OW_AMC_JSON.exists():
            with open(OW_AMC_JSON, "r", encoding="utf-8") as f:
                contracts = json.load(f).get("contracts", [])
        if not contracts:
            return jsonify({"error": "No contracts to export"}), 404
        df  = pd.DataFrame(contracts)
        out = io.BytesIO()
        with pd.ExcelWriter(out, engine="openpyxl") as writer:
            df.to_excel(writer, index=False, sheet_name="ONEWEST AMC")
        out.seek(0)
        filename = f"ONEWEST_AMC_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        return send_file(out, mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                         as_attachment=True, download_name=filename)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@ow_ppm_bp.route("/ow_api/amc/update", methods=["POST"])
@login_required
@require_property("ONEWEST")
def ow_api_amc_update():
    try:
        data        = request.get_json()
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
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# ═════════════════════════════════════════════════════════════════════════════
# INVENTORY
# ═════════════════════════════════════════════════════════════════════════════

@ow_ppm_bp.route("/ow_inventory_dashboard")
def ow_inventory_dashboard():
    return render_template("ow_inventory_dashboard.html")


@ow_ppm_bp.route("/ow_api/inventory/items")
@login_required
@require_property("ONEWEST")
def ow_get_inventory_items():
    try:
        if not OW_INVENTORY_XLSX.exists():
            return jsonify({"success": False, "items": [], "total": 0})
        df    = pd.read_excel(OW_INVENTORY_XLSX, engine="openpyxl")
        items = []
        for _, row in df.iterrows():
            code = str(row.get("Item_Code","")).strip()
            if not code or code.lower() in ("nan","none",""): continue
            cur = float(row.get("Current_Stock",0))   if pd.notna(row.get("Current_Stock"))   else 0
            mn  = float(row.get("Min_Stock_Level",0)) if pd.notna(row.get("Min_Stock_Level")) else 0
            status = "Out of Stock" if cur <= 0 else ("Low Stock" if cur < mn else "In Stock")
            color  = "danger"       if cur <= 0 else ("warning"   if cur < mn else "success")
            items.append({"item_code": code, "item_name": str(row.get("Item_Name","Unknown")).strip(),
                           "department": str(row.get("Department","General")).strip(),
                           "unit": str(row.get("Unit","Nos")).strip(),
                           "current_stock": cur, "min_stock_level": mn,
                           "status": status, "status_color": color})
        df_filter = request.args.get("department","all").strip()
        if df_filter != "all":
            items = [i for i in items if i["department"].lower() == df_filter.lower()]
        return jsonify({"success": True, "items": items, "total": len(items), "property": "ONEWEST"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e), "items": []}), 500


@ow_ppm_bp.route("/ow_api/inventory/stats")
@login_required
@require_property("ONEWEST")
def ow_get_inventory_stats():
    try:
        if not OW_INVENTORY_XLSX.exists():
            return jsonify({"total_items":0,"in_stock":0,"low_stock":0,"out_of_stock":0})
        df    = pd.read_excel(OW_INVENTORY_XLSX)
        total = in_s = low = out = 0
        depts = set()
        for _, row in df.iterrows():
            code = str(row.get("Item_Code","")).strip()
            if not code or code.lower() in ("nan","none",""): continue
            total += 1
            depts.add(str(row.get("Department","General")).strip())
            cur = float(row.get("Current_Stock",0)) if pd.notna(row.get("Current_Stock")) else 0
            mn  = float(row.get("Min_Stock_Level",0)) if pd.notna(row.get("Min_Stock_Level")) else 0
            if cur <= 0: out += 1
            elif cur < mn: low += 1
            else: in_s += 1
        return jsonify({"total_items":total,"in_stock":in_s,"low_stock":low,"out_of_stock":out,
                        "departments":list(depts),"property":"ONEWEST"})
    except Exception as e:
        return jsonify({"total_items":0,"in_stock":0,"low_stock":0,"out_of_stock":0}), 500


@ow_ppm_bp.route("/ow_api/inventory/movement", methods=["POST"])
@login_required
@require_property("ONEWEST")
def ow_update_stock_movement():
    try:
        data          = request.get_json()
        item_code     = data.get("item_code")
        movement_type = data.get("movement_type")
        quantity      = int(data.get("quantity",0))
        if not item_code or not movement_type or quantity <= 0:
            return jsonify({"success":False,"error":"Invalid data"}), 400
        if not OW_INVENTORY_XLSX.exists():
            return jsonify({"success":False,"error":"Inventory file not found"}), 404
        df   = pd.read_excel(OW_INVENTORY_XLSX)
        mask = df["Item_Code"] == item_code
        if not mask.any():
            return jsonify({"success":False,"error":"Item not found"}), 404
        cur = float(df.loc[mask,"Current_Stock"].iloc[0]) if pd.notna(df.loc[mask,"Current_Stock"].iloc[0]) else 0
        if movement_type.upper() == "IN":
            new_stock = cur + quantity
            df.loc[mask,"Stock_In"] = (df.loc[mask,"Stock_In"].iloc[0] if pd.notna(df.loc[mask,"Stock_In"].iloc[0]) else 0) + quantity
        elif movement_type.upper() == "OUT":
            if quantity > cur:
                return jsonify({"success":False,"error":"Insufficient stock"}), 400
            new_stock = cur - quantity
            df.loc[mask,"Stock_Out"] = (df.loc[mask,"Stock_Out"].iloc[0] if pd.notna(df.loc[mask,"Stock_Out"].iloc[0]) else 0) + quantity
        else:
            return jsonify({"success":False,"error":"Invalid movement type"}), 400
        df.loc[mask,"Current_Stock"] = new_stock
        df.loc[mask,"Last_Updated"]  = datetime.now().strftime("%Y-%m-%d")
        import time
        for attempt in range(3):
            try:
                df.to_excel(OW_INVENTORY_XLSX, index=False)
                break
            except PermissionError:
                if attempt == 2:
                    return jsonify({"success":False,"error":"File locked"}), 500
                time.sleep(1)
        return jsonify({"success":True,"new_stock":new_stock})
    except Exception as e:
        return jsonify({"success":False,"error":str(e)}), 500


@ow_ppm_bp.route("/ow_api/inventory/alerts")
@login_required
@require_property("ONEWEST")
def ow_get_inventory_alerts():
    try:
        if not OW_INVENTORY_XLSX.exists():
            return jsonify({"alerts":[],"total":0})
        df     = pd.read_excel(OW_INVENTORY_XLSX)
        alerts = []
        for _, row in df.iterrows():
            code = str(row.get("Item_Code","")).strip()
            if not code or code.lower() in ("nan","none",""): continue
            cur = float(row.get("Current_Stock",0)) if pd.notna(row.get("Current_Stock")) else 0
            mn  = float(row.get("Min_Stock_Level",0)) if pd.notna(row.get("Min_Stock_Level")) else 0
            if cur < mn:
                alerts.append({"item_code":code,"item_name":str(row.get("Item_Name","Unknown")).strip(),
                                "department":str(row.get("Department","General")).strip(),
                                "current_stock":cur,"min_stock_level":mn,"shortage":mn-cur,
                                "severity":"critical" if cur<=0 else "warning"})
        return jsonify({"alerts":alerts,"total":len(alerts),"property":"ONEWEST"})
    except Exception as e:
        return jsonify({"alerts":[],"total":0}), 500


@ow_ppm_bp.route("/ow_api/inventory/export")
@login_required
@require_property("ONEWEST")
def ow_export_inventory():
    try:
        if not OW_INVENTORY_XLSX.exists():
            return jsonify({"error":"No data"}), 404
        filename = f"ONEWEST_Inventory_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        return send_file(OW_INVENTORY_XLSX,
                         mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                         as_attachment=True, download_name=filename)
    except Exception as e:
        return jsonify({"error":str(e)}), 500


# ═════════════════════════════════════════════════════════════════════════════
# TECHNICIANS & SUPERVISORS
# ═════════════════════════════════════════════════════════════════════════════

@ow_ppm_bp.route("/ow_api/technicians")
@login_required
def ow_api_technicians():
    if "ONEWEST" in session.get("properties",[]) or session.get("role") == "admin":
        session["active_property"] = "ONEWEST"
    try:
        OW_TECHNICIANS_JSON.parent.mkdir(parents=True, exist_ok=True)
        if not OW_TECHNICIANS_JSON.exists():
            with open(OW_TECHNICIANS_JSON, "w", encoding="utf-8") as f:
                json.dump(_OW_TECHS, f, indent=2)
            return jsonify(_OW_TECHS)
        with open(OW_TECHNICIANS_JSON, "r", encoding="utf-8") as f:
            raw = f.read().strip()
        if not raw: return jsonify({"technicians":[]})
        raw  = _re.sub(r",\s*([\]\}])", r"\1", raw)
        data = json.loads(raw)
        if isinstance(data, list): data = {"technicians": data}
        return jsonify({"technicians": data.get("technicians",[])})
    except Exception as e:
        return jsonify({"technicians":[],"error":str(e)}), 200


@ow_ppm_bp.route("/ow_api/debug/technicians")
@login_required
def ow_api_technicians_debug():
    try:
        result = {"session_user": session.get("user"),
                  "session_active_property": session.get("active_property"),
                  "session_role": session.get("role"),
                  "session_properties": session.get("properties",[]),
                  "OW_TECHNICIANS_JSON": str(OW_TECHNICIANS_JSON),
                  "file_exists": OW_TECHNICIANS_JSON.exists()}
        if OW_TECHNICIANS_JSON.exists():
            with open(OW_TECHNICIANS_JSON, "r", encoding="utf-8") as f:
                result["file_contents"] = json.load(f)
        return jsonify(result)
    except Exception as e:
        return jsonify({"error":str(e)}), 500


@ow_ppm_bp.route("/ow_api/supervisors")
@login_required
def ow_api_supervisors():
    if "ONEWEST" in session.get("properties",[]) or session.get("role") == "admin":
        session["active_property"] = "ONEWEST"
    try:
        OW_SUPERVISORS_JSON.parent.mkdir(parents=True, exist_ok=True)
        if not OW_SUPERVISORS_JSON.exists():
            with open(OW_SUPERVISORS_JSON, "w", encoding="utf-8") as f:
                json.dump(_OW_SUPS, f, indent=2)
            return jsonify(_OW_SUPS)
        with open(OW_SUPERVISORS_JSON, "r", encoding="utf-8") as f:
            raw = f.read().strip()
        if not raw: return jsonify({"supervisors":[]})
        raw  = _re.sub(r",\s*([\]\}])", r"\1", raw)
        data = json.loads(raw)
        if isinstance(data, list): data = {"supervisors": data}
        return jsonify({"supervisors": data.get("supervisors",[])})
    except Exception as e:
        return jsonify({"supervisors":[],"error":str(e)}), 200


# ═════════════════════════════════════════════════════════════════════════════
# STATIC UPLOADS SERVE
# ═════════════════════════════════════════════════════════════════════════════

@ow_ppm_bp.route("/uploads/OW/ppm/<filename>")
@login_required
def serve_ow_ppm_upload(filename):
    return send_from_directory(OW_PPM_WO_UPLOADS, filename)


# ═════════════════════════════════════════════════════════════════════════════
# DAILY MAIL + SCHEDULER
# ═════════════════════════════════════════════════════════════════════════════

def ow_send_daily_ppm_mail():
    try:
        today_str   = datetime.now().strftime("%Y-%m-%d")
        work_orders = []
        if OW_WORK_ORDERS_JSON.exists():
            with open(OW_WORK_ORDERS_JSON, "r", encoding="utf-8") as f:
                work_orders = json.load(f).get("work_orders", [])
        today_wos   = [w for w in work_orders
                       if w.get("due_date","")[:10] == today_str
                       and (w.get("status","") or "").lower() not in ("completed","closed")]
        today_date  = datetime.now().date()
        pending_wos = [w for w in work_orders
                       if (w.get("status","") or "").lower() not in ("completed","closed")
                       and _is_overdue(w, today_date)]

        html_body = f"""<div style="font-family:sans-serif;background:#020617;color:#e2e8f0;padding:32px;max-width:800px;margin:0 auto;">
            <h1 style="font-family:monospace;color:#f97316;">ONEWEST</h1>
            <p>Daily PPM Maintenance Report — {datetime.now().strftime('%A, %d %B %Y')}</p>
            <p>Today's Work Orders: <strong>{len(today_wos)}</strong> | Pending/Overdue: <strong>{len(pending_wos)}</strong></p>
        </div>"""

        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"ONEWEST Daily PPM — {datetime.now().strftime('%d %b %Y')} — {len(today_wos)} Today | {len(pending_wos)} Pending"
        msg["From"]    = formataddr(("ONEWEST MMS", SENDER_EMAIL))
        msg["To"]      = ", ".join(OW_EMAIL_RECEIVERS)
        msg.attach(MIMEText(html_body, "html"))
        _smtp_send(msg, OW_EMAIL_RECEIVERS, caller="OW-PPM-daily")
        return {"success": True, "wo_count": len(today_wos), "pending_count": len(pending_wos)}
    except Exception as e:
        print(f"❌ OW daily mail error: {e}")
        return {"success": False, "error": str(e)}


def _is_overdue(wo, today_date):
    try:
        return datetime.strptime(wo.get("due_date","")[:10], "%Y-%m-%d").date() < today_date
    except Exception:
        return False


@ow_ppm_bp.route("/ow_api/trigger-daily-mail", methods=["POST"])
@login_required
@require_property("ONEWEST")
def ow_api_trigger_daily_mail():
    return jsonify(ow_send_daily_ppm_mail())


def _setup_ow_ppm_scheduler():
    try:
        from apscheduler.schedulers.background import BackgroundScheduler
        scheduler = BackgroundScheduler()
        scheduler.add_job(func=ow_send_daily_ppm_mail, trigger="cron",
                          hour=8, minute=0, timezone="Asia/Kolkata", id="ow_daily_ppm_mail")
        scheduler.start()
        print("✅ ONEWEST: Daily PPM mail scheduler started at 8:00 AM IST")
        return scheduler
    except Exception as e:
        print(f"⚠️  ONEWEST scheduler error: {e}")
        return None

# Start scheduler on import
_ow_scheduler = _setup_ow_ppm_scheduler()
