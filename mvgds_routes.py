"""
MVGDS ROUTES
Maintenance & Vendor Governance Documentation Suite.
Checklist template upload/list/download/delete per department.
"""
from flask import Blueprint, request, jsonify, send_file, abort
from werkzeug.utils import secure_filename

from decorators import login_required
from config import BASE_DIR
from audit import log_audit_action

mvgds_bp = Blueprint("mvgds", __name__)

# ── Constants ─────────────────────────────────────────────────────────────────
CHECKLIST_DEPTS   = {"mep", "hk", "sec", "fire"}
CHECKLIST_ALLOWED = {"xlsx", "xls", "docx", "doc", "pdf"}
CHECKLIST_ROOT    = BASE_DIR / "uploads" / "checklist_templates"

# Ensure department directories exist
for _dept in CHECKLIST_DEPTS:
    (CHECKLIST_ROOT / _dept).mkdir(parents=True, exist_ok=True)


# ─────────────────────────────────────────────────────────────────────────────
# UPLOAD
# ─────────────────────────────────────────────────────────────────────────────

@mvgds_bp.route("/api/checklist/upload/<dept>", methods=["POST"])
@login_required
def checklist_upload(dept):
    """Upload a checklist template file to a department folder."""
    if dept not in CHECKLIST_DEPTS:
        return jsonify({"success": False, "error": f"Unknown department: {dept}"}), 400
    if "file" not in request.files:
        return jsonify({"success": False, "error": "No file provided"}), 400

    file = request.files["file"]
    if not file or file.filename == "":
        return jsonify({"success": False, "error": "Empty filename"}), 400

    ext = file.filename.rsplit(".", 1)[-1].lower()
    if ext not in CHECKLIST_ALLOWED:
        return jsonify({"success": False,
                        "error": f"File type .{ext} not allowed. Use: xlsx, xls, docx, doc, pdf"}), 400

    filename  = secure_filename(file.filename)
    dest_dir  = CHECKLIST_ROOT / dept
    dest_path = dest_dir / filename

    # Avoid overwriting — append counter suffix if exists
    if dest_path.exists():
        stem, suffix = dest_path.stem, dest_path.suffix
        counter = 1
        while (dest_dir / f"{stem}_{counter}{suffix}").exists():
            counter += 1
        filename  = f"{stem}_{counter}{suffix}"
        dest_path = dest_dir / filename

    file.save(dest_path)
    log_audit_action("Checklist Upload", "MVGDS", f"{dept}/{filename}")

    return jsonify({
        "success":  True,
        "dept":     dept,
        "filename": filename,
        "size":     dest_path.stat().st_size,
        "ext":      ext,
    })


# ─────────────────────────────────────────────────────────────────────────────
# LIST
# ─────────────────────────────────────────────────────────────────────────────

@mvgds_bp.route("/api/checklist/list/<dept>")
@login_required
def checklist_list(dept):
    """Return list of uploaded checklist templates for a department."""
    if dept not in CHECKLIST_DEPTS:
        return jsonify({"success": False, "error": "Unknown department"}), 400

    dept_dir = CHECKLIST_ROOT / dept
    files    = []
    if dept_dir.exists():
        for p in sorted(dept_dir.iterdir()):
            if p.is_file() and p.suffix.lstrip(".").lower() in CHECKLIST_ALLOWED:
                files.append({
                    "filename": p.name,
                    "ext":      p.suffix.lstrip(".").lower(),
                    "size":     p.stat().st_size,
                    "modified": int(p.stat().st_mtime * 1000),
                })
    return jsonify({"success": True, "dept": dept, "files": files})


# ─────────────────────────────────────────────────────────────────────────────
# DOWNLOAD / SERVE
# ─────────────────────────────────────────────────────────────────────────────

@mvgds_bp.route("/api/checklist/download/<dept>/<filename>")
@login_required
def checklist_download(dept, filename):
    """Serve/download a checklist template file."""
    if dept not in CHECKLIST_DEPTS:
        abort(404)

    safe_name = secure_filename(filename)
    file_path = CHECKLIST_ROOT / dept / safe_name

    if not file_path.exists() or not file_path.is_file():
        abort(404)

    ext          = safe_name.rsplit(".", 1)[-1].lower()
    as_attachment = ext != "pdf"   # PDFs served inline so viewer modal can embed

    return send_file(file_path, as_attachment=as_attachment, download_name=safe_name)


# ─────────────────────────────────────────────────────────────────────────────
# DELETE
# ─────────────────────────────────────────────────────────────────────────────

@mvgds_bp.route("/api/checklist/delete/<dept>/<filename>", methods=["DELETE"])
@login_required
def checklist_delete(dept, filename):
    """Delete a checklist template file."""
    if dept not in CHECKLIST_DEPTS:
        return jsonify({"success": False, "error": "Unknown department"}), 400

    safe_name = secure_filename(filename)
    file_path = CHECKLIST_ROOT / dept / safe_name

    if not file_path.exists():
        return jsonify({"success": False, "error": "File not found"}), 404

    file_path.unlink()
    log_audit_action("Checklist Delete", "MVGDS", f"{dept}/{safe_name}")
    return jsonify({"success": True, "deleted": safe_name})
