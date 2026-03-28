"""
SLN WORK TRACK — DAILY WORKS / COST IMPLICATION WORKFLOW
SLN TERMINUS Property Management System
Blueprint prefix: /sln_work_track
"""

from flask import Blueprint, request, jsonify, session
from functools import wraps
from datetime import datetime
from pathlib import Path
import json
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

# ─────────────────────────────────────────────────────────
# BLUEPRINT
# ─────────────────────────────────────────────────────────
sln_work_track_bp = Blueprint("sln_work_track", __name__)

# ─────────────────────────────────────────────────────────
# PATHS
# ─────────────────────────────────────────────────────────
BASE_DIR                = Path(__file__).parent.resolve()
SLN_WORK_TRACK_DATA_FILE = BASE_DIR / "static" / "data" / "sln_work_track_works.json"
SLN_WORK_TRACK_LOG_FILE  = BASE_DIR / "static" / "data" / "sln_work_track_mail_log.json"
SLN_WORK_TRACK_TMPL_FILE = BASE_DIR / "static" / "data" / "sln_work_track_templates.json"

for _p in [SLN_WORK_TRACK_DATA_FILE, SLN_WORK_TRACK_LOG_FILE, SLN_WORK_TRACK_TMPL_FILE]:
    _p.parent.mkdir(parents=True, exist_ok=True)

# ─────────────────────────────────────────────────────────
# SMTP CONFIG
# ─────────────────────────────────────────────────────────
_SMTP_SERVER = "smtp.gmail.com"
_SMTP_PORT   = 587
_SMTP_USER   = "maintenance.slnterminus@gmail.com"
_SMTP_PASS   = "xaottgrqtqnkouqn"

# ─────────────────────────────────────────────────────────
# DEPARTMENT EMAIL MAP
# ─────────────────────────────────────────────────────────
SLN_DEPT_EMAILS = {
    "GM":          ["maintenance.slnterminus@gmail.com", "yasven7545@gmail.com", "Kiran@terminus-global.com"],
    "Procurement": ["maintenance.slnterminus@gmail.com", "yasven7545@gmail.com", "Kiran@terminus-global.com"],
    "Finance":     ["maintenance.slnterminus@gmail.com", "yasven7545@gmail.com", "Kiran@terminus-global.com"],
    "Management":  ["maintenance.slnterminus@gmail.com", "yasven7545@gmail.com", "Kiran@terminus-global.com"],
    "PM":          ["maintenance.slnterminus@gmail.com", "yasven7545@gmail.com", "Kiran@terminus-global.com"],
    "Accounts":    ["maintenance.slnterminus@gmail.com", "yasven7545@gmail.com", "Kiran@terminus-global.com"],
    "All":         ["maintenance.slnterminus@gmail.com", "yasven7545@gmail.com", "Kiran@terminus-global.com"],
}

SLN_EMERGENCY_EMAILS = [
    "maintenance.slnterminus@gmail.com",
    "yasven7545@gmail.com",
    "Kiran@terminus-global.com"
]

# ─────────────────────────────────────────────────────────
# WORKFLOW DEFINITION
# ─────────────────────────────────────────────────────────
WORKFLOW_STAGES = [
    "Issue Identification",
    "GM Approval",
    "Procurement / Finance Action",
    "Management Approval",
    "Contract Awarded",
    "Execution & Daily Monitoring",
    "Completion & Closure",
]

STAGE_DEPTS = {
    "Issue Identification":         ["GM", "Management"],
    "GM Approval":                  ["Procurement", "Finance"],
    "Procurement / Finance Action": ["Management", "PM"],
    "Management Approval":          ["All"],
    "Contract Awarded":             ["All"],
    "Execution & Daily Monitoring": ["PM", "Management"],
    "Completion & Closure":         ["All"],
}

DEFAULT_SUBJECTS = {
    "Issue Identification":         "[SLN TERMINUS] Cost Implication Work - Issue Identified: {title}",
    "GM Approval":                  "[SLN TERMINUS] GM Approval Required: {title}",
    "Procurement / Finance Action": "[SLN TERMINUS] Procurement/Finance Action Required: {title}",
    "Management Approval":          "[SLN TERMINUS] Final Management Approval: {title}",
    "Contract Awarded":             "[SLN TERMINUS] Contract Awarded / PO Issued: {title}",
    "Execution & Daily Monitoring": "[SLN TERMINUS] Daily Progress Update - {date}: {title}",
    "Completion & Closure":         "[SLN TERMINUS] Work Completed and Closed: {title}",
}

DEFAULT_BODIES = {
    "Issue Identification": (
        "Dear GM / Management,\n\n"
        "🚨 A new cost implication work has been identified and requires your immediate review and approval.\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "📌 WORK DETAILS\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "  📝  Work Title     : {title}\n"
        "  📍  Location       : {location}\n"
        "  ⚠️   Priority       : {priority}\n"
        "  💰  Estimated Cost : ₹ {cost}\n"
        "  👤  Identified By  : {identified_by}\n"
        "  📅  Date           : {date}\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "  📋  SCOPE / DESCRIPTION\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "  {description}\n\n"
        "Kindly review and provide necessary approval at the earliest.\n\n"
        "Regards,\nemerZhent Property Management Services"
    ),
    "GM Approval": (
        "Dear GM,\n\n"
        "📤 A cost implication work requires your approval before proceeding to procurement.\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "📌 WORK DETAILS\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "  📝  Work Title     : {title}\n"
        "  📍  Location       : {location}\n"
        "  ⚠️   Priority       : {priority}\n"
        "  💰  Estimated Cost : ₹ {cost}\n"
        "  📋  Description    : {description}\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "Please review and approve to initiate the procurement process.\n\n"
        "Regards,\nemerZhent Property Management Services"
    ),
    "Procurement / Finance Action": (
        "Dear Procurement / Finance Team,\n\n"
        "📦 GM approval has been obtained. Please initiate the quotation process and budget verification.\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "📌 WORK DETAILS\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "  📝  Work Title     : {title}\n"
        "  📍  Location       : {location}\n"
        "  💰  Estimated Cost : ₹ {cost}\n"
        "  📋  Description    : {description}\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "Kindly obtain multiple quotations and prepare a comparative statement.\n\n"
        "Regards,\nemerZhent Property Management Services"
    ),
    "Management Approval": (
        "Dear Management,\n\n"
        "✅ Quotations have been received and comparative analysis is ready for your final approval.\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "📌 WORK DETAILS\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "  📝  Work Title     : {title}\n"
        "  📍  Location       : {location}\n"
        "  🏭  Vendor         : {vendor}\n"
        "  💰  Final Cost     : ₹ {cost}\n"
        "  📋  Description    : {description}\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "Please provide final approval to proceed with awarding the contract / PO.\n\n"
        "Regards,\nemerZhent Property Management Services"
    ),
    "Contract Awarded": (
        "Dear Sir / Madam,\n\n"
        "🤝 The Purchase Order / Contract has been awarded. Work execution commences shortly.\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "📌 CONTRACT DETAILS\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "  📝  Work Title     : {title}\n"
        "  📍  Location       : {location}\n"
        "  🏭  Vendor         : {vendor}\n"
        "  💰  PO / Contract  : ₹ {cost}\n"
        "  📅  Expected Start : {start_date}\n"
        "  ⏱️   Expected End   : {end_date}\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "Regards,\nemerZhent Property Management Services"
    ),
    "Execution & Daily Monitoring": (
        "Dear Sir / Madam,\n\n"
        "📊 Daily Progress Update — {date}\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "🏗️  WORK IN PROGRESS\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "  📝  Work Title     : {title}\n"
        "  📍  Location       : {location}\n"
        "  🎯  Current Stage  : {stage}\n"
        "  📈  Progress       : {progress}%\n"
        "  🗒️   Remarks        : {remarks}\n"
        "  ⏱️   Expected End   : {end_date}\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "Regards,\nemerZhent Property Management Services"
    ),
    "Completion & Closure": (
        "Dear Sir / Madam,\n\n"
        "🏆 We are pleased to inform that the following work has been completed and closed.\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "✅ CLOSURE SUMMARY\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "  📝  Work Title      : {title}\n"
        "  📍  Location        : {location}\n"
        "  🏭  Vendor          : {vendor}\n"
        "  💰  Final Cost      : ₹ {cost}\n"
        "  📅  Completion Date : {date}\n"
        "  🔍  Inspection      : {inspection}\n"
        "  🗒️   Remarks         : {remarks}\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "Regards,\nemerZhent Property Management Services"
    ),
}

# ─────────────────────────────────────────────────────────
# AUTH DECORATORS
# ─────────────────────────────────────────────────────────
def _slnt_auth(f):
    @wraps(f)
    def w(*a, **kw):
        try:
            if "user" not in session:
                return jsonify({"success": False, "error": "Not authenticated"}), 401
        except RuntimeError:
            return f(*a, **kw)
        return f(*a, **kw)
    return w

def _slnt_prop(f):
    @wraps(f)
    def w(*a, **kw):
        # Property check: accept any logged-in user assigned to this property.
        # We check that active_property is set (non-empty) — the specific value
        # may vary by server config (e.g. "SLN Terminus", "sln_terminus", "SLN TERMINUS").
        try:
            prop = (session.get("active_property") or "").strip()
            role = (session.get("role") or "").strip()
            if not prop and role not in ("admin", "superadmin"):
                return jsonify({"success": False, "error": "No active property in session"}), 403
        except RuntimeError:
            pass  # outside request context (e.g. scheduler) — allow through
        return f(*a, **kw)
    return w

def _slnt_current_user():
    """Return session username safely — returns 'System' outside request context."""
    try:
        return session.get("user", "System") or "System"
    except RuntimeError:
        return "System"

# ─────────────────────────────────────────────────────────
# DATA HELPERS
# ─────────────────────────────────────────────────────────
def _slnt_load():
    if not SLN_WORK_TRACK_DATA_FILE.exists():
        return []
    try:
        with open(SLN_WORK_TRACK_DATA_FILE, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return []

def _slnt_save(data):
    SLN_WORK_TRACK_DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(SLN_WORK_TRACK_DATA_FILE, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, default=str)

def _slnt_load_templates():
    if not SLN_WORK_TRACK_TMPL_FILE.exists():
        return {}
    try:
        with open(SLN_WORK_TRACK_TMPL_FILE, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return {}

def _slnt_save_templates(data):
    with open(SLN_WORK_TRACK_TMPL_FILE, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2)

def _slnt_log_mail(work_id, stage, recipients, status, error=""):
    log = []
    if SLN_WORK_TRACK_LOG_FILE.exists():
        try:
            with open(SLN_WORK_TRACK_LOG_FILE, "r", encoding="utf-8") as fh:
                log = json.load(fh)
        except Exception:
            log = []
    log.append({
        "work_id":    work_id,
        "stage":      stage,
        "recipients": recipients,
        "status":     status,
        "error":      error,
        "timestamp":  datetime.now().isoformat(),
    })
    with open(SLN_WORK_TRACK_LOG_FILE, "w", encoding="utf-8") as fh:
        json.dump(log[-500:], fh, indent=2)

def _slnt_next_id():
    works = _slnt_load()
    if not works:
        return "OWT-0001"
    nums = []
    for w in works:
        try:
            nums.append(int(w.get("id", "OWT-0000").split("-")[1]))
        except Exception:
            nums.append(0)
    return f"OWT-{max(nums) + 1:04d}"

def _slnt_build_ctx(work, extra=None):
    ctx = {
        "title":         work.get("title", ""),
        "location":      work.get("location", ""),
        "description":   work.get("description", ""),
        "cost":          work.get("estimated_cost", ""),
        "priority":      work.get("priority", ""),
        "identified_by": work.get("identified_by", ""),
        "vendor":        work.get("vendor", ""),
        "start_date":    work.get("start_date", ""),
        "end_date":      work.get("end_date", ""),
        "progress":      work.get("progress", 0),
        "remarks":       work.get("remarks", ""),
        "inspection":    work.get("inspection", ""),
        "stage":         work.get("current_stage", ""),
        "date":          datetime.now().strftime("%d %b %Y"),
    }
    if extra:
        ctx.update(extra)
    return ctx

def _slnt_resolve_recipients(depts):
    seen, result = set(), []
    for d in depts:
        for r in SLN_DEPT_EMAILS.get(d, SLN_DEPT_EMAILS["All"]):
            if r not in seen:
                seen.add(r)
                result.append(r)
    return result

# ─────────────────────────────────────────────────────────
# EMAIL HELPERS
# ─────────────────────────────────────────────────────────
def _slnt_build_html(work, subject, plain_body):
    stage = work.get("current_stage", "")
    si    = WORKFLOW_STAGES.index(stage) if stage in WORKFLOW_STAGES else 0
    steps = ""
    for i, s in enumerate(WORKFLOW_STAGES):
        if i < si:
            dot_bg  = "#22c55e"
            dot_clr = "#ffffff"
            num     = "&#10003;"
            lbl_clr = "#22c55e"
            lbl_wgt = "normal"
        elif i == si:
            dot_bg  = "#f59e0b"
            dot_clr = "#000000"
            num     = str(i + 1)
            lbl_clr = "#f59e0b"
            lbl_wgt = "700"
        else:
            dot_bg  = "#2d3748"
            dot_clr = "#718096"
            num     = str(i + 1)
            lbl_clr = "#6b7280"
            lbl_wgt = "normal"

        # Each step: fixed-size circle that never shrinks + label that never overlaps
        steps += (
            f'<table role="presentation" cellpadding="0" cellspacing="0" border="0" '
            f'style="margin-bottom:8px;border-collapse:collapse;">'
            f'<tr>'
            f'<td style="width:28px;min-width:28px;max-width:28px;padding:0;vertical-align:middle;">'
            f'<div style="width:28px;height:28px;min-width:28px;border-radius:50%;'
            f'background:{dot_bg};color:{dot_clr};'
            f'font-size:11px;font-weight:700;line-height:28px;'
            f'text-align:center;font-family:Arial,sans-serif;">'
            f'{num}</div>'
            f'</td>'
            f'<td style="padding:0 0 0 10px;vertical-align:middle;">'
            f'<span style="font-size:12px;font-family:Arial,sans-serif;'
            f'color:{lbl_clr};font-weight:{lbl_wgt};white-space:nowrap;">{s}</span>'
            f'</td>'
            f'</tr>'
            f'</table>'
        )

    DASHBOARD_LOGIN_URL = "https://descriptive-joya-unsolidified.ngrok-free.dev/login"

    body_html = plain_body.replace("\n", "<br>")
    return (
        "<!DOCTYPE html>"
        "<html><head><meta charset=\"UTF-8\">"
        "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
        "</head>"
        "<body style=\"margin:0;padding:20px;background:#0d1117;font-family:Arial,sans-serif;\">"
        "<div style=\"max-width:620px;margin:0 auto;background:#161b22;"
        "border:1px solid #30363d;border-radius:12px;overflow:hidden;\">"

        # ── Header ──
        "<div style=\"background:linear-gradient(135deg,#f59e0b,#d97706);padding:18px 24px;\">"
        f"<h2 style=\"margin:0;color:#000000;font-size:16px;font-family:Arial,sans-serif;\">"
        f"SLN TERMINUS &#8212; Works &amp; Cost Tracker</h2>"
        f"<p style=\"margin:5px 0 0;color:#1a1a1a;font-size:12px;font-family:Arial,sans-serif;\">"
        f"{subject}</p>"
        "</div>"

        # ── Workflow Pipeline ──
        "<div style=\"padding:20px 24px;\">"
        "<p style=\"font-size:10px;color:#8b949e;text-transform:uppercase;"
        "letter-spacing:.1em;margin:0 0 14px;font-family:Arial,sans-serif;\">Workflow Progress</p>"
        f"{steps}"
        "</div>"

        # ── Mail Body ──
        f"<div style=\"margin:0 24px 20px;background:#0d1117;border:1px solid #21262d;"
        f"border-radius:8px;padding:16px;font-size:13px;color:#e6edf3;"
        f"line-height:1.8;font-family:Arial,sans-serif;\">{body_html}</div>"

        # ── Login CTA Button ──
        "<div style=\"padding:0 24px 24px;text-align:center;\">"
        "<p style=\"font-size:13px;color:#ffffff;margin:0 0 12px;"
        "font-family:Arial,sans-serif;\">Access the Facility Dashboard to view details, "
        "update progress or take action:</p>"
        "<table role=\"presentation\" cellpadding=\"0\" cellspacing=\"0\" "
        "border=\"0\" style=\"margin:0 auto;\">"
        "<tr><td style=\"border-radius:8px;background:linear-gradient(135deg,#f59e0b,#d97706);"
        "padding:0;\">"
        f"<a href=\"{DASHBOARD_LOGIN_URL}\" target=\"_blank\" "
        "style=\"display:inline-block;padding:13px 32px;"
        "font-family:Arial,sans-serif;font-size:13px;font-weight:700;"
        "color:#000000;text-decoration:none;border-radius:8px;"
        "letter-spacing:0.04em;\">"
        "&#127970;&nbsp; Login to EPMS Dashboard"
        "</a>"
        "</td></tr></table>"
        "<p style=\"font-size:12px;color:#ffffff;margin:10px 0 0;"
        "font-family:Arial,sans-serif;\">Facility Dashboards &nbsp;|&nbsp; Emerzhent</p>"
        "</div>"

        # ── Footer ──
        "<div style=\"padding:12px 24px;border-top:1px solid #21262d;"
        "text-align:center;font-size:12px;color:#ffffff;font-family:Arial,sans-serif;\">"
        f"emerZhent Property Management Services (LLP) &nbsp;|&nbsp; Auto-generated &nbsp;|&nbsp;"
        f"{datetime.now().strftime('%d %b %Y %H:%M')} IST"
        "<br><span style=\"font-size:9px;color:#ffffff;\">"
        "This is a system-generated notification. Do not reply to this email.</span>"
        "</div>"

        "</div></body></html>"
    )

def _slnt_send_smtp(recipients, subject, plain_body, html_body=None):
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"]    = f"SLN TERMINUS Works Tracker <{_SMTP_USER}>"
        msg["To"]      = ", ".join(recipients)
        msg.attach(MIMEText(plain_body, "plain"))
        if html_body:
            msg.attach(MIMEText(html_body, "html"))
        with smtplib.SMTP(_SMTP_SERVER, _SMTP_PORT) as srv:
            srv.ehlo()
            srv.starttls()
            srv.login(_SMTP_USER, _SMTP_PASS)
            srv.sendmail(_SMTP_USER, recipients, msg.as_string())
        return {"success": True}
    except Exception as exc:
        return {"success": False, "error": str(exc)}

# ─────────────────────────────────────────────────────────
# ROUTES - WORKS CRUD
# ─────────────────────────────────────────────────────────

@sln_work_track_bp.route("/works", methods=["GET"])
@_slnt_auth
@_slnt_prop
def sln_work_track_list():
    works      = _slnt_load()
    status_f   = request.args.get("status",   "all")
    stage_f    = request.args.get("stage",    "all")
    priority_f = request.args.get("priority", "all")
    if status_f   != "all": works = [w for w in works if w.get("status")        == status_f]
    if stage_f    != "all": works = [w for w in works if w.get("current_stage") == stage_f]
    if priority_f != "all": works = [w for w in works if w.get("priority")      == priority_f]
    return jsonify({"success": True, "works": list(reversed(works)), "total": len(works)})


@sln_work_track_bp.route("/works", methods=["POST"])
@_slnt_auth
@_slnt_prop
def sln_work_track_create():
    data = request.get_json(silent=True) or {}
    if not data.get("title", "").strip():
        return jsonify({"success": False, "error": "Work title is required"}), 400
    works = _slnt_load()
    now   = datetime.now().isoformat()
    work  = {
        "id":             _slnt_next_id(),
        "title":          data.get("title", "").strip(),
        "location":       data.get("location", ""),
        "description":    data.get("description", ""),
        "priority":       data.get("priority", "Medium"),
        "estimated_cost": data.get("estimated_cost", ""),
        "identified_by":  data.get("identified_by", _slnt_current_user()),
        "vendor":         data.get("vendor", ""),
        "start_date":     data.get("start_date", ""),
        "end_date":       data.get("end_date", ""),
        "progress":       int(data.get("progress", 0)),
        "remarks":        data.get("remarks", ""),
        "inspection":     data.get("inspection", "Pending"),
        "current_stage":  "Issue Identification",
        "status":         "Active",
        "type":           "Cost Implication",
        "daily_updates":  [],
        "history":        [],
        "created_at":     now,
        "updated_at":     now,
        "created_by":     _slnt_current_user(),
    }
    work["history"].append({
        "stage":     "Issue Identification",
        "action":    "Work Created",
        "by":        _slnt_current_user(),
        "timestamp": now,
        "notes":     data.get("description", ""),
    })
    works.append(work)
    try:
        _slnt_save(works)
    except Exception as e:
        return jsonify({"success": False, "error": f"Failed to save: {e}"}), 500
    return jsonify({"success": True, "work": work, "id": work["id"]})


@sln_work_track_bp.route("/works/<work_id>", methods=["GET"])
@_slnt_auth
@_slnt_prop
def sln_work_track_get(work_id):
    work = next((w for w in _slnt_load() if w["id"] == work_id), None)
    if not work:
        return jsonify({"success": False, "error": "Work not found"}), 404
    return jsonify({"success": True, "work": work})


@sln_work_track_bp.route("/works/<work_id>", methods=["PUT"])
@_slnt_auth
@_slnt_prop
def sln_work_track_update(work_id):
    data  = request.get_json(silent=True) or {}
    works = _slnt_load()
    idx   = next((i for i, w in enumerate(works) if w["id"] == work_id), None)
    if idx is None:
        return jsonify({"success": False, "error": "Work not found"}), 404
    for f in ["title","location","description","priority","estimated_cost",
              "vendor","start_date","end_date","progress","remarks","inspection","status"]:
        if f in data:
            works[idx][f] = data[f]
    works[idx]["updated_at"] = datetime.now().isoformat()
    _slnt_save(works)
    return jsonify({"success": True, "work": works[idx]})


@sln_work_track_bp.route("/works/<work_id>", methods=["DELETE"])
@_slnt_auth
@_slnt_prop
def sln_work_track_delete(work_id):
    works  = _slnt_load()
    before = len(works)
    works  = [w for w in works if w["id"] != work_id]
    if len(works) == before:
        return jsonify({"success": False, "error": "Work not found"}), 404
    _slnt_save(works)
    return jsonify({"success": True})


# ─────────────────────────────────────────────────────────
# ROUTES - STAGE
# ─────────────────────────────────────────────────────────

@sln_work_track_bp.route("/works/<work_id>/stage", methods=["POST"])
@_slnt_auth
@_slnt_prop
def sln_work_track_stage(work_id):
    data  = request.get_json(silent=True) or {}
    works = _slnt_load()
    idx   = next((i for i, w in enumerate(works) if w["id"] == work_id), None)
    if idx is None:
        return jsonify({"success": False, "error": "Work not found"}), 404
    current   = works[idx].get("current_stage", WORKFLOW_STAGES[0])
    ci        = WORKFLOW_STAGES.index(current) if current in WORKFLOW_STAGES else 0
    new_stage = data.get("stage") or WORKFLOW_STAGES[min(ci + 1, len(WORKFLOW_STAGES) - 1)]
    works[idx]["current_stage"] = new_stage
    works[idx]["updated_at"]    = datetime.now().isoformat()
    if new_stage == "Completion & Closure":
        works[idx]["status"] = "Completed"
    works[idx]["history"].append({
        "stage":     new_stage,
        "action":    f"Stage set to: {new_stage}",
        "by":        _slnt_current_user(),
        "timestamp": datetime.now().isoformat(),
        "notes":     data.get("notes", ""),
    })
    _slnt_save(works)
    return jsonify({"success": True, "work": works[idx], "new_stage": new_stage})


# ─────────────────────────────────────────────────────────
# ROUTES - DAILY UPDATE
# ─────────────────────────────────────────────────────────

@sln_work_track_bp.route("/works/<work_id>/daily-update", methods=["POST"])
@_slnt_auth
@_slnt_prop
def sln_work_track_daily_update(work_id):
    data  = request.get_json(silent=True) or {}
    works = _slnt_load()
    idx   = next((i for i, w in enumerate(works) if w["id"] == work_id), None)
    if idx is None:
        return jsonify({"success": False, "error": "Work not found"}), 404
    entry = {
        "date":             data.get("date", datetime.now().strftime("%Y-%m-%d")),
        "progress":         int(data.get("progress", works[idx].get("progress", 0))),
        "remarks":          data.get("remarks", ""),
        "delays":           data.get("delays", ""),
        "revised_timeline": data.get("revised_timeline", ""),
        "by":               _slnt_current_user(),
        "timestamp":        datetime.now().isoformat(),
    }
    works[idx].setdefault("daily_updates", []).append(entry)
    works[idx]["progress"]   = entry["progress"]
    works[idx]["updated_at"] = datetime.now().isoformat()
    _slnt_save(works)
    return jsonify({"success": True, "entry": entry})


# ─────────────────────────────────────────────────────────
# ROUTES - EMAIL
# ─────────────────────────────────────────────────────────

@sln_work_track_bp.route("/trigger-mail", methods=["POST"])
@_slnt_auth
@_slnt_prop
def sln_work_track_trigger_mail():
    data    = request.get_json(silent=True) or {}
    work_id = data.get("work_id", "")
    stage   = data.get("stage", "")
    depts   = data.get("departments", [])
    subj_ov = data.get("subject", "")
    body_ov = data.get("body", "")
    works   = _slnt_load()
    work    = next((w for w in works if w["id"] == work_id), None)
    if not work:
        return jsonify({"success": False, "error": "Work not found"}), 404
    if not depts:
        depts = STAGE_DEPTS.get(stage, ["All"])
    recipients = _slnt_resolve_recipients(depts)
    ctx        = _slnt_build_ctx(work)
    subject    = (subj_ov or DEFAULT_SUBJECTS.get(stage, "[SLN TERMINUS] Work Update: {title}")).format(**ctx)
    body       = (body_ov or DEFAULT_BODIES.get(stage, "Work update for {title}.")).format(**ctx)
    html       = _slnt_build_html(work, subject, body)
    result     = _slnt_send_smtp(recipients, subject, body, html)
    _slnt_log_mail(work_id, stage, recipients,
                  "sent" if result["success"] else "failed",
                  result.get("error", ""))
    if result["success"]:
        return jsonify({"success": True, "recipients": recipients, "count": len(recipients)})
    return jsonify({"success": False, "error": result["error"]}), 500


@sln_work_track_bp.route("/emergency-mail", methods=["POST"])
@_slnt_auth
@_slnt_prop
def sln_work_track_emergency_mail():
    data    = request.get_json(silent=True) or {}
    work_id = data.get("work_id", "")
    works   = _slnt_load()
    work    = next((w for w in works if w["id"] == work_id), None)
    if not work:
        return jsonify({"success": False, "error": "Work not found"}), 404
    subject = data.get("subject") or f"[SLN TERMINUS][EMERGENCY] Immediate Attention: {work.get('title','')}"
    body    = data.get("body")
    if not body:
        ctx  = _slnt_build_ctx(work)
        body = (
            "EMERGENCY NOTICE\n\n"
            "Urgent action required for the following work at SLN TERMINUS.\n\n"
            f"Work ID       : {work.get('id','')}\n"
            f"Work Title    : {ctx['title']}\n"
            f"Location      : {ctx['location']}\n"
            f"Current Stage : {ctx['stage']}\n"
            f"Priority      : {ctx['priority']}\n"
            f"Progress      : {ctx['progress']}%\n"
            f"Remarks       : {ctx['remarks']}\n\n"
            "Please take immediate action.\n\nRegards,\nEPMS Property Management"
        )
    html   = _slnt_build_html(work, subject, body)
    result = _slnt_send_smtp(SLN_EMERGENCY_EMAILS, subject, body, html)
    _slnt_log_mail(work_id, "EMERGENCY", SLN_EMERGENCY_EMAILS,
                  "sent" if result["success"] else "failed",
                  result.get("error", ""))
    if result["success"]:
        return jsonify({"success": True, "recipients": SLN_EMERGENCY_EMAILS,
                        "count": len(SLN_EMERGENCY_EMAILS)})
    return jsonify({"success": False, "error": result["error"]}), 500


@sln_work_track_bp.route("/preview-mail", methods=["POST"])
@_slnt_auth
@_slnt_prop
def sln_work_track_preview_mail():
    data    = request.get_json(silent=True) or {}
    stage   = data.get("stage", "Issue Identification")
    work_id = data.get("work_id", "")
    depts   = data.get("departments", [])
    works   = _slnt_load()
    work    = next((w for w in works if w["id"] == work_id), {}) if work_id else {}
    ctx     = _slnt_build_ctx(work)
    if not depts:
        depts = STAGE_DEPTS.get(stage, ["All"])
    subject = (data.get("subject") or DEFAULT_SUBJECTS.get(stage, "")).format(**ctx)
    body    = (data.get("body")    or DEFAULT_BODIES.get(stage, "")).format(**ctx)
    return jsonify({
        "success":     True,
        "subject":     subject,
        "body":        body,
        "recipients":  _slnt_resolve_recipients(depts),
        "departments": depts,
    })


@sln_work_track_bp.route("/mail-log", methods=["GET"])
@_slnt_auth
@_slnt_prop
def sln_work_track_mail_log():
    if not SLN_WORK_TRACK_LOG_FILE.exists():
        return jsonify({"success": True, "log": []})
    try:
        with open(SLN_WORK_TRACK_LOG_FILE, "r", encoding="utf-8") as fh:
            log = json.load(fh)
        return jsonify({"success": True, "log": list(reversed(log[-200:]))})
    except Exception:
        return jsonify({"success": False, "error": "Log read error"}), 500


# ─────────────────────────────────────────────────────────
# ROUTES - TEMPLATES
# ─────────────────────────────────────────────────────────

@sln_work_track_bp.route("/default-templates", methods=["GET"])
@_slnt_auth
@_slnt_prop
def sln_work_track_default_templates():
    return jsonify({
        "success":     True,
        "stages":      WORKFLOW_STAGES,
        "subjects":    DEFAULT_SUBJECTS,
        "bodies":      DEFAULT_BODIES,
        "stage_depts": STAGE_DEPTS,
        "departments": list(SLN_DEPT_EMAILS.keys()),
    })


@sln_work_track_bp.route("/templates", methods=["GET"])
@_slnt_auth
@_slnt_prop
def sln_work_track_get_templates():
    return jsonify({"success": True, "templates": _slnt_load_templates()})


@sln_work_track_bp.route("/templates", methods=["POST"])
@_slnt_auth
@_slnt_prop
def sln_work_track_save_template():
    data  = request.get_json(silent=True) or {}
    stage = data.get("stage", "")
    if not stage:
        return jsonify({"success": False, "error": "Stage required"}), 400
    templates        = _slnt_load_templates()
    templates[stage] = {
        "subject":     data.get("subject", DEFAULT_SUBJECTS.get(stage, "")),
        "body":        data.get("body",    DEFAULT_BODIES.get(stage, "")),
        "departments": data.get("departments", STAGE_DEPTS.get(stage, ["All"])),
    }
    _slnt_save_templates(templates)
    return jsonify({"success": True})


# ─────────────────────────────────────────────────────────
# ROUTES - STATS & HEALTH
# ─────────────────────────────────────────────────────────

@sln_work_track_bp.route("/stats", methods=["GET"])
@_slnt_auth
@_slnt_prop
def sln_work_track_stats():
    works = _slnt_load()
    return jsonify({
        "success":     True,
        "total":       len(works),
        "active":      sum(1 for w in works if w.get("status") == "Active"),
        "completed":   sum(1 for w in works if w.get("status") == "Completed"),
        "on_hold":     sum(1 for w in works if w.get("status") == "On Hold"),
        "by_stage":    {s: sum(1 for w in works if w.get("current_stage") == s) for s in WORKFLOW_STAGES},
        "by_priority": {p: sum(1 for w in works if w.get("priority") == p) for p in ("High","Medium","Low")},
    })


@sln_work_track_bp.route("/health", methods=["GET"])
def sln_work_track_health():
    return jsonify({
        "success":   True,
        "module":    "sln_work_track",
        "property":  "SLN TERMINUS",
        "timestamp": datetime.now().isoformat(),
    })


# ─────────────────────────────────────────────────────────
# AUTO-SCHEDULER - 08:00 IST DAILY
# ─────────────────────────────────────────────────────────

# Set inside sln_work_track_register(app) — NEVER at module level.
_slnt_flask_app      = None
_slnt_scheduler_inst = None


def sln_work_track_daily_auto_mail():
    """
    Fired by APScheduler at 08:00 IST every day.
    Sends daily status mail for ALL active works AND observations (every stage)
    Runs OUTSIDE request context — never touches flask.session/request.
    """
    import traceback as _tb

    print(f"\n{'='*55}")
    print(f"[SLN AUTO-MAIL] Triggered at {__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M:%S')} IST")
    print(f"{'='*55}")

    def _run():
        try:
            works     = _slnt_load()
            obs_all   = _obs_load()
            active_works = [w for w in works if w.get("status") == "Active"]
            active_obs   = [o for o in obs_all if o.get("status") == "Active"]
            all_works_list = works  # for full list in digest
            all_obs_list   = obs_all

            print(f"[SLN AUTO-MAIL] Active — Works: {len(active_works)} | Obs: {len(active_obs)}")

            if not active_works and not active_obs:
                print("[SLN AUTO-MAIL] Nothing active — skipping digest")
                return

            # ── Build ONE digest email ─────────────────────────
            now_str   = datetime.now().strftime("%d %b %Y, %I:%M %p IST")
            date_str  = datetime.now().strftime("%d %b %Y")
            recipients = _slnt_resolve_recipients(["All"])

            subject = f"[SLN TERMINUS] Daily Status Digest — {len(active_works)} Works · {len(active_obs)} Observations — {date_str}"

            # ── Plain text digest ──────────────────────────────
            lines = [
                f"SLN TERMINUS — Daily Status Digest",
                f"Generated : {now_str}",
                f"{'═'*52}",
                "",
            ]
            pri_ico = lambda p: "🔴" if p=="High" else "🟡" if p=="Medium" else "🟢"

            if active_works:
                lines += [f"🔧 COST IMPLICATION WORKS ({len(active_works)} active)", "─"*52]
                for i, w in enumerate(active_works, 1):
                    lines += [
                        f"  {i}. {pri_ico(w.get('priority',''))} [{w['id']}] {w.get('title','')}",
                        f"     📍 {w.get('location','')}   |   Stage: {w.get('current_stage','')}",
                        f"     📈 Progress: {w.get('progress',0)}%   |   ₹ {w.get('estimated_cost','')}",
                        "",
                    ]

            if active_obs:
                lines += [f"👁️  OBSERVATIONS ({len(active_obs)} active)", "─"*52]
                for i, o in enumerate(active_obs, 1):
                    lines += [
                        f"  {i}. {pri_ico(o.get('priority',''))} [{o['id']}] {o.get('title','')}",
                        f"     Stage: {o.get('current_stage','')}   |   Raised by: {o.get('raised_by','')}",
                        "",
                    ]

            lines += ["\u2550"*52, "Log in to EPMS dashboard for full details.", "Regards,", "emerZhent Property Management Services"]
            plain_body = "\n".join(lines)

            # ── HTML digest with table + highlights ───────────────
            PRI_COLOR = {"High":"#ff4d6a","Medium":"#f59e0b","Low":"#2dd882"}
            STAGE_HIGHLIGHT = {
                "Issue Identification":"#f5a623",
                "GM Approval":"#4d90ff",
                "Procurement / Finance Action":"#b06cff",
                "Procurement/Finance Action":"#b06cff",
                "Management Approval":"#17d4e8",
                "Contract Awarded":"#ff7c3a",
                "Execution & Daily Monitoring":"#2dd882",
                "Completion & Closure":"#2dd882",
                "Observation Raised by GM/Management":"#a855f7",
                "PM Review & Response":"#818cf8",
                "GM Verification":"#38bdf8",
                "Work In Progress":"#4ade80",
                "Completed":"#2dd882",
            }

            def stage_badge(s):
                c = STAGE_HIGHLIGHT.get(s,"#888")
                return (f'<span style="display:inline-block;padding:2px 8px;border-radius:12px;'
                        f'background:rgba(255,255,255,.07);color:{c};border:1px solid {c}44;'
                        f'font-size:11px;font-weight:600;">{s}</span>')

            def pri_badge(p):
                c = PRI_COLOR.get(p,"#888")
                return (f'<span style="display:inline-block;padding:2px 8px;border-radius:12px;'
                        f'background:{c}22;color:{c};border:1px solid {c}66;'
                        f'font-size:11px;font-weight:700;">{p}</span>')

            def prog_bar(pct):
                pct = int(pct or 0)
                bar_color = "#2dd882" if pct>=80 else "#f5a623" if pct>=40 else "#ff4d6a"
                return (f'<div style="display:flex;align-items:center;gap:6px;">'
                        f'<div style="flex:1;height:6px;background:#1e2636;border-radius:3px;overflow:hidden;min-width:60px;">'
                        f'<div style="width:{pct}%;height:100%;background:{bar_color};border-radius:3px;"></div></div>'
                        f'<span style="font-size:11px;color:#aaa;font-family:monospace;">{pct}%</span></div>')

            works_rows = "".join(
                f'<tr style="border-bottom:1px solid #1e2636;">'
                f'<td style="padding:9px 12px;font-family:monospace;font-size:11px;color:#f5a623;">{w["id"]}</td>'
                f'<td style="padding:9px 12px;font-weight:600;color:#dde4f0;">{w.get("title","")}<br>'
                f'<span style="font-size:10px;color:#8899aa;">📍 {w.get("location","")}</span></td>'
                f'<td style="padding:9px 12px;">{pri_badge(w.get("priority",""))}</td>'
                f'<td style="padding:9px 12px;">{stage_badge(w.get("current_stage",""))}</td>'
                f'<td style="padding:9px 12px;min-width:100px;">{prog_bar(w.get("progress",0))}</td>'
                f'<td style="padding:9px 12px;font-size:11px;color:#aaa;">₹ {w.get("estimated_cost","")}</td>'
                f'</tr>'
                for w in active_works
            ) if active_works else f'<tr><td colspan="6" style="padding:14px;text-align:center;color:#556;">No active works</td></tr>'

            obs_rows = "".join(
                f'<tr style="border-bottom:1px solid #1e2636;">'
                f'<td style="padding:9px 12px;font-family:monospace;font-size:11px;color:#c084fc;">{o["id"]}</td>'
                f'<td style="padding:9px 12px;font-weight:600;color:#dde4f0;">{o.get("title","")}<br>'
                f'<span style="font-size:10px;color:#8899aa;">{'📍 ' + o.get('location','') if o.get('location') else ''}</span></td>'
                f'<td style="padding:9px 12px;">{pri_badge(o.get("priority",""))}</td>'
                f'<td style="padding:9px 12px;">{stage_badge(o.get("current_stage",""))}</td>'
                f'<td style="padding:9px 12px;font-size:11px;color:#aaa;">{o.get("raised_by","")}</td>'
                f'<td style="padding:9px 12px;font-size:10px;color:#8899aa;">{(o.get("created_at","") or "")[:10]}</td>'
                f'</tr>'
                for o in active_obs
            ) if active_obs else f'<tr><td colspan="6" style="padding:14px;text-align:center;color:#556;">No active observations</td></tr>'

            html_body = f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8"></head>
<body style="margin:0;padding:0;background:#07090d;font-family:'Inter',Arial,sans-serif;color:#dde4f0;">
<div style="max-width:700px;margin:0 auto;padding:24px 16px;">

  <!-- Header -->
  <div style="background:#0c1018;border:1px solid #1e2636;border-radius:10px;padding:20px 24px;margin-bottom:20px;border-top:3px solid #f5a623;">
    <div style="font-size:20px;font-weight:800;color:#f5a623;letter-spacing:.02em;">SLN TERMINUS</div>
    <div style="font-size:13px;color:#8899aa;margin-top:2px;">Daily Status Digest — {date_str}</div>
    <div style="font-size:11px;color:#8899aa;margin-top:6px;">Generated: {now_str}</div>
  </div>

  <!-- Summary pills -->
  <div style="display:flex;gap:12px;margin-bottom:20px;flex-wrap:wrap;">
    <div style="background:#0c1018;border:1px solid #f5a62333;border-radius:8px;padding:12px 20px;flex:1;min-width:120px;">
      <div style="font-size:22px;font-weight:700;color:#f5a623;">{len(active_works)}</div>
      <div style="font-size:11px;color:#8899aa;">Active Works</div>
    </div>
    <div style="background:#0c1018;border:1px solid #a855f733;border-radius:8px;padding:12px 20px;flex:1;min-width:120px;">
      <div style="font-size:22px;font-weight:700;color:#c084fc;">{len(active_obs)}</div>
      <div style="font-size:11px;color:#8899aa;">Active Observations</div>
    </div>
    <div style="background:#0c1018;border:1px solid #ff4d6a33;border-radius:8px;padding:12px 20px;flex:1;min-width:120px;">
      <div style="font-size:22px;font-weight:700;color:#ff4d6a;">{sum(1 for w in active_works if w.get("priority")=="High") + sum(1 for o in active_obs if o.get("priority")=="High")}</div>
      <div style="font-size:11px;color:#8899aa;">High Priority</div>
    </div>
  </div>

  <!-- Works table -->
  <div style="background:#0c1018;border:1px solid #1e2636;border-radius:10px;overflow:hidden;margin-bottom:16px;">
    <div style="padding:12px 16px;border-bottom:1px solid #1e2636;display:flex;align-items:center;gap:8px;">
      <span style="font-size:14px;">🔧</span>
      <span style="font-weight:700;color:#f5a623;">Cost Implication Works</span>
      <span style="margin-left:auto;background:#f5a62322;color:#f5a623;border:1px solid #f5a62344;padding:2px 10px;border-radius:12px;font-size:11px;">{len(active_works)} active</span>
    </div>
    <table style="width:100%;border-collapse:collapse;">
      <thead>
        <tr style="background:#070c14;">
          <th style="padding:8px 12px;text-align:left;font-size:9px;color:#aabbcc;text-transform:uppercase;letter-spacing:.1em;font-weight:700;">Work ID</th>
          <th style="padding:8px 12px;text-align:left;font-size:9px;color:#aabbcc;text-transform:uppercase;letter-spacing:.1em;font-weight:700;">Title / Location</th>
          <th style="padding:8px 12px;text-align:left;font-size:9px;color:#aabbcc;text-transform:uppercase;letter-spacing:.1em;font-weight:700;">Priority</th>
          <th style="padding:8px 12px;text-align:left;font-size:9px;color:#aabbcc;text-transform:uppercase;letter-spacing:.1em;font-weight:700;">Current Stage</th>
          <th style="padding:8px 12px;text-align:left;font-size:9px;color:#aabbcc;text-transform:uppercase;letter-spacing:.1em;font-weight:700;">Progress</th>
          <th style="padding:8px 12px;text-align:left;font-size:9px;color:#aabbcc;text-transform:uppercase;letter-spacing:.1em;font-weight:700;">Est. Cost</th>
        </tr>
      </thead>
      <tbody>{works_rows}</tbody>
    </table>
  </div>

  <!-- Obs table -->
  <div style="background:#0c1018;border:1px solid #1e2636;border-radius:10px;overflow:hidden;margin-bottom:16px;">
    <div style="padding:12px 16px;border-bottom:1px solid #1e2636;display:flex;align-items:center;gap:8px;">
      <span style="font-size:14px;">👁️</span>
      <span style="font-weight:700;color:#c084fc;">Observations</span>
      <span style="margin-left:auto;background:#a855f722;color:#c084fc;border:1px solid #a855f744;padding:2px 10px;border-radius:12px;font-size:11px;">{len(active_obs)} active</span>
    </div>
    <table style="width:100%;border-collapse:collapse;">
      <thead>
        <tr style="background:#070c14;">
          <th style="padding:8px 12px;text-align:left;font-size:9px;color:#aabbcc;text-transform:uppercase;letter-spacing:.1em;font-weight:700;">Obs ID</th>
          <th style="padding:8px 12px;text-align:left;font-size:9px;color:#aabbcc;text-transform:uppercase;letter-spacing:.1em;font-weight:700;">Title / Location</th>
          <th style="padding:8px 12px;text-align:left;font-size:9px;color:#aabbcc;text-transform:uppercase;letter-spacing:.1em;font-weight:700;">Priority</th>
          <th style="padding:8px 12px;text-align:left;font-size:9px;color:#aabbcc;text-transform:uppercase;letter-spacing:.1em;font-weight:700;">Current Stage</th>
          <th style="padding:8px 12px;text-align:left;font-size:9px;color:#aabbcc;text-transform:uppercase;letter-spacing:.1em;font-weight:700;">Raised By</th>
          <th style="padding:8px 12px;text-align:left;font-size:9px;color:#aabbcc;text-transform:uppercase;letter-spacing:.1em;font-weight:700;">Date</th>
        </tr>
      </thead>
      <tbody>{obs_rows}</tbody>
    </table>
  </div>

  <!-- Footer -->
  <div style="text-align:center;padding:20px 16px;border-top:1px solid #1e2636;margin-top:8px;">
    <p style="font-size:11px;color:#aabbcc;margin:0 0 10px;">Log in to the EPMS dashboard for full details and actions.</p>
    <a href="https://descriptive-joya-unsolidified.ngrok-free.dev/login" target="_blank"
       style="display:inline-block;padding:10px 28px;background:linear-gradient(135deg,#f5a623,#d4870a);
              color:#000000;font-size:12px;font-weight:700;text-decoration:none;border-radius:6px;letter-spacing:.03em;">
      &#127970;&nbsp; Open EPMS Dashboard
    </a>
    <p style="font-size:10px;color:#8899aa;margin:10px 0 0;">
      SLN TERMINUS &nbsp;·&nbsp; emerZhent Property Management Services
    </p>
  </div>

</div></body></html>"""

            result = _slnt_send_smtp(recipients, subject, plain_body, html_body)
            status = "digest-sent" if result["success"] else "digest-failed"
            all_ids = [w["id"] for w in active_works] + [o["id"] for o in active_obs]
            _slnt_log_mail("DIGEST", "daily-digest", recipients, status, result.get("error",""))
            print(f"[SLN AUTO-MAIL] {'✅ DIGEST SENT' if result['success'] else '❌ DIGEST FAILED'} → {len(recipients)} recipients | {len(active_works)} works + {len(active_obs)} obs")

        except Exception as exc:
            print(f"[SLN AUTO-MAIL] ❌ EXCEPTION: {exc}")
            _tb.print_exc()
            _slnt_log_mail("AUTO", "all-stages", [], "auto-error", str(exc))

    if _slnt_flask_app is not None:
        with _slnt_flask_app.app_context():
            _run()
    else:
        print("[SLN AUTO-MAIL] ⚠️  _slnt_flask_app is None — "
              "sln_work_track_register(app) was not called!")
        _run()



# ─────────────────────────────────────────────────────────
# REGISTRATION HELPER — call ONCE in server.py
# ─────────────────────────────────────────────────────────

def sln_work_track_register(app):
    """
    Call in server.py after app = Flask(...):

        from sln_work_track_routes import sln_work_track_register
        sln_work_track_register(app)

    Order:
      1. Store Flask app ref        → scheduler always has app_context
      2. Register blueprint
      3. Create + start scheduler   → app ref guaranteed to exist
    """
    global _slnt_flask_app, _slnt_scheduler_inst

    # 1. Store app reference FIRST
    _slnt_flask_app = app

    # 2. Register blueprint
    app.register_blueprint(sln_work_track_bp, url_prefix="/sln_work_track")
    print("✅ SLN Work Track Blueprint registered at /sln_work_track")

    # 3. Start scheduler only once
    if _slnt_scheduler_inst is not None:
        print("ℹ️  SLN Work Track Scheduler already running — skipped.")
        return

    try:
        from apscheduler.schedulers.background import BackgroundScheduler
        from apscheduler.triggers.cron import CronTrigger

        _slnt_scheduler_inst = BackgroundScheduler(
            timezone="Asia/Kolkata",
            job_defaults={
                "misfire_grace_time": 600,   # allow up to 10 min late
                "coalesce":           True,  # collapse missed runs into one
            },
        )
        _slnt_scheduler_inst.add_job(
            func=sln_work_track_daily_auto_mail,
            # ✅ Changed to 08:00 AM
            trigger=CronTrigger(hour=8, minute=0, timezone="Asia/Kolkata"),
            # ✅ Updated ID to match new time
            id="sln_work_track_0800",
            name="SLN TERMINUS Works Daily Mail 08:00 IST",
            replace_existing=True,
        )
        _slnt_scheduler_inst.start()

        # ✅ Updated get_job to match the new ID
        job = _slnt_scheduler_inst.get_job("sln_work_track_0800")  
        next_run = (job.next_run_time.strftime("%Y-%m-%d %H:%M:%S %Z")
                    if job and job.next_run_time else "unknown")
        print(f"✅ SLN Work Track Scheduler started — next run: {next_run}")

    except Exception as exc:
        import traceback
        print(f"⚠️  SLN Work Track Scheduler setup failed: {exc}")
        traceback.print_exc()

# ═══════════════════════════════════════════════════════════════
# OBSERVATIONS MODULE
# GM/Management → PM → GM → Management → Procurement → PM
# ═══════════════════════════════════════════════════════════════

from werkzeug.utils import secure_filename

SLN_OBSERVATIONS_FILE = BASE_DIR / "static" / "data" / "sln_observations.json"
SLN_OBS_UPLOADS_DIR   = BASE_DIR / "uploads" / "sln_observations"
SLN_OBS_UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
SLN_OBSERVATIONS_FILE.parent.mkdir(parents=True, exist_ok=True)

# OBSERVATIONS WORKFLOW DEFINITION
OBS_STAGES = [
    "Observation Raised by GM/Management",
    "PM Review & Response", 
    "GM Verification",
    "Management Approval",
    "Procurement/Finance Action",
    "Work In Progress",
    "Completed",
]

OBS_STAGE_DEPTS = {
    # GM/Management identifies observation → sends to Property Manager
    "Observation Raised by GM/Management": ["PM"],
    
    # Property Manager reviews & responds → sends to GM/Management
    "PM Review & Response": ["GM", "Management"],
    
    # GM verifies → sends to Management for approval
    "GM Verification": ["Management"],
    
    # Management approves → sends to Procurement/Finance
    "Management Approval": ["Procurement", "Finance"],
    
    # Procurement/Finance completes action → sends to Property Manager
    "Procurement/Finance Action": ["PM"],
    
    # Property Manager monitors work → updates GM/Management
    "Work In Progress": ["GM", "Management"],
    
    # Completion → informs all
    "Completed": ["All"],
}

OBS_SUBJECTS = {
    "Observation Raised by GM/Management": "[SLN TERMINUS][OBS] New Observation Identified: {title}",
    "PM Review & Response": "[SLN TERMINUS][OBS] PM Response Submitted: {title}",
    "GM Verification": "[SLN TERMINUS][OBS] GM Verification Required: {title}",
    "Management Approval": "[SLN TERMINUS][OBS] Management Approval Required: {title}",
    "Procurement/Finance Action": "[SLN TERMINUS][OBS] Procurement/Finance Action Completed: {title}",
    "Work In Progress": "[SLN TERMINUS][OBS] Work In Progress Update: {title}",
    "Completed": "[SLN TERMINUS][OBS] Observation Closed: {title}",
}

OBS_BODIES = {
    "Observation Raised by GM/Management": (
        "Dear Property Manager,\n\n"
        "👁️  A new observation has been raised by GM / Management. Your prompt review and response is required.\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "📋 OBSERVATION DETAILS\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "  🔢  Observation ID : {obs_id}\n"
        "  📅  Date           : {obs_date}\n"
        "  👤  Raised By      : {raised_by_name}\n"
        "  📝  Title          : {title}\n"
        "  📍  Location       : {location}\n"
        "  ⚠️   Priority       : {priority}\n"
        "  ⏱️   Expected Date  : {expected_date}\n"
        "  🔍  Inspection Req : {inspection}\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "  🗒️  DESCRIPTION\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "  {description}\n\n"
        "Please review, assess, and submit your response with cost implication status.\n\n"
        "Regards,\nemerZhent Property Management Services"
    ),
    "PM Review & Response": (
        "Dear GM / Management,\n\n"
        "📨 Property Manager has reviewed the observation and submitted a response.\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "📋 OBSERVATION & PM RESPONSE\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "  🔢  Observation ID  : {obs_id}\n"
        "  📝  Title           : {title}\n"
        "  📍  Location        : {location}\n"
        "  ⚠️   Priority        : {priority}\n"
        "  👤  Raised By       : {raised_by_name}\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "  💬  PM Response     : {pm_response}\n"
        "  💰  Cost Implication: {is_cost_implication}\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "Please review the PM response and provide further instructions or approval.\n\n"
        "Regards,\nemerZhent Property Management Services"
    ),
    "GM Verification": (
        "Dear Management,\n\n"
        "✅ GM has reviewed and verified the observation. Management approval is now required.\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "📋 VERIFICATION DETAILS\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "  🔢  Observation ID : {obs_id}\n"
        "  📝  Title          : {title}\n"
        "  🗒️   GM Notes       : {gm_notes}\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "Kindly review and provide approval to proceed.\n\n"
        "Regards,\nemerZhent Property Management Services"
    ),
    "Management Approval": (
        "Dear Procurement / Finance Team,\n\n"
        "📦 Management has approved the observation. Please initiate the procurement process immediately.\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "📋 APPROVAL DETAILS\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "  🔢  Observation ID  : {obs_id}\n"
        "  📝  Title           : {title}\n"
        "  💰  Approved Budget : ₹ {approved_budget}\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "Please initiate procurement, obtain quotations and share comparative statement.\n\n"
        "Regards,\nemerZhent Property Management Services"
    ),
    "Procurement/Finance Action": (
        "Dear Property Manager,\n\n"
        "🤝 Procurement / Finance action has been completed. Please coordinate and monitor work execution.\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "📌 VENDOR & COST DETAILS\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "  🔢  Observation ID : {obs_id}\n"
        "  📝  Title          : {title}\n"
        "  🏭  Vendor         : {vendor}\n"
        "  💰  Final Cost     : ₹ {final_cost}\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "Please monitor and report work progress regularly.\n\n"
        "Regards,\nemerZhent Property Management Services"
    ),
    "Work In Progress": (
        "Dear GM / Management,\n\n"
        "🏗️  Work is currently in progress for the following observation.\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "📊 PROGRESS UPDATE\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "  🔢  Observation ID : {obs_id}\n"
        "  📝  Title          : {title}\n"
        "  📈  Progress       : {progress}%\n"
        "  🎯  Status         : {work_status}\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "Regards,\nemerZhent Property Management Services"
    ),
    "Completed": (
        "Dear All,\n\n"
        "🏆 The observation work has been completed and closed successfully.\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "✅ CLOSURE SUMMARY\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "  🔢  Observation ID  : {obs_id}\n"
        "  📝  Title           : {title}\n"
        "  📅  Completion Date : {completion_date}\n"
        "  💰  Final Cost      : ₹ {final_cost}\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "Regards,\nemerZhent Property Management Services"
    ),
}

# ── Helpers ────────────────────────────────────────────────

def _obs_load():
    if not SLN_OBSERVATIONS_FILE.exists():
        return []
    try:
        with open(SLN_OBSERVATIONS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []

def _obs_save(data):
    SLN_OBSERVATIONS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(SLN_OBSERVATIONS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, default=str)

def _obs_next_id():
    obs  = _obs_load()
    nums = []
    for o in obs:
        try:   
            nums.append(int(o.get("id","OBS-0000").split("-")[1]))
        except: 
            nums.append(0)
    return f"OBS-{(max(nums)+1 if nums else 1):04d}"

def _obs_ctx(ob):
    return {
        "obs_id":              ob.get("id",""),
        "title":               ob.get("title",""),
        "obs_date":            ob.get("obs_date",""),
        "location":            ob.get("location",""),
        "priority":            ob.get("priority",""),
        "expected_date":       ob.get("expected_date",""),
        "description":         ob.get("description",""),
        "remarks":             ob.get("remarks",""),
        "inspection":          ob.get("inspection",""),
        "raised_by":           ob.get("raised_by",""),
        "raised_by_name":      ob.get("raised_by_name",""),
        "pm_response":         ob.get("pm_response",""),
        "is_cost_implication": ob.get("is_cost_implication","Pending"),
        "gm_notes":            ob.get("gm_notes",""),
        "approved_budget":     ob.get("approved_budget",""),
        "vendor":              ob.get("vendor",""),
        "final_cost":          ob.get("final_cost",""),
        "progress":            ob.get("progress",0),
        "work_status":         ob.get("work_status",""),
        "completion_date":     ob.get("completion_date",""),
        "date":                datetime.now().strftime("%d %b %Y"),
    }

def _obs_build_html(ob, subject, plain_body):
    """Purple-themed structured HTML email for observations."""
    stage = ob.get("current_stage", OBS_STAGES[0])
    si    = OBS_STAGES.index(stage) if stage in OBS_STAGES else 0
    steps = ""
    for i, s in enumerate(OBS_STAGES):
        if   i < si:  dot_bg,dot_clr,num,lbl_clr,lbl_w = "#22c55e","#fff","&#10003;","#22c55e","normal"
        elif i == si: dot_bg,dot_clr,num,lbl_clr,lbl_w = "#a855f7","#fff",str(i+1),"#a855f7","700"
        else:         dot_bg,dot_clr,num,lbl_clr,lbl_w = "#2d3748","#718096",str(i+1),"#6b7280","normal"
        steps += (
            f'<table role="presentation" cellpadding="0" cellspacing="0" border="0" style="margin-bottom:8px;border-collapse:collapse;">'
            f'<tr>'
            f'<td style="width:28px;min-width:28px;max-width:28px;padding:0;vertical-align:middle;">'
            f'<div style="width:28px;height:28px;border-radius:50%;background:{dot_bg};color:{dot_clr};'
            f'font-size:11px;font-weight:700;line-height:28px;text-align:center;font-family:Arial,sans-serif;">{num}</div>'
            f'</td>'
            f'<td style="padding:0 0 0 10px;vertical-align:middle;">'
            f'<span style="font-size:12px;font-family:Arial,sans-serif;color:{lbl_clr};font-weight:{lbl_w};white-space:nowrap;">{s}</span>'
            f'</td></tr></table>'
        )

    LOGIN_URL = "https://descriptive-joya-unsolidified.ngrok-free.dev/login"

    # Build a structured details table from observation data
    ctx = _obs_ctx(ob)
    rows = [
        ("Observation ID",  ctx.get("obs_id","")),
        ("Date",            ctx.get("obs_date","")),
        ("Raised By",       ctx.get("raised_by_name","") or ctx.get("raised_by","")),
        ("Title",           ctx.get("title","")),
        ("Location",        ctx.get("location","")),
        ("Priority",        ctx.get("priority","")),
        ("Expected Completion", ctx.get("expected_date","")),
        ("Inspection Required", ctx.get("inspection","")),
        ("Cost Implication", ctx.get("is_cost_implication","Pending")),
        ("Current Stage",   stage),
    ]
    if ctx.get("pm_response"):
        rows.append(("PM Response", ctx["pm_response"]))
    if ctx.get("description"):
        rows.append(("Description", ctx["description"]))
    if ctx.get("remarks"):
        rows.append(("Remarks", ctx["remarks"]))

    details_rows_html = ""
    for lbl, val in rows:
        if not val:
            val_style = "color:#8b949e;"
        else:
            val_style = "color:#e6edf3;font-weight:500;"
        details_rows_html += (
            f'<tr>'
            f'<td style="padding:6px 12px 6px 0;font-size:11px;color:#8b949e;'
            f'font-family:Arial,sans-serif;white-space:nowrap;vertical-align:top;'
            f'text-transform:uppercase;letter-spacing:.04em;border-bottom:1px solid #21262d;width:35%;">{lbl}</td>'
            f'<td style="padding:6px 0 6px 12px;font-size:12px;{val_style}'
            f'font-family:Arial,sans-serif;vertical-align:top;border-bottom:1px solid #21262d;">{val or "—"}</td>'
            f'</tr>'
        )

    body_html = plain_body.replace("\n", "<br>")
    
    return (
        '<!DOCTYPE html><html><head><meta charset="UTF-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '</head>'
        '<body style="margin:0;padding:20px;background:#0d1117;font-family:Arial,sans-serif;">'
        '<div style="max-width:640px;margin:0 auto;background:#161b22;border:1px solid #30363d;border-radius:12px;overflow:hidden;">'

        # Header
        '<div style="background:linear-gradient(135deg,#7c3aed,#4c1d95);padding:20px 26px;">'
        f'<p style="margin:0 0 4px;font-size:10px;color:#ddd6fe;letter-spacing:.12em;'
        f'text-transform:uppercase;font-family:Arial,sans-serif;">SLN TERMINUS &#8212; OBSERVATIONS</p>'
        f'<h2 style="margin:0 0 2px;color:#fff;font-size:17px;font-family:Arial,sans-serif;font-weight:700;">{ob.get("title","Observation")}</h2>'
        f'<p style="margin:6px 0 0;color:#ddd6fe;font-size:11px;font-family:Arial,sans-serif;">{subject}</p>'
        '</div>'

        # Workflow pipeline
        '<div style="padding:4px 26px 16px;">'
        '<p style="font-size:9px;color:#8b949e;text-transform:uppercase;letter-spacing:.12em;'
        'margin:0 0 10px;font-family:Arial,sans-serif;">Workflow Progress</p>'
        f'{steps}'
        '</div>'

        # Details table
        '<div style="margin:0 26px 20px;background:#0d1117;border:1px solid #21262d;border-radius:8px;overflow:hidden;">'
        '<div style="padding:10px 16px;background:#161b22;border-bottom:1px solid #21262d;">'
        '<p style="margin:0;font-size:9px;color:#8b949e;text-transform:uppercase;letter-spacing:.12em;font-family:Arial,sans-serif;">Observation Details</p>'
        '</div>'
        f'<table role="presentation" cellpadding="0" cellspacing="0" border="0" style="width:100%;border-collapse:collapse;padding:0 16px;">'
        f'<tbody style="display:block;padding:6px 16px 10px;">{details_rows_html}</tbody>'
        f'</table>'
        '</div>'

        # Message body
        f'<div style="margin:0 26px 20px;padding:16px;background:#0d1117;border:1px solid #21262d;'
        f'border-radius:8px;font-size:13px;color:#e6edf3;line-height:1.8;font-family:Arial,sans-serif;">{body_html}</div>'

        # CTA Button
        '<div style="padding:4px 26px 24px;text-align:center;">'
        '<p style="font-size:12px;color:#adbac7;margin:0 0 14px;font-family:Arial,sans-serif;">'
        'Log in to the EPMS dashboard to view full details, respond or take action:</p>'
        '<table role="presentation" cellpadding="0" cellspacing="0" border="0" style="margin:0 auto;">'
        '<tr><td style="border-radius:8px;background:linear-gradient(135deg,#7c3aed,#4c1d95);padding:0;">'
        f'<a href="{LOGIN_URL}" target="_blank" style="display:inline-block;padding:12px 30px;'
        f'font-family:Arial,sans-serif;font-size:13px;font-weight:700;color:#fff;'
        f'text-decoration:none;border-radius:8px;letter-spacing:.03em;">📊 Login to EPMS Dashboard</a>'
        '</td></tr></table>'
        '</div>'

        # Footer
        '<div style="padding:12px 26px;border-top:1px solid #21262d;text-align:center;'
        'font-size:10px;color:#6b7280;font-family:Arial,sans-serif;">'
        f'emerZhent Property Management Services (LLP) | Auto-generated | '
        f'{datetime.now().strftime("%d %b %Y %H:%M")} IST'
        '<br><span style="font-size:9px;">System-generated notification. Do not reply to this email.</span>'
        '</div>'

        '</div></body></html>'
    )

def _obs_send_mail(ob, stage, override_body=None):
    ctx        = _obs_ctx(ob)
    subject    = OBS_SUBJECTS.get(stage, "[SLN TERMINUS][OBS] Update: {title}").format(**ctx)
    body       = override_body or OBS_BODIES.get(stage, "Observation update.").format(**ctx)
    recipients = _slnt_resolve_recipients(OBS_STAGE_DEPTS.get(stage, ["All"]))
    html       = _obs_build_html(ob, subject, body)
    result     = _slnt_send_smtp(recipients, subject, body, html)
    _slnt_log_mail(ob["id"], f"OBS|{stage}", recipients,
                  "sent" if result["success"] else "failed",
                  result.get("error",""))
    return result, recipients


# ── CRUD ───────────────────────────────────────────────────

@sln_work_track_bp.route("/observations", methods=["GET"])
@_slnt_auth
@_slnt_prop
def obs_list():
    return jsonify({"success":True,"observations":list(reversed(_obs_load())),"total":len(_obs_load())})


@sln_work_track_bp.route("/observations", methods=["POST"])
@_slnt_auth
@_slnt_prop
def obs_create():
    # Supports multipart (with image) or JSON
    if request.content_type and "multipart" in request.content_type:
        data  = request.form.to_dict()
        image = request.files.get("image")
    else:
        data  = request.get_json(silent=True) or {}
        image = None

    if not data.get("title","").strip():
        return jsonify({"success":False,"error":"Title is required"}), 400

    now   = datetime.now().isoformat()
    ob_id = _obs_next_id()

    # Save image if present
    image_path = ""
    if image and image.filename:
        ext = image.filename.rsplit(".",1)[-1].lower()
        if ext in {"png","jpg","jpeg","gif","webp","pdf"}:
            fname = secure_filename(f"{ob_id}_{image.filename}")
            image.save(str(SLN_OBS_UPLOADS_DIR / fname))
            image_path = f"/sln_work_track/obs-image/{fname}"

    ob = {
        "id":                ob_id,
        "title":             data.get("title","").strip(),
        "obs_date":          data.get("obs_date", datetime.now().strftime("%Y-%m-%d")),
        "location":          data.get("location",""),
        "priority":          data.get("priority","Medium"),
        "expected_date":     data.get("expected_date",""),
        "description":       data.get("description",""),
        "remarks":           data.get("remarks",""),
        "inspection":        data.get("inspection","Yes"),
        "image_path":        image_path,
        "raised_by":         data.get("raised_by", _slnt_current_user()),
        "raised_by_name":    data.get("raised_by_name",""),
        "current_stage":     "Observation Raised by GM/Management",
        "pm_response":       "",
        "is_cost_implication": "Pending",
        "gm_notes":          "",
        "approved_budget":   "",
        "vendor":            "",
        "final_cost":        "",
        "progress":          0,
        "work_status":       "",
        "completion_date":   "",
        "status":            "Active",
        "history":           [],
        "created_at":        now,
        "updated_at":        now,
    }
    ob["history"].append({
        "stage":"Observation Raised by GM/Management",
        "action":"Observation Created",
        "by":_slnt_current_user(),
        "timestamp":now,
        "notes":data.get("description",""),
    })
    obs = _obs_load()
    obs.append(ob)
    try:
        _obs_save(obs)
    except Exception as e:
        return jsonify({"success": False, "error": f"Failed to save observation: {e}"}), 500

    result, recipients = _obs_send_mail(ob, "Observation Raised by GM/Management")
    return jsonify({"success":True,"observation":ob,"id":ob_id,
                    "mail_sent":result["success"],"recipients":recipients})


@sln_work_track_bp.route("/observations/<obs_id>", methods=["GET"])
@_slnt_auth
@_slnt_prop
def obs_get(obs_id):
    ob = next((o for o in _obs_load() if o["id"]==obs_id), None)
    if not ob: return jsonify({"success":False,"error":"Not found"}),404
    return jsonify({"success":True,"observation":ob})


@sln_work_track_bp.route("/observations/<obs_id>", methods=["PUT"])
@_slnt_auth
@_slnt_prop
def obs_update(obs_id):
    data = request.get_json(silent=True) or {}
    obs  = _obs_load()
    idx  = next((i for i,o in enumerate(obs) if o["id"]==obs_id), None)
    if idx is None: return jsonify({"success":False,"error":"Not found"}),404
    for f in ["title","location","description","priority","expected_date",
              "remarks","inspection","pm_response","is_cost_implication",
              "gm_notes","approved_budget","vendor","final_cost","progress",
              "work_status","completion_date","status","raised_by_name"]:
        if f in data: obs[idx][f] = data[f]
    obs[idx]["updated_at"] = datetime.now().isoformat()
    _obs_save(obs)
    return jsonify({"success":True,"observation":obs[idx]})


@sln_work_track_bp.route("/observations/<obs_id>", methods=["DELETE"])
@_slnt_auth
@_slnt_prop
def obs_delete(obs_id):
    obs    = _obs_load()
    before = len(obs)
    obs    = [o for o in obs if o["id"]!=obs_id]
    if len(obs)==before: return jsonify({"success":False,"error":"Not found"}),404
    _obs_save(obs)
    return jsonify({"success":True})


# ── PM submits response ────────────────────────────────────

@sln_work_track_bp.route("/observations/<obs_id>/pm-response", methods=["POST"])
@_slnt_auth
@_slnt_prop
def obs_pm_response(obs_id):
    data = request.get_json(silent=True) or {}
    obs  = _obs_load()
    idx  = next((i for i,o in enumerate(obs) if o["id"]==obs_id), None)
    if idx is None: return jsonify({"success":False,"error":"Not found"}),404

    obs[idx]["pm_response"] = data.get("pm_response","")
    obs[idx]["is_cost_implication"] = data.get("is_cost_implication","No")
    obs[idx]["current_stage"] = "PM Review & Response"
    obs[idx]["updated_at"] = datetime.now().isoformat()
    
    obs[idx]["history"].append({
        "stage":"PM Review & Response",
        "action":"PM Response Submitted",
        "by":_slnt_current_user(),
        "timestamp":datetime.now().isoformat(),
        "notes":data.get("pm_response",""),
    })
    
    _obs_save(obs)
    result, recipients = _obs_send_mail(obs[idx], "PM Review & Response")
    return jsonify({
        "success": True,
        "observation": obs[idx],
        "mail_sent": result["success"],
        "recipients": recipients,
        "error": result.get("error", "") if not result["success"] else ""
    })


# ── GM Verification ────────────────────────────────────────

@sln_work_track_bp.route("/observations/<obs_id>/gm-verify", methods=["POST"])
@_slnt_auth
@_slnt_prop
def obs_gm_verify(obs_id):
    data = request.get_json(silent=True) or {}
    obs  = _obs_load()
    idx  = next((i for i,o in enumerate(obs) if o["id"]==obs_id), None)
    if idx is None: return jsonify({"success":False,"error":"Not found"}),404

    obs[idx]["gm_notes"] = data.get("gm_notes","")
    obs[idx]["current_stage"] = "GM Verification"
    obs[idx]["updated_at"] = datetime.now().isoformat()
    
    obs[idx]["history"].append({
        "stage": "GM Verification",
        "action": "GM Verified Observation",
        "by": _slnt_current_user(),
        "timestamp": datetime.now().isoformat(),
        "notes": data.get("gm_notes",""),
    })
    
    _obs_save(obs)
    result, recipients = _obs_send_mail(obs[idx], "GM Verification")
    return jsonify({"success": True, "observation": obs[idx]})


# ── Management Approval ────────────────────────────────────

@sln_work_track_bp.route("/observations/<obs_id>/management-approve", methods=["POST"])
@_slnt_auth
@_slnt_prop
def obs_management_approve(obs_id):
    data = request.get_json(silent=True) or {}
    obs  = _obs_load()
    idx  = next((i for i,o in enumerate(obs) if o["id"]==obs_id), None)
    if idx is None: return jsonify({"success":False,"error":"Not found"}),404

    obs[idx]["approved_budget"] = data.get("approved_budget","")
    obs[idx]["current_stage"] = "Management Approval"
    obs[idx]["updated_at"] = datetime.now().isoformat()
    
    obs[idx]["history"].append({
        "stage": "Management Approval",
        "action": "Management Approved",
        "by": _slnt_current_user(),
        "timestamp": datetime.now().isoformat(),
        "notes": f"Approved budget: {data.get('approved_budget','')}",
    })
    
    _obs_save(obs)
    result, recipients = _obs_send_mail(obs[idx], "Management Approval")
    return jsonify({"success": True, "observation": obs[idx]})



# ── GM Approval / Cost Decision ────────────────────────────
# Called from the "Approval" tab in obs detail overlay.
# decision = "Yes" → Cost Implication → Procurement/Finance Action
# decision = "No"  → Direct Work     → Work In Progress

@sln_work_track_bp.route("/observations/<obs_id>/approve", methods=["POST"])
@_slnt_auth
@_slnt_prop
def obs_approve(obs_id):
    data = request.get_json(silent=True) or {}
    decision = data.get("decision", "Yes")   # "Yes" or "No"
    notes    = data.get("notes", "")

    obs  = _obs_load()
    idx  = next((i for i, o in enumerate(obs) if o["id"] == obs_id), None)
    if idx is None:
        return jsonify({"success": False, "error": "Observation not found"}), 404

    now = datetime.now().isoformat()

    if decision == "Yes":
        next_stage = "Procurement/Finance Action"
        obs[idx]["is_cost_implication"] = "Yes"
    else:
        next_stage = "Work In Progress"
        obs[idx]["is_cost_implication"] = "No"

    obs[idx]["current_stage"] = next_stage
    obs[idx]["gm_notes"]      = notes
    obs[idx]["updated_at"]    = now
    obs[idx]["history"].append({
        "stage":     next_stage,
        "action":    f"GM/Mgmt Approved — Cost Implication: {decision}",
        "by":        _slnt_current_user(),
        "timestamp": now,
        "notes":     notes,
    })

    try:
        _obs_save(obs)
    except Exception as e:
        return jsonify({"success": False, "error": f"Save failed: {e}"}), 500

    result, recipients = _obs_send_mail(obs[idx], next_stage)
    return jsonify({
        "success":    True,
        "next_stage": next_stage,
        "mail_sent":  result.get("success", False),
        "observation": obs[idx],
    })


# ── Procurement Completion ─────────────────────────────────

@sln_work_track_bp.route("/observations/<obs_id>/procurement-complete", methods=["POST"])
@_slnt_auth
@_slnt_prop
def obs_procurement_complete(obs_id):
    data = request.get_json(silent=True) or {}
    obs  = _obs_load()
    idx  = next((i for i,o in enumerate(obs) if o["id"]==obs_id), None)
    if idx is None: return jsonify({"success":False,"error":"Not found"}),404

    obs[idx]["vendor"] = data.get("vendor","")
    obs[idx]["final_cost"] = data.get("final_cost","")
    obs[idx]["current_stage"] = "Procurement/Finance Action"
    obs[idx]["updated_at"] = datetime.now().isoformat()
    
    obs[idx]["history"].append({
        "stage": "Procurement/Finance Action",
        "action": "Procurement Action Completed",
        "by": _slnt_current_user(),
        "timestamp": datetime.now().isoformat(),
        "notes": f"Vendor: {data.get('vendor','')}, Cost: {data.get('final_cost','')}",
    })
    
    _obs_save(obs)
    result, recipients = _obs_send_mail(obs[idx], "Procurement/Finance Action")
    return jsonify({"success": True, "observation": obs[idx]})


# ── Work Progress Update ──────────────────────────────────

@sln_work_track_bp.route("/observations/<obs_id>/work-progress", methods=["POST"])
@_slnt_auth
@_slnt_prop
def obs_work_progress(obs_id):
    data = request.get_json(silent=True) or {}
    obs  = _obs_load()
    idx  = next((i for i,o in enumerate(obs) if o["id"]==obs_id), None)
    if idx is None: return jsonify({"success":False,"error":"Not found"}),404

    obs[idx]["progress"] = data.get("progress",0)
    obs[idx]["work_status"] = data.get("work_status","")
    obs[idx]["current_stage"] = "Work In Progress"
    obs[idx]["updated_at"] = datetime.now().isoformat()
    
    obs[idx]["history"].append({
        "stage": "Work In Progress",
        "action": "Progress Update",
        "by": _slnt_current_user(),
        "timestamp": datetime.now().isoformat(),
        "notes": f"Progress: {data.get('progress',0)}%, Status: {data.get('work_status','')}",
    })
    
    _obs_save(obs)
    result, recipients = _obs_send_mail(obs[idx], "Work In Progress")
    return jsonify({"success": True, "observation": obs[idx]})


# ── Complete Observation ───────────────────────────────────

@sln_work_track_bp.route("/observations/<obs_id>/complete", methods=["POST"])
@_slnt_auth
@_slnt_prop
def obs_complete(obs_id):
    data = request.get_json(silent=True) or {}
    obs  = _obs_load()
    idx  = next((i for i,o in enumerate(obs) if o["id"]==obs_id), None)
    if idx is None: return jsonify({"success":False,"error":"Not found"}),404

    obs[idx]["completion_date"] = data.get("completion_date", datetime.now().strftime("%Y-%m-%d"))
    obs[idx]["current_stage"] = "Completed"
    obs[idx]["status"] = "Completed"
    obs[idx]["updated_at"] = datetime.now().isoformat()
    
    obs[idx]["history"].append({
        "stage": "Completed",
        "action": "Observation Closed",
        "by": _slnt_current_user(),
        "timestamp": datetime.now().isoformat(),
        "notes": data.get("completion_notes",""),
    })
    
    _obs_save(obs)
    result, recipients = _obs_send_mail(obs[idx], "Completed")
    return jsonify({"success": True, "observation": obs[idx]})


# ── Manual mail trigger ────────────────────────────────────


@sln_work_track_bp.route("/observations/<obs_id>/stage", methods=["POST"])
@_slnt_auth
@_slnt_prop
def obs_advance_stage(obs_id):
    """Advance observation to next stage and send mail. Used by advanceObsStage() JS."""
    obs = _obs_load()
    idx = next((i for i, o in enumerate(obs) if o["id"] == obs_id), None)
    if idx is None:
        return jsonify({"success": False, "error": "Observation not found"}), 404

    ob = obs[idx]
    STAGE_ORDER = [
        "Observation Raised by GM/Management",
        "PM Review & Response",
        "GM Verification",
        "Management Approval",
        "Procurement/Finance Action",
        "Work In Progress",
        "Completed",
    ]
    current = ob.get("current_stage", STAGE_ORDER[0])
    ci = STAGE_ORDER.index(current) if current in STAGE_ORDER else 0
    if ci >= len(STAGE_ORDER) - 1:
        return jsonify({"success": False, "error": "Already at final stage"}), 400

    new_stage = STAGE_ORDER[ci + 1]
    obs[idx]["current_stage"] = new_stage
    obs[idx].setdefault("history", []).append({
        "stage": new_stage,
        "timestamp": datetime.now().isoformat(),
        "notes": "Advanced via dashboard",
    })
    if new_stage == "Completed":
        obs[idx]["status"] = "Completed"
        obs[idx]["completed_at"] = datetime.now().isoformat()

    _obs_save(obs)
    result, recipients = _obs_send_mail(obs[idx], new_stage)
    return jsonify({
        "success":   True,
        "new_stage": new_stage,
        "mail_sent": result.get("success", False),
        "count":     len(recipients),
    })

@sln_work_track_bp.route("/observations/<obs_id>/trigger-mail", methods=["POST"])
@_slnt_auth
@_slnt_prop
def obs_trigger_mail(obs_id):
    data = request.get_json(silent=True) or {}
    obs  = _obs_load()
    ob   = next((o for o in obs if o["id"]==obs_id), None)
    if not ob: return jsonify({"success":False,"error":"Not found"}),404
    stage  = data.get("stage") or ob.get("current_stage", OBS_STAGES[0])
    result, recipients = _obs_send_mail(ob, stage, override_body=data.get("body"))
    if result["success"]:
        return jsonify({"success":True,"recipients":recipients,"count":len(recipients)})
    return jsonify({"success":False,"error":result.get("error","")}),500


# ── Observation Emergency Mail ─────────────────────────────

@sln_work_track_bp.route("/observations/<obs_id>/emergency-mail", methods=["POST"])
@_slnt_auth
@_slnt_prop
def obs_emergency_mail(obs_id):
    """Send emergency mail to ALL departments for an observation."""
    data = request.get_json(silent=True) or {}
    obs  = _obs_load()
    ob   = next((o for o in obs if o["id"] == obs_id), None)
    if not ob:
        return jsonify({"success": False, "error": "Observation not found"}), 404

    ctx     = _obs_ctx(ob)
    subject = data.get("subject") or f"[SLN TERMINUS][EMERGENCY][OBS] Immediate Attention: {ob.get('title','')}"
    body    = data.get("body") or (
        "EMERGENCY NOTICE\n\n"
        "Urgent attention required for the following observation at SLN TERMINUS.\n\n"
        f"Observation ID : {ctx['obs_id']}\n"
        f"Title          : {ctx['title']}\n"
        f"Location       : {ctx['location']}\n"
        f"Current Stage  : {ob.get('current_stage','')}\n"
        f"Priority       : {ctx['priority']}\n"
        f"Raised By      : {ctx.get('raised_by_name','') or ctx.get('raised_by','')}\n\n"
        "Please take immediate action.\n\nRegards,\nemerZhent Property Management Services"
    )
    recipients = _slnt_resolve_recipients(["All"])
    html       = _obs_build_html(ob, subject, body)
    result     = _slnt_send_smtp(recipients, subject, body, html)
    _slnt_log_mail(obs_id, "OBS|EMERGENCY", recipients,
                  "sent" if result["success"] else "failed",
                  result.get("error", ""))
    if result["success"]:
        return jsonify({"success": True, "recipients": recipients, "count": len(recipients)})
    return jsonify({"success": False, "error": result.get("error", "")}), 500


# ── Observation Mail Preview ──────────────────────────────

@sln_work_track_bp.route("/observations/<obs_id>/preview-mail", methods=["POST"])
@_slnt_auth
@_slnt_prop
def obs_preview_mail(obs_id):
    """Return subject + rendered body for a given stage (mail preview UI)."""
    data  = request.get_json(silent=True) or {}
    stage = data.get("stage", "")
    obs   = _obs_load()
    ob    = next((o for o in obs if o["id"] == obs_id), None)
    if not ob:
        return jsonify({"success": False, "error": "Not found"}), 404
    ctx     = _obs_ctx(ob)
    subject = OBS_SUBJECTS.get(stage, "").format(**ctx)
    body    = OBS_BODIES.get(stage, "").format(**ctx)
    depts   = OBS_STAGE_DEPTS.get(stage, ["All"])
    return jsonify({"success": True, "subject": subject, "body": body, "departments": depts})


# ── Image serving ──────────────────────────────────────────

@sln_work_track_bp.route("/obs-image/<filename>")
@_slnt_auth
@_slnt_prop
def obs_image(filename):
    from flask import send_from_directory
    return send_from_directory(str(SLN_OBS_UPLOADS_DIR), secure_filename(filename))


# ── Stats ──────────────────────────────────────────────────

@sln_work_track_bp.route("/observations/stats", methods=["GET"])
@_slnt_auth
@_slnt_prop
def obs_stats():
    obs = _obs_load()
    return jsonify({
        "success":True,"total":len(obs),
        "active":     sum(1 for o in obs if o.get("status")=="Active"),
        "completed":  sum(1 for o in obs if o.get("status")=="Completed"),
        "by_stage":   {s:sum(1 for o in obs if o.get("current_stage")==s) for s in OBS_STAGES},
        "by_priority":{p:sum(1 for o in obs if o.get("priority")==p) for p in ("High","Medium","Low")},
    })