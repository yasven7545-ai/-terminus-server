"""
SLN TERMINUS — MMS ROUTES  v4.0  (production-ready)
Blueprint : sln_mms_bp
Endpoints : /sln_api/mms/*   |   Page: /sln_mms_dashboard

KEY FIX (v4.0):
  Assets.xlsx column structure:
    Assets  sheet: s_no, asset_name, asset_code, location
    Inhouse sheet: s_no, equip_no, equip_name, equip_type, ppm_by, location,
                   last_service, next_due, freq_color_code, last_service.1, next_due_date
    Vendor  sheet: same as Inhouse (no trade column)

  CORRECT join key: equip_no (Inhouse/Vendor) == asset_code (Assets)
  NOT by name — asset_name has duplicates (405 rows but only 146 unique names)

  Result: 265 inhouse + 139 vendor = 404 total assets, ALL with nextDueDate
"""

from flask import Blueprint, request, jsonify, send_file, session, render_template, redirect, url_for
from pathlib import Path
import pandas as pd
import json
import traceback
from datetime import datetime
from werkzeug.utils import secure_filename
import io

# ─────────────────────────────────────────────────────────────
# BLUEPRINT
# ─────────────────────────────────────────────────────────────
sln_mms_bp = Blueprint("sln_mms_bp", __name__)

# ─────────────────────────────────────────────────────────────
# PATHS
# ─────────────────────────────────────────────────────────────
BASE_DIR    = Path(__file__).parent.resolve()
DATA_DIR    = BASE_DIR / "static" / "data"
ASSETS_XLSX = DATA_DIR / "Assets.xlsx"
WO_JSON     = DATA_DIR / "sln_work_orders.json"
TECH_JSON   = DATA_DIR / "technicians.json"
SUP_JSON    = DATA_DIR / "supervisors.json"
AMC_JSON    = DATA_DIR / "sln_amc_contracts.json"
UPLOAD_DIR  = BASE_DIR / "uploads" / "SLN" / "ppm"

for _d in [DATA_DIR, UPLOAD_DIR]:
    _d.mkdir(parents=True, exist_ok=True)

ALLOWED_IMG = {"png", "jpg", "jpeg", "gif", "webp"}

# ─────────────────────────────────────────────────────────────
# SMTP (hardcoded from server.py — no import dependency)
# ─────────────────────────────────────────────────────────────
SMTP_HOST       = "smtp.gmail.com"
SMTP_PORT       = 587
SMTP_USER       = "maintenance.slnterminus@gmail.com"
SMTP_PASS       = "xaottgrqtqnkouqn"
FROM_ADDR       = "maintenance.slnterminus@gmail.com"
RECEIVER_EMAILS = [
    "maintenance.slnterminus@gmail.com",
    "yasven7545@gmail.com",
    "engineering@terminus-global.com",
    "kiran@terminus-global.com",
    "madhav.reddy@terminus-global.com",
]

# ─────────────────────────────────────────────────────────────
# JSON HELPERS
# ─────────────────────────────────────────────────────────────

def _read_json(path, default):
    try:
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception as e:
        print(f"[SLN MMS] JSON read error ({path.name}): {e}")
    return default


def _write_json(path, data):
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, default=str)
        return True
    except Exception as e:
        print(f"[SLN MMS] JSON write error ({path.name}): {e}")
        return False


# ─────────────────────────────────────────────────────────────
# DATA HELPERS
# ─────────────────────────────────────────────────────────────

def _clean(val) -> str:
    """Any value → trimmed string; '' for null/NaN."""
    try:
        if pd.isna(val):
            return ""
    except Exception:
        pass
    s = str(val).strip()
    return "" if s.lower() in ("nan", "none", "nat", "") else s


def _ts_to_str(val) -> str:
    """pandas Timestamp / date string → 'YYYY-MM-DD'. Never raises."""
    if val is None:
        return ""
    try:
        if pd.isna(val):
            return ""
    except Exception:
        pass
    try:
        if hasattr(val, "strftime"):          # pandas Timestamp / datetime
            return val.strftime("%Y-%m-%d")
        s = str(val).strip()
        return "" if s.lower() in ("nat", "nan", "none", "") else s[:10]
    except Exception:
        return ""


def _normalise_freq(raw: str) -> str:
    r = (raw or "").strip().lower()
    if r in ("monthly", "per month", "month"):                      return "MONTHLY"
    if r in ("quaterly", "quarterly", "quarter", "q"):              return "QUARTERLY"
    if r in ("half-yearly", "half yearly", "biannual", "semi-annual", "half"):
                                                                    return "HALF-YEARLY"
    if r in ("yearly", "annual", "annually", "year"):               return "YEARLY"
    if r in ("per day", "daily", "day"):                            return "DAILY"
    if r in ("weekly", "week"):                                     return "WEEKLY"
    return raw.upper().strip() or "MONTHLY"


def _categorise(name: str, equip_type: str = "") -> str:
    """Map equip_type / asset name → category key."""
    for text in ((equip_type or "").lower(), (name or "").lower()):
        if not text:
            continue
        if any(k in text for k in ("chiller", "cooling tower", "condenser pump",
                                    "ct tub", "ct fan", "condensing tank",
                                    "package ac", "package pump")):       return "chiller"
        if any(k in text for k in ("dg set", "dg-", "dg ", "diesel generator",
                                    "amf panel", "generator", "amf")):    return "dg"
        if "transformer" in text:                                         return "transformer"
        if any(k in text for k in ("fresh air", "exhaust", "scrubber",
                                    "air washer", "pressurization", "fcu",
                                    "ahu", "air handling", "fan coil")):  return "ahu_fcu"
        if any(k in text for k in ("lift", "elevator", "escalator",
                                    "travellator")):                      return "lift"
        if any(k in text for k in ("pump", "dewatering", "fire fighting pump",
                                    "water pump", "stp pump", "stainer",
                                    "strainer", "prv", "water storage",
                                    "water tank")):                       return "pump"
        if any(k in text for k in ("fire", "fa&pa", "sprinkler",
                                    "suppression", "fire alarm")):        return "fire"
        if any(k in text for k in ("bms", "cctv", "camera",
                                    "access control", "plc", "scada")):  return "bms_cctv"
        if any(k in text for k in ("ups", "battery charger", "battery")): return "ups"
        if any(k in text for k in ("panel", "mdb", "sdb", "eldb", "rpdb",
                                    "acb", "vcb", "ht panel", "lt kiosk",
                                    "capacitor", "starter", "feeder",
                                    "apfcr", "ht ")):                     return "panels"
        if any(k in text for k in ("jet fan", "ventilation fan",
                                    "car park fan")):                     return "jet_fan"
    return "general"


def _asset_priority(name: str, category: str = "") -> str:
    if category in {"dg", "transformer", "lift", "fire", "chiller", "ups"}:
        return "High"
    nl = (name or "").lower()
    if any(k in nl for k in ("fire", "transformer", "generator", "dg",
                               "elevator", "lift", "chiller", "ups", "ht")):
        return "High"
    return "Medium"


# ─────────────────────────────────────────────────────────────
# _read_assets  (v4 — CORRECT JOIN KEY: equip_no == asset_code)
#
# The Assets sheet has duplicate asset_names (e.g. 405 rows but only
# 146 unique names).  The TRUE unique key is asset_code = equip_no.
#
# Algorithm:
#   1. Parse Assets sheet → dict  asset_code → {name, location}
#   2. Parse Inhouse  → for each row use equip_no as ID, look up
#      location from Assets dict, add nextDueDate from next_due Timestamp
#   3. Parse Vendor  → same, append with ppm_type='vendor'
# ─────────────────────────────────────────────────────────────

def _read_assets():
    if not ASSETS_XLSX.exists():
        print(f"[SLN MMS] Assets.xlsx not found at {ASSETS_XLSX}")
        return []

    try:
        xl = pd.ExcelFile(ASSETS_XLSX, engine="openpyxl")

        def _load(sheet_name):
            """Parse sheet, normalise column names."""
            try:
                df = xl.parse(sheet_name)
                df.columns = (df.columns
                              .str.strip()
                              .str.lower()
                              .str.replace(r"[\s\t]+", "_", regex=True))
                return df
            except Exception as e:
                print(f"[SLN MMS] Cannot parse sheet '{sheet_name}': {e}")
                return pd.DataFrame()

        sheet_names = [s.strip() for s in xl.sheet_names]

        # ── Step 1: Assets sheet → code_map ──────────────────────────────
        # asset_code is unique identifier; asset_name may duplicate
        code_map = {}   # lower(asset_code) → {name, location, code}
        a_sheet = next((s for s in sheet_names if s.lower() == "assets"), None)
        if a_sheet:
            df = _load(a_sheet)
            for _, row in df.iterrows():
                code = _clean(row.get("asset_code", ""))
                name = _clean(row.get("asset_name", ""))
                if not code:
                    continue
                code_map[code.lower()] = {
                    "name":     name or code,
                    "location": _clean(row.get("location", "")),
                    "code":     code,
                }
        print(f"[SLN MMS] Assets code_map: {len(code_map)} entries")

        result = []

        # ── Step 2: Inhouse sheet ─────────────────────────────────────────
        ih_sheet = next((s for s in sheet_names
                         if s.lower() in ("inhouse", "in-house", "in_house")), None)
        if ih_sheet:
            df = _load(ih_sheet)
            for _, row in df.iterrows():
                equip_no   = _clean(row.get("equip_no",   ""))
                equip_name = _clean(row.get("equip_name", ""))
                if not equip_no:                       # skip blank rows
                    continue

                # Look up canonical name from Assets sheet; fall back to equip_name
                asset_info = code_map.get(equip_no.lower(), {})
                name       = equip_name or asset_info.get("name", equip_no)
                location   = _clean(row.get("location", "")) or asset_info.get("location", "")

                eq_type  = _clean(row.get("equip_type",      ""))
                next_due = _ts_to_str(row.get("next_due"))        # Timestamp → str
                last_svc = _ts_to_str(row.get("last_service"))
                freq     = _normalise_freq(_clean(row.get("freq_color_code", "")))
                ppm_by   = _clean(row.get("ppm_by", ""))

                result.append({
                    "id":          equip_no,
                    "name":        name,
                    "location":    location,
                    "category":    _categorise(name, eq_type),
                    "ppm_type":    "inhouse",
                    "lastService": last_svc,
                    "nextDueDate": next_due,
                    "frequency":   freq,
                    "ppm_by":      ppm_by,
                    "equip_type":  eq_type,
                })

        # ── Step 3: Vendor sheet ──────────────────────────────────────────
        v_sheet = next((s for s in sheet_names if s.lower() == "vendor"), None)
        if v_sheet:
            df = _load(v_sheet)
            for _, row in df.iterrows():
                equip_no   = _clean(row.get("equip_no",   ""))
                equip_name = _clean(row.get("equip_name", ""))
                if not equip_no:
                    continue

                asset_info = code_map.get(equip_no.lower(), {})
                name       = equip_name or asset_info.get("name", equip_no)
                location   = _clean(row.get("location", "")) or asset_info.get("location", "")
                eq_type    = _clean(row.get("equip_type",      ""))
                next_due   = _ts_to_str(row.get("next_due"))
                last_svc   = _ts_to_str(row.get("last_service"))
                freq       = _normalise_freq(_clean(row.get("freq_color_code", "")))
                ppm_by     = _clean(row.get("ppm_by", ""))

                result.append({
                    "id":          equip_no,
                    "name":        name,
                    "location":    location,
                    "category":    _categorise(name, eq_type),
                    "ppm_type":    "vendor",
                    "lastService": last_svc,
                    "nextDueDate": next_due,
                    "frequency":   freq,
                    "ppm_by":      ppm_by,
                    "equip_type":  eq_type,
                })

        inhouse_ct = sum(1 for r in result if r["ppm_type"] == "inhouse")
        vendor_ct  = sum(1 for r in result if r["ppm_type"] == "vendor")
        with_due   = sum(1 for r in result if r["nextDueDate"])
        print(f"[SLN MMS] Loaded {len(result)} assets "
              f"({inhouse_ct} inhouse, {vendor_ct} vendor, {with_due} with nextDueDate)")
        return result

    except Exception as e:
        print(f"[SLN MMS] _read_assets error: {e}")
        traceback.print_exc()
        return []


# ─────────────────────────────────────────────────────────────
# WO ID
# ─────────────────────────────────────────────────────────────

def _next_wo_id(counter: int = None) -> str:
    if counter is None:
        data    = _read_json(WO_JSON, {"work_orders": []})
        counter = len(data.get("work_orders", [])) + 1
    return f"SLN-PPM-{datetime.now().strftime('%Y-%m')}-{str(counter).zfill(4)}"


# ─────────────────────────────────────────────────────────────
# AMC SEED
# ─────────────────────────────────────────────────────────────

def _seed_amc_if_empty():
    data = _read_json(AMC_JSON, {"contracts": []})
    if data.get("contracts"):
        return
    sample = [
        {"contract_id":"SLN-AMC-2026-001","asset_id":"HT I/C  VCB-1","asset_name":"HT Panel I/C Source -1 VCB","vendor":"Siemens Energy Pvt Ltd","start_date":"2026-01-01","end_date":"2026-12-31","service_frequency":"Yearly","next_service":"2026-07-01","value":"85000","status":"active","scope":"Annual maintenance of HT VCB panels including testing and calibration","notes":"Includes 2 visits/year"},
        {"contract_id":"SLN-AMC-2026-002","asset_id":"DG set-1","asset_name":"DG set-1 1500 KVA","vendor":"Cummins India Ltd","start_date":"2026-01-01","end_date":"2026-12-31","service_frequency":"Quarterly","next_service":"2026-04-01","value":"120000","status":"active","scope":"Quarterly service of DG sets including oil change, filter replacement","notes":"4 services/year per DG"},
        {"contract_id":"SLN-AMC-2026-003","asset_id":"Chiller-01","asset_name":"Chiller Unit-1","vendor":"Carrier Midea India","start_date":"2025-07-01","end_date":"2026-06-30","service_frequency":"Half-Yearly","next_service":"2026-04-15","value":"95000","status":"expiring","scope":"Chiller maintenance including refrigerant top-up, condenser cleaning","notes":"Contract renewal due June 2026"},
        {"contract_id":"SLN-AMC-2026-004","asset_id":"LIFT-01","asset_name":"Elevator - Block A","vendor":"Otis Elevator Company","start_date":"2025-01-01","end_date":"2025-12-31","service_frequency":"Monthly","next_service":"2026-03-15","value":"48000","status":"expired","scope":"Monthly maintenance of elevators including safety checks","notes":"Renewal pending"},
        {"contract_id":"SLN-AMC-2026-005","asset_id":"FA-001","asset_name":"Fire Alarm & PA System","vendor":"Honeywell Building Technologies","start_date":"2026-01-01","end_date":"2026-12-31","service_frequency":"Quarterly","next_service":"2026-04-01","value":"72000","status":"active","scope":"Quarterly testing of all fire detectors, panels and PA system","notes":"Includes 24x7 remote monitoring"},
        {"contract_id":"SLN-AMC-2026-006","asset_id":"UPS-01","asset_name":"UPS System - BMS Room","vendor":"Vertiv India Pvt Ltd","start_date":"2026-02-01","end_date":"2027-01-31","service_frequency":"Half-Yearly","next_service":"2026-08-01","value":"38000","status":"active","scope":"Half-yearly preventive maintenance of UPS and battery banks","notes":""},
        {"contract_id":"SLN-AMC-2026-007","asset_id":"STP-PUMP-01","asset_name":"STP Pump Motors","vendor":"Grundfos Pumps India","start_date":"2026-01-15","end_date":"2026-12-31","service_frequency":"Quarterly","next_service":"2026-04-15","value":"55000","status":"active","scope":"Quarterly maintenance of STP pumps, motors and controls","notes":"Includes motor winding check"},
        {"contract_id":"SLN-AMC-2026-008","asset_id":"CCTV-SYS","asset_name":"CCTV Surveillance System","vendor":"Axis Communications","start_date":"2026-01-01","end_date":"2026-12-31","service_frequency":"Half-Yearly","next_service":"2026-06-30","value":"42000","status":"active","scope":"Camera cleaning, NVR maintenance, network check","notes":"160 cameras across property"},
    ]
    _write_json(AMC_JSON, {"contracts": sample})
    print(f"[SLN MMS] Seeded {len(sample)} AMC sample contracts")


# ─────────────────────────────────────────────────────────────
# PAGE ROUTE
# ─────────────────────────────────────────────────────────────

@sln_mms_bp.route("/sln_mms_dashboard")
def sln_mms_dashboard():
    if "user" not in session:
        return redirect(url_for("login"))
    _seed_amc_if_empty()
    return render_template("sln_mms_dashboard.html")


# ─────────────────────────────────────────────────────────────
# API — ASSETS
# ─────────────────────────────────────────────────────────────

@sln_mms_bp.route("/sln_api/mms/assets")
def sln_mms_assets():
    try:
        assets = _read_assets()
        return jsonify({"success": True, "assets": assets, "total": len(assets)})
    except Exception as e:
        traceback.print_exc()
        return jsonify({"success": False, "assets": [], "total": 0, "error": str(e)}), 500


@sln_mms_bp.route("/sln_api/mms/assets/import", methods=["POST"])
def sln_mms_import_assets():
    try:
        f = request.files.get("file")
        if not f:
            return jsonify({"success": False, "error": "No file uploaded"}), 400
        f.save(str(ASSETS_XLSX))
        assets = _read_assets()
        return jsonify({"success": True, "total": len(assets),
                        "message": f"Imported {len(assets)} assets"})
    except Exception as e:
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500


# ─────────────────────────────────────────────────────────────
# API — STATS
# ─────────────────────────────────────────────────────────────

@sln_mms_bp.route("/sln_api/mms/stats")
def sln_mms_stats():
    try:
        assets = _read_assets()
        today  = datetime.now().date()
        data   = _read_json(WO_JSON, {"work_orders": []})
        wos    = data.get("work_orders", [])

        # WO counts (asset-loop overdue removed — now counted from WOs below)

        open_wos   = [w for w in wos if (w.get("status") or "").lower()
                      in ("open", "overdue", "in-progress", "in_progress")]
        closed_wos = [w for w in wos if (w.get("status") or "").lower()
                      in ("completed", "closed")]
        compliance = round(len(closed_wos) / max(len(wos), 1) * 100)

        # overdue = WOs with status=overdue (matches mail report)
        overdue_wos_count = sum(1 for w in wos if (w.get("status") or "").lower() == "overdue")
        # due_soon = assets whose nextDueDate is within 7 days and no open WO yet
        open_asset_ids = {w.get("asset_id","") for w in open_wos}
        due_soon = sum(
            1 for a in assets
            if a.get("nextDueDate") and a["id"] not in open_asset_ids
            and 0 <= (lambda d: (d - today).days if d else 999)(
                __import__('datetime').datetime.strptime(a["nextDueDate"][:10], "%Y-%m-%d").date()
                if a.get("nextDueDate") else None) <= 7
        )

        inhouse = [a for a in assets if a.get("ppm_type") != "vendor"]
        vendor  = [a for a in assets if a.get("ppm_type") == "vendor"]

        inhouse_open = [w for w in open_wos if w.get("ppm_type") != "vendor"]
        vendor_open  = [w for w in open_wos if w.get("ppm_type") == "vendor"]
        inhouse_ov   = sum(1 for w in open_wos if w.get("ppm_type") != "vendor"
                           and (w.get("status") or "").lower() == "overdue")
        vendor_ov    = sum(1 for w in open_wos if w.get("ppm_type") == "vendor"
                           and (w.get("status") or "").lower() == "overdue")

        return jsonify({
            "success":         True,
            "total_assets":    len(assets),
            "inhouse_count":   len(inhouse),
            "vendor_count":    len(vendor),
            "overdue":         overdue_wos_count,
            "due_soon":        due_soon,
            "open_wos":        len(open_wos),
            "closed_wos":      len(closed_wos),
            "total_wos":       len(wos),
            "compliance_pct":  compliance,
            "inhouse_open":    len(inhouse_open),
            "inhouse_overdue": inhouse_ov,
            "vendor_open":     len(vendor_open),
            "vendor_overdue":  vendor_ov,
        })
    except Exception as e:
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500


# ─────────────────────────────────────────────────────────────
# API — WORK ORDERS
# ─────────────────────────────────────────────────────────────

@sln_mms_bp.route("/sln_api/mms/workorders")
def sln_mms_workorders():
    try:
        data   = _read_json(WO_JSON, {"work_orders": []})
        wos    = data.get("work_orders", [])
        status = request.args.get("status", "all").lower()
        if status != "all":
            wos = [w for w in wos if (w.get("status") or "").lower() == status]
        return jsonify({"success": True, "work_orders": wos, "total": len(wos)})
    except Exception as e:
        return jsonify({"success": False, "work_orders": [], "total": 0, "error": str(e)}), 500


@sln_mms_bp.route("/sln_api/mms/workorders/by-date")
def sln_mms_wo_by_date():
    date_str = request.args.get("date", "")
    try:
        data = _read_json(WO_JSON, {"work_orders": []})
        wos  = [w for w in data.get("work_orders", [])
                if w.get("due_date", "")[:10] == date_str[:10]]
        return jsonify({"success": True, "work_orders": wos})
    except Exception as e:
        return jsonify({"success": False, "work_orders": [], "error": str(e)}), 500


@sln_mms_bp.route("/sln_api/mms/workorders/export")
def sln_mms_wo_export():
    try:
        data = _read_json(WO_JSON, {"work_orders": []})
        rows = [{
            "WO ID":       w.get("work_order_id", ""),
            "Asset ID":    w.get("asset_id",       ""),
            "Asset":       w.get("asset_name",     ""),
            "Location":    w.get("location",       ""),
            "Category":    w.get("category",       ""),
            "Frequency":   w.get("frequency",      ""),
            "Due Date":    w.get("due_date",        ""),
            "Priority":    w.get("priority",       ""),
            "Status":      w.get("status",         ""),
            "PPM Type":    w.get("ppm_type",        ""),
            "Assigned To": w.get("assigned_to",    ""),
            "Supervisor":  w.get("supervisor",     ""),
            "Created":     w.get("created_at",     ""),
            "Closed":      w.get("closed_at",      ""),
        } for w in data.get("work_orders", [])]
        df  = pd.DataFrame(rows)
        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine="openpyxl") as writer:
            df.to_excel(writer, index=False, sheet_name="WorkOrders")
        buf.seek(0)
        fname = f"SLN_WOs_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        return send_file(buf,
                         mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                         as_attachment=True, download_name=fname)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ─────────────────────────────────────────────────────────────
# API — AUTO-GENERATE WORK ORDERS
# ─────────────────────────────────────────────────────────────

def _auto_generate_wos(trigger: str = "scheduled") -> dict:
    """Generate WOs for all assets whose next_due <= today and no open WO exists."""
    today  = datetime.now().date()
    assets = _read_assets()
    data   = _read_json(WO_JSON, {"work_orders": []})
    wos    = data.get("work_orders", [])

    open_ids = {
        w.get("asset_id", "")
        for w in wos
        if (w.get("status") or "").lower() not in ("completed", "closed")
    }

    generated = []
    counter   = len(wos)

    for a in assets:
        nd = a.get("nextDueDate", "")
        if not nd:
            continue
        try:
            due = datetime.strptime(nd[:10], "%Y-%m-%d").date()
        except ValueError:
            continue
        if due > today or a["id"] in open_ids:
            continue

        counter += 1
        wo = {
            "work_order_id": f"SLN-PPM-{datetime.now().strftime('%Y-%m')}-{str(counter).zfill(4)}",
            "asset_id":      a["id"],
            "asset_name":    a["name"],
            "location":      a.get("location", ""),
            "due_date":      nd[:10],
            "priority":      _asset_priority(a["name"], a.get("category", "")),
            "status":        "overdue" if due < today else "open",
            "ppm_type":      a.get("ppm_type", "inhouse"),
            "category":      a.get("category", "general"),
            "frequency":     a.get("frequency", "MONTHLY"),
            "assigned_to":   "",
            "supervisor":    "",
            "checklist":     [],
            "images":        [],
            "notes":         f"Auto-generated ({trigger}) for scheduled PPM",
            "created_at":    datetime.now().isoformat(),
            "property":      "SLN Terminus",
        }
        wos.append(wo)
        open_ids.add(a["id"])
        generated.append(wo)

    if generated:
        data["work_orders"] = wos
        _write_json(WO_JSON, data)
        print(f"[SLN MMS] Auto-generated {len(generated)} WOs ({trigger})")

    return {"generated": len(generated), "work_orders": generated}


@sln_mms_bp.route("/sln_api/mms/workorders/auto-generate", methods=["POST"])
def sln_mms_auto_generate():
    try:
        result = _auto_generate_wos(trigger="manual")
        return jsonify({"success": True, **result})
    except Exception as e:
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500


# ─────────────────────────────────────────────────────────────
# API — CREATE / UPDATE / CLOSE WORK ORDER
# ─────────────────────────────────────────────────────────────

@sln_mms_bp.route("/sln_api/mms/workflow/create", methods=["POST"])
def sln_mms_create_wo():
    try:
        d        = request.get_json() or {}
        asset_id = d.get("assetId",   "")
        due_date = d.get("dueDate",   "")
        a_name   = d.get("assetName", "")
        location = d.get("location",  "")
        ppm_type = d.get("ppmType",   "inhouse")

        # Normalise MM/DD/YYYY → YYYY-MM-DD
        if "/" in (due_date or ""):
            p = due_date.split("/")
            try:
                due_date = f"{p[2]}-{p[0].zfill(2)}-{p[1].zfill(2)}"
            except IndexError:
                pass

        if not asset_id:
            return jsonify({"success": False, "error": "assetId required"}), 400

        # Enrich from Excel if names missing
        if not a_name:
            match = next((a for a in _read_assets() if a["id"] == asset_id), None)
            if match:
                a_name   = match["name"]
                location = match.get("location", "")
                ppm_type = match.get("ppm_type", "inhouse")
            else:
                a_name = f"Asset_{asset_id}"

        wo_id = _next_wo_id()
        wo    = {
            "work_order_id": wo_id,
            "asset_id":      asset_id,
            "asset_name":    a_name,
            "location":      location,
            "due_date":      due_date,
            "priority":      _asset_priority(a_name),
            "status":        "open",
            "ppm_type":      ppm_type,
            "assigned_to":   "",
            "supervisor":    "",
            "checklist":     [],
            "images":        [],
            "notes":         "",
            "created_at":    datetime.now().isoformat(),
            "property":      "SLN Terminus",
        }
        data = _read_json(WO_JSON, {"work_orders": []})
        data.setdefault("work_orders", []).append(wo)
        _write_json(WO_JSON, data)
        return jsonify({"success": True, "work_order_id": wo_id, "work_order": wo})
    except Exception as e:
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500


@sln_mms_bp.route("/sln_api/mms/workflow/update", methods=["POST"])
def sln_mms_update_wo():
    try:
        d     = request.get_json() or {}
        wo_id = d.get("work_order_id") or d.get("wo_id")
        if not wo_id:
            return jsonify({"success": False, "error": "wo_id required"}), 400

        data = _read_json(WO_JSON, {"work_orders": []})
        wos  = data.get("work_orders", [])
        idx  = next((i for i, w in enumerate(wos) if w.get("work_order_id") == wo_id), None)
        if idx is None:
            return jsonify({"success": False, "error": "WO not found"}), 404

        for key in ["status", "assigned_to", "supervisor", "checklist", "notes",
                    "priority", "images", "approval_notes", "closed_by"]:
            if key in d:
                wos[idx][key] = d[key]

        if (d.get("status") or "").lower() in ("completed", "closed"):
            wos[idx]["closed_at"] = datetime.now().isoformat()

        data["work_orders"] = wos
        _write_json(WO_JSON, data)
        return jsonify({"success": True, "work_order": wos[idx]})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@sln_mms_bp.route("/sln_api/mms/workflow/close", methods=["POST"])
def sln_mms_close_wo():
    try:
        d     = request.get_json() or {}
        wo_id = d.get("work_order_id") or d.get("wo_id")
        if not wo_id:
            return jsonify({"success": False, "error": "wo_id required"}), 400

        data = _read_json(WO_JSON, {"work_orders": []})
        wos  = data.get("work_orders", [])
        idx  = next((i for i, w in enumerate(wos) if w.get("work_order_id") == wo_id), None)
        if idx is None:
            return jsonify({"success": False, "error": "WO not found"}), 404

        wos[idx].update({
            "status":    "completed",
            "closed_at": datetime.now().isoformat(),
            "closed_by": d.get("closed_by", ""),
            "notes":     d.get("notes", wos[idx].get("notes", "")),
        })
        data["work_orders"] = wos
        _write_json(WO_JSON, data)
        return jsonify({"success": True, "work_order": wos[idx]})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@sln_mms_bp.route("/sln_api/mms/workflow/reopen", methods=["POST"])
def sln_mms_reopen_wo():
    """Reopen a completed/closed WO — resets status to 'open', clears closed fields."""
    try:
        d     = request.get_json() or {}
        wo_id = d.get("work_order_id") or d.get("wo_id")
        if not wo_id:
            return jsonify({"success": False, "error": "wo_id required"}), 400

        data = _read_json(WO_JSON, {"work_orders": []})
        wos  = data.get("work_orders", [])
        idx  = next((i for i, w in enumerate(wos) if w.get("work_order_id") == wo_id), None)
        if idx is None:
            return jsonify({"success": False, "error": "WO not found"}), 404

        wos[idx].update({
            "status":        "open",
            "closed_at":     None,
            "closed_by":     "",
            "approval_notes": "",
            "reopen_reason": d.get("reason", "Reopened by supervisor"),
            "reopened_at":   datetime.now().isoformat(),
        })
        data["work_orders"] = wos
        _write_json(WO_JSON, data)
        return jsonify({"success": True, "work_order": wos[idx]})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# ─────────────────────────────────────────────────────────────
# API — IMAGE UPLOAD
# ─────────────────────────────────────────────────────────────

@sln_mms_bp.route("/sln_api/mms/workorders/upload-image", methods=["POST"])
def sln_mms_upload_image():
    try:
        wo_id = request.form.get("wo_id", "")
        f     = request.files.get("image")
        if not f or not wo_id:
            return jsonify({"success": False, "error": "wo_id and image required"}), 400
        ext = f.filename.rsplit(".", 1)[-1].lower()
        if ext not in ALLOWED_IMG:
            return jsonify({"success": False, "error": "Invalid file type"}), 400
        fname    = secure_filename(f"{wo_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}.{ext}")
        save_dir = UPLOAD_DIR / wo_id
        save_dir.mkdir(parents=True, exist_ok=True)
        f.save(str(save_dir / fname))
        data = _read_json(WO_JSON, {"work_orders": []})
        wos  = data.get("work_orders", [])
        idx  = next((i for i, w in enumerate(wos) if w.get("work_order_id") == wo_id), None)
        if idx is not None:
            wos[idx].setdefault("images", []).append(
                {"filename": fname, "path": f"/uploads/SLN/ppm/{wo_id}/{fname}"}
            )
            _write_json(WO_JSON, data)
        return jsonify({"success": True, "filename": fname})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# ─────────────────────────────────────────────────────────────
# SERVE UPLOADED IMAGES  — /uploads/SLN/ppm/<wo_id>/<filename>
# ─────────────────────────────────────────────────────────────
@sln_mms_bp.route("/uploads/SLN/ppm/<wo_id>/<filename>")
def sln_mms_serve_image(wo_id, filename):
    """Serve a work-order photo from  uploads/SLN/ppm/<wo_id>/."""
    from flask import send_from_directory, abort
    img_dir = UPLOAD_DIR / secure_filename(wo_id)
    safe    = secure_filename(filename)
    if not safe or not (img_dir / safe).exists():
        abort(404)
    return send_from_directory(str(img_dir), safe)


# ─────────────────────────────────────────────────────────────
# API — TECHNICIANS / SUPERVISORS
# ─────────────────────────────────────────────────────────────

@sln_mms_bp.route("/sln_api/mms/technicians")
def sln_mms_technicians():
    try:
        t = _read_json(TECH_JSON, [])
        if isinstance(t, dict):
            t = t.get("technicians", [])
        return jsonify({"technicians": t, "total": len(t)})
    except Exception:
        return jsonify({"technicians": [], "total": 0}), 500


@sln_mms_bp.route("/sln_api/mms/supervisors")
def sln_mms_supervisors():
    try:
        s = _read_json(SUP_JSON, [])
        if isinstance(s, dict):
            s = s.get("supervisors", [])
        return jsonify({"supervisors": s, "total": len(s)})
    except Exception:
        return jsonify({"supervisors": [], "total": 0}), 500


# ─────────────────────────────────────────────────────────────
# API — AMC CONTRACTS
# ─────────────────────────────────────────────────────────────

def _days_to_expiry(contract, today):
    ed = contract.get("end_date", "")
    if not ed:
        return None
    try:
        return (datetime.strptime(str(ed)[:10], "%Y-%m-%d").date() - today).days
    except Exception:
        return None


@sln_mms_bp.route("/sln_api/mms/amc/contracts")
def sln_mms_amc_contracts():
    try:
        _seed_amc_if_empty()
        data      = _read_json(AMC_JSON, {"contracts": []})
        contracts = data.get("contracts", [])
        today     = datetime.now().date()
        flt       = request.args.get("filter", "all").lower()

        for c in contracts:
            d = _days_to_expiry(c, today)
            if d is not None and d <= 0:
                c["status"] = "expired"
            elif d is not None and 0 < d <= 90 and c.get("status") == "active":
                c["status"] = "expiring"

        if flt in ("active", "expiring", "expired"):
            contracts = [c for c in contracts if c.get("status") == flt]

        return jsonify({"contracts": contracts, "total": len(contracts)})
    except Exception as e:
        return jsonify({"contracts": [], "total": 0, "error": str(e)}), 500


@sln_mms_bp.route("/sln_api/mms/amc/update", methods=["POST"])
def sln_mms_amc_update():
    try:
        updated = request.get_json() or {}
        cid     = updated.get("contract_id")
        if not cid:
            return jsonify({"success": False, "error": "contract_id required"}), 400
        data = _read_json(AMC_JSON, {"contracts": []})
        cs   = data.get("contracts", [])
        idx  = next((i for i, c in enumerate(cs) if c.get("contract_id") == cid), None)
        if idx is None:
            cs.append(updated)
        else:
            cs[idx] = updated
        data["contracts"] = cs
        _write_json(AMC_JSON, data)
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@sln_mms_bp.route("/sln_api/mms/amc/bulk-import", methods=["POST"])
def sln_mms_amc_bulk_import():
    try:
        d         = request.get_json() or {}
        contracts = d.get("contracts", [])
        data      = _read_json(AMC_JSON, {"contracts": []})
        existing  = {c.get("contract_id"): c for c in data.get("contracts", [])}
        for c in contracts:
            cid = c.get("contract_id", "")
            if cid:
                existing[cid] = c
        data["contracts"] = list(existing.values())
        _write_json(AMC_JSON, data)
        return jsonify({"success": True, "total": len(data["contracts"])})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@sln_mms_bp.route("/sln_api/mms/amc/contracts/export")
def sln_mms_amc_export():
    try:
        data = _read_json(AMC_JSON, {"contracts": []})
        df   = pd.DataFrame(data.get("contracts", []))
        buf  = io.BytesIO()
        with pd.ExcelWriter(buf, engine="openpyxl") as writer:
            df.to_excel(writer, index=False, sheet_name="AMC_Contracts")
        buf.seek(0)
        fname = f"SLN_AMC_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        return send_file(buf,
                         mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                         as_attachment=True, download_name=fname)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ─────────────────────────────────────────────────────────────
# MAIL — BUILD + SEND
# ─────────────────────────────────────────────────────────────

def _build_mail_html(today_wos, overdue_wos, open_wos, gen_count, date_str):
    TH = lambda t: (f'<th style="padding:7px 10px;text-align:left;font-size:9px;'
                    f'color:#475569;letter-spacing:.1em;text-transform:uppercase;">{t}</th>')
    thead = "<tr>" + "".join(TH(t) for t in
                              ["WO ID", "Asset ID", "Asset", "Location", "Due", "Status", "Priority", "Assigned"]) + "</tr>"

    def wo_row(w, bg="#1e2535"):
        st  = (w.get("status") or "open").lower()
        stc = {"open": "#06b6d4", "overdue": "#f43f5e", "in-progress": "#8b5cf6"}.get(st, "#94a3b8")
        pri = w.get("priority", "")
        prc = "#f43f5e" if pri == "High" else "#f59e0b"
        return (
            f'<tr style="background:{bg};border-bottom:1px solid #1e293b;">'
            f'<td style="padding:8px 10px;font-family:monospace;color:#06b6d4;font-size:11px;">'
            f'{w.get("work_order_id","")}</td>'
            f'<td style="padding:8px 10px;font-family:monospace;color:#94a3b8;font-size:10px;">'
            f'{w.get("asset_id","—")}</td>'
            f'<td style="padding:8px 10px;color:#e2e8f0;font-size:12px;">{w.get("asset_name","")}</td>'
            f'<td style="padding:8px 10px;color:#94a3b8;font-size:11px;">{w.get("location","")}</td>'
            f'<td style="padding:8px 10px;color:#94a3b8;font-size:11px;">{w.get("due_date","")}</td>'
            f'<td style="padding:8px 10px;">'
            f'<span style="padding:2px 7px;border-radius:4px;background:{stc}22;color:{stc};'
            f'border:1px solid {stc}44;font-size:10px;font-weight:700;">{st.upper()}</span></td>'
            f'<td style="padding:8px 10px;color:{prc};font-size:11px;font-weight:700;">{pri}</td>'
            f'<td style="padding:8px 10px;color:#64748b;font-size:11px;">'
            f'{w.get("assigned_to","") or "—"}</td>'
            f'</tr>'
        )

    empty_row = lambda msg: (f'<tr><td colspan="7" style="padding:16px;text-align:center;'
                             f'color:#475569;">{msg}</td></tr>')
    rows_t = "".join(wo_row(w) for w in today_wos)         or empty_row("No PPM tasks due today ✅")
    rows_o = "".join(wo_row(w, "#2a1c1c") for w in overdue_wos) or empty_row("No overdue tasks ✅")

    kpi = "".join(
        f'<div style="flex:1;padding:18px;text-align:center;border-right:1px solid #1e293b;">'
        f'<p style="color:#475569;font-size:9px;letter-spacing:.1em;text-transform:uppercase;margin:0 0 4px;">'
        f'{lbl}</p><p style="color:{col};font-size:26px;font-weight:800;margin:0;">{val}</p></div>'
        for lbl, col, val in [
            ("Due Today", "#06b6d4", len(today_wos)),
            ("Overdue",   "#f43f5e", len(overdue_wos)),
            ("Total Open","#f59e0b", len(open_wos)),
            ("Generated", "#10b981", gen_count),
        ]
    )
    return f"""<!DOCTYPE html><html><head><meta charset="UTF-8"></head>
<body style="margin:0;padding:0;background:#030712;font-family:'Segoe UI',Arial,sans-serif;">
<div style="max-width:800px;margin:30px auto;background:#0f172a;border-radius:16px;
     overflow:hidden;border:1px solid rgba(6,182,212,.2);">
  <div style="background:linear-gradient(135deg,#0891b2,#7c3aed);padding:28px 32px;">
    <h1 style="color:white;margin:0;font-size:20px;font-weight:800;letter-spacing:.06em;">
        SLN TERMINUS — MMS DAILY REPORT</h1>
    <p style="color:rgba(255,255,255,.75);margin:6px 0 0;font-size:13px;">
        {date_str} · Maintenance Management System · 08:00 AM IST</p>
  </div>
  <div style="display:flex;border-bottom:1px solid #1e293b;">{kpi}</div>
  <div style="padding:22px 22px 0;">
    <h2 style="color:#06b6d4;font-size:13px;font-weight:700;letter-spacing:.07em;
        text-transform:uppercase;margin:0 0 12px;padding-bottom:8px;
        border-bottom:1px solid #1e293b;">
        📋 Today's PPM Schedule ({len(today_wos)} tasks)</h2>
    <table style="width:100%;border-collapse:collapse;">
        <thead>{thead}</thead><tbody>{rows_t}</tbody></table>
  </div>
  <div style="padding:22px 22px 0;">
    <h2 style="color:#f43f5e;font-size:13px;font-weight:700;letter-spacing:.07em;
        text-transform:uppercase;margin:0 0 12px;padding-bottom:8px;
        border-bottom:1px solid #2d1e1e;">
        ⚠️ Overdue Work Orders ({len(overdue_wos)} tasks)</h2>
    <table style="width:100%;border-collapse:collapse;">
        <thead>{thead}</thead><tbody>{rows_o}</tbody></table>
  </div>
  <div style="padding:24px 22px;margin-top:20px;border-top:1px solid #1e293b;text-align:center;">
    <a href="https://descriptive-joya-unsolidified.ngrok-free.dev/dashboard"
       style="display:inline-block;padding:13px 36px;background:linear-gradient(135deg,#0891b2,#7c3aed);
              color:white;font-family:'Segoe UI',Arial,sans-serif;font-size:13px;font-weight:700;
              letter-spacing:.08em;text-transform:uppercase;text-decoration:none;
              border-radius:10px;margin-bottom:16px;">
       VIEW DASHBOARD
    </a>
    <p style="color:#334155;font-size:11px;margin:8px 0 0;">
        SLN Terminus MMS · Automated report · Do not reply</p>
  </div>
</div></body></html>"""


def _send_mms_daily_mail(trigger: str = "scheduled") -> dict:
    import smtplib
    from email.mime.multipart import MIMEMultipart
    from email.mime.text      import MIMEText
    from email.utils          import formataddr

    try:
        gen_result  = _auto_generate_wos(trigger=trigger)
        today       = datetime.now().date()
        data        = _read_json(WO_JSON, {"work_orders": []})
        wos         = data.get("work_orders", [])
        open_wos    = [w for w in wos if (w.get("status") or "").lower()
                       in ("open", "overdue", "in-progress")]
        today_wos   = [w for w in open_wos if w.get("due_date", "")[:10] == str(today)]
        overdue_wos = [w for w in open_wos if (w.get("status") or "").lower() == "overdue"]
        html        = _build_mail_html(today_wos, overdue_wos, open_wos,
                                       gen_result["generated"], today.strftime("%d %B %Y"))
        msg = MIMEMultipart("alternative")
        msg["Subject"] = (f"SLN MMS Report — {today.strftime('%d %b %Y')} | "
                          f"{len(today_wos)} Due · {len(overdue_wos)} Overdue")
        msg["From"]    = formataddr(("SLN Terminus MMS", FROM_ADDR))
        msg["To"]      = ", ".join(RECEIVER_EMAILS)
        msg.attach(MIMEText(html, "html", "utf-8"))

        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=20) as srv:
            srv.ehlo()
            srv.starttls()
            srv.ehlo()
            srv.login(SMTP_USER, SMTP_PASS)
            srv.sendmail(FROM_ADDR, RECEIVER_EMAILS, msg.as_string())

        print(f"[SLN MMS] Mail sent — {len(today_wos)} due, {len(overdue_wos)} overdue, "
              f"{gen_result['generated']} generated")
        return {"success": True, "sent_to": RECEIVER_EMAILS,
                "today_wos": len(today_wos), "overdue_wos": len(overdue_wos),
                "generated": gen_result["generated"]}
    except Exception as e:
        traceback.print_exc()
        return {"success": False, "error": str(e)}


@sln_mms_bp.route("/sln_api/mms/trigger-daily-mail", methods=["POST"])
def sln_mms_trigger_daily_mail():
    try:
        result = _send_mms_daily_mail(trigger="manual")
        if result.get("success"):
            return jsonify({
                "success": True,
                "message": (f"Mail sent to {len(result.get('sent_to', []))} recipients. "
                            f"{result.get('generated', 0)} WO(s) auto-generated."),
                **result
            })
        return jsonify({"success": False, "error": result.get("error", "Unknown")}), 500
    except Exception as e:
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500


# ─────────────────────────────────────────────────────────────
# SCHEDULER
# Call in server.py:
#   from sln_mms_routes import register_mms_scheduler
#   register_mms_scheduler(app)
# ─────────────────────────────────────────────────────────────

def register_mms_scheduler(app):
    try:
        from apscheduler.schedulers.background import BackgroundScheduler
        from apscheduler.triggers.cron         import CronTrigger
        import pytz

        tz  = pytz.timezone("Asia/Kolkata")
        sch = BackgroundScheduler(
            timezone=tz,
            job_defaults={"misfire_grace_time": 600, "coalesce": True, "max_instances": 1}
        )

        def _job():
            with app.app_context():
                r = _send_mms_daily_mail(trigger="scheduled")
                status = "sent" if r.get("success") else f"FAILED: {r.get('error','')}"
                print(f"[SLN MMS] Scheduled mail {status}")

        # PRODUCTION: fires daily at 08:00 AM IST
        sch.add_job(_job, CronTrigger(hour=8, minute=0, timezone=tz),
                    id="sln_mms_daily", replace_existing=True)
        sch.start()
        print("[SLN MMS] Daily scheduler registered — fires 08:00 AM IST")
        return sch
    except ImportError:
        print("[SLN MMS] apscheduler/pytz not installed. Run: pip install apscheduler pytz")
    except Exception as e:
        print(f"[SLN MMS] Scheduler error: {e}")