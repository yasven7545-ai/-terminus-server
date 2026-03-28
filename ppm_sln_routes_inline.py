"""
PPM SLN ROUTES (INLINE)
SLN Terminus PPM work orders, assets, email trigger, daily scheduler,
work order close/create, PPM checklist upload, AMC tracker, PPM dashboard stats.
"""
from flask import Blueprint, request, jsonify, session, send_file
from pathlib import Path
from datetime import datetime, timedelta
import json
import traceback
import pandas as pd

from decorators import login_required
from config import BASE_DIR, WO_JSON, ASSETS_XLSX, PPM_DATA_FILE, PPM_CHECKLIST_DIR, _smtp_send, SENDER_EMAIL, RECEIVER_EMAILS
from werkzeug.utils import secure_filename
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr

ppm_sln_bp = Blueprint("ppm_sln", __name__)


# ─────────────────────────────────────────────────────────────────────────────
# HELPER FUNCTIONS
# ─────────────────────────────────────────────────────────────────────────────

def get_asset_details(asset_id):
    """Safely retrieve asset details from Excel with proper column handling."""
    _ASSETS = Path(__file__).parent / "static" / "data" / "Assets.xlsx"
    if not _ASSETS.exists():
        return {"name": f"Asset_{asset_id}", "location": "Unknown Location",
                "priority": "Medium", "frequency": "Monthly"}
    try:
        df = pd.read_excel(_ASSETS)
        df.columns = df.columns.str.strip()
        asset_row = df[df["Asset Code"] == asset_id]
        if asset_row.empty:
            return {"name": f"Asset_{asset_id}", "location": "Unknown Location",
                    "priority": "Medium", "frequency": "Monthly"}
        asset_name = str(asset_row.iloc[0]["Asset Name"]).strip()
        location   = str(asset_row.iloc[0]["Location"]).strip()
        asset_lower = asset_name.lower()
        priority = "High" if any(k in asset_lower for k in ["fire", "dg", "transformer", "elevator", "escalator"]) else "Medium"
        frequency  = "Monthly"
        for col in ["Frequency", "frequency"]:
            if col in asset_row.columns:
                val = str(asset_row.iloc[0][col]).strip().lower()
                if val in ("monthly", "quarterly", "yearly"):
                    frequency = val
                    break
        return {"name": asset_name, "location": location, "priority": priority, "frequency": frequency}
    except Exception as e:
        print(f"⚠️ Error loading asset {asset_id}: {str(e)}")
        return {"name": f"Asset_{asset_id}", "location": "Unknown Location",
                "priority": "Medium", "frequency": "Monthly"}


def get_today_wos():
    """Extracts work orders with due_date matching today."""
    if not WO_JSON.exists():
        return []
    try:
        with open(WO_JSON, "r", encoding="utf-8") as f:
            data = json.load(f)
        today_str = datetime.now().date().strftime("%Y-%m-%d")
        return [wo for wo in data.get("work_orders", [])
                if wo.get("due_date", "").strip() == today_str
                and wo.get("status", "").strip().lower() in ("open", "in-progress", "overdue")]
    except Exception as e:
        print(f"❌ Error reading work orders: {str(e)}")
        return []


def calculate_next_due_date(last_service_date, frequency="monthly"):
    """Calculates next due date based on maintenance frequency."""
    if not last_service_date:
        return None
    try:
        parts = last_service_date.split("/")
        if len(parts) == 3:
            last_date = datetime(int(parts[2]), int(parts[0]), int(parts[1]))
        else:
            return None
    except Exception:
        return None

    if frequency.lower() == "monthly":
        nm, ny = last_date.month + 1, last_date.year
        if nm > 12: nm, ny = 1, ny + 1
        try: return datetime(ny, nm, last_date.day).strftime("%Y-%m-%d")
        except ValueError: return (datetime(ny, nm, 1) - timedelta(days=1)).strftime("%Y-%m-%d")
    elif frequency.lower() == "quarterly":
        nm, ny = last_date.month + 3, last_date.year
        if nm > 12: nm, ny = nm - 12, ny + 1
        try: return datetime(ny, nm, last_date.day).strftime("%Y-%m-%d")
        except ValueError: return (datetime(ny, nm, 1) - timedelta(days=1)).strftime("%Y-%m-%d")
    elif frequency.lower() == "yearly":
        try: return datetime(last_date.year + 1, last_date.month, last_date.day).strftime("%Y-%m-%d")
        except ValueError: return (datetime(last_date.year + 1, last_date.month, 1) - timedelta(days=1)).strftime("%Y-%m-%d")
    return None


# ─────────────────────────────────────────────────────────────────────────────
# PPM ASSETS API
# ─────────────────────────────────────────────────────────────────────────────

@ppm_sln_bp.route("/api/ppm/assets")
def get_ppm_assets():
    """API: Get all PPM assets directly from Assets.xlsx."""
    try:
        location_filter = request.args.get("location", "all")
        _xl = BASE_DIR / "static" / "data" / "Assets.xlsx"
        if not _xl.exists():
            return jsonify({"assets": [], "total": 0})
        try:
            df = pd.read_excel(_xl, engine="openpyxl")
        except Exception:
            df = pd.read_excel(_xl, engine="xlrd")
        assets = []
        for _, row in df.iterrows():
            code = str(row.get("Asset Code", "")).strip()
            if not code or code.lower() in ("nan", "none", ""):
                continue
            asset = {
                "id":          code,
                "name":        str(row.get("Asset Name", "Unknown Asset")).strip(),
                "category":    str(row.get("In-House/Vendor", "General")).strip(),
                "location":    str(row.get("Location", "Unknown Location")).strip(),
                "lastService": str(row.get("Last Service", "")).strip(),
                "nextDueDate": str(row.get("nextDueDate", "")).strip(),
                "colorCode":   "Green",
            }
            assets.append(asset)
        if location_filter not in ("all", ""):
            assets = [a for a in assets if a["location"] == location_filter.strip()]
        return jsonify({"assets": assets, "total": len(assets)})
    except Exception as e:
        traceback.print_exc()
        return jsonify({"assets": [], "total": 0})


# ─────────────────────────────────────────────────────────────────────────────
# PPM WORK ORDERS API
# ─────────────────────────────────────────────────────────────────────────────

@ppm_sln_bp.route("/api/ppm/workorders")
def get_ppm_workorders():
    """API: Get ALL saved work orders from work_orders.json."""
    try:
        if not WO_JSON.exists():
            return jsonify({"success": True, "work_orders": [], "total": 0})
        with open(WO_JSON, "r", encoding="utf-8") as f:
            data = json.load(f)
        cleaned = []
        for wo in data.get("work_orders", []):
            cleaned.append({k.strip(): (v.strip() if isinstance(v, str) else v)
                             for k, v in wo.items()})
        sf = request.args.get("status",   "all").lower().strip()
        pf = request.args.get("priority", "all").lower().strip()
        if sf != "all": cleaned = [w for w in cleaned if w.get("status","").lower() == sf]
        if pf != "all": cleaned = [w for w in cleaned if w.get("priority","").lower() == pf]
        formatted = [{
            "WO ID":      wo.get("work_order_id", "N/A"),
            "Asset":      wo.get("asset_name",    "Unknown Asset"),
            "Location":   wo.get("location",      "Unknown Location"),
            "Due Date":   wo.get("due_date",      "N/A"),
            "Priority":   wo.get("priority",      "Medium"),
            "Status":     wo.get("status",        "open"),
            "created_at": wo.get("created_at",    datetime.now().isoformat()),
        } for wo in cleaned]
        return jsonify({"success": True, "work_orders": formatted, "total": len(formatted)})
    except Exception as e:
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e), "work_orders": [], "total": 0}), 500


# ─────────────────────────────────────────────────────────────────────────────
# CREATE WORK ORDER
# ─────────────────────────────────────────────────────────────────────────────

@ppm_sln_bp.route("/api/workflow/create", methods=["POST"])
def create_work_order():
    """API: Create work order."""
    try:
        data     = request.get_json()
        asset_id = data.get("assetId")
        due_date = data.get("dueDate")
        today    = datetime.now().date()

        existing_wos = []
        if WO_JSON.exists():
            with open(WO_JSON, "r") as f:
                existing_wos = json.load(f).get("work_orders", [])
        wo_id    = f"WO-PPM-{today.strftime('%Y-%m')}-{str(len(existing_wos)+1).zfill(4)}"
        details  = get_asset_details(asset_id)

        # Normalize due_date
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

        new_wo = {
            "work_order_id": wo_id,
            "asset_id":      asset_id,
            "asset_name":    details["name"],
            "location":      details["location"],
            "due_date":      due_date,
            "priority":      details["priority"],
            "status":        "open",
            "created_at":    datetime.now().isoformat(),
        }
        existing_wos.append(new_wo)
        with open(WO_JSON, "w") as f:
            json.dump({"work_orders": existing_wos,
                       "last_updated": datetime.now().isoformat(),
                       "total_count": len(existing_wos)}, f, indent=2)
        print(f"✅ Work Order Created: {wo_id} for {asset_id}")
        return jsonify({"success": True, "work_order_id": wo_id, "message": "Work order created successfully!"})
    except Exception as e:
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500


# ─────────────────────────────────────────────────────────────────────────────
# CLOSE WORK ORDER
# ─────────────────────────────────────────────────────────────────────────────

@ppm_sln_bp.route("/api/workflow/close", methods=["POST"])
def close_work_order():
    """API: Close work order with supervisor approval."""
    try:
        data           = request.get_json()
        wo_id          = data.get("workOrderId")
        approval_notes = data.get("approvalNotes", "")
        if not WO_JSON.exists():
            return jsonify({"success": False, "error": "Work orders file not found"}), 404
        with open(WO_JSON, "r") as f:
            work_data = json.load(f)
        work_orders = work_data.get("work_orders", [])
        updated = False
        for wo in work_orders:
            if wo.get("work_order_id") == wo_id or wo.get("WO ID") == wo_id:
                wo["status"] = wo["Status"] = "completed"
                wo["closed_at"]           = datetime.now().isoformat()
                wo["closed_by"]           = session.get("user", "Supervisor")
                wo["approval_notes"]      = approval_notes
                wo["supervisor_approval"] = True
                updated = True
                break
        if not updated:
            return jsonify({"success": False, "error": "Work order not found"}), 404
        with open(WO_JSON, "w") as f:
            json.dump({"work_orders": work_orders,
                       "last_updated": datetime.now().isoformat(),
                       "total_count": len(work_orders)}, f, indent=2)
        return jsonify({"success": True, "message": "Work order closed successfully"})
    except Exception as e:
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500


# ─────────────────────────────────────────────────────────────────────────────
# PPM DASHBOARD STATS
# ─────────────────────────────────────────────────────────────────────────────

@ppm_sln_bp.route("/api/ppm/dashboard/stats")
def get_ppm_dashboard_stats():
    """PPM dashboard stats endpoint."""
    try:
        if not WO_JSON.exists():
            return jsonify({"total_assets": 438, "pending_ppm": 0,
                            "completed_ppm": 0, "ppm_due_today": 0,
                            "ppm_overdue": 0, "compliance_rate": 0.0})
        with open(WO_JSON, "r") as f:
            data = json.load(f)
        work_orders = data.get("work_orders", [])
        today = datetime.now().date()
        overdue = due_today = pending = 0
        for wo in work_orders:
            due_str = wo.get("due_date", "")
            if not due_str: continue
            date_obj = None
            for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y"):
                try: date_obj = datetime.strptime(due_str, fmt).date(); break
                except Exception: continue
            if not date_obj: continue
            if date_obj < today:   overdue  += 1
            elif date_obj == today: due_today += 1; pending += 1
        total = len(work_orders)
        compliance = round(((total - overdue) / total * 100), 1) if total else 0.0
        return jsonify({"total_assets": 438, "pending_ppm": pending,
                        "completed_ppm": total - overdue - pending,
                        "ppm_due_today": due_today, "ppm_overdue": overdue,
                        "compliance_rate": compliance})
    except Exception as e:
        return jsonify({"total_assets": 438, "pending_ppm": 0, "completed_ppm": 0,
                        "ppm_due_today": 0, "ppm_overdue": 0, "compliance_rate": 0.0})


# ─────────────────────────────────────────────────────────────────────────────
# MANUAL EMAIL TRIGGER
# ─────────────────────────────────────────────────────────────────────────────

@ppm_sln_bp.route("/api/send-daily-email", methods=["POST"])
@login_required
def send_daily_email():
    """Manually trigger daily PPM summary email."""
    try:
        today_wos = get_today_wos()
        today = datetime.now().date()
        smtp_user  = SENDER_EMAIL
        recipients = RECEIVER_EMAILS

        html_content = f"""<!DOCTYPE html><html><head><meta charset="UTF-8">
<title>Daily PPM Summary</title></head><body>
<p>Daily PPM Summary — {today.strftime('%d %b %Y')}</p>
<p>{len(today_wos)} work orders due today.</p>
</body></html>"""

        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"🔧 {len(today_wos)} Maintenance Tasks - {today.strftime('%d %b %Y')}"
        msg["From"]    = formataddr(("SLN Terminus MMS", smtp_user))
        msg["To"]      = ", ".join(recipients)
        msg.attach(MIMEText(html_content, "html"))
        _smtp_send(msg, recipients, caller="MMS-manual")
        return jsonify({"success": True, "recipients": recipients,
                        "wo_count": len(today_wos), "message": "Email sent successfully"})
    except Exception as e:
        traceback.print_exc()
        return jsonify({"success": False, "error": f"Email failed: {str(e)}"}), 500


# ─────────────────────────────────────────────────────────────────────────────
# EXCEL IMPORT
# ─────────────────────────────────────────────────────────────────────────────

@ppm_sln_bp.route("/api/ppm/import-excel", methods=["POST"])
@login_required
def import_ppm_excel():
    """Import PPM assets from Excel."""
    try:
        file = request.files.get("file")
        if not file:
            return jsonify({"status": "error", "message": "No file uploaded"}), 400
        upload_path = BASE_DIR / "static" / "data" / "Assets.xlsx"
        file.save(upload_path)
        df = pd.read_excel(upload_path)
        assets = []
        for _, row in df.iterrows():
            if pd.notna(row.get("Asset Code")) and str(row.get("Asset Code")).strip():
                assets.append({
                    "id":          str(row.get("Asset Code",       "")).strip(),
                    "name":        str(row.get("Asset Name",       "")).strip(),
                    "category":    str(row.get("In-House/Vendor",  "General")).strip(),
                    "location":    str(row.get("Location",         "")).strip(),
                    "lastService": str(row.get("Last Service",     "")).strip(),
                    "nextDueDate": str(row.get("nextDueDate",      "")).strip(),
                    "colorCode":   "Red",
                })
        with open(PPM_DATA_FILE, "w") as f:
            json.dump({"assets": assets}, f, indent=2)
        return jsonify({"status": "success",
                        "message": f"Successfully imported {len(assets)} assets",
                        "count": len(assets)})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


# ─────────────────────────────────────────────────────────────────────────────
# PPM CHECKLIST UPLOAD & PARSE
# ─────────────────────────────────────────────────────────────────────────────

@ppm_sln_bp.route("/api/ppm/checklist/upload", methods=["POST"])
@login_required
def upload_ppm_checklist():
    """Parse uploaded PPM checklist Excel and return structured data."""
    try:
        if "file" not in request.files:
            return jsonify({"success": False, "error": "No file uploaded"}), 400
        file = request.files["file"]
        if not file or file.filename == "":
            return jsonify({"success": False, "error": "Empty filename"}), 400
        ext = file.filename.rsplit(".", 1)[-1].lower()
        if ext not in ("xlsx", "xls"):
            return jsonify({"success": False, "error": "Only .xlsx / .xls files accepted"}), 400
        filename  = secure_filename(file.filename)
        save_path = PPM_CHECKLIST_DIR / filename
        file.save(save_path)

        df        = pd.read_excel(save_path, sheet_name=0, header=None)
        raw_title = str(df.iloc[0, 0]).strip() if not pd.isna(df.iloc[0, 0]) else "PPM Checklist"
        ehs_steps = []
        sections  = []
        current_grp = None
        HEADER_ROW = None
        for i, row in df.iterrows():
            v0 = str(row.iloc[0]).strip().lower() if not pd.isna(row.iloc[0]) else ""
            if v0 == "s.no":
                HEADER_ROW = i
                break
        if HEADER_ROW and HEADER_ROW >= 3:
            for i in range(2, HEADER_ROW):
                row = df.iloc[i]
                for cp in [(0, 1), (2, 3)]:
                    sno, desc = row.iloc[cp[0]], row.iloc[cp[1]]
                    if not pd.isna(sno) and not pd.isna(desc):
                        ehs_steps.append({"sno": str(int(sno)) if isinstance(sno, float) else str(sno),
                                          "description": str(desc).strip()})
        if HEADER_ROW is not None:
            for i in range(HEADER_ROW + 1, len(df)):
                row  = df.iloc[i]
                sno  = row.iloc[0]
                desc = row.iloc[1] if len(row) > 1 else None
                if pd.isna(sno) and not pd.isna(desc):
                    grp = str(desc).strip()
                    if any(kw in grp.lower() for kw in ("sign", "spares", "supervisor", "executive")):
                        continue
                    current_grp = grp
                    sections.append({"group": current_grp, "items": []})
                    continue
                if not pd.isna(sno) and not pd.isna(desc):
                    item_desc = str(desc).strip().replace("\n", " ")
                    if not item_desc or any(kw in item_desc.lower() for kw in ("sign:", "spares used")):
                        continue
                    if not sections:
                        sections.append({"group": "General", "items": []})
                    sections[-1]["items"].append({
                        "sno": str(int(sno)) if isinstance(sno, float) else str(sno),
                        "description": item_desc,
                    })
        return jsonify({"success": True, "title": raw_title, "filename": filename,
                        "ehs_steps": ehs_steps, "sections": sections,
                        "total_items": sum(len(s["items"]) for s in sections)})
    except Exception as e:
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500


# ─────────────────────────────────────────────────────────────────────────────
# AMC TRACKER
# ─────────────────────────────────────────────────────────────────────────────

@ppm_sln_bp.route("/api/amc/contracts")
def get_amc_contracts():
    try:
        AMC_JSON = BASE_DIR / "static" / "data" / "amc_contracts.json"
        AMC_JSON.parent.mkdir(parents=True, exist_ok=True)
        if not AMC_JSON.exists():
            return jsonify({"contracts": []})
        with open(AMC_JSON, "r", encoding="utf-8") as f:
            data = json.load(f)
        return jsonify({"contracts": data.get("contracts", [])})
    except Exception as e:
        traceback.print_exc()
        return jsonify({"contracts": []}), 500


@ppm_sln_bp.route("/api/amc/update", methods=["POST"])
def update_amc_contract():
    try:
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "error": "No data provided"}), 400
        contract_id = data.get("contract_id")
        if not contract_id:
            return jsonify({"success": False, "error": "Contract ID is required"}), 400
        AMC_JSON = BASE_DIR / "static" / "data" / "amc_contracts.json"
        AMC_JSON.parent.mkdir(parents=True, exist_ok=True)
        if AMC_JSON.exists():
            with open(AMC_JSON, "r", encoding="utf-8") as f:
                amc_data = json.load(f)
        else:
            amc_data = {"contracts": []}
        contracts = amc_data.get("contracts", [])
        updated = False
        for i, c in enumerate(contracts):
            if c.get("contract_id") == contract_id:
                contracts[i] = data
                updated = True
                break
        if not updated:
            contracts.append(data)
        amc_data["contracts"]    = contracts
        amc_data["last_updated"] = datetime.now().isoformat()
        with open(AMC_JSON, "w", encoding="utf-8") as f:
            json.dump(amc_data, f, indent=2)
        return jsonify({"success": True, "message": "Contract updated successfully"})
    except Exception as e:
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500


# ─────────────────────────────────────────────────────────────────────────────
# FILE DOWNLOAD
# ─────────────────────────────────────────────────────────────────────────────

@ppm_sln_bp.route("/download-excel")
@login_required
def download_excel():
    import os
    from flask import current_app, send_from_directory
    path = os.path.join(current_app.static_folder, "data")
    return send_from_directory(path, "SLN_Terminus_Dashboard_Data.xlsx", as_attachment=True)
