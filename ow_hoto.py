"""
OW HOTO MODULE — ONEWEST Handover Takeover Workspace
Routes, upload/list/delete APIs, all prefixed ow_hoto_
Folder structure: uploads/ow_hoto/<category>/
"""

from flask import Blueprint, render_template, request, jsonify, session, send_from_directory, abort
from pathlib import Path
from functools import wraps
from werkzeug.utils import secure_filename
from datetime import datetime
import os

# ── Blueprint ────────────────────────────────────────────────────────────────
ow_hoto_bp = Blueprint("ow_hoto", __name__)

# ── Paths ────────────────────────────────────────────────────────────────────
BASE_DIR          = Path(__file__).parent.resolve()
OW_HOTO_ROOT      = BASE_DIR / "uploads" / "ow_hoto"
OW_HOTO_DATA_DIR  = BASE_DIR / "static" / "data" / "OW"

# ── Categories (ONEWEST Handover) ────────────────────────────────────────────
OW_HOTO_CATEGORIES = {
    "Admin":      "Administrative & Contract Documents",
    "Technical":  "Technical & Design Documents",
    "OM":         "O & M Manuals",
    "Testing":    "Testing & Commissioning Records",
    "Assets":     "Asset Inventory",
    "Compliance": "Compliance & Safety",
    "Training":   "Training & Support",
    "Digital":    "Digital Handover",
    "Snags":      "Snag List & Punch Items",
}

ALLOWED_EXTENSIONS_HOTO = {
    "pdf", "doc", "docx", "xls", "xlsx", "ppt", "pptx",
    "jpg", "jpeg", "png", "gif", "webp", "dwg", "dxf",
    "zip", "rar", "csv", "txt"
}

# Ensure all category directories exist on startup
def ow_hoto_ensure_dirs():
    OW_HOTO_ROOT.mkdir(parents=True, exist_ok=True)
    OW_HOTO_DATA_DIR.mkdir(parents=True, exist_ok=True)
    for key in OW_HOTO_CATEGORIES:
        (OW_HOTO_ROOT / key).mkdir(parents=True, exist_ok=True)

ow_hoto_ensure_dirs()

# ── Auth helpers ─────────────────────────────────────────────────────────────
def ow_hoto_login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if "user" not in session:
            if request.path.startswith("/ow_hoto_api/"):
                return jsonify({"success": False, "error": "Not authenticated"}), 401
            from flask import redirect, url_for
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return wrapper

def ow_hoto_require_onewest(f):
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

def ow_hoto_allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS_HOTO

# ── PAGE ROUTE ───────────────────────────────────────────────────────────────
@ow_hoto_bp.route("/ow_hoto")
@ow_hoto_login_required
@ow_hoto_require_onewest
def ow_hoto_page():
    """ONEWEST Handover Takeover Workspace page."""
    session["active_property"] = "ONEWEST"
    session["property_code"]   = "OW"
    print(f"\n📁 Accessing OW HOTO — User: {session.get('user')}")
    return render_template("ow_hoto.html")

# ── UPLOAD API ───────────────────────────────────────────────────────────────
@ow_hoto_bp.route("/ow_hoto_api/upload/<category>", methods=["POST"])
@ow_hoto_login_required
@ow_hoto_require_onewest
def ow_hoto_upload(category):
    """Upload a file to an OW HOTO category folder."""
    if category not in OW_HOTO_CATEGORIES:
        return jsonify({"error": f"Invalid category: {category}"}), 400

    if "file" not in request.files:
        return jsonify({"error": "No file provided"}), 400

    file = request.files["file"]
    if not file or file.filename == "":
        return jsonify({"error": "Empty filename"}), 400

    if not ow_hoto_allowed_file(file.filename):
        return jsonify({"error": "File type not allowed"}), 400

    save_dir = OW_HOTO_ROOT / category
    save_dir.mkdir(parents=True, exist_ok=True)

    filename  = secure_filename(file.filename)
    save_path = save_dir / filename
    file.save(save_path)

    print(f"✅ OW HOTO Upload: {category}/{filename} by {session.get('user')}")
    return jsonify({
        "success":  True,
        "message":  "Uploaded successfully",
        "filename": filename,
        "category": category,
    })

# ── LIST API ─────────────────────────────────────────────────────────────────
@ow_hoto_bp.route("/ow_hoto_api/list/<category>")
@ow_hoto_login_required
@ow_hoto_require_onewest
def ow_hoto_list(category):
    """List files in an OW HOTO category folder."""
    if category not in OW_HOTO_CATEGORIES:
        return jsonify([])

    folder = OW_HOTO_ROOT / category
    folder.mkdir(parents=True, exist_ok=True)

    files = []
    for f in sorted(folder.iterdir(), key=lambda x: x.stat().st_mtime, reverse=True):
        if f.is_file():
            files.append({
                "name": f.name,
                "size": f"{round(f.stat().st_size / 1024, 1)} KB",
                "date": datetime.fromtimestamp(f.stat().st_mtime).strftime("%Y-%m-%d %H:%M"),
            })

    return jsonify(files)

# ── DELETE API ───────────────────────────────────────────────────────────────
@ow_hoto_bp.route("/ow_hoto_api/delete/<category>/<filename>", methods=["DELETE"])
@ow_hoto_login_required
@ow_hoto_require_onewest
def ow_hoto_delete(category, filename):
    """Delete a file from an OW HOTO category folder."""
    if category not in OW_HOTO_CATEGORIES:
        return jsonify({"success": False, "error": "Invalid category"}), 400

    safe_name = secure_filename(filename)
    file_path = OW_HOTO_ROOT / category / safe_name

    if not file_path.exists() or not file_path.is_file():
        return jsonify({"success": False, "error": "File not found"}), 404

    file_path.unlink()
    print(f"🗑️ OW HOTO Delete: {category}/{safe_name} by {session.get('user')}")
    return jsonify({"success": True, "deleted": safe_name})

# ── SERVE UPLOADED FILES ─────────────────────────────────────────────────────
@ow_hoto_bp.route("/ow_hoto_files/<category>/<filename>")
@ow_hoto_login_required
def ow_hoto_serve_file(category, filename):
    """Serve an uploaded OW HOTO file (for preview / download)."""
    if category not in OW_HOTO_CATEGORIES:
        abort(404)
    safe_name = secure_filename(filename)
    folder    = OW_HOTO_ROOT / category
    file_path = folder / safe_name
    if not file_path.exists():
        abort(404)
    return send_from_directory(str(folder), safe_name)

# ── STATS API ────────────────────────────────────────────────────────────────
@ow_hoto_bp.route("/ow_hoto_api/stats")
@ow_hoto_login_required
@ow_hoto_require_onewest
def ow_hoto_stats():
    """Return file counts per category for the dashboard."""
    stats = {}
    total = 0
    for cat in OW_HOTO_CATEGORIES:
        folder = OW_HOTO_ROOT / cat
        folder.mkdir(parents=True, exist_ok=True)
        count       = len([f for f in folder.iterdir() if f.is_file()])
        stats[cat]  = count
        total      += count
    return jsonify({"categories": stats, "total": total, "property": "ONEWEST"})

# ── REGISTRATION HELPER ──────────────────────────────────────────────────────
def ow_hoto_register(app):
    """Register ow_hoto blueprint onto the Flask app."""
    app.register_blueprint(ow_hoto_bp)
    print("✅ Registered: ow_hoto_bp (ONEWEST Handover Takeover Workspace)")