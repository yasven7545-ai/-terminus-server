"""
OW OCCUPANCY MODULE
Serves the ONEWEST SFT Details occupancy dashboard.
File: static/data/OW_ SFT_Details.xlsx
All functions and routes prefixed with ow_ to avoid collisions.
"""

from flask import Blueprint, render_template, jsonify, request, session
from pathlib import Path
from functools import wraps
import pandas as pd
import json
import traceback
from datetime import datetime

# ── Blueprint ────────────────────────────────────────────────────────────────
ow_occupancy_bp = Blueprint("ow_occupancy", __name__)

# ── Paths ────────────────────────────────────────────────────────────────────
BASE_DIR   = Path(__file__).parent.resolve()
DATA_DIR   = BASE_DIR / "static" / "data"
OW_SFT_XLSX     = DATA_DIR / "OW_ SFT_Details.xlsx"   # exact filename with space
OW_OCC_OVERRIDE = DATA_DIR / "ow_occupancy_override.json"

DATA_DIR.mkdir(parents=True, exist_ok=True)


# ── Auth helper (mirrors server.py pattern) ──────────────────────────────────
def ow_login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if "user" not in session:
            return jsonify({"success": False, "error": "Not authenticated"}), 401
        return f(*args, **kwargs)
    return wrapper


def ow_require_onewest(f):
    """Allow ONEWEST users and global admin/manager roles."""
    @wraps(f)
    def wrapper(*args, **kwargs):
        if "user" not in session:
            return jsonify({"success": False, "error": "Not authenticated"}), 401
        bypass = {"admin", "management", "general manager", "property manager"}
        role   = (session.get("role") or "").lower()
        props  = session.get("properties", [])
        if role in bypass or "ONEWEST" in props:
            return f(*args, **kwargs)
        return jsonify({"success": False, "error": "Access denied"}), 403
    return wrapper


# ────────────────────────────────────────────────────────────────────────────
# PAGE ROUTE
# ────────────────────────────────────────────────────────────────────────────
@ow_occupancy_bp.route("/ow_occupancy")
@ow_login_required
@ow_require_onewest
def ow_occupancy_page():
    session["active_property"] = "ONEWEST"
    return render_template("ow_occupancy.html")


# ────────────────────────────────────────────────────────────────────────────
# DATA API — GET
# ────────────────────────────────────────────────────────────────────────────
@ow_occupancy_bp.route("/ow_api/occupancy")
@ow_login_required
@ow_require_onewest
def ow_get_occupancy():
    """Return tenant SFT data from override JSON or Excel source."""
    try:
        # 1. Try JSON override (saved edits)
        if OW_OCC_OVERRIDE.exists():
            try:
                spaces = json.loads(OW_OCC_OVERRIDE.read_text(encoding="utf-8"))
            except Exception:
                spaces = []
        # 2. Fall back to Excel
        elif OW_SFT_XLSX.exists():
            spaces = _ow_parse_excel()
        else:
            return jsonify({"error": "OW_ SFT_Details.xlsx not found in static/data/"}), 404

        # Compute summary
        total_area  = sum(s.get("area", 0) or 0 for s in spaces)
        occ_area    = sum(s.get("area", 0) or 0 for s in spaces if _ow_status(s) == "occupied")
        vac_area    = sum(s.get("area", 0) or 0 for s in spaces if _ow_status(s) == "vacant")
        total_units = len(spaces)
        occ_count   = sum(1 for s in spaces if _ow_status(s) == "occupied")
        vac_count   = sum(1 for s in spaces if _ow_status(s) == "vacant")
        fit_count   = sum(1 for s in spaces if _ow_status(s) == "fitout")

        return jsonify({
            "summary": {
                "total_area":    round(total_area, 2),
                "occupied_area": round(occ_area,  2),
                "vacant_area":   round(vac_area,  2),
                "total_units":   total_units,
                "occupied_count": occ_count,
                "vacant_count":  vac_count,
                "fitout_count":  fit_count,
            },
            "spaces": spaces
        })

    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


# ────────────────────────────────────────────────────────────────────────────
# DATA API — UPDATE (save edits as JSON override)
# ────────────────────────────────────────────────────────────────────────────
@ow_occupancy_bp.route("/ow_api/occupancy/update", methods=["POST"])
@ow_login_required
@ow_require_onewest
def ow_update_occupancy():
    """Save edited spaces as a JSON override (does not mutate the Excel)."""
    try:
        data   = request.get_json(force=True) or {}
        spaces = data.get("spaces", [])
        if not isinstance(spaces, list):
            return jsonify({"success": False, "error": "Invalid payload"}), 400
        OW_OCC_OVERRIDE.parent.mkdir(parents=True, exist_ok=True)
        OW_OCC_OVERRIDE.write_text(
            json.dumps(spaces, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )
        return jsonify({"success": True, "count": len(spaces)})
    except Exception as e:
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500


# ────────────────────────────────────────────────────────────────────────────
# HELPERS
# ────────────────────────────────────────────────────────────────────────────
def _ow_status(s):
    """Derive occupancy status from a space dict."""
    nm = (s.get("clientName") or s.get("officeName") or "").lower().strip()
    if nm in ("vacant", ""):
        return "vacant"
    if "fit" in nm and "out" in nm:
        return "fitout"
    return "occupied"


def _ow_parse_excel():
    """Parse OW_ SFT_Details.xlsx and return a list of space dicts."""
    spaces        = []
    current_floor = None
    sno_col       = None   # will detect

    try:
        df = pd.read_excel(str(OW_SFT_XLSX), header=None)
    except Exception:
        df = pd.read_excel(str(OW_SFT_XLSX), engine="xlrd", header=None)

    for idx, row in df.iterrows():
        vals = list(row)

        # Skip header rows (detect by checking first non-null value)
        first = str(vals[0]).strip() if vals[0] is not None else ""
        if first.upper() in ("TENANTS SFT DETAILS", "S.NO", ""):
            continue

        # Try to cast S.NO to int
        try:
            sno = int(float(str(vals[0]).strip()))
        except (ValueError, TypeError):
            continue   # skip formula / total rows

        floor_val  = str(vals[1]).strip() if vals[1] is not None else ""
        client_name = str(vals[2]).strip() if vals[2] is not None else ""
        area_raw   = vals[3]

        # Resolve area — skip formula cells
        try:
            area = float(str(area_raw).replace(",", "").replace("=", ""))
            # skip if it looks like a formula (contains letters after strip)
            if any(c.isalpha() for c in str(area_raw).replace(".", "").replace("-", "")):
                area = 0.0
        except (ValueError, TypeError):
            area = 0.0

        # Update current floor if this row has one
        if floor_val and floor_val.lower() not in ("none", ""):
            current_floor = floor_val

        if not client_name or client_name.lower() == "none":
            continue

        spaces.append({
            "id":         str(sno),
            "sno":        sno,
            "floor":      current_floor or "Unknown",
            "clientName": client_name,
            "area":       round(area, 2),
        })

    return spaces


# ────────────────────────────────────────────────────────────────────────────
# REGISTRATION HELPER (called from server.py)
# ────────────────────────────────────────────────────────────────────────────
def ow_occupancy_register(app):
    """Register the ow_occupancy blueprint onto the Flask app."""
    app.register_blueprint(ow_occupancy_bp)
    print("✅ Registered: ow_occupancy_bp (ONEWEST Space Occupancy)")