"""
SLN SECURITY MODULE — ROUTES
Blueprint: sln_sec_bp
Prefix:    /sln_hk_sec
All route/function names prefixed: sln_hk_
Excel data store: static/data/sln_security.xlsx
"""

from flask import (
    Blueprint, render_template, request, jsonify,
    session, redirect, url_for, send_file
)
from functools import wraps
from pathlib import Path
from datetime import datetime
import json
import os
import pandas as pd
import io

# ─── Blueprint ────────────────────────────────────────────────────────────────
sln_sec_bp = Blueprint(
    "sln_sec",
    __name__,
    url_prefix="/sln_hk_sec",
    template_folder="templates",
)

# ─── Paths ────────────────────────────────────────────────────────────────────
BASE_DIR      = Path(__file__).parent.resolve()
DATA_DIR      = BASE_DIR / "static" / "data"
SEC_XLSX      = DATA_DIR / "sln_security.xlsx"
SEC_JSON      = DATA_DIR / "sln_security.json"   # fast-write cache

DATA_DIR.mkdir(parents=True, exist_ok=True)

# ─── Sheet names ──────────────────────────────────────────────────────────────
SHEET_INCIDENTS = "Incidents"
SHEET_GUARDS    = "Guards"
SHEET_VISITORS  = "Visitors"
SHEET_PATROLS   = "Patrols"

# ─── Auth decorator (reuses server.py session conventions) ───────────────────
def sln_hk_login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if "user" not in session:
            if request.path.startswith("/sln_hk_sec/api/"):
                return jsonify({"success": False, "error": "Not authenticated"}), 401
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return wrapper


# ═════════════════════════════════════════════════════════════════════════════
# HELPER — read / write Excel
# ═════════════════════════════════════════════════════════════════════════════

def sln_hk_init_excel():
    """Create the Excel file with all required sheets if it doesn't exist."""
    if SEC_XLSX.exists():
        return
    with pd.ExcelWriter(SEC_XLSX, engine="openpyxl") as writer:
        pd.DataFrame(columns=[
            "id","type","severity","location","datetime",
            "description","reported_by","assigned","action","status","created"
        ]).to_excel(writer, sheet_name=SHEET_INCIDENTS, index=False)

        pd.DataFrame(columns=[
            "id","name","badge","shift","status","post","contact","agency"
        ]).to_excel(writer, sheet_name=SHEET_GUARDS, index=False)

        pd.DataFrame(columns=[
            "id","name","company","host","floor","id_type","id_num",
            "vehicle","in_time","out_time","remarks","status","pass_no"
        ]).to_excel(writer, sheet_name=SHEET_VISITORS, index=False)

        pd.DataFrame(columns=[
            "id","guard","shift","route","start","freq","log"
        ]).to_excel(writer, sheet_name=SHEET_PATROLS, index=False)


def sln_hk_read_excel():
    """Read all sheets from Excel and return as dict of lists-of-dicts."""
    sln_hk_init_excel()
    result = {
        "incidents": [], "guards": [], "visitors": [], "patrols": []
    }
    try:
        xf = pd.ExcelFile(SEC_XLSX)
        sheet_map = {
            SHEET_INCIDENTS: "incidents",
            SHEET_GUARDS:    "guards",
            SHEET_VISITORS:  "visitors",
            SHEET_PATROLS:   "patrols",
        }
        for sheet, key in sheet_map.items():
            if sheet in xf.sheet_names:
                df = pd.read_excel(xf, sheet_name=sheet, dtype=str).fillna("")
                rows = df.to_dict(orient="records")
                # Deserialise 'log' column for patrols (stored as JSON string)
                if key == "patrols":
                    for row in rows:
                        try:
                            row["log"] = json.loads(row.get("log") or "[]")
                        except Exception:
                            row["log"] = []
                result[key] = rows
    except Exception as e:
        print(f"⚠️  sln_sec read_excel error: {e}")
    return result


def sln_hk_write_excel(data: dict):
    """Write all lists-of-dicts back to the Excel file (all sheets)."""
    sln_hk_init_excel()
    try:
        # Serialise patrol 'log' lists to JSON strings before writing
        patrols_copy = []
        for row in data.get("patrols", []):
            r = dict(row)
            r["log"] = json.dumps(r.get("log", []))
            patrols_copy.append(r)

        with pd.ExcelWriter(SEC_XLSX, engine="openpyxl", mode="w") as writer:
            inc_df  = pd.DataFrame(data.get("incidents", []))
            grd_df  = pd.DataFrame(data.get("guards", []))
            vis_df  = pd.DataFrame(data.get("visitors", []))
            pat_df  = pd.DataFrame(patrols_copy)

            # Ensure all columns present even if dataframe is empty
            _ensure_cols(inc_df, ["id","type","severity","location","datetime","description","reported_by","assigned","action","status","created"])
            _ensure_cols(grd_df, ["id","name","badge","shift","status","post","contact","agency"])
            _ensure_cols(vis_df, ["id","name","company","host","floor","id_type","id_num","vehicle","in_time","out_time","remarks","status","pass_no"])
            _ensure_cols(pat_df, ["id","guard","shift","route","start","freq","log"])

            inc_df.to_excel(writer, sheet_name=SHEET_INCIDENTS, index=False)
            grd_df.to_excel(writer, sheet_name=SHEET_GUARDS,    index=False)
            vis_df.to_excel(writer, sheet_name=SHEET_VISITORS,  index=False)
            pat_df.to_excel(writer, sheet_name=SHEET_PATROLS,   index=False)

        # Also cache as JSON for fast reads
        with open(SEC_JSON, "w") as f:
            json.dump(data, f)
        return True
    except Exception as e:
        print(f"⚠️  sln_sec write_excel error: {e}")
        return False


def _ensure_cols(df: pd.DataFrame, cols: list):
    for c in cols:
        if c not in df.columns:
            df[c] = ""


# ═════════════════════════════════════════════════════════════════════════════
# PAGE ROUTES
# ═════════════════════════════════════════════════════════════════════════════

@sln_sec_bp.route("/")
@sln_hk_login_required
def sln_hk_index():
    """Serve the Security Module HTML page."""
    return render_template("sln_sec.html")


# ═════════════════════════════════════════════════════════════════════════════
# API — GET all data
# ═════════════════════════════════════════════════════════════════════════════

@sln_sec_bp.route("/api/data")
@sln_hk_login_required
def sln_hk_api_data():
    """Return all security data as JSON."""
    # Fast path: use JSON cache if newer than xlsx
    if SEC_JSON.exists() and SEC_XLSX.exists():
        try:
            if SEC_JSON.stat().st_mtime >= SEC_XLSX.stat().st_mtime:
                with open(SEC_JSON) as f:
                    return jsonify(json.load(f))
        except Exception:
            pass
    data = sln_hk_read_excel()
    return jsonify(data)


# ═════════════════════════════════════════════════════════════════════════════
# API — SAVE all data
# ═════════════════════════════════════════════════════════════════════════════

@sln_sec_bp.route("/api/save", methods=["POST"])
@sln_hk_login_required
def sln_hk_api_save():
    """Receive full state from the client and persist to Excel."""
    try:
        data = request.get_json(force=True) or {}
        ok   = sln_hk_write_excel(data)
        return jsonify({"success": ok})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# ═════════════════════════════════════════════════════════════════════════════
# API — INCIDENTS CRUD
# ═════════════════════════════════════════════════════════════════════════════

@sln_sec_bp.route("/api/incidents")
@sln_hk_login_required
def sln_hk_api_incidents():
    data = sln_hk_read_excel()
    return jsonify(data["incidents"])


@sln_sec_bp.route("/api/incidents", methods=["POST"])
@sln_hk_login_required
def sln_hk_api_add_incident():
    try:
        inc  = request.get_json(force=True) or {}
        data = sln_hk_read_excel()
        inc.setdefault("id", "INC-" + datetime.now().strftime("%Y%m%d%H%M%S%f")[:18])
        inc.setdefault("created", datetime.now().isoformat())
        inc.setdefault("status", "Open")
        data["incidents"].insert(0, inc)
        sln_hk_write_excel(data)
        return jsonify({"success": True, "id": inc["id"]})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@sln_sec_bp.route("/api/incidents/<inc_id>", methods=["PATCH"])
@sln_hk_login_required
def sln_hk_api_update_incident(inc_id):
    try:
        patch = request.get_json(force=True) or {}
        data  = sln_hk_read_excel()
        for i, row in enumerate(data["incidents"]):
            if row.get("id") == inc_id:
                data["incidents"][i].update(patch)
                break
        sln_hk_write_excel(data)
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@sln_sec_bp.route("/api/incidents/<inc_id>", methods=["DELETE"])
@sln_hk_login_required
def sln_hk_api_delete_incident(inc_id):
    try:
        data = sln_hk_read_excel()
        data["incidents"] = [r for r in data["incidents"] if r.get("id") != inc_id]
        sln_hk_write_excel(data)
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# ═════════════════════════════════════════════════════════════════════════════
# API — GUARDS CRUD
# ═════════════════════════════════════════════════════════════════════════════

@sln_sec_bp.route("/api/guards")
@sln_hk_login_required
def sln_hk_api_guards():
    data = sln_hk_read_excel()
    return jsonify(data["guards"])


@sln_sec_bp.route("/api/guards", methods=["POST"])
@sln_hk_login_required
def sln_hk_api_add_guard():
    try:
        guard = request.get_json(force=True) or {}
        data  = sln_hk_read_excel()
        guard.setdefault("id", "G-" + datetime.now().strftime("%Y%m%d%H%M%S%f")[:18])
        # Upsert by id
        idx = next((i for i, r in enumerate(data["guards"]) if r.get("id") == guard["id"]), -1)
        if idx >= 0:
            data["guards"][idx] = guard
        else:
            data["guards"].append(guard)
        sln_hk_write_excel(data)
        return jsonify({"success": True, "id": guard["id"]})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@sln_sec_bp.route("/api/guards/<guard_id>", methods=["DELETE"])
@sln_hk_login_required
def sln_hk_api_delete_guard(guard_id):
    try:
        data = sln_hk_read_excel()
        data["guards"] = [r for r in data["guards"] if r.get("id") != guard_id]
        sln_hk_write_excel(data)
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# ═════════════════════════════════════════════════════════════════════════════
# API — VISITORS CRUD
# ═════════════════════════════════════════════════════════════════════════════

@sln_sec_bp.route("/api/visitors")
@sln_hk_login_required
def sln_hk_api_visitors():
    data = sln_hk_read_excel()
    return jsonify(data["visitors"])


@sln_sec_bp.route("/api/visitors", methods=["POST"])
@sln_hk_login_required
def sln_hk_api_add_visitor():
    try:
        vis  = request.get_json(force=True) or {}
        data = sln_hk_read_excel()
        vis.setdefault("id", "VP-" + datetime.now().strftime("%Y%m%d%H%M%S%f")[:18])
        vis.setdefault("pass_no", "SLN-" + vis["id"][-6:])
        vis.setdefault("status", "Active")
        idx = next((i for i, r in enumerate(data["visitors"]) if r.get("id") == vis["id"]), -1)
        if idx >= 0:
            data["visitors"][idx] = vis
        else:
            data["visitors"].append(vis)
        sln_hk_write_excel(data)
        return jsonify({"success": True, "id": vis["id"], "pass_no": vis["pass_no"]})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@sln_sec_bp.route("/api/visitors/<vis_id>/checkout", methods=["PATCH"])
@sln_hk_login_required
def sln_hk_api_checkout_visitor(vis_id):
    try:
        data = sln_hk_read_excel()
        for i, row in enumerate(data["visitors"]):
            if row.get("id") == vis_id:
                data["visitors"][i]["out_time"] = datetime.now().isoformat()
                data["visitors"][i]["status"]   = "Checked Out"
                break
        sln_hk_write_excel(data)
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@sln_sec_bp.route("/api/visitors/<vis_id>", methods=["DELETE"])
@sln_hk_login_required
def sln_hk_api_delete_visitor(vis_id):
    try:
        data = sln_hk_read_excel()
        data["visitors"] = [r for r in data["visitors"] if r.get("id") != vis_id]
        sln_hk_write_excel(data)
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# ═════════════════════════════════════════════════════════════════════════════
# API — PATROLS CRUD
# ═════════════════════════════════════════════════════════════════════════════

@sln_sec_bp.route("/api/patrols")
@sln_hk_login_required
def sln_hk_api_patrols():
    data = sln_hk_read_excel()
    return jsonify(data["patrols"])


@sln_sec_bp.route("/api/patrols", methods=["POST"])
@sln_hk_login_required
def sln_hk_api_add_patrol():
    try:
        pat  = request.get_json(force=True) or {}
        data = sln_hk_read_excel()
        pat.setdefault("id", "PAT-" + datetime.now().strftime("%Y%m%d%H%M%S%f")[:18])
        pat.setdefault("log", [])
        idx = next((i for i, r in enumerate(data["patrols"]) if r.get("id") == pat["id"]), -1)
        if idx >= 0:
            data["patrols"][idx] = pat
        else:
            data["patrols"].append(pat)
        sln_hk_write_excel(data)
        return jsonify({"success": True, "id": pat["id"]})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@sln_sec_bp.route("/api/patrols/<pat_id>/log", methods=["PATCH"])
@sln_hk_login_required
def sln_hk_api_log_patrol(pat_id):
    """Append a timestamp to the patrol's log list."""
    try:
        data = sln_hk_read_excel()
        for i, row in enumerate(data["patrols"]):
            if row.get("id") == pat_id:
                log = row.get("log") or []
                if isinstance(log, str):
                    try:
                        log = json.loads(log)
                    except Exception:
                        log = []
                log.append(datetime.now().isoformat())
                data["patrols"][i]["log"] = log
                break
        sln_hk_write_excel(data)
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@sln_sec_bp.route("/api/patrols/<pat_id>", methods=["DELETE"])
@sln_hk_login_required
def sln_hk_api_delete_patrol(pat_id):
    try:
        data = sln_hk_read_excel()
        data["patrols"] = [r for r in data["patrols"] if r.get("id") != pat_id]
        sln_hk_write_excel(data)
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# ═════════════════════════════════════════════════════════════════════════════
# API — STATS summary
# ═════════════════════════════════════════════════════════════════════════════

@sln_sec_bp.route("/api/stats")
@sln_hk_login_required
def sln_hk_api_stats():
    try:
        data   = sln_hk_read_excel()
        today  = datetime.now().date().isoformat()
        open_inc  = [i for i in data["incidents"] if i.get("status") != "Resolved"]
        on_duty   = [g for g in data["guards"]    if g.get("status") == "On Duty"]
        today_vis = [v for v in data["visitors"]
                     if v.get("in_time", "").startswith(today)]
        return jsonify({
            "open_incidents": len(open_inc),
            "guards_on_duty": len(on_duty),
            "visitors_today": len(today_vis),
            "total_guards":   len(data["guards"]),
            "total_patrols":  len(data["patrols"]),
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ═════════════════════════════════════════════════════════════════════════════
# EXPORT — Download the raw Excel file
# ═════════════════════════════════════════════════════════════════════════════

@sln_sec_bp.route("/api/export")
@sln_hk_login_required
def sln_hk_api_export():
    """Download the full security Excel workbook."""
    sln_hk_init_excel()
    if not SEC_XLSX.exists():
        return jsonify({"error": "No data file"}), 404
    fname = f"SLN_Security_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    return send_file(
        SEC_XLSX,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        as_attachment=True,
        download_name=fname,
    )