"""
PORTAL ROUTES
Miscellaneous page routes: CAM, MIS, KRA, documents, issues, vendor_visit,
inventory dashboard, energy portal, GM dashboard, OW VMS, OW occupancy,
SLN HK/Sec/Fire portals, MVGDS page.
"""
from flask import Blueprint, render_template, session, redirect, url_for
from decorators import login_required, require_property, require_role

portal_bp = Blueprint("portal", __name__)

# ── General page routes ───────────────────────────────────────────────────────

@portal_bp.route("/inventory_dashboard")
@login_required
def inventory_dashboard():
    return render_template("inventory_dashboard.html")


@portal_bp.route("/tenant")
@login_required
def tenant():
    return render_template("tenant.html")


@portal_bp.route("/cam_charges")
@login_required
def cam_charges_page():
    return render_template("cam_charges.html")


@portal_bp.route("/cam_review")
@login_required
def cam_review():
    return render_template("cam_review.html")


@portal_bp.route("/pm_dashboard")
@login_required
def pm_dashboard():
    return render_template("pm_dashboard.html")


@portal_bp.route("/property-manager-updates")
@login_required
def pm_daily_updates_page():
    return render_template("pm_daily_updates.html")


@portal_bp.route("/gm_dashboard")
@require_role("General Manager")
def gm_dashboard():
    return render_template("gm_dashboard.html")


@portal_bp.route("/documents")
@login_required
def documents():
    return render_template("documents.html")


@portal_bp.route("/issues")
@login_required
def issues():
    return render_template("issues.html")


@portal_bp.route("/vendor_visit")
@login_required
def vendor_visit():
    return render_template("vendor_visit.html")


@portal_bp.route("/mis")
@login_required
def mis():
    return render_template("mis.html")


@portal_bp.route("/kra")
@login_required
def kra():
    return render_template("kra.html")


@portal_bp.route("/energy")
@login_required
@require_property("SLN Terminus")
def energy():
    """SLN Energy Module"""
    return render_template("energy.html")


# ── SLN Housekeeping / Security / Fire portals ────────────────────────────────

@portal_bp.route("/sln_hk")
@login_required
def sln_hk_portal():
    """SLN Housekeeping Module — redirects to blueprint dashboard"""
    return redirect(url_for("sln_hk.sln_hk_dashboard"))


@portal_bp.route("/sln_sec")
@login_required
@require_property("SLN Terminus")
def sln_sec_portal():
    """SLN Security Module — redirects to blueprint dashboard"""
    return redirect("/sln_hk_sec/")


@portal_bp.route("/sln_fire_portal")
@login_required
@require_property("SLN Terminus")
def sln_fire_portal():
    """SLN Fire Fighting Module"""
    return redirect("/sln_fire/")


# ── ONEWEST portals ───────────────────────────────────────────────────────────

@portal_bp.route("/ow_issues")
@login_required
@require_property("ONEWEST")
def ow_issues():
    """ONEWEST Issues Dashboard"""
    session["active_property"] = "ONEWEST"
    session["property_code"]   = "OW"
    print(f"\n🏢 Accessing ONEWEST Issues - User: {session.get('user')}")
    return render_template("issues/ow_issues.html")


@portal_bp.route("/ow_vms")
@login_required
@require_property("ONEWEST")
def ow_vms():
    """ONEWEST Visitor Management System Portal"""
    session["active_property"] = "ONEWEST"
    session["property_code"]   = "OW"
    print(f"\n🏢 Accessing ONEWEST VMS - User: {session.get('user')}")
    return render_template("ow_vms.html")


@portal_bp.route("/ow_ppm_dashboard")
@login_required
@require_property("ONEWEST")
def ow_ppm_dashboard():
    """ONEWEST PPM Dashboard"""
    session["active_property"] = "ONEWEST"
    return render_template("ow_ppm_dashboard.html")


@portal_bp.route("/ow_occupancy")
@login_required
@require_property("ONEWEST")
def ow_occupancy_page():
    """ONEWEST Space Occupancy dashboard."""
    session["active_property"] = "ONEWEST"
    session["property_code"]   = "OW"
    print(f"\n🏢 Accessing OW Occupancy — User: {session.get('user')}")
    return render_template("ow_occupancy.html")


# ── MVGDS page ────────────────────────────────────────────────────────────────

@portal_bp.route("/mvgds")
@login_required
@require_property("SLN Terminus")
def mvgds():
    """Maintenance & Vendor Governance Documentation Suite"""
    print(f"\n📋 Accessing MVGDS - User: {session.get('user')}")
    return render_template("mvgds.html")


# ── SLN Occupancy page ────────────────────────────────────────────────────────

@portal_bp.route("/sln_occupancy")
@login_required
def sln_occupancy():
    return render_template("sln_occupancy.html")


# ── Project Handover pages ────────────────────────────────────────────────────

@portal_bp.route("/project_handover")
@login_required
def project_handover():
    return render_template("project_handover_workspace.html")


@portal_bp.route("/project_handover_workspace")
@login_required
def project_handover_workspace():
    return render_template("project_handover_workspace.html")
