"""
DECORATORS
Shared authentication/authorization decorators.
Imported by server.py AND all blueprint files — avoids circular imports.
"""

from functools import wraps
from flask import session, request, jsonify, redirect, url_for, abort


# ─── API path prefixes that should return JSON errors instead of redirects ───
API_PREFIXES = (
    "/ow_api/", "/api/", "/inventory/", "/ow_work_track/",
    "/sln_work_track/", "/ow_vms/", "/ow_mail/", "/ow_sec", "/ow_security",
    "/sln_fire/api/", "/sln_hk/api/", "/sln_sec/api/",
    "/ow_fire/api/", "/td_fire/api/", "/ogm_fire/api/",
)

BYPASS_ROLES = {"admin", "management", "general manager", "property manager"}


def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if "user" not in session:
            if request.path.startswith(API_PREFIXES):
                return jsonify({"success": False, "error": "Not authenticated"}), 401
            return redirect(url_for("auth.login") + "?next=" + request.path)
        return f(*args, **kwargs)
    return wrapper


def require_property(property_name):
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            if "user" not in session:
                if request.path.startswith(API_PREFIXES):
                    return jsonify({"success": False, "error": "Not authenticated"}), 401
                return redirect(url_for("auth.login"))
            if (session.get("role") or "").lower() in BYPASS_ROLES:
                return fn(*args, **kwargs)
            if request.path.startswith(API_PREFIXES):
                if property_name in session.get("properties", []):
                    session["active_property"] = property_name
                    return fn(*args, **kwargs)
                return jsonify({"success": False, "error": f"No access to {property_name}"}), 403
            if session.get("active_property") != property_name:
                abort(403)
            return fn(*args, **kwargs)
        return wrapper
    return decorator


def require_role(required_role):
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            if "user" not in session:
                return redirect(url_for("auth.login"))
            if session.get("role") != required_role and session.get("role") != "admin":
                abort(403)
            return fn(*args, **kwargs)
        return wrapper
    return decorator
