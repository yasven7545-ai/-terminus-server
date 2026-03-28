"""
TERMINUS MMS — WEB ROUTES  (web_routes.py)
==========================================
Blueprint that holds every session-authenticated *page* route
(GET → render_template).  All API endpoints remain in server.py
or their own blueprint files.  Logic is identical to server.py;
only the registration mechanism changes (Blueprint instead of @app).

Registration in server.py (add after existing blueprint registrations):
    from web_routes import web_bp
    app.register_blueprint(web_bp)

NOTE: login_required, require_property, and USERS are imported from
server.py at runtime to avoid circular imports.
"""

from flask import (
    Blueprint, render_template, request, redirect,
    url_for, session, jsonify, abort
)

web_bp = Blueprint("web_bp", __name__)


# ── Lazy imports from server (avoids circular import at module load) ──────────

def _login_required():
    import server as _s
    return _s.login_required

def _require_property():
    import server as _s
    return _s.require_property

def _USERS():
    import server as _s
    return _s.USERS

def _ROLE_MODULES():
    import server as _s
    return _s.ROLE_MODULES

def _PROPERTY_MODULES():
    import server as _s
    return _s.PROPERTY_MODULES


# ── Decorator shims that pull the real decorators at call time ────────────────

from functools import wraps

def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        return _login_required()(f)(*args, **kwargs)
    return wrapper

def require_property(prop):
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            return _require_property()(prop)(f)(*args, **kwargs)
        return wrapper
    return decorator


# =====================================================================
# HOME / LOGIN / LOGOUT / DASHBOARD
# (Duplicated here so web_bp covers these routes when server.py delegates)
# These are NO-OPs if server.py already registers them directly — Flask
# raises no error because Blueprint routes don't conflict with app routes
# unless registered with the same endpoint name. Use url_prefix="" to
# keep paths identical.
# =====================================================================

@web_bp.route("/web/dashboard")
@login_required
def wb_dashboard():
    """Alias dashboard accessible via /web/dashboard."""
    return render_template("dashboard.html")


# =====================================================================
# PROPERTY PORTAL PAGES
# =====================================================================

@web_bp.route("/web/sln_terminus")
@login_required
@require_property("SLN Terminus")
def wb_sln_terminus():
    session["active_property"] = "SLN Terminus"
    return render_template("sln_terminus.html")


@web_bp.route("/web/sln_pm_daily")
@login_required
@require_property("SLN Terminus")
def wb_sln_pm_daily():
    session["active_property"] = "SLN Terminus"
    return render_template("sln_pm_daily.html")


@web_bp.route("/web/mvgds")
@login_required
@require_property("SLN Terminus")
def wb_mvgds():
    session["active_property"] = "SLN Terminus"
    return render_template("mvgds.html")


@web_bp.route("/web/the_district")
@login_required
@require_property("The District")
def wb_the_district():
    session["active_property"] = "The District"
    return render_template("the_district.html")


@web_bp.route("/web/ogm")
@login_required
@require_property("One Golden Mile")
def wb_ogm():
    session["active_property"] = "One Golden Mile"
    return render_template("ogm.html")


@web_bp.route("/web/ogm_pm_daily")
@login_required
@require_property("One Golden Mile")
def wb_ogm_pm_daily():
    session["active_property"] = "One Golden Mile"
    return render_template("ogm_pm_daily.html")


@web_bp.route("/web/nine_hills")
@login_required
@require_property("Nine Hills")
def wb_nine_hills():
    session["active_property"] = "Nine Hills"
    return render_template("nine_hills.html")


@web_bp.route("/web/onewest")
@login_required
@require_property("ONEWEST")
def wb_onewest():
    session["active_property"] = "ONEWEST"
    return render_template("onewest.html")


# =====================================================================
# COMMAND CENTER
# =====================================================================

@web_bp.route("/web/command_center")
@login_required
def wb_command_center():
    return render_template("command_center.html")


# =====================================================================
# PPM / MMS
# =====================================================================

@web_bp.route("/web/ow_ppm_dashboard")
@login_required
@require_property("ONEWEST")
def wb_ow_ppm_dashboard():
    session["active_property"] = "ONEWEST"
    return render_template("ow_ppm_dashboard.html")


@web_bp.route("/web/sln_mms_dashboard")
@login_required
@require_property("SLN Terminus")
def wb_sln_mms_dashboard():
    session["active_property"] = "SLN Terminus"
    return render_template("sln_mms_dashboard.html")


# =====================================================================
# ENERGY ANALYTICS
# =====================================================================

@web_bp.route("/web/energy")
@login_required
@require_property("SLN Terminus")
def wb_energy():
    session["active_property"] = "SLN Terminus"
    return render_template("energy.html")


@web_bp.route("/web/ow_energy")
@login_required
@require_property("ONEWEST")
def wb_ow_energy():
    session["active_property"] = "ONEWEST"
    return render_template("ow_energy.html")


# =====================================================================
# SPACE OCCUPANCY
# =====================================================================

@web_bp.route("/web/sln_occupancy")
@login_required
@require_property("SLN Terminus")
def wb_sln_occupancy():
    session["active_property"] = "SLN Terminus"
    return render_template("sln_occupancy.html")


# =====================================================================
# CAM BILLING
# =====================================================================

@web_bp.route("/web/cam_charges")
@login_required
@require_property("SLN Terminus")
def wb_cam_charges():
    session["active_property"] = "SLN Terminus"
    return render_template("cam_charges.html")


# =====================================================================
# PROJECT HANDOVER
# =====================================================================

@web_bp.route("/web/project_handover")
@login_required
@require_property("SLN Terminus")
def wb_project_handover():
    session["active_property"] = "SLN Terminus"
    return render_template("project_handover.html")


@web_bp.route("/web/ow_hoto")
@login_required
@require_property("ONEWEST")
def wb_ow_hoto():
    session["active_property"] = "ONEWEST"
    return render_template("ow_hoto.html")


# =====================================================================
# GM DASHBOARD / TASKS
# =====================================================================

@web_bp.route("/web/gm_dashboard")
@login_required
def wb_gm_dashboard():
    return render_template("gm_dashboard.html")


@web_bp.route("/web/gm_tasks")
@login_required
def wb_gm_tasks():
    return render_template("gm_tasks.html")


# =====================================================================
# HOUSEKEEPING
# =====================================================================

@web_bp.route("/web/sln_hk")
@login_required
@require_property("SLN Terminus")
def wb_sln_hk():
    session["active_property"] = "SLN Terminus"
    return render_template("sln_hk.html")


@web_bp.route("/web/ow_hk")
@login_required
@require_property("ONEWEST")
def wb_ow_hk():
    session["active_property"] = "ONEWEST"
    return render_template("ow_hk.html")


# =====================================================================
# SECURITY
# =====================================================================

@web_bp.route("/web/sln_sec")
@login_required
@require_property("SLN Terminus")
def wb_sln_sec():
    session["active_property"] = "SLN Terminus"
    return render_template("sln_sec.html")


@web_bp.route("/web/ow_sec")
@login_required
@require_property("ONEWEST")
def wb_ow_sec():
    session["active_property"] = "ONEWEST"
    return render_template("ow_sec.html")


# =====================================================================
# FIRE FIGHTING
# =====================================================================

@web_bp.route("/web/sln_fire")
@login_required
@require_property("SLN Terminus")
def wb_sln_fire():
    session["active_property"] = "SLN Terminus"
    return render_template("sln_fire.html")


@web_bp.route("/web/ow_fire")
@login_required
@require_property("ONEWEST")
def wb_ow_fire():
    session["active_property"] = "ONEWEST"
    return render_template("ow_fire.html")


@web_bp.route("/web/td_fire")
@login_required
@require_property("The District")
def wb_td_fire():
    session["active_property"] = "The District"
    return render_template("td_fire.html")


@web_bp.route("/web/ogm_fire")
@login_required
def wb_ogm_fire():
    session["active_property"] = "One Golden Mile"
    return render_template("ogm_fire.html")


# =====================================================================
# RESOURCE MANAGEMENT / BUDGET
# =====================================================================

@web_bp.route("/web/sln_resource_mgmt")
@login_required
@require_property("SLN Terminus")
def wb_sln_resource_mgmt():
    session["active_property"] = "SLN Terminus"
    return render_template("sln_resource_mgmt.html")


@web_bp.route("/web/sln_budget")
@login_required
@require_property("SLN Terminus")
def wb_sln_budget():
    session["active_property"] = "SLN Terminus"
    return render_template("sln_budget.html")


# =====================================================================
# DOCUMENTS
# =====================================================================

@web_bp.route("/web/documents")
@login_required
def wb_documents():
    return render_template("documents.html")


# =====================================================================
# KRA / MIS
# =====================================================================

@web_bp.route("/web/ow_kra")
@login_required
@require_property("ONEWEST")
def wb_ow_kra():
    session["active_property"] = "ONEWEST"
    return render_template("ow_kra.html")


@web_bp.route("/web/ow_pm_daily")
@login_required
@require_property("ONEWEST")
def wb_ow_pm_daily():
    session["active_property"] = "ONEWEST"
    return render_template("ow_pm_daily.html")


# =====================================================================
# ISSUES
# =====================================================================

@web_bp.route("/web/issues")
@login_required
def wb_issues():
    return render_template("issues.html")


# =====================================================================
# VENDOR VISIT
# =====================================================================

@web_bp.route("/web/vendor_visit")
@login_required
def wb_vendor_visit():
    return render_template("vendor_visit.html")
