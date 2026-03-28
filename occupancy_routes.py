"""
OCCUPANCY ROUTES
SLN Terminus space occupancy get/update.
ONEWEST space occupancy get/update (inline fallback — ow_occupancy.py blueprint takes priority).
"""
from flask import Blueprint, jsonify, request
import json
import traceback
import pandas as pd

from decorators import login_required, require_property
from config import BASE_DIR

occupancy_bp = Blueprint("occupancy", __name__)

# ─────────────────────────────────────────────────────────────────────────────
# SLN TERMINUS OCCUPANCY
# ─────────────────────────────────────────────────────────────────────────────

@occupancy_bp.route("/api/sln/occupancy")
@login_required
def get_sln_occupancy():
    """Get SLN space occupancy data from Excel or JSON override."""
    try:
        OVERRIDE_JSON = BASE_DIR / "static" / "data" / "sln_occupancy_override.json"
        EXCEL_PATH    = BASE_DIR / "static" / "data" / "Space Occupancy.xlsx"

        if OVERRIDE_JSON.exists():
            try:
                spaces = json.loads(OVERRIDE_JSON.read_text(encoding="utf-8"))
            except Exception:
                spaces = []
        elif EXCEL_PATH.exists():
            df    = pd.read_excel(EXCEL_PATH, sheet_name=0)
            df    = df.fillna("")
            spaces       = []
            current_floor = None
            for _, row in df.iterrows():
                if pd.isna(row.iloc[0]) or str(row.iloc[0]).strip() == "":
                    continue
                try:
                    office_name   = str(row.iloc[2]) if len(row) > 2 else ""
                    floor_level   = str(row.iloc[1]) if len(row) > 1 else ""
                    unit_no       = str(row.iloc[3]) if len(row) > 3 else ""
                    occupied_area = float(str(row.iloc[4]).replace(",", "")) if len(row) > 4 else 0
                    area          = float(str(row.iloc[5]).replace(",", "")) if len(row) > 5 else 0
                    cam_rate      = float(str(row.iloc[6]).replace(",", "")) if len(row) > 6 else 0
                    cam_rate_date = str(row.iloc[7]).strip() if len(row) > 7 else ""
                    if floor_level.strip():
                        current_floor = floor_level.strip()
                    if office_name.strip():
                        spaces.append({
                            "id":           str(row.iloc[0]),
                            "floorId":      current_floor or "L4",
                            "officeName":   office_name.strip(),
                            "unitNo":       unit_no.strip(),
                            "occupiedArea": occupied_area,
                            "area":         area,
                            "camRate":      cam_rate,
                            "camRateDate":  cam_rate_date,
                        })
                except Exception:
                    continue
        else:
            return jsonify({"error": "Space Occupancy data not found"}), 404

        def _status(s):
            nm = (s.get("officeName", "")).lower()
            if nm in ("vacant", "") or nm == "vacant": return "vacant"
            if "fit" in nm and "out" in nm:            return "fitout"
            if s.get("camRate", 0) == 0:               return "fitout"
            return "occupied"

        total_units    = len(spaces)
        vacant_count   = sum(1 for s in spaces if _status(s) == "vacant")
        fitout_count   = sum(1 for s in spaces if _status(s) == "fitout")
        occupied_count = total_units - vacant_count - fitout_count

        return jsonify({
            "summary": {
                "total_area":     sum(s.get("area", 0)         for s in spaces),
                "occupied_area":  sum(s.get("occupiedArea", 0) for s in spaces if _status(s) == "occupied"),
                "vacant_area":    sum(s.get("area", 0)         for s in spaces if _status(s) == "vacant"),
                "total_units":    total_units,
                "vacant_count":   vacant_count,
                "fitout_count":   fitout_count,
                "occupied_count": occupied_count,
            },
            "spaces": spaces,
        })

    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@occupancy_bp.route("/api/sln/occupancy/update", methods=["POST"])
@login_required
def update_sln_occupancy():
    """Save edited SLN space occupancy as JSON override."""
    try:
        data   = request.get_json(force=True) or {}
        spaces = data.get("spaces", [])
        if not isinstance(spaces, list):
            return jsonify({"success": False, "error": "Invalid payload"}), 400
        OVERRIDE_JSON = BASE_DIR / "static" / "data" / "sln_occupancy_override.json"
        OVERRIDE_JSON.parent.mkdir(parents=True, exist_ok=True)
        OVERRIDE_JSON.write_text(json.dumps(spaces, ensure_ascii=False, indent=2), encoding="utf-8")
        return jsonify({"success": True, "count": len(spaces)})
    except Exception as e:
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500


# ─────────────────────────────────────────────────────────────────────────────
# ONEWEST OCCUPANCY (inline fallback — ow_occupancy.py blueprint takes priority)
# ─────────────────────────────────────────────────────────────────────────────

_OW_SFT_XLSX     = BASE_DIR / "static" / "data" / "OW_ SFT_Details.xlsx"
_OW_OCC_OVERRIDE = BASE_DIR / "static" / "data" / "ow_occupancy_override.json"


def _ow_parse_sft():
    """Parse OW_ SFT_Details.xlsx → list of space dicts."""
    spaces        = []
    current_floor = None
    try:
        try:
            df = pd.read_excel(str(_OW_SFT_XLSX), header=None, engine="openpyxl")
        except Exception:
            df = pd.read_excel(str(_OW_SFT_XLSX), header=None, engine="xlrd")
    except Exception as e:
        print(f"❌ OW SFT Excel read error: {e}")
        return spaces

    for _, row in df.iterrows():
        vals  = list(row)
        first = str(vals[0]).strip() if vals[0] is not None else ""
        if first.upper() in ("TENANTS SFT DETAILS", "S.NO", ""):
            continue
        try:
            sno = int(float(first))
        except (ValueError, TypeError):
            continue

        floor_val   = str(vals[1]).strip() if vals[1] is not None else ""
        client_name = str(vals[2]).strip() if vals[2] is not None else ""
        area_raw    = vals[3]

        try:
            area_str = str(area_raw).replace(",", "").strip()
            if any(c.isalpha() for c in area_str.replace(".", "").replace("-", "")):
                area = 0.0
            else:
                area = float(area_str)
        except (ValueError, TypeError):
            area = 0.0

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


@occupancy_bp.route("/ow_api/occupancy")
@login_required
@require_property("ONEWEST")
def ow_api_occupancy_get():
    """Return ONEWEST SFT occupancy data."""
    try:
        if _OW_OCC_OVERRIDE.exists():
            try:
                spaces = json.loads(_OW_OCC_OVERRIDE.read_text(encoding="utf-8"))
            except Exception:
                spaces = []
        elif _OW_SFT_XLSX.exists():
            spaces = _ow_parse_sft()
        else:
            return jsonify({"error": "OW_ SFT_Details.xlsx not found in static/data/"}), 404

        def _st(s):
            n = (s.get("clientName") or "").lower().strip()
            if n in ("vacant", ""):    return "vacant"
            if "fit" in n and "out" in n: return "fitout"
            return "occupied"

        total_area  = sum(s.get("area", 0) or 0 for s in spaces)
        occ_area    = sum(s.get("area", 0) or 0 for s in spaces if _st(s) == "occupied")
        vac_area    = sum(s.get("area", 0) or 0 for s in spaces if _st(s) == "vacant")
        total_units = len(spaces)
        occ_count   = sum(1 for s in spaces if _st(s) == "occupied")
        vac_count   = sum(1 for s in spaces if _st(s) == "vacant")
        fit_count   = sum(1 for s in spaces if _st(s) == "fitout")

        return jsonify({
            "summary": {
                "total_area":     round(total_area, 2),
                "occupied_area":  round(occ_area,   2),
                "vacant_area":    round(vac_area,    2),
                "total_units":    total_units,
                "occupied_count": occ_count,
                "vacant_count":   vac_count,
                "fitout_count":   fit_count,
            },
            "spaces": spaces,
        })
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@occupancy_bp.route("/ow_api/occupancy/update", methods=["POST"])
@login_required
@require_property("ONEWEST")
def ow_api_occupancy_update():
    """Save edited ONEWEST occupancy data as JSON override."""
    try:
        data   = request.get_json(force=True) or {}
        spaces = data.get("spaces", [])
        if not isinstance(spaces, list):
            return jsonify({"success": False, "error": "Invalid payload"}), 400
        _OW_OCC_OVERRIDE.parent.mkdir(parents=True, exist_ok=True)
        _OW_OCC_OVERRIDE.write_text(
            json.dumps(spaces, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return jsonify({"success": True, "count": len(spaces)})
    except Exception as e:
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500
