"""
audit.py — Shared audit logging helper.
Imports from models only (no dependency on server.py).
Uses current_app so it works inside any request or app context.
"""
from flask import session, request, current_app
from models import db, AuditLog


def log_audit_action(action, entity_type, entity_id):
    """Log audit action to database — never raises."""
    try:
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
