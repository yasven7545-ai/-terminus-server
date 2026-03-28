"""
═══════════════════════════════════════════════════════════════════════
SERVER.PY  —  SECURITY MODULE PATCH
Add the following blocks to server.py at the marked positions.
═══════════════════════════════════════════════════════════════════════
"""

# ─────────────────────────────────────────────────────────────────────
# STEP 1  ►  Add this import near the top of server.py
#            (after the other safe_register calls, ~line 174)
# ─────────────────────────────────────────────────────────────────────

safe_register("sln_sec_routes", "sln_sec_bp")          # ← ADD THIS LINE


# ─────────────────────────────────────────────────────────────────────
# STEP 2  ►  Add this route anywhere in the routes section
#            (e.g. after the sln_hk_portal route, ~line 4753)
# ─────────────────────────────────────────────────────────────────────

from flask import Flask, render_template, request, redirect, url_for, session, jsonify, send_from_directory, abort, send_file, Blueprint
from functools import wraps

# NOTE: login_required and require_property are already defined in server.py

@app.route("/sln_sec")
@login_required
@require_property("SLN Terminus")
def sln_sec_portal():
    """SLN Terminus — Security Module portal page."""
    return redirect("/sln_hk_sec/")


# ─────────────────────────────────────────────────────────────────────
# STEP 3  ►  Add "security" to PROPERTY_MODULES and ROLE_MODULES
#            so access-control gating works (optional — depends on
#            whether you want to gate this module by role).
#
#  In PROPERTY_MODULES["SLN Terminus"], append:
#      "security"
#
#  In ROLE_MODULES, add "security" to whichever roles should see it.
#  Example:
#      ALL_MODULES = [..., "security"]        # already full
#      "Executive":  [..., "security"],
#      "Supervisor": [..., "security"],
#      "Technician": [..., "security"],
# ─────────────────────────────────────────────────────────────────────


# ─────────────────────────────────────────────────────────────────────
# STEP 4  ►  Print entry added to the startup banner (~line 4793)
# ─────────────────────────────────────────────────────────────────────
#   🔒 SLN Security:       http://localhost:5000/sln_sec
# ─────────────────────────────────────────────────────────────────────