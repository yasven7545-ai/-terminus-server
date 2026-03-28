"""
issues_routes.py  — SLN Terminus Incident SLA Hub
Registered in server.py with url_prefix="/sln"

URLs:
  GET  /sln/api/technicians/list      — technicians only (for Technician dropdown)
  GET  /sln/api/supervisors/list      — supervisors only (for Supervisor dropdown)
  GET  /sln/api/issues/list
  POST /sln/api/issues/create
  POST /sln/api/issues/update_status/<id>
  POST /sln/api/issues/upload/<id>
  GET  /sln/api/issues/export

Changes v2:
  • assigned_group column added (tech | sup | mgmt) — stored alongside assigned_to
  • trade resolved from ALL staff sources: technicians.json trade field,
    supervisors.json trade field (Sr. Supervisor → Supervisor, GM/PM/Exe → Management)
  • /sln/api/supervisors/list endpoint added
  • _role_map() covers supervisors + management for phone lookup
  • Safe column migration runs on every start — no data loss
  • General trade as valid default for unmatched assignments
"""

import sqlite3
import json
import pandas as pd
import io
from flask import (Blueprint, g, jsonify, request,
                   send_file, send_from_directory, session)
from pathlib import Path
from datetime import datetime

issues_bp = Blueprint("issues_bp", __name__)

# ── Paths ────────────────────────────────────────────────────
BASE_DIR       = Path(__file__).parent.resolve()
STATIC_UPLOADS = BASE_DIR / "static" / "uploads"
DB_DIR         = BASE_DIR / "database"
DB_PATH        = DB_DIR   / "issues.db"

STATIC_UPLOADS.mkdir(parents=True, exist_ok=True)
DB_DIR.mkdir(parents=True, exist_ok=True)

# ── Management roles (mirrors the HTML dropdowns exactly) ────
MANAGEMENT_NAMES = {
    "Mr. Kiran Kumar",
    "Mr. Madhav Reddy",
    "Mr. Venu",
    "Mr. Dhanunjay",
    "Mr. Shailender Singh Thakur",
}

# ── DB helpers ───────────────────────────────────────────────
def get_db():
    db = getattr(g, "_issues_db", None)
    if db is None:
        db = sqlite3.connect(str(DB_PATH))
        db.row_factory = sqlite3.Row
        g._issues_db = db
    return db

@issues_bp.teardown_app_request
def close_db(_exc=None):
    db = getattr(g, "_issues_db", None)
    if db:
        try:
            db.close()
        except Exception:
            pass
        g._issues_db = None

# ── Schema init ──────────────────────────────────────────────
def init_db():
    con = sqlite3.connect(str(DB_PATH))
    c   = con.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS issues (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            issue_id       TEXT UNIQUE,
            title          TEXT,
            status         TEXT DEFAULT 'Open',
            trade          TEXT DEFAULT 'General',
            level          TEXT DEFAULT 'Technician',
            assigned_to    TEXT,
            assigned_group TEXT DEFAULT 'tech',
            issued_by      TEXT,
            created_at     TEXT
        )
    """)
    # Safe column migrations — never drops existing data
    c.execute("PRAGMA table_info(issues)")
    existing = {r[1] for r in c.fetchall()}
    migrations = [
        ("trade",          "TEXT DEFAULT 'General'"),
        ("level",          "TEXT DEFAULT 'Technician'"),
        ("assigned_to",    "TEXT"),
        ("assigned_group", "TEXT DEFAULT 'tech'"),
        ("issued_by",      "TEXT"),
    ]
    for col, defn in migrations:
        if col not in existing:
            c.execute(f"ALTER TABLE issues ADD COLUMN {col} {defn}")

    c.execute("""
        CREATE TABLE IF NOT EXISTS attachments (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            issue_id    TEXT,
            url         TEXT,
            uploaded_at TEXT
        )
    """)
    con.commit()
    con.close()

# ── JSON loader ──────────────────────────────────────────────
def _load_json(path: Path) -> list:
    try:
        if path.exists():
            raw = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(raw, list):
                return raw
            if isinstance(raw, dict):
                for key in ("technicians", "supervisors", "data", "items"):
                    if key in raw and isinstance(raw[key], list):
                        return raw[key]
    except Exception as e:
        print(f"WARNING: Could not load {path}: {e}")
    return []

# ── Staff helpers ─────────────────────────────────────────────
def _techs() -> list:
    return _load_json(BASE_DIR / "technicians.json")

def _sups() -> list:
    return _load_json(BASE_DIR / "supervisors.json")

def _all_staff() -> list:
    return _techs() + _sups()

def _phone_map() -> dict:
    """name → phone for every staff member"""
    return {p["name"]: p.get("phone", "") for p in _all_staff() if "name" in p}

def _resolve_trade(assigned_to: str, assigned_group: str) -> str:
    """
    Resolve the trade/role label for a given assignment.

    assigned_group values:
      'tech'  → look up trade in technicians.json (Electrical, Plumbing, HVAC, Carpenter, Painter, General)
      'sup'   → 'Supervisor'
      'mgmt'  → 'Management'
      ''      → try technicians.json first, then supervisors.json, then 'General'
    """
    grp = (assigned_group or "").strip().lower()

    if grp == "sup":
        return "Supervisor"

    if grp == "mgmt" or assigned_to in MANAGEMENT_NAMES:
        return "Management"

    # For technicians or unknown — search technicians.json by name
    for p in _techs():
        if p.get("name") == assigned_to:
            return p.get("trade") or "General"

    # Fallback: search supervisors.json trade field
    for p in _sups():
        if p.get("name") == assigned_to:
            trade = p.get("trade", "")
            if trade in ("GM", "PM", "Sr. Executive", "HK Exe", "Sec Exe"):
                return "Management"
            if "supervisor" in trade.lower():
                return "Supervisor"
            return trade or "General"

    return "General"

def _resolve_level(assigned_group: str) -> str:
    """Map assigned_group to a human-readable level label"""
    return {
        "tech":  "Technician",
        "sup":   "Supervisor",
        "mgmt":  "Management",
    }.get((assigned_group or "").lower(), "Technician")

# ── Static file serving ───────────────────────────────────────
@issues_bp.route("/static/uploads/<path:filename>")
def uploaded_file(filename):
    return send_from_directory(str(STATIC_UPLOADS), filename)

# ── GET /sln/api/technicians/list ────────────────────────────
@issues_bp.route("/api/technicians/list")
def technician_list():
    """Returns technicians.json list — used for the Technician dropdown only"""
    techs = _techs()
    return jsonify(techs), 200

# ── GET /sln/api/supervisors/list ────────────────────────────
@issues_bp.route("/api/supervisors/list")
def supervisor_list():
    """Returns supervisors.json list — available for future Supervisor dropdown fetch"""
    sups = _sups()
    return jsonify(sups), 200

# ── POST /sln/api/issues/create ──────────────────────────────
@issues_bp.route("/api/issues/create", methods=["POST"])
def create_issue():
    data = request.get_json(force=True) or {}

    title          = (data.get("title") or "").strip()
    assigned_to    = (data.get("assigned_to") or "").strip()
    assigned_group = (data.get("assigned_group") or "tech").strip().lower()

    if not title:
        return jsonify({"ok": False, "error": "Title is required"}), 400
    if not assigned_to:
        return jsonify({"ok": False, "error": "Assigned-to is required"}), 400

    issued_by  = session.get("user") or _resolve_level(assigned_group)
    trade      = _resolve_trade(assigned_to, assigned_group)
    level      = _resolve_level(assigned_group)
    issue_id   = "ISS-" + datetime.utcnow().strftime("%Y%m%d%H%M%S%f")[:18]
    created_at = datetime.utcnow().isoformat()

    db = get_db()
    db.execute(
        """INSERT INTO issues
           (issue_id, title, status, trade, level, assigned_to, assigned_group, issued_by, created_at)
           VALUES (?,?,?,?,?,?,?,?,?)""",
        (issue_id, title, "Open", trade, level,
         assigned_to, assigned_group, issued_by, created_at)
    )
    db.commit()
    return jsonify({"ok": True, "issue_id": issue_id}), 201

# ── GET /sln/api/issues/list ─────────────────────────────────
@issues_bp.route("/api/issues/list")
def list_issues():
    db     = get_db()
    rows   = db.execute("SELECT * FROM issues ORDER BY id DESC").fetchall()
    phones = _phone_map()
    out    = []
    for r in rows:
        att = db.execute(
            "SELECT url FROM attachments WHERE issue_id=? ORDER BY id DESC LIMIT 1",
            (r["issue_id"],)
        ).fetchone()
        row = dict(r)
        row["thumb"]      = att["url"] if att else None
        row["tech_phone"] = phones.get(r["assigned_to"], "")
        out.append(row)
    return jsonify(out), 200

# ── POST /sln/api/issues/update_status/<id> ──────────────────
@issues_bp.route("/api/issues/update_status/<issue_id>", methods=["POST"])
def update_status(issue_id):
    data       = request.get_json(force=True) or {}
    new_status = data.get("status", "Open")
    if new_status not in ("Open", "Closed"):
        return jsonify({"ok": False, "error": "Invalid status"}), 400
    db = get_db()
    db.execute("UPDATE issues SET status=? WHERE issue_id=?", (new_status, issue_id))
    db.commit()
    return jsonify({"ok": True})

# ── POST /sln/api/issues/upload/<id> ─────────────────────────
@issues_bp.route("/api/issues/upload/<issue_id>", methods=["POST"])
def upload_file(issue_id):
    file = request.files.get("file")
    if not file or not file.filename:
        return jsonify({"ok": False, "error": "No file provided"}), 400

    safe     = "".join(c if c.isalnum() or c in "._-" else "_" for c in file.filename)
    filename = f"{issue_id}_{safe}"
    file.save(str(STATIC_UPLOADS / filename))

    url = f"/sln/static/uploads/{filename}"
    db  = get_db()
    db.execute(
        "INSERT INTO attachments (issue_id, url, uploaded_at) VALUES (?,?,?)",
        (issue_id, url, datetime.utcnow().isoformat())
    )
    db.commit()
    return jsonify({"ok": True, "url": url})

# ── GET /sln/api/issues/export ───────────────────────────────
@issues_bp.route("/api/issues/export")
def export_excel():
    con = sqlite3.connect(str(DB_PATH))
    con.row_factory = sqlite3.Row
    try:
        df = pd.read_sql_query(
            """SELECT issue_id, title, status, trade, level,
                      assigned_to, assigned_group, issued_by, created_at
               FROM issues ORDER BY id DESC""",
            con
        )
    finally:
        con.close()

    # Friendly column names for the spreadsheet
    df.rename(columns={
        "issue_id":       "Issue ID",
        "title":          "Title",
        "status":         "Status",
        "trade":          "Trade / Dept",
        "level":          "Assigned Group",
        "assigned_to":    "Assigned To",
        "assigned_group": "Group Code",
        "issued_by":      "Raised By",
        "created_at":     "Created At",
    }, inplace=True)

    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Issues")
    output.seek(0)
    fname = f"SLA_Report_{datetime.now().strftime('%Y-%m-%d')}.xlsx"
    return send_file(
        output,
        as_attachment=True,
        download_name=fname,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

# ── Init on import ───────────────────────────────────────────
init_db()