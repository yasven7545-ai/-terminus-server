"""
OW PM DAILY ROUTES — ONEWEST Property Management Daily Log
Blueprint: ow_pm_daily_bp
All routes, functions, and variables prefixed with ow_pm_daily_
Data directory: static/data/OW/pm_daily/
"""

import json
import os
import smtplib
import threading
from datetime import datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from functools import wraps
from pathlib import Path

from flask import (
    Blueprint, jsonify, render_template, request,
    session, redirect, url_for, send_file
)

# ──────────────────────────────────────────────────────────────────────────────
# BLUEPRINT
# ──────────────────────────────────────────────────────────────────────────────
ow_pm_daily_bp = Blueprint("ow_pm_daily", __name__)

# ──────────────────────────────────────────────────────────────────────────────
# PATHS
# ──────────────────────────────────────────────────────────────────────────────
_OW_BASE_DIR        = Path(__file__).parent.resolve()
_OW_PM_DAILY_DIR    = _OW_BASE_DIR / "static" / "data" / "OW" / "pm_daily"
_OW_PM_DAILY_DIR.mkdir(parents=True, exist_ok=True)

# ──────────────────────────────────────────────────────────────────────────────
# SEPARATE EMAIL CONFIGURATION
# ──────────────────────────────────────────────────────────────────────────────
OW_PM_SMTP_SERVER   = "smtp.gmail.com"
OW_PM_SMTP_PORT     = 587
OW_PM_SENDER_EMAIL  = "maintenance.slnterminus@gmail.com"
OW_PM_SENDER_PASS   = "xaottgrqtqnkouqn"
OW_PM_RECEIVERS     = [
    "maintenance.slnterminus@gmail.com",
    "yasven7545@gmail.com",
    "engineering@terminus-global.com",
]

# Thread lock — never share with other modules
_OW_PM_SMTP_LOCK    = threading.Lock()
_OW_PM_LAST_SEND    = {"ts": 0.0}
_OW_PM_MIN_GAP      = 6   # seconds

# ──────────────────────────────────────────────────────────────────────────────
# AUTH HELPERS
# ──────────────────────────────────────────────────────────────────────────────
def _ow_pm_login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if "user" not in session:
            if request.path.startswith("/ow_pm"):
                return jsonify({"success": False, "error": "Not authenticated"}), 401
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return wrapper


def _ow_pm_require_onewest(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if "user" not in session:
            return jsonify({"success": False, "error": "Not authenticated"}), 401
        bypass = {"admin", "management", "general manager", "property manager"}
        role   = (session.get("role") or "").lower()
        props  = session.get("properties", [])
        if role in bypass or "ONEWEST" in props:
            return f(*args, **kwargs)
        return jsonify({"success": False, "error": "Access denied — ONEWEST property required"}), 403
    return wrapper


# ──────────────────────────────────────────────────────────────────────────────
# DATA HELPERS
# ──────────────────────────────────────────────────────────────────────────────
def _ow_pm_daily_file(date_str: str) -> Path:
    """Return path to JSON file for a given date (YYYY-MM-DD)."""
    return _OW_PM_DAILY_DIR / f"{date_str}.json"


def _ow_pm_load_log(date_str: str) -> dict:
    """Load a daily log; return empty dict if not found."""
    fp = _ow_pm_daily_file(date_str)
    if fp.exists():
        try:
            with open(fp, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def _ow_pm_save_log(date_str: str, data: dict) -> None:
    """Persist a daily log to disk."""
    fp = _ow_pm_daily_file(date_str)
    with open(fp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def _ow_pm_all_logs() -> list:
    """Return all saved logs sorted newest-first."""
    logs = []
    for fp in sorted(_OW_PM_DAILY_DIR.glob("????-??-??.json"), reverse=True):
        try:
            with open(fp, "r", encoding="utf-8") as f:
                data = json.load(f)
            tasks = data.get("tasks", [])
            logs.append({
                "date":       data.get("date", fp.stem),
                "shift":      data.get("shift", "—"),
                "author":     data.get("author", "—"),
                "task_count": len(tasks),
                "completed":  sum(1 for t in tasks if t.get("status") == "Completed"),
                "high_prio":  sum(1 for t in tasks if t.get("priority") == "H"),
            })
        except Exception:
            pass
    return logs


# ──────────────────────────────────────────────────────────────────────────────
# SMTP SEND HELPER (isolated — never shares lock with server.py)
# ──────────────────────────────────────────────────────────────────────────────
def _ow_pm_smtp_send(msg_obj, caller="ow_pm"):
    """Thread-safe SMTP send with retry and minimum inter-send gap."""
    import time as _time
    with _OW_PM_SMTP_LOCK:
        gap = _time.time() - _OW_PM_LAST_SEND["ts"]
        if gap < _OW_PM_MIN_GAP:
            _time.sleep(_OW_PM_MIN_GAP - gap)
        for attempt in range(1, 4):
            try:
                with smtplib.SMTP(OW_PM_SMTP_SERVER, OW_PM_SMTP_PORT, timeout=25) as srv:
                    srv.ehlo()
                    srv.starttls()
                    srv.login(OW_PM_SENDER_EMAIL, OW_PM_SENDER_PASS)
                    srv.sendmail(OW_PM_SENDER_EMAIL, OW_PM_RECEIVERS,
                                 msg_obj.as_string())
                _OW_PM_LAST_SEND["ts"] = _time.time()
                print(f"✅ [{caller}] Email sent to {len(OW_PM_RECEIVERS)} recipients")
                return True
            except smtplib.SMTPAuthenticationError as e:
                print(f"⚠️  [{caller}] SMTP auth error (attempt {attempt}): {e}")
                break
            except (smtplib.SMTPException, OSError) as e:
                import time
                wait = 2 ** attempt
                print(f"⚠️  [{caller}] SMTP error (attempt {attempt}): {e} — retry in {wait}s")
                time.sleep(wait)
    return False


# ──────────────────────────────────────────────────────────────────────────────
# EMAIL BUILDERS
# ──────────────────────────────────────────────────────────────────────────────
def _ow_pm_build_today_html(log: dict) -> str:
    tasks   = log.get("tasks", [])
    total   = len(tasks)
    done    = sum(1 for t in tasks if t.get("status") == "Completed")
    high    = sum(1 for t in tasks if t.get("priority") == "H")
    pend    = sum(1 for t in tasks if t.get("status") in ("Pending", "In Progress"))

    prio_colors = {"H": "#dc2626", "M": "#d97706", "L": "#16a34a"}
    status_colors = {
        "Completed":   "#16a34a",
        "In Progress": "#d97706",
        "Pending":     "#b45309",
        "Deferred":    "#6b7280",
    }

    rows_html = ""
    for i, t in enumerate(tasks, 1):
        p = t.get("priority", "M")
        s = t.get("status", "Pending")
        rows_html += f"""
        <tr style="border-bottom:1px solid #f3f4f6;">
          <td style="padding:7px 10px;text-align:center;color:#9ca3af;font-size:11px;">{i}</td>
          <td style="padding:7px 10px;font-size:12px;">{t.get('location','—')}</td>
          <td style="padding:7px 10px;font-size:12px;">{t.get('description','—')}</td>
          <td style="padding:7px 10px;text-align:center;">
            <span style="display:inline-block;padding:2px 8px;border-radius:3px;font-size:10px;
                         font-weight:700;color:{prio_colors.get(p,'#374151')};
                         background:{prio_colors.get(p,'#e5e7eb')}22;
                         border:1px solid {prio_colors.get(p,'#e5e7eb')}44;">{p}</span>
          </td>
          <td style="padding:7px 10px;font-size:12px;
                     color:{status_colors.get(s,'#374151')};font-weight:600;">{s}</td>
          <td style="padding:7px 10px;font-size:11px;color:#6b7280;">{t.get('remarks','—')}</td>
        </tr>"""

    remarks_section = ""
    if log.get("remarks"):
        remarks_section = f"""
        <div style="margin-top:24px;padding:14px;background:#f9fafb;border-radius:8px;
                    border:1px solid #e5e7eb;">
          <div style="font-size:10px;font-weight:700;letter-spacing:1px;text-transform:uppercase;
                      color:#9ca3af;margin-bottom:8px;">Remarks / Observations</div>
          <div style="font-size:12px;color:#374151;white-space:pre-wrap;line-height:1.7;">
            {log.get('remarks','')}
          </div>
        </div>"""

    return f"""<!DOCTYPE html><html><body style="margin:0;padding:0;background:#f9fafb;
font-family:'Segoe UI',Arial,sans-serif;">
<div style="max-width:720px;margin:24px auto;background:#fff;border-radius:12px;
     box-shadow:0 2px 16px rgba(0,0,0,.08);overflow:hidden;">

  <!-- Header -->
  <div style="background:linear-gradient(135deg,#0d9488,#06b6d4);padding:24px 28px;">
    <div style="color:rgba(255,255,255,.7);font-size:10px;letter-spacing:2px;
                text-transform:uppercase;margin-bottom:4px;">ONEWEST · Property Management</div>
    <div style="color:#fff;font-size:22px;font-weight:800;letter-spacing:-.3px;">
      PM Daily Log Report</div>
    <div style="color:rgba(255,255,255,.8);font-size:12px;margin-top:6px;">
      {log.get('date','—')} &nbsp;·&nbsp; Shift: {log.get('shift','—')}
      &nbsp;·&nbsp; By: {log.get('author','—')}
    </div>
  </div>

  <!-- Stats -->
  <div style="display:flex;gap:0;border-bottom:1px solid #e5e7eb;">
    <div style="flex:1;padding:18px;text-align:center;border-right:1px solid #e5e7eb;">
      <div style="font-size:28px;font-weight:800;color:#111827;">{total}</div>
      <div style="font-size:10px;color:#9ca3af;text-transform:uppercase;letter-spacing:.5px;">
        Total Tasks</div>
    </div>
    <div style="flex:1;padding:18px;text-align:center;border-right:1px solid #e5e7eb;">
      <div style="font-size:28px;font-weight:800;color:#16a34a;">{done}</div>
      <div style="font-size:10px;color:#9ca3af;text-transform:uppercase;letter-spacing:.5px;">
        Completed</div>
    </div>
    <div style="flex:1;padding:18px;text-align:center;border-right:1px solid #e5e7eb;">
      <div style="font-size:28px;font-weight:800;color:#d97706;">{pend}</div>
      <div style="font-size:10px;color:#9ca3af;text-transform:uppercase;letter-spacing:.5px;">
        Open</div>
    </div>
    <div style="flex:1;padding:18px;text-align:center;">
      <div style="font-size:28px;font-weight:800;color:#dc2626;">{high}</div>
      <div style="font-size:10px;color:#9ca3af;text-transform:uppercase;letter-spacing:.5px;">
        High Priority</div>
    </div>
  </div>

  <!-- Table -->
  <div style="padding:24px 28px;">
    <div style="font-size:10px;font-weight:700;letter-spacing:1.2px;text-transform:uppercase;
                color:#9ca3af;margin-bottom:10px;">Task Log</div>
    <table style="width:100%;border-collapse:collapse;">
      <thead>
        <tr style="border-bottom:2px solid #111827;">
          <th style="padding:8px 10px;text-align:center;font-size:10px;color:#6b7280;
                     font-weight:700;text-transform:uppercase;letter-spacing:.5px;">#</th>
          <th style="padding:8px 10px;text-align:left;font-size:10px;color:#6b7280;
                     font-weight:700;text-transform:uppercase;letter-spacing:.5px;">Location</th>
          <th style="padding:8px 10px;text-align:left;font-size:10px;color:#6b7280;
                     font-weight:700;text-transform:uppercase;letter-spacing:.5px;">Task</th>
          <th style="padding:8px 10px;text-align:center;font-size:10px;color:#6b7280;
                     font-weight:700;text-transform:uppercase;letter-spacing:.5px;">Prio</th>
          <th style="padding:8px 10px;text-align:left;font-size:10px;color:#6b7280;
                     font-weight:700;text-transform:uppercase;letter-spacing:.5px;">Status</th>
          <th style="padding:8px 10px;text-align:left;font-size:10px;color:#6b7280;
                     font-weight:700;text-transform:uppercase;letter-spacing:.5px;">Remarks</th>
        </tr>
      </thead>
      <tbody>{rows_html or '<tr><td colspan="6" style="padding:20px;text-align:center;color:#9ca3af;">No tasks recorded.</td></tr>'}</tbody>
    </table>
    {remarks_section}
  </div>

  <!-- Footer -->
  <div style="padding:14px 28px;border-top:1px solid #f3f4f6;display:flex;
              justify-content:space-between;font-size:10px;color:#d1d5db;">
    <span>ONEWEST — OW PM Daily Log &nbsp;·&nbsp; Auto-generated</span>
    <span>{datetime.now().strftime('%d %b %Y %H:%M')}</span>
  </div>
</div>
</body></html>"""


def _ow_pm_build_monthly_html(logs: list) -> str:
    total_logs  = len(logs)
    total_tasks = sum(l.get("task_count", 0) for l in logs)
    total_done  = sum(l.get("completed",  0) for l in logs)
    total_high  = sum(l.get("high_prio",  0) for l in logs)
    month_label = datetime.now().strftime("%B %Y")

    rows_html = ""
    for l in logs:
        comp_pct = int(l["completed"] / l["task_count"] * 100) if l["task_count"] else 0
        rows_html += f"""
        <tr style="border-bottom:1px solid #f3f4f6;">
          <td style="padding:8px 10px;font-size:12px;font-weight:600;color:#111827;">{l['date']}</td>
          <td style="padding:8px 10px;font-size:12px;color:#6b7280;">{l['shift']}</td>
          <td style="padding:8px 10px;font-size:12px;color:#6b7280;">{l['author']}</td>
          <td style="padding:8px 10px;text-align:center;font-size:13px;font-weight:700;color:#111827;">{l['task_count']}</td>
          <td style="padding:8px 10px;text-align:center;font-size:13px;font-weight:700;color:#16a34a;">{l['completed']}</td>
          <td style="padding:8px 10px;text-align:center;font-size:13px;font-weight:700;color:#dc2626;">{l['high_prio']}</td>
          <td style="padding:8px 10px;text-align:center;">
            <span style="font-size:11px;font-weight:700;color:{'#16a34a' if comp_pct>=80 else '#d97706' if comp_pct>=50 else '#dc2626'};">
              {comp_pct}%</span>
          </td>
        </tr>"""

    return f"""<!DOCTYPE html><html><body style="margin:0;padding:0;background:#f9fafb;
font-family:'Segoe UI',Arial,sans-serif;">
<div style="max-width:720px;margin:24px auto;background:#fff;border-radius:12px;
     box-shadow:0 2px 16px rgba(0,0,0,.08);overflow:hidden;">

  <div style="background:linear-gradient(135deg,#0d9488,#06b6d4);padding:24px 28px;">
    <div style="color:rgba(255,255,255,.7);font-size:10px;letter-spacing:2px;
                text-transform:uppercase;margin-bottom:4px;">ONEWEST · Property Management</div>
    <div style="color:#fff;font-size:22px;font-weight:800;">Monthly PM Summary</div>
    <div style="color:rgba(255,255,255,.8);font-size:12px;margin-top:6px;">{month_label}</div>
  </div>

  <div style="display:flex;gap:0;border-bottom:1px solid #e5e7eb;">
    <div style="flex:1;padding:18px;text-align:center;border-right:1px solid #e5e7eb;">
      <div style="font-size:28px;font-weight:800;color:#111827;">{total_logs}</div>
      <div style="font-size:10px;color:#9ca3af;text-transform:uppercase;letter-spacing:.5px;">Log Days</div>
    </div>
    <div style="flex:1;padding:18px;text-align:center;border-right:1px solid #e5e7eb;">
      <div style="font-size:28px;font-weight:800;color:#111827;">{total_tasks}</div>
      <div style="font-size:10px;color:#9ca3af;text-transform:uppercase;letter-spacing:.5px;">Total Tasks</div>
    </div>
    <div style="flex:1;padding:18px;text-align:center;border-right:1px solid #e5e7eb;">
      <div style="font-size:28px;font-weight:800;color:#16a34a;">{total_done}</div>
      <div style="font-size:10px;color:#9ca3af;text-transform:uppercase;letter-spacing:.5px;">Completed</div>
    </div>
    <div style="flex:1;padding:18px;text-align:center;">
      <div style="font-size:28px;font-weight:800;color:#dc2626;">{total_high}</div>
      <div style="font-size:10px;color:#9ca3af;text-transform:uppercase;letter-spacing:.5px;">High Priority</div>
    </div>
  </div>

  <div style="padding:24px 28px;">
    <div style="font-size:10px;font-weight:700;letter-spacing:1.2px;text-transform:uppercase;
                color:#9ca3af;margin-bottom:10px;">Log History</div>
    <table style="width:100%;border-collapse:collapse;">
      <thead>
        <tr style="border-bottom:2px solid #111827;">
          <th style="padding:8px 10px;text-align:left;font-size:10px;color:#6b7280;font-weight:700;text-transform:uppercase;letter-spacing:.5px;">Date</th>
          <th style="padding:8px 10px;text-align:left;font-size:10px;color:#6b7280;font-weight:700;text-transform:uppercase;letter-spacing:.5px;">Shift</th>
          <th style="padding:8px 10px;text-align:left;font-size:10px;color:#6b7280;font-weight:700;text-transform:uppercase;letter-spacing:.5px;">By</th>
          <th style="padding:8px 10px;text-align:center;font-size:10px;color:#6b7280;font-weight:700;text-transform:uppercase;letter-spacing:.5px;">Tasks</th>
          <th style="padding:8px 10px;text-align:center;font-size:10px;color:#16a34a;font-weight:700;text-transform:uppercase;letter-spacing:.5px;">Done</th>
          <th style="padding:8px 10px;text-align:center;font-size:10px;color:#dc2626;font-weight:700;text-transform:uppercase;letter-spacing:.5px;">High</th>
          <th style="padding:8px 10px;text-align:center;font-size:10px;color:#6b7280;font-weight:700;text-transform:uppercase;letter-spacing:.5px;">%Done</th>
        </tr>
      </thead>
      <tbody>{rows_html or '<tr><td colspan="7" style="padding:20px;text-align:center;color:#9ca3af;">No logs this month.</td></tr>'}</tbody>
    </table>
  </div>

  <div style="padding:14px 28px;border-top:1px solid #f3f4f6;display:flex;
              justify-content:space-between;font-size:10px;color:#d1d5db;">
    <span>ONEWEST — OW PM Monthly Summary &nbsp;·&nbsp; Auto-generated</span>
    <span>{datetime.now().strftime('%d %b %Y %H:%M')}</span>
  </div>
</div></body></html>"""


# ──────────────────────────────────────────────────────────────────────────────
# PAGE ROUTE
# ──────────────────────────────────────────────────────────────────────────────
@ow_pm_daily_bp.route("/ow_pm_daily")
@_ow_pm_login_required
@_ow_pm_require_onewest
def ow_pm_daily_page():
    """Serve the OW PM Daily Log page."""
    session["active_property"] = "ONEWEST"
    session["property_code"]   = "OW"
    print(f"\n📋 OW PM Daily — User: {session.get('user')}")
    return render_template("ow_pm_daily.html")


# ──────────────────────────────────────────────────────────────────────────────
# API — SAVE
# ──────────────────────────────────────────────────────────────────────────────
@ow_pm_daily_bp.route("/ow_pm/daily/save", methods=["POST"])
@_ow_pm_login_required
@_ow_pm_require_onewest
def ow_pm_daily_save():
    """Save daily log for a specific date."""
    try:
        data = request.get_json(force=True) or {}
        date_str = data.get("date")
        if not date_str:
            return jsonify({"success": False, "error": "Date required"}), 400
        data["saved_at"] = datetime.now().isoformat()
        data["saved_by"] = session.get("user", "unknown")
        _ow_pm_save_log(date_str, data)
        print(f"✅ OW PM Daily saved: {date_str} by {session.get('user')}")
        return jsonify({"success": True, "date": date_str})
    except Exception as e:
        print(f"❌ OW PM Daily save error: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


# ──────────────────────────────────────────────────────────────────────────────
# API — LOAD
# ──────────────────────────────────────────────────────────────────────────────
@ow_pm_daily_bp.route("/ow_pm/daily/load")
@_ow_pm_login_required
@_ow_pm_require_onewest
def ow_pm_daily_load():
    """Load daily log for a given date."""
    date_str = request.args.get("date", datetime.now().strftime("%Y-%m-%d"))
    log = _ow_pm_load_log(date_str)
    if log:
        return jsonify({"success": True, "log": log})
    return jsonify({"success": False, "log": None})


# ──────────────────────────────────────────────────────────────────────────────
# API — HISTORY
# ──────────────────────────────────────────────────────────────────────────────
@ow_pm_daily_bp.route("/ow_pm/daily/history")
@_ow_pm_login_required
@_ow_pm_require_onewest
def ow_pm_daily_history():
    """Return all saved daily logs (newest first)."""
    logs = _ow_pm_all_logs()
    return jsonify({"success": True, "logs": logs})


# ──────────────────────────────────────────────────────────────────────────────
# API — EXPORT PDF (HTML print fallback)
# ──────────────────────────────────────────────────────────────────────────────
@ow_pm_daily_bp.route("/ow_pm/daily/export_pdf", methods=["POST"])
@_ow_pm_login_required
@_ow_pm_require_onewest
def ow_pm_daily_export_pdf():
    """Return HTML print view — browser handles PDF save."""
    try:
        data = request.get_json(force=True) or {}
        html = _ow_pm_build_today_html(data)
        from flask import Response
        return Response(html, mimetype="text/html")
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# ──────────────────────────────────────────────────────────────────────────────
# API — SEND TODAY'S LOG
# ──────────────────────────────────────────────────────────────────────────────
@ow_pm_daily_bp.route("/ow_pm/daily/send_today", methods=["POST"])
@_ow_pm_login_required
@_ow_pm_require_onewest
def ow_pm_daily_send_today():
    """Send today's PM log immediately to all receivers."""
    try:
        payload = request.get_json(force=True) or {}
        date_str = payload.get("date", datetime.now().strftime("%Y-%m-%d"))

        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"OW PM Daily Log — {date_str} | ONEWEST"
        msg["From"]    = OW_PM_SENDER_EMAIL
        msg["To"]      = ", ".join(OW_PM_RECEIVERS)

        html_body = _ow_pm_build_today_html(payload)
        msg.attach(MIMEText(html_body, "html", "utf-8"))

        ok = _ow_pm_smtp_send(msg, caller="ow_pm_send_today")
        if ok:
            return jsonify({
                "success":    True,
                "recipients": len(OW_PM_RECEIVERS),
                "task_count": len(payload.get("tasks", [])),
            })
        return jsonify({"success": False, "error": "SMTP send failed — check server logs"}), 500

    except Exception as e:
        print(f"❌ OW PM send_today error: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


# ──────────────────────────────────────────────────────────────────────────────
# API — MONTHLY SUMMARY MAIL
# ──────────────────────────────────────────────────────────────────────────────
@ow_pm_daily_bp.route("/ow_pm/daily/send_mail", methods=["POST"])
@_ow_pm_login_required
@_ow_pm_require_onewest
def ow_pm_daily_send_mail():
    """Send monthly PM summary to all receivers."""
    try:
        now       = datetime.now()
        month_str = now.strftime("%B %Y")
        logs      = _ow_pm_all_logs()

        # Filter to current month only
        month_key = now.strftime("%Y-%m")
        month_logs = [l for l in logs if l["date"].startswith(month_key)]

        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"OW PM Monthly Summary — {month_str} | ONEWEST"
        msg["From"]    = OW_PM_SENDER_EMAIL
        msg["To"]      = ", ".join(OW_PM_RECEIVERS)

        html_body = _ow_pm_build_monthly_html(month_logs)
        msg.attach(MIMEText(html_body, "html", "utf-8"))

        ok = _ow_pm_smtp_send(msg, caller="ow_pm_monthly_mail")
        if ok:
            return jsonify({
                "success":    True,
                "log_count":  len(month_logs),
                "task_total": sum(l["task_count"] for l in month_logs),
            })
        return jsonify({"success": False, "error": "SMTP send failed — check server logs"}), 500

    except Exception as e:
        print(f"❌ OW PM monthly mail error: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


# ──────────────────────────────────────────────────────────────────────────────
# REGISTRATION HELPER
# ──────────────────────────────────────────────────────────────────────────────
def ow_pm_daily_register(app):
    """Register ow_pm_daily_bp onto the Flask app."""
    app.register_blueprint(ow_pm_daily_bp)
    print("✅ Registered: ow_pm_daily_bp (ONEWEST PM Daily Log)")