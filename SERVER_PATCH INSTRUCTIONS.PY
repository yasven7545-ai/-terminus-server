"""
SERVER.PY — PATCH INSTRUCTIONS
================================
Add the following TWO blocks to your existing server.py.
Do NOT replace the entire file — just insert these snippets.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PATCH 1 — Register breakdown blueprint
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Find the block that starts with:
    # =====================================================
    # 2. SAFE BLUEPRINT REGISTRATION
    # =====================================================

Add this line anywhere inside that block (after the other safe_register calls):

    safe_register("breakdown_routes", "breakdown_bp")

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PATCH 2 — Command Center route
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Add this route anywhere in Section 8 (Property Dashboard Routes),
e.g. right after the /dashboard route:
"""

# ── paste this into server.py ────────────────────────────────────────────────

# =====================================================
# COMMAND CENTER (global — all properties)
# =====================================================
from flask import Flask, render_template, request, redirect, url_for, session, jsonify

# Place this safe_register call with the other blueprint registrations (Patch 1):
#   safe_register("breakdown_routes", "breakdown_bp")

# Place this route in Section 8 alongside other property routes (Patch 2):
# @app.route("/command_center")
# @login_required
# def command_center():
#     """Global Command Center — all 5 properties, operational tabs"""
#     return render_template("command_center.html")