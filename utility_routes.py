"""
UTILITY ROUTES
Health check, datetime API, favicon, error handlers, and audit log helper.
"""
from flask import Blueprint, jsonify, request, redirect, url_for, session, render_template
from datetime import datetime

from models import db, AuditLog
from decorators import login_required

utility_bp = Blueprint("utility", __name__)


# ─────────────────────────────────────────────────────────────────────────────
# UTILITY ENDPOINTS
# ─────────────────────────────────────────────────────────────────────────────

@utility_bp.route("/api/datetime")
def get_datetime():
    return jsonify({
        "current_datetime": datetime.now().strftime("%A, %B %d, %Y | %I:%M %p"),
        "server_time":      datetime.now().isoformat(),
    })


@utility_bp.route("/health")
def health_check():
    return jsonify({
        "status":    "healthy",
        "service":   "Terminus MMS",
        "timestamp": datetime.now().isoformat(),
        "version":   "3.0.0",
    }), 200


@utility_bp.route("/favicon.ico")
def favicon():
    return "", 204


# ─────────────────────────────────────────────────────────────────────────────
# AUDIT LOGGING HELPER
# ─────────────────────────────────────────────────────────────────────────────

def log_audit_action(action, entity_type, entity_id):
    """Log audit action to database. Safe — never raises."""
    try:
        from flask import current_app
        with current_app.app_context():
            log = AuditLog(
                user_id     = session.get("user_id", 0),
                username    = session.get("user",    "system"),
                action      = action,
                entity_type = entity_type,
                entity_id   = str(entity_id),
                ip_address  = request.remote_addr if request else "127.0.0.1",
            )
            db.session.add(log)
            db.session.commit()
    except Exception:
        pass


# ─────────────────────────────────────────────────────────────────────────────
# ERROR HANDLERS
# (Register on the app object in server.py, not on the blueprint directly,
#  because Flask error handlers on blueprints don't catch app-wide errors.)
# These functions are imported and registered in server.py.
# ─────────────────────────────────────────────────────────────────────────────

def handle_404(e):
    if request.path.startswith("/api/"):
        return jsonify({"error": "Not Found", "message": "Resource not found"}), 404
    return render_template("onewest.html", error_code=404), 404


def handle_403(e):
    if "user" not in session:
        return redirect(url_for("auth.login"))
    if request.path.startswith(("/ow_api/", "/api/", "/inventory/",
                                "/ow_work_track/", "/sln_work_track/",
                                "/ow_vms/", "/ow_mail/")):
        return jsonify({"success": False, "error": "Access denied — check your active property"}), 403
    return render_template("dashboard.html", error="Access denied"), 403


def handle_500(e):
    print(f"500 Error: {str(e)}")
    if request.path.startswith(("/ow_api/", "/api/", "/inventory/",
                                "/ow_work_track/", "/sln_work_track/",
                                "/ow_vms/", "/ow_mail/")):
        return jsonify({"success": False, "error": f"Server error: {str(e)}"}), 500
    return render_template("error.html", error_code=500), 500
