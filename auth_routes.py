"""
AUTH ROUTES
Login, logout, dashboard, user profile, and property portal page routes.
"""
from flask import Blueprint, render_template, request, redirect, url_for, session, jsonify, abort
from functools import wraps

auth_bp = Blueprint("auth", __name__)

# ── Import shared config from server ─────────────────────────────────────────
# These are defined in server.py and passed via app context or imported directly.
# In production, import USERS, ROLE_MODULES, PROPERTY_MODULES from a config module.
from decorators import login_required, require_property, require_role
from config import USERS, ROLE_MODULES, PROPERTY_MODULES

# =====================================================
# AUTHENTICATION ROUTES
# =====================================================
@auth_bp.route("/")
def home():
    if "user" in session:
        return redirect(url_for("auth.dashboard"))
    return redirect(url_for("auth.login"))


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    error = None

    if request.method == "POST":
        username      = request.form.get("username", "").strip()
        password      = request.form.get("password", "").strip()
        property_name = request.form.get("property", "").strip()

        print(f"\n🔐 Login Attempt:")
        print(f"   Username: {username}")
        print(f"   Property: {property_name}")
        print(f"   Available Users: {list(USERS.keys())}")

        if username not in USERS:
            error = "User not found. Please check your username."
            print(f"   ❌ Error: {error}")
            return render_template("dashboard.html", error=error)

        user_data = USERS[username]

        if user_data["password"] != password:
            error = "Invalid password. Please try again."
            print(f"   ❌ Error: {error}")
            return render_template("dashboard.html", error=error)

        if property_name and property_name not in user_data["properties"]:
            error = f"You don't have access to {property_name}. Please select another property."
            print(f"   ❌ Error: {error}")
            print(f"   User Properties: {user_data['properties']}")
            return render_template("dashboard.html", error=error)

        session.clear()
        session.permanent = True
        session["user"]            = username
        session["role"]            = user_data["role"]
        session["properties"]      = user_data["properties"]
        session["active_property"] = property_name or user_data["properties"][0]
        session["logged_in"]       = True

        print(f"   ✅ Login successful!")
        print(f"   Role: {session['role']}")
        print(f"   Active Property: {session['active_property']}")

        next_url = (
            request.args.get("next", "").strip() or
            request.form.get("next", "").strip()
        )
        if next_url and next_url.startswith("/") and not next_url.startswith("//"):
            print(f"   ↪ Redirecting to next: {next_url}")
            return redirect(next_url)

        property_routes = {
            "SLN Terminus":    "auth.sln_terminus",
            "ONEWEST":         "auth.onewest",
            "The District":    "auth.the_district",
            "One Golden Mile": "auth.ogm",
            "Nine Hills":      "auth.nine_hills",
        }
        redirect_route = property_routes.get(property_name, "auth.dashboard")
        return redirect(url_for(redirect_route))

    return render_template("dashboard.html", error=error)


@auth_bp.route("/logout")
def logout():
    print(f"\n👋 Logout: {session.get('user')}")
    session.clear()
    return redirect(url_for("auth.login"))


@auth_bp.route("/dashboard")
@login_required
def dashboard():
    return render_template("dashboard.html")


# =====================================================
# USER PROFILE API
# =====================================================
@auth_bp.route("/api/user_profile")
@login_required
def get_user_profile():
    role            = session.get("role", "Technician")
    active_property = session.get("active_property", "SLN Terminus")

    role_modules     = ROLE_MODULES.get(role, ROLE_MODULES.get("Technician", []))
    property_modules = PROPERTY_MODULES.get(active_property, [])

    full_access_roles = {"admin", "management", "general manager", "property manager"}
    if role.lower() in full_access_roles:
        allowed_modules = property_modules
    else:
        allowed_modules = [m for m in role_modules if m in property_modules]

    return jsonify({
        "username":        session.get("user", ""),
        "role":            role,
        "active_property": active_property,
        "properties":      session.get("properties", ["SLN Terminus"]),
        "allowed_modules": allowed_modules,
    })


# =====================================================
# PROPERTY PORTAL PAGE ROUTES
# =====================================================
@auth_bp.route("/sln_terminus")
@login_required
@require_property("SLN Terminus")
def sln_terminus():
    print(f"\n🏢 Accessing SLN Terminus - User: {session.get('user')}")
    return render_template("sln_terminus.html")


@auth_bp.route("/sln_pm_daily")
@login_required
@require_property("SLN Terminus")
def sln_pm_daily_page():
    print(f"\n🗒️  Accessing SLN PM Daily - User: {session.get('user')}")
    return render_template("sln_pm_daily.html")


@auth_bp.route("/onewest")
@login_required
@require_property("ONEWEST")
def onewest():
    session["active_property"] = "ONEWEST"
    session["property_code"]   = "OW"
    print(f"\n🏢 Accessing ONEWEST - User: {session.get('user')}")
    print(f"   Active Property: {session.get('active_property')}")
    print(f"   User Role: {session.get('role')}")
    return render_template("onewest.html")


@auth_bp.route("/the_district")
@login_required
@require_property("The District")
def the_district():
    print(f"\n🏢 Accessing The District - User: {session.get('user')}")
    return render_template("the_district.html")


@auth_bp.route("/one_golden_mile")
def one_golden_mile_redirect():
    """Alias redirect — keeps old bookmarks working"""
    return redirect(url_for("auth.ogm"))


@auth_bp.route("/ogm")
@login_required
@require_property("One Golden Mile")
def ogm():
    print(f"\n🏢 Accessing One Golden Mile - User: {session.get('user')}")
    return render_template("ogm.html")


@auth_bp.route("/ogm_pm_daily")
@login_required
@require_property("One Golden Mile")
def ogm_pm_daily_page():
    print(f"\n🗒️  Accessing OGM PM Daily - User: {session.get('user')}")
    return render_template("ogm_pm_daily.html")


@auth_bp.route("/nine_hills")
@login_required
@require_property("Nine Hills")
def nine_hills():
    print(f"\n🏢 Accessing Nine Hills - User: {session.get('user')}")
    return render_template("nine_hills.html")


@auth_bp.route("/sln_work_track")
@login_required
@require_property("SLN Terminus")
def sln_work_track():
    return render_template("sln_work_track.html")


@auth_bp.route("/ow_work_track")
@login_required
@require_property("ONEWEST")
def ow_work_track():
    return render_template("ow_work_track.html")
