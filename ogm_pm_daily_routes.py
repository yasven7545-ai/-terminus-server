"""
ogm_pm_daily_routes.py
══════════════════════════════════════════════════════════════════
ONE GOLDEN MILE — Property Management Daily Log Routes
All routes prefixed with /ogm/pm/daily
Blueprint: ogm_pm_daily_bp
══════════════════════════════════════════════════════════════════
Register in server.py:
    safe_register("ogm_pm_daily_routes", "ogm_pm_daily_bp")
"""

from flask import (
    Blueprint, request, jsonify, session,
    render_template, send_file
)
from functools import wraps
from pathlib import Path
from datetime import datetime
import json, io, traceback, ssl

# ── PDF (optional — graceful fallback if not installed) ─────────
try:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib import colors
    from reportlab.platypus import (
        SimpleDocTemplate, Table, TableStyle,
        Paragraph, Spacer, HRFlowable
    )
    REPORTLAB_OK = True
except ImportError:
    REPORTLAB_OK = False

# ── Email ────────────────────────────────────────────────────────
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text      import MIMEText

# ══════════════════════════════════════════════════════════════
#  CONFIG  (OW-specific receivers; SMTP shared with server.py)
# ══════════════════════════════════════════════════════════════
SMTP_SERVER     = "smtp.gmail.com"
SMTP_PORT       = 587
SENDER_EMAIL    = "maintenance.slnterminus@gmail.com"
SENDER_PASSWORD = "xaottgrqtqnkouqn"            # Gmail App Password
RECEIVER_EMAILS = [
    "maintenance.slnterminus@gmail.com",
    "yasven7545@gmail.com",
    "kiran@terminus-global.com",
    "engineering@terminus-global.com",
    
]

PROPERTY_NAME   = "One Golden Mile"
PROPERTY_CODE   = "OGM"
BRAND_COLOR     = "#10b981"   # OGM emerald green

# ══════════════════════════════════════════════════════════════
#  BLUEPRINT + DATA DIR
# ══════════════════════════════════════════════════════════════
ogm_pm_daily_bp = Blueprint("ogm_pm_daily_bp", __name__)

BASE_DIR = Path(__file__).parent.resolve()
DATA_DIR = BASE_DIR / "static" / "data" / "OGM" / "pm_daily"
DATA_DIR.mkdir(parents=True, exist_ok=True)


# ══════════════════════════════════════════════════════════════
#  HELPERS
# ══════════════════════════════════════════════════════════════
def ogm_login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if "user" not in session:
            return jsonify({"success": False, "error": "Not authenticated"}), 401
        return f(*args, **kwargs)
    return wrapper


def ogm_require_property(f):
    """Ensure user has access to One Golden Mile."""
    @wraps(f)
    def wrapper(*args, **kwargs):
        if "user" not in session:
            return jsonify({"success": False, "error": "Not authenticated"}), 401
        role = session.get("role", "")
        properties = session.get("properties", [])
        if role in ("Admin", "admin", "General Manager", "Executive") or \
           PROPERTY_NAME in properties:
            session["active_property"] = PROPERTY_NAME
            return f(*args, **kwargs)
        return jsonify({"success": False, "error": f"No access to {PROPERTY_NAME}"}), 403
    return wrapper


def _log_path(date_str: str) -> Path:
    return DATA_DIR / f"ogm_pm_log_{date_str}.json"


def _smtp_send(msg: MIMEMultipart) -> None:
    """Robust SMTP send using Gmail STARTTLS + SSL context."""
    context = ssl.create_default_context()
    with smtplib.SMTP(SMTP_SERVER, SMTP_PORT, timeout=20) as server:
        server.ehlo()
        server.starttls(context=context)
        server.ehlo()
        server.login(SENDER_EMAIL, SENDER_PASSWORD)
        server.sendmail(SENDER_EMAIL, RECEIVER_EMAILS, msg.as_string())
        print(f"✅ OW PM Mail sent to {RECEIVER_EMAILS}")


def _handle_smtp_error(e: Exception):
    if isinstance(e, smtplib.SMTPAuthenticationError):
        return jsonify({"success": False,
                        "error": (
                            "Gmail authentication failed. "
                            "Ensure 2-Step Verification is ON and the App Password is current."
                        )}), 500
    if isinstance(e, smtplib.SMTPException):
        return jsonify({"success": False, "error": f"SMTP error: {e}"}), 500
    traceback.print_exc()
    return jsonify({"success": False, "error": str(e)}), 500


# ══════════════════════════════════════════════════════════════
#  PAGE ROUTE
# ══════════════════════════════════════════════════════════════
@ogm_pm_daily_bp.route("/ogm/pm/daily")
@ogm_login_required
@ogm_require_property
def ogm_pm_daily_page():
    return render_template("ogm_pm_daily.html")


# ══════════════════════════════════════════════════════════════
#  API: SAVE
# ══════════════════════════════════════════════════════════════
@ogm_pm_daily_bp.route("/ogm/pm/daily/save", methods=["POST"])
@ogm_login_required
@ogm_require_property
def ogm_pm_daily_save():
    try:
        data = request.get_json(force=True)
        if not data:
            return jsonify({"success": False, "error": "No data received"}), 400

        date_str = data.get("date", datetime.now().strftime("%Y-%m-%d"))
        try:
            datetime.strptime(date_str, "%Y-%m-%d")
        except ValueError:
            return jsonify({"success": False, "error": "Invalid date format"}), 400

        log = {
            "date":       date_str,
            "shift":      data.get("shift", "Full Day"),
            "author":     data.get("author", session.get("user", "Unknown")),
            "property":   PROPERTY_NAME,
            "tasks":      data.get("tasks", []),
            "remarks":    data.get("remarks", ""),
            "task_count": len(data.get("tasks", [])),
            "saved_at":   datetime.now().isoformat(),
            "saved_by":   session.get("user", "Unknown"),
        }

        with open(_log_path(date_str), "w", encoding="utf-8") as f:
            json.dump(log, f, indent=2)

        print(f"✅ OW PM Daily saved: {date_str} by {log['author']}")
        return jsonify({"success": True, "date": date_str, "task_count": log["task_count"]})

    except Exception as e:
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500


# ══════════════════════════════════════════════════════════════
#  API: LOAD
# ══════════════════════════════════════════════════════════════
@ogm_pm_daily_bp.route("/ogm/pm/daily/load", methods=["GET"])
@ogm_login_required
@ogm_require_property
def ogm_pm_daily_load():
    date_str = request.args.get("date", datetime.now().strftime("%Y-%m-%d"))
    try:
        datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        return jsonify({"success": False, "error": "Invalid date format"}), 400

    path = _log_path(date_str)
    if not path.exists():
        return jsonify({"success": False, "log": None})

    try:
        with open(path, encoding="utf-8") as f:
            return jsonify({"success": True, "log": json.load(f)})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# ══════════════════════════════════════════════════════════════
#  API: HISTORY
# ══════════════════════════════════════════════════════════════
@ogm_pm_daily_bp.route("/ogm/pm/daily/history", methods=["GET"])
@ogm_login_required
@ogm_require_property
def ogm_pm_daily_history():
    try:
        logs = []
        for f in sorted(DATA_DIR.glob("ogm_pm_log_*.json"), reverse=True):
            try:
                with open(f, encoding="utf-8") as fh:
                    d = json.load(fh)
                logs.append({
                    "date":       d.get("date", ""),
                    "shift":      d.get("shift", ""),
                    "author":     d.get("author", ""),
                    "task_count": d.get("task_count", 0),
                    "saved_at":   d.get("saved_at", ""),
                })
            except Exception:
                continue
        return jsonify({"success": True, "logs": logs, "total": len(logs)})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# ══════════════════════════════════════════════════════════════
#  API: EXPORT PDF
# ══════════════════════════════════════════════════════════════
@ogm_pm_daily_bp.route("/ogm/pm/daily/export_pdf", methods=["POST"])
@ogm_login_required
@ogm_require_property
def ogm_pm_daily_export_pdf():
    try:
        data     = request.get_json(force=True) or {}
        date_str = data.get("date",     datetime.now().strftime("%Y-%m-%d"))
        shift    = data.get("shift",    "Full Day")
        author   = data.get("author",   "N/A")
        tasks    = data.get("tasks",    [])
        remarks  = data.get("remarks",  "")

        if not REPORTLAB_OK:
            html = _build_print_html(date_str, shift, author, tasks, remarks)
            return html, 200, {"Content-Type": "text/html"}

        buf = io.BytesIO()
        doc = SimpleDocTemplate(buf, pagesize=A4,
                                leftMargin=15*mm, rightMargin=15*mm,
                                topMargin=15*mm, bottomMargin=15*mm)
        doc.build(_build_pdf_story(date_str, shift, author, tasks, remarks))
        buf.seek(0)
        return send_file(buf, mimetype="application/pdf",
                         as_attachment=True,
                         download_name=f"OGM_PM_Daily_{date_str}.pdf")

    except Exception as e:
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500


# ══════════════════════════════════════════════════════════════
#  API: SEND TODAY'S LOG (immediate single-day email)
# ══════════════════════════════════════════════════════════════
@ogm_pm_daily_bp.route("/ogm/pm/daily/send_today", methods=["POST"])
@ogm_login_required
@ogm_require_property
def ogm_pm_daily_send_today():
    """Send today's PM log immediately to all OW receivers."""
    try:
        data     = request.get_json(force=True) or {}
        date_str = data.get("date", datetime.now().strftime("%Y-%m-%d"))
        shift    = data.get("shift",  "—")
        author   = data.get("author", session.get("user", "Unknown"))
        tasks    = data.get("tasks",  [])
        remarks  = data.get("remarks", "")

        # Fall back to saved file if no inline tasks
        if not tasks:
            path = _log_path(date_str)
            if path.exists():
                with open(path, encoding="utf-8") as f:
                    saved   = json.load(f)
                tasks   = saved.get("tasks",   tasks)
                shift   = saved.get("shift",   shift)
                author  = saved.get("author",  author)
                remarks = saved.get("remarks", remarks)

        total = len(tasks)
        done  = sum(1 for t in tasks if t.get("status") == "Completed")
        high  = sum(1 for t in tasks if t.get("priority") == "H")

        html_body = _build_today_mail_html(
            date_str, shift, author, tasks, remarks, total, done, high
        )

        msg            = MIMEMultipart("alternative")
        msg["Subject"] = f"[ONE GOLDEN MILE] PM Daily Log — {date_str}"
        msg["From"]    = f"ONE GOLDEN MILE MMS <{SENDER_EMAIL}>"
        msg["To"]      = ", ".join(RECEIVER_EMAILS)
        msg.attach(MIMEText(html_body, "html"))

        _smtp_send(msg)
        return jsonify({
            "success":    True,
            "date":       date_str,
            "recipients": len(RECEIVER_EMAILS),
            "task_count": total,
        })

    except Exception as e:
        return _handle_smtp_error(e)


# ══════════════════════════════════════════════════════════════
#  API: MONTHLY MAIL
# ══════════════════════════════════════════════════════════════
@ogm_pm_daily_bp.route("/ogm/pm/daily/send_mail", methods=["POST"])
@ogm_login_required
@ogm_require_property
def ogm_pm_daily_send_mail():
    """Send aggregated monthly summary to all OW receivers."""
    try:
        now       = datetime.now()
        month_str = now.strftime("%B %Y")
        prefix    = now.strftime("ogm_pm_log_%Y-%m-")
        logs      = []

        for f in sorted(DATA_DIR.glob(f"{prefix}*.json")):
            try:
                with open(f, encoding="utf-8") as fh:
                    logs.append(json.load(fh))
            except Exception:
                continue

        total_tasks     = sum(l.get("task_count", 0) for l in logs)
        total_completed = sum(
            sum(1 for t in l.get("tasks", []) if t.get("status") == "Completed")
            for l in logs
        )
        total_high      = sum(
            sum(1 for t in l.get("tasks", []) if t.get("priority") == "H")
            for l in logs
        )

        html_body = _build_monthly_mail_html(
            month_str, logs, total_tasks, total_completed, total_high
        )

        msg            = MIMEMultipart("alternative")
        msg["Subject"] = f"[ONE GOLDEN MILE] PM Monthly Summary — {month_str}"
        msg["From"]    = f"ONE GOLDEN MILE MMS <{SENDER_EMAIL}>"
        msg["To"]      = ", ".join(RECEIVER_EMAILS)
        msg.attach(MIMEText(html_body, "html"))

        _smtp_send(msg)
        return jsonify({
            "success":    True,
            "month":      month_str,
            "log_count":  len(logs),
            "task_total": total_tasks,
        })

    except Exception as e:
        return _handle_smtp_error(e)


# ══════════════════════════════════════════════════════════════
#  API: DELETE LOG
# ══════════════════════════════════════════════════════════════
@ogm_pm_daily_bp.route("/ogm/pm/daily/delete", methods=["POST"])
@ogm_login_required
@ogm_require_property
def ogm_pm_daily_delete():
    if session.get("role") not in ("Admin", "admin", "Management", "General Manager"):
        return jsonify({"success": False, "error": "Insufficient permissions"}), 403
    data     = request.get_json(force=True) or {}
    date_str = data.get("date", "")
    if not date_str:
        return jsonify({"success": False, "error": "Date required"}), 400
    path = _log_path(date_str)
    if path.exists():
        path.unlink()
        return jsonify({"success": True, "deleted": date_str})
    return jsonify({"success": False, "error": "Log not found"}), 404


# ══════════════════════════════════════════════════════════════
#  EMAIL HTML BUILDERS
# ══════════════════════════════════════════════════════════════
def _prio_badge(p):
    m = {
        "H": ("background:#fee2e2;color:#b91c1c;border:1px solid #fca5a5;", "HIGH"),
        "M": ("background:#fff7ed;color:#c2410c;border:1px solid #fdba74;", "MED"),
        "L": ("background:#dcfce7;color:#15803d;border:1px solid #86efac;", "LOW"),
    }
    s, label = m.get(p, ("background:#f3f4f6;color:#6b7280;border:1px solid #d1d5db;", p))
    return (f'<span style="display:inline-block;font-size:9px;font-weight:700;'
            f'letter-spacing:.5px;padding:2px 8px;border-radius:3px;'
            f'white-space:nowrap;{s}">{label}</span>')


def _status_color(s):
    return {"Completed":"#15803d","In Progress":"#c2410c",
            "Pending":"#b45309","Deferred":"#6b7280"}.get(s, "#374151")


def _build_today_mail_html(date_str, shift, author, tasks, remarks, total, done, high):
    # Sort H → M → L
    prio_order = {"H": 0, "M": 1, "L": 2}
    sorted_tasks = sorted(tasks, key=lambda t: prio_order.get(t.get("priority", "M"), 1))

    TH = ("padding:8px 10px;text-align:left;font-size:9px;letter-spacing:.8px;"
          "text-transform:uppercase;color:#ffffff;font-weight:700;"
          "border-bottom:1px solid #1f4e3a;white-space:nowrap;")

    task_rows = "".join(
        f"""<tr style="background:{'#ffffff' if i%2==1 else '#f7faf8'};border-bottom:1px solid #e5e7eb;">
          <td style="padding:7px 10px;font-size:11px;color:#9ca3af;text-align:center;width:28px;">{i}</td>
          <td style="padding:7px 10px;font-size:11px;color:#1a2c3d;font-weight:600;width:110px;word-wrap:break-word;">{t.get('location') or '&mdash;'}</td>
          <td style="padding:7px 10px;font-size:11px;color:#1a2c3d;word-wrap:break-word;">{t.get('description') or '&mdash;'}</td>
          <td style="padding:7px 10px;text-align:center;width:72px;white-space:nowrap;">{_prio_badge(t.get('priority','M'))}</td>
          <td style="padding:7px 10px;font-size:11px;font-weight:600;width:90px;white-space:nowrap;color:{_status_color(t.get('status','Pending'))};">{t.get('status') or '&mdash;'}</td>
          <td style="padding:7px 10px;font-size:11px;color:#607585;width:130px;word-wrap:break-word;">{t.get('remarks') or t.get('assigned') or '&mdash;'}</td>
        </tr>"""
        for i, t in enumerate(sorted_tasks, 1)
    ) or ('<tr><td colspan="6" style="padding:14px;text-align:center;'
          'color:#aaa;font-size:12px;">No tasks recorded</td></tr>')

    remarks_block = (
        f'<div style="margin:0 28px 24px;background:#f0fdf4;'
        f'border-left:3px solid #10b981;padding:12px 16px;'
        f'border-radius:0 6px 6px 0;font-size:12px;color:#1a2c3d;'
        f'white-space:pre-wrap;line-height:1.7;">'
        f'<strong style="display:block;margin-bottom:6px;font-size:10px;'
        f'letter-spacing:1px;text-transform:uppercase;color:#065f46;">'
        f'Remarks / Observations</strong>{remarks}</div>'
    ) if remarks.strip() else ""

    return f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/></head>
<body style="font-family:Arial,sans-serif;background:#f0f4f8;margin:0;padding:20px;">
<div style="max-width:680px;margin:auto;background:#fff;border-radius:10px;
            overflow:hidden;box-shadow:0 2px 24px rgba(0,0,0,.12);">

  <div style="background:#060c12;padding:24px 28px 20px;border-bottom:3px solid #10b981;">
    <div style="color:#10b981;font-size:10px;letter-spacing:2px;text-transform:uppercase;margin-bottom:6px;">ONE GOLDEN MILE · Property Management</div>
    <div style="color:#fff;font-size:22px;font-weight:800;letter-spacing:-.3px;">PM Daily Log Report</div>
    <div style="color:#5a7a8f;font-size:12px;margin-top:6px;font-family:monospace;">
      {date_str} &nbsp;·&nbsp; Shift: {shift} &nbsp;·&nbsp; By: {author}</div>
  </div>

  <table style="width:100%;border-collapse:collapse;border-bottom:1px solid #e8edf5;">
    <tr>
      <td style="padding:16px 10px;text-align:center;border-right:1px solid #e8edf5;">
        <div style="font-size:28px;font-weight:800;color:#0b0e14;line-height:1;">{total}</div>
        <div style="font-size:9px;color:#607585;letter-spacing:1px;text-transform:uppercase;margin-top:3px;">Total Tasks</div>
      </td>
      <td style="padding:16px 10px;text-align:center;border-right:1px solid #e8edf5;">
        <div style="font-size:28px;font-weight:800;color:#15803d;line-height:1;">{done}</div>
        <div style="font-size:9px;color:#607585;letter-spacing:1px;text-transform:uppercase;margin-top:3px;">Completed</div>
      </td>
      <td style="padding:16px 10px;text-align:center;border-right:1px solid #e8edf5;">
        <div style="font-size:28px;font-weight:800;color:#b45309;line-height:1;">{total - done}</div>
        <div style="font-size:9px;color:#607585;letter-spacing:1px;text-transform:uppercase;margin-top:3px;">Open</div>
      </td>
      <td style="padding:16px 10px;text-align:center;">
        <div style="font-size:28px;font-weight:800;color:#b91c1c;line-height:1;">{high}</div>
        <div style="font-size:9px;color:#607585;letter-spacing:1px;text-transform:uppercase;margin-top:3px;">High Priority</div>
      </td>
    </tr>
  </table>

  <div style="padding:20px 28px 10px;">
    <div style="font-weight:800;font-size:11px;color:#0b0e14;margin-bottom:10px;text-transform:uppercase;letter-spacing:1px;border-bottom:2px solid #10b981;padding-bottom:4px;">Task Log</div>
  </div>

  <table style="width:100%;border-collapse:collapse;table-layout:fixed;">
    <colgroup>
      <col style="width:28px;"/>
      <col style="width:110px;"/>
      <col/>
      <col style="width:72px;"/>
      <col style="width:90px;"/>
      <col style="width:130px;"/>
    </colgroup>
    <thead><tr style="background:#065f46;">
      <th style="{TH}text-align:center;">#</th>
      <th style="{TH}">Location</th>
      <th style="{TH}">Task Description</th>
      <th style="{TH}text-align:center;">Priority</th>
      <th style="{TH}">Status</th>
      <th style="{TH}">Remarks</th>
    </tr></thead>
    <tbody>{task_rows}</tbody>
  </table>

  {remarks_block}

  <div style="padding:14px 28px;background:#f6f8fc;border-top:1px solid #e8edf5;font-size:10px;color:#aaa;">
    ONE GOLDEN MILE MMS — Auto-generated &nbsp;·&nbsp;
    {datetime.now().strftime('%d %b %Y %H:%M IST')} &nbsp;·&nbsp; Confidential
  </div>
</div>
</body></html>"""

def _build_monthly_mail_html(month_str, logs, total_tasks, total_completed, total_high):
    rows = "".join(
        f"""<tr style="border-bottom:1px solid #e8edf5;">
          <td style="padding:8px 12px;font-size:12px;color:#0b0e14;font-weight:600;font-family:monospace;">{l['date']}</td>
          <td style="padding:8px 12px;font-size:12px;color:#607585;">{l.get('shift','—')}</td>
          <td style="padding:8px 12px;font-size:12px;font-weight:700;color:#0b0e14;">{l.get('task_count',0)}</td>
          <td style="padding:8px 12px;font-size:12px;color:#607585;">{l.get('author','—')}</td>
        </tr>"""
        for l in logs
    ) or ('<tr><td colspan="4" style="padding:20px;text-align:center;'
          'color:#aaa;font-size:12px;">No logs saved this month</td></tr>')

    return f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/></head>
<body style="font-family:Arial,sans-serif;background:#f0f4f8;margin:0;padding:20px;">
<div style="max-width:640px;margin:auto;background:#fff;border-radius:10px;
            overflow:hidden;box-shadow:0 2px 24px rgba(0,0,0,.12);">

  <div style="background:#060c12;padding:24px 28px 20px;
              border-bottom:3px solid #f59e0b;">
    <div style="color:#f59e0b;font-size:10px;letter-spacing:2px;
                text-transform:uppercase;margin-bottom:6px;">ONE GOLDEN MILE · Property Management</div>
    <div style="color:#fff;font-size:22px;font-weight:800;letter-spacing:-.3px;">PM Monthly Summary</div>
    <div style="color:#5a7a8f;font-size:12px;margin-top:6px;">{month_str}</div>
  </div>

  <table style="width:100%;border-collapse:collapse;border-bottom:1px solid #e8edf5;">
    <tr>
      <td style="padding:16px 8px;text-align:center;border-right:1px solid #e8edf5;">
        <div style="font-size:28px;font-weight:800;color:#0b0e14;line-height:1;">{len(logs)}</div>
        <div style="font-size:9px;color:#607585;letter-spacing:1px;text-transform:uppercase;margin-top:3px;">Log Days</div>
      </td>
      <td style="padding:16px 8px;text-align:center;border-right:1px solid #e8edf5;">
        <div style="font-size:28px;font-weight:800;color:#0b0e14;line-height:1;">{total_tasks}</div>
        <div style="font-size:9px;color:#607585;letter-spacing:1px;text-transform:uppercase;margin-top:3px;">Total Tasks</div>
      </td>
      <td style="padding:16px 8px;text-align:center;border-right:1px solid #e8edf5;">
        <div style="font-size:28px;font-weight:800;color:#009b74;line-height:1;">{total_completed}</div>
        <div style="font-size:9px;color:#607585;letter-spacing:1px;text-transform:uppercase;margin-top:3px;">Completed</div>
      </td>
      <td style="padding:16px 8px;text-align:center;">
        <div style="font-size:28px;font-weight:800;color:#cc1030;line-height:1;">{total_high}</div>
        <div style="font-size:9px;color:#607585;letter-spacing:1px;text-transform:uppercase;margin-top:3px;">High Priority</div>
      </td>
    </tr>
  </table>

  <div style="padding:20px 28px 10px;">
    <div style="font-weight:800;font-size:11px;color:#0b0e14;margin-bottom:12px;
                text-transform:uppercase;letter-spacing:1px;">Daily Log Summary</div>
  </div>
  <table style="width:100%;border-collapse:collapse;">
    <thead><tr style="background:#f6f8fc;">
      <th style="padding:9px 12px;text-align:left;font-size:9px;letter-spacing:1px;text-transform:uppercase;color:#607585;font-weight:700;border-bottom:1px solid #e8edf5;">Date</th>
      <th style="padding:9px 12px;text-align:left;font-size:9px;letter-spacing:1px;text-transform:uppercase;color:#607585;font-weight:700;border-bottom:1px solid #e8edf5;">Shift</th>
      <th style="padding:9px 12px;text-align:left;font-size:9px;letter-spacing:1px;text-transform:uppercase;color:#607585;font-weight:700;border-bottom:1px solid #e8edf5;">Tasks</th>
      <th style="padding:9px 12px;text-align:left;font-size:9px;letter-spacing:1px;text-transform:uppercase;color:#607585;font-weight:700;border-bottom:1px solid #e8edf5;">Reported By</th>
    </tr></thead>
    <tbody>{rows}</tbody>
  </table>

  <div style="padding:14px 28px;background:#f6f8fc;border-top:1px solid #e8edf5;
              font-size:10px;color:#aaa;margin-top:20px;">
    ONE GOLDEN MILE MMS — Auto-generated &nbsp;·&nbsp;
    {datetime.now().strftime('%d %b %Y %H:%M IST')} &nbsp;·&nbsp; Confidential
  </div>
</div>
</body></html>"""


# ══════════════════════════════════════════════════════════════
#  PDF STORY BUILDER
# ══════════════════════════════════════════════════════════════
def _build_pdf_story(date_str, shift, author, tasks, remarks):
    styles = getSampleStyleSheet()
    story  = []
    BRAND  = colors.HexColor("#10b981")   # OGM green
    DARK   = colors.HexColor("#060c12")
    GREY   = colors.HexColor("#c8dae8")

    title_s = ParagraphStyle("T", parent=styles["Heading1"],
                              fontName="Helvetica-Bold", fontSize=16,
                              textColor=DARK, spaceAfter=4)
    sub_s   = ParagraphStyle("S", parent=styles["Normal"],
                              fontName="Helvetica", fontSize=8,
                              textColor=colors.grey, spaceAfter=8)
    h2_s    = ParagraphStyle("H2", parent=styles["Heading2"],
                              fontName="Helvetica-Bold", fontSize=11,
                              textColor=DARK, spaceAfter=4)

    story.append(Paragraph("PROPERTY MANAGEMENT DAILY REPORT", title_s))
    story.append(Paragraph(
        f"ONE GOLDEN MILE  ·  Date: {date_str}  ·  Shift: {shift}  ·  By: {author}", sub_s))
    story.append(HRFlowable(width="100%", thickness=1.5, color=BRAND, spaceAfter=10))

    total = len(tasks)
    done  = sum(1 for t in tasks if t.get("status") == "Completed")
    high  = sum(1 for t in tasks if t.get("priority") == "H")

    s_data = [["Total Tasks","Completed","High Priority","Generated"],
              [str(total), str(done), str(high),
               datetime.now().strftime("%d %b %Y %H:%M")]]
    s_tbl  = Table(s_data, colWidths=[45*mm]*4)
    s_tbl.setStyle(TableStyle([
        ("BACKGROUND",(0,0),(-1,0),BRAND), ("TEXTCOLOR",(0,0),(-1,0),colors.black),
        ("FONTNAME",(0,0),(-1,0),"Helvetica-Bold"), ("FONTSIZE",(0,0),(-1,-1),8),
        ("ALIGN",(0,0),(-1,-1),"CENTER"), ("VALIGN",(0,0),(-1,-1),"MIDDLE"),
        ("ROWBACKGROUNDS",(0,1),(-1,-1),[colors.white,colors.HexColor("#f0f4f8")]),
        ("GRID",(0,0),(-1,-1),0.5,colors.HexColor("#c8d8e8")),
        ("TOPPADDING",(0,0),(-1,-1),5), ("BOTTOMPADDING",(0,0),(-1,-1),5),
    ]))
    story.append(s_tbl)
    story.append(Spacer(1, 8*mm))
    story.append(Paragraph("TASK LOG", h2_s))

    headers = ["#","Time","Location / Area","Task Description","Priority","Status","Assigned To"]
    col_w   = [8*mm,16*mm,30*mm,60*mm,15*mm,20*mm,24*mm]
    rows    = [headers] + [
        [str(i), t.get("time",""), t.get("location",""), t.get("description",""),
         t.get("priority","M"), t.get("status","Pending"), t.get("assigned","")]
        for i, t in enumerate(tasks, 1)
    ]
    prio_colors = {"H":colors.HexColor("#ff406030"),
                   "M":colors.HexColor("#ffb70025"),
                   "L":colors.HexColor("#0af0b020")}
    t_tbl = Table(rows, colWidths=col_w, repeatRows=1)
    ts = TableStyle([
        ("BACKGROUND",(0,0),(-1,0),DARK), ("TEXTCOLOR",(0,0),(-1,0),colors.white),
        ("FONTNAME",(0,0),(-1,0),"Helvetica-Bold"), ("FONTSIZE",(0,0),(-1,-1),8),
        ("VALIGN",(0,0),(-1,-1),"TOP"),
        ("GRID",(0,0),(-1,-1),0.4,colors.HexColor("#c8d8e8")),
        ("TOPPADDING",(0,0),(-1,-1),4), ("BOTTOMPADDING",(0,0),(-1,-1),4),
        ("LEFTPADDING",(0,0),(-1,-1),4),
    ])
    for i, t in enumerate(tasks, 1):
        ts.add("BACKGROUND",(4,i),(4,i),prio_colors.get(t.get("priority","M"),colors.white))
    for i in range(1, len(rows)):
        if i % 2 == 0:
            ts.add("BACKGROUND",(0,i),(2,i),colors.HexColor("#f6f9fc"))
            ts.add("BACKGROUND",(5,i),(-1,i),colors.HexColor("#f6f9fc"))
    t_tbl.setStyle(ts)
    story.append(t_tbl)

    if remarks.strip():
        story.append(Spacer(1, 8*mm))
        story.append(Paragraph("REMARKS / OBSERVATIONS", h2_s))
        story.append(Paragraph(
            remarks.replace("\n","<br/>"),
            ParagraphStyle("R", parent=styles["Normal"],
                           fontName="Helvetica", fontSize=9, leading=14,
                           borderPadding=8, borderColor=BRAND, borderWidth=0.5,
                           backColor=colors.HexColor("#fffbf0"))))

    story.append(Spacer(1, 12*mm))
    story.append(HRFlowable(width="100%", thickness=0.5, color=GREY))
    story.append(Paragraph(
        f"Generated by ONE GOLDEN MILE MMS · "
        f"{datetime.now().strftime('%d %b %Y %H:%M')} · Confidential",
        ParagraphStyle("F", parent=styles["Normal"],
                       fontName="Helvetica", fontSize=7, textColor=colors.grey)))
    return story


def _build_print_html(date_str, shift, author, tasks, remarks):
    """Browser-print fallback when reportlab is unavailable."""
    rows = "".join(
        f"<tr><td>{i}</td><td>{t.get('time','')}</td>"
        f"<td>{t.get('location','')}</td><td>{t.get('description','')}</td>"
        f"<td class='p{t.get('priority','M')}'>{t.get('priority','M')}</td>"
        f"<td>{t.get('status','')}</td><td>{t.get('assigned','')}</td></tr>"
        for i, t in enumerate(tasks, 1)
    )
    return f"""<!DOCTYPE html><html><head><meta charset="UTF-8"/>
<title>OGM PM Daily — {date_str}</title>
<style>
  body{{font-family:Arial,sans-serif;font-size:11px;margin:20mm;color:#1a2c3d;}}
  h1{{font-size:16px;margin-bottom:2px;}}
  .sub{{color:#607585;font-size:9px;margin-bottom:12px;}}
  hr{{border:none;border-top:3px solid #f59e0b;margin:8px 0 12px;}}
  table{{width:100%;border-collapse:collapse;}}
  th{{background:#060c12;color:#fff;padding:5px;font-size:9px;letter-spacing:1px;}}
  td{{padding:4px 6px;border:1px solid #c8d8e8;vertical-align:top;}}
  tr:nth-child(even){{background:#fffbf0;}}
  .pH{{background:#ff406030;font-weight:700;color:#cc0020;}}
  .pM{{background:#ffb70025;font-weight:700;color:#8a6000;}}
  .pL{{background:#0af0b020;font-weight:700;color:#007050;}}
  .remarks{{background:#fffbf0;border:1px solid #f59e0b;padding:10px;
            margin-top:12px;white-space:pre-wrap;line-height:1.6;}}
  @media print{{@page{{size:A4;margin:15mm;}}}}
</style></head>
<body onload="window.print()">
<h1>PROPERTY MANAGEMENT DAILY REPORT</h1>
<div class="sub">ONE GOLDEN MILE · {date_str} · Shift: {shift} · By: {author}</div>
<hr/>
<table>
  <thead><tr><th>#</th><th>TIME</th><th>LOCATION</th><th>TASK</th>
  <th>PRIO</th><th>STATUS</th><th>ASSIGNED</th></tr></thead>
  <tbody>{rows}</tbody>
</table>
{'<div class="remarks"><strong>REMARKS:</strong><br/>'+remarks+'</div>' if remarks.strip() else ''}
<p style="font-size:8px;color:#aaa;margin-top:20px;">
  ONE GOLDEN MILE MMS · {datetime.now().strftime('%d %b %Y %H:%M')} · Confidential
</p>
</body></html>"""