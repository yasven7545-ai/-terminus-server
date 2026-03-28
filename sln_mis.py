"""
sln_mis.py — MIS Report Blueprint for SLN Terminus
Handles: training image upload / list / delete
All heavy data parsing is done client-side via XLSX.js
"""

from flask import Blueprint, request, jsonify, url_for, send_from_directory, session
from pathlib import Path
from datetime import datetime
import os

# ── Blueprint ──────────────────────────────────────────────────
mis_bp = Blueprint("mis_bp", __name__)

# ── Paths ──────────────────────────────────────────────────────
BASE_DIR             = Path(__file__).parent.resolve()
TRAINING_ROOT        = BASE_DIR / "uploads" / "training"
ALLOWED_IMAGE_EXT    = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"}

TRAINING_ROOT.mkdir(parents=True, exist_ok=True)


# ── Helpers ────────────────────────────────────────────────────
def _login_required():
    return "user" not in session


def _allowed(filename: str) -> bool:
    return Path(filename).suffix.lower() in ALLOWED_IMAGE_EXT


def _safe_dept(dept: str) -> str:
    """Whitelist department names to prevent path traversal."""
    allowed = {"MEP", "HK", "Security", "Housekeeping", "Admin", "Other"}
    return dept.strip() if dept.strip() in allowed else ""


# ── Routes ─────────────────────────────────────────────────────

@mis_bp.route("/api/mis/training/list", methods=["GET"])
def mis_list_training():
    """List training images for a department."""
    if _login_required():
        return jsonify({"error": "Unauthorized"}), 401

    dept = _safe_dept(request.args.get("department", ""))
    if not dept:
        return jsonify({"error": "Invalid or missing department"}), 400

    dest = TRAINING_ROOT / dept
    if not dest.exists():
        return jsonify({"department": dept, "files": []})

    files = []
    for p in sorted(dest.iterdir(), key=lambda x: x.stat().st_mtime, reverse=True):
        if p.is_file() and _allowed(p.name):
            files.append({
                "name": p.name,
                "url":  f"/api/mis/training/serve/{dept}/{p.name}",
                "size": f"{round(p.stat().st_size / 1024, 1)} KB",
                "date": datetime.fromtimestamp(p.stat().st_mtime).strftime("%d %b %Y"),
            })

    return jsonify({"department": dept, "count": len(files), "files": files})


@mis_bp.route("/api/mis/training/upload", methods=["POST"])
def mis_upload_training():
    """Upload a training image for a department."""
    if _login_required():
        return jsonify({"error": "Unauthorized"}), 401

    dept = _safe_dept(request.form.get("department", ""))
    if not dept:
        return jsonify({"error": "Invalid or missing department"}), 400

    if "file" not in request.files:
        return jsonify({"error": "No file in request"}), 400

    f = request.files["file"]
    if not f or f.filename == "":
        return jsonify({"error": "Empty filename"}), 400

    if not _allowed(f.filename):
        return jsonify({"error": "File type not allowed"}), 400

    # Safe filename: timestamp prefix prevents collisions
    from werkzeug.utils import secure_filename
    orig = secure_filename(f.filename)
    ts   = datetime.now().strftime("%Y%m%d_%H%M%S_")
    dest = TRAINING_ROOT / dept
    dest.mkdir(parents=True, exist_ok=True)
    save_path = dest / (ts + orig)
    f.save(save_path)

    return jsonify({
        "success":  True,
        "filename": ts + orig,
        "url":      f"/api/mis/training/serve/{dept}/{ts + orig}",
    })


@mis_bp.route("/api/mis/training/delete", methods=["DELETE"])
def mis_delete_training():
    """Delete a training image by its serve URL."""
    if _login_required():
        return jsonify({"error": "Unauthorized"}), 401

    data = request.get_json(silent=True) or {}
    url  = data.get("url", "").strip()

    # url format: /api/mis/training/serve/<dept>/<filename>
    prefix = "/api/mis/training/serve/"
    if not url.startswith(prefix):
        return jsonify({"error": "Invalid URL"}), 400

    parts = url[len(prefix):].split("/", 1)
    if len(parts) != 2:
        return jsonify({"error": "Malformed URL"}), 400

    dept, filename = parts
    dept = _safe_dept(dept)
    if not dept:
        return jsonify({"error": "Invalid department"}), 400

    # Prevent path traversal
    from werkzeug.utils import secure_filename
    safe_name = secure_filename(filename)
    target    = TRAINING_ROOT / dept / safe_name

    if not target.exists():
        return jsonify({"error": "File not found"}), 404

    target.unlink()
    return jsonify({"success": True, "deleted": safe_name})


@mis_bp.route("/api/mis/training/serve/<department>/<filename>")
def mis_serve_training(department, filename):
    """Serve a training image file."""
    dept = _safe_dept(department)
    if not dept:
        return jsonify({"error": "Invalid department"}), 400
    folder = TRAINING_ROOT / dept
    return send_from_directory(folder, filename)