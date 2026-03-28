"""
PROJECT HANDOVER ROUTES
File upload/list/delete/serve for project handover workspace.
Training image upload/list/serve.
"""
from flask import Blueprint, request, jsonify, session, url_for, send_from_directory
from datetime import datetime
import os

from decorators import login_required
from config import BASE_DIR, UPLOAD_ROOT, TRAINING_UPLOAD_ROOT, CATEGORIES, ALLOWED_EXTENSIONS, ALLOWED_IMAGE_EXT
from audit import log_audit_action
from werkzeug.utils import secure_filename

project_handover_bp = Blueprint("project_handover", __name__)


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def allowed_image(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_IMAGE_EXT


# ─────────────────────────────────────────────────────────────────────────────
# PROJECT HANDOVER FILE ROUTES
# ─────────────────────────────────────────────────────────────────────────────

@project_handover_bp.route("/api/upload/<category>", methods=["POST"])
@login_required
def upload_file(category):
    """Upload file to project handover category."""
    if category not in CATEGORIES:
        return jsonify({"error": "Invalid category"}), 400
    if "file" not in request.files:
        return jsonify({"error": "No file"}), 400
    file = request.files["file"]
    if file.filename == "":
        return jsonify({"error": "Empty filename"}), 400

    save_dir = UPLOAD_ROOT / category
    save_dir.mkdir(parents=True, exist_ok=True)
    filename  = secure_filename(file.filename)
    save_path = save_dir / filename
    file.save(save_path)
    log_audit_action("File Upload", "ProjectHandover", filename)
    return jsonify({"message": "Uploaded successfully", "filename": filename})


@project_handover_bp.route("/api/list/<category>")
@login_required
def list_files(category):
    """List files in project handover category."""
    if category not in CATEGORIES:
        return jsonify([])
    folder = UPLOAD_ROOT / category
    if not folder.exists():
        folder.mkdir(parents=True, exist_ok=True)
        return jsonify([])
    files = []
    for f in sorted(folder.iterdir(), key=lambda x: x.stat().st_mtime, reverse=True):
        if f.is_file():
            files.append({
                "name": f.name,
                "size": f"{round(f.stat().st_size / 1024, 1)} KB",
                "date": datetime.fromtimestamp(f.stat().st_mtime).strftime("%Y-%m-%d %H:%M"),
            })
    return jsonify(files)


@project_handover_bp.route("/api/folder/<category>")
@login_required
def folder_count(category):
    """Alias for list_files — used by file-count tiles."""
    return list_files(category)


@project_handover_bp.route("/api/delete/<category>/<filename>", methods=["DELETE"])
@login_required
def delete_file(category, filename):
    """Delete file from project handover."""
    if category not in CATEGORIES:
        return jsonify({"success": False, "error": "Invalid category"}), 400
    file_path = UPLOAD_ROOT / category / filename
    if file_path.exists():
        os.remove(file_path)
        log_audit_action("File Delete", "ProjectHandover", filename)
        return jsonify({"success": True})
    return jsonify({"success": False, "error": "File not found"}), 404


@project_handover_bp.route("/files/<category>/<filename>")
@login_required
def serve_file(category, filename):
    """Serve project handover file."""
    return send_from_directory(UPLOAD_ROOT / category, filename)


@project_handover_bp.route("/uploads/<category>/<filename>")
@login_required
def serve_upload(category, filename):
    """Serve upload file."""
    return send_from_directory(UPLOAD_ROOT / category, filename)


# ─────────────────────────────────────────────────────────────────────────────
# TRAINING IMAGES
# ─────────────────────────────────────────────────────────────────────────────

@project_handover_bp.route("/api/training/list")
@login_required
def list_training_images():
    """List training images by department."""
    dept = request.args.get("department", "").strip()
    if not dept:
        return jsonify({"error": "Department required"}), 400
    dest_dir = TRAINING_UPLOAD_ROOT / dept
    if not dest_dir.exists():
        return jsonify({"department": dept, "files": []})
    files = []
    for p in sorted(dest_dir.iterdir(), key=lambda x: x.name):
        if p.is_file() and allowed_image(p.name):
            files.append({
                "name": p.name,
                "url":  url_for("project_handover.serve_training_image",
                                department=dept, filename=p.name),
                "size": f"{round(p.stat().st_size / 1024, 1)} KB",
                "date": datetime.fromtimestamp(p.stat().st_mtime).strftime("%Y-%m-%d"),
            })
    return jsonify({"department": dept, "files": files})


@project_handover_bp.route("/api/training/upload", methods=["POST"])
@login_required
def upload_training_image():
    """Upload training image."""
    dept = request.form.get("department", "").strip()
    if not dept:
        return jsonify({"error": "Department required"}), 400
    if "file" not in request.files:
        return jsonify({"error": "No file"}), 400
    file = request.files["file"]
    if not file or file.filename == "":
        return jsonify({"error": "Empty filename"}), 400
    if not allowed_image(file.filename):
        return jsonify({"error": "Invalid file type"}), 400

    dest_dir = TRAINING_UPLOAD_ROOT / dept
    dest_dir.mkdir(parents=True, exist_ok=True)
    filename  = secure_filename(file.filename)
    save_path = dest_dir / filename
    file.save(save_path)
    log_audit_action("Training Image Upload", "Training", f"{dept}/{filename}")
    return jsonify({"success": True, "filename": filename})


@project_handover_bp.route("/uploads/training/<department>/<filename>")
def serve_training_image(department, filename):
    """Serve training image."""
    return send_from_directory(TRAINING_UPLOAD_ROOT / department, filename)
