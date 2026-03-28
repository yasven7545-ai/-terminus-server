# cam_charges_routes.py
# Auto-reminder schedule:
#   Day +1  after due → 1st reminder
#   Day +3             → 2nd reminder
#   Day +7  (1 week)   → 3rd reminder
#   Day +10            → 4th reminder
#   Day +15            → 5th reminder
#   Day +16+ (daily)   → every day until outstanding = 0

import os
import json
import smtplib
import pandas as pd
from pathlib import Path
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from flask import Blueprint, request, jsonify, send_file, session
from werkzeug.utils import secure_filename
from functools import wraps

cam_charges_bp = Blueprint('cam_charges', __name__)

# ── Paths ──────────────────────────────────────────────────────────────────
BASE_DIR  = Path(__file__).parent.resolve()
DATA_DIR  = BASE_DIR / "static" / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
DATA_FILE = DATA_DIR / "cam_charges.xlsx"
LOG_FILE  = DATA_DIR / "cam_mail_log.json"

# ── SMTP ───────────────────────────────────────────────────────────────────
SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 587
SMTP_USER = os.environ.get("CAM_SMTP_USER", "maintenance.slnterminus@gmail.com")
SMTP_PASS = os.environ.get("CAM_SMTP_PASS", "xaottgrqtqnkouqn")
RECEIVER_EMAILS = [
    "maintenance.slnterminus@gmail.com",
    "yasven7545@gmail.com",
    "engineering@terminus-global.com",
]

# ── Reminder schedule (days past due) ─────────────────────────────────────
REMINDER_SCHEDULE = [1, 3, 7]  # specific trigger days
# After day 7 → trigger every day (was day 15)

# ── Column aliases ─────────────────────────────────────────────────────────
COL_MAP = {
    "client name": "clientName", "client": "clientName", "name": "clientName",
    "a/c head": "accountHead", "account head": "accountHead", "ac head": "accountHead", "head": "accountHead",
    "period": "period",
    "invoice no": "invoiceNo", "invoice no.": "invoiceNo", "invoice": "invoiceNo", "invoice number": "invoiceNo",
    "amount": "invoiceDate", "invoice date": "invoiceDate",
    "amount (rs)": "amountNumeric", "amount(rs)": "amountNumeric", "amt": "amountNumeric",
    "cam amount": "amountNumeric", "total amount": "amountNumeric",
    "mode of payment": "modeOfPayment", "mode": "modeOfPayment", "payment mode": "modeOfPayment",
    "due date": "dueDate", "due": "dueDate",
    "amt received": "amtReceived", "amount received": "amtReceived", "received": "amtReceived",
    "tds": "tds", "tds deducted": "tds",
    "outstanding": "outstanding", "balance": "outstanding", "pending": "outstanding",
    "mail_id": "mailId", "mail id": "mailId", "email": "mailId", "e-mail": "mailId",
}


def _normalize_row(row: dict) -> dict:
    out = {}
    for raw_key, val in row.items():
        key = str(raw_key).strip().lower()
        internal = COL_MAP.get(key, raw_key)
        if not isinstance(val, str) and pd.isna(val):
            val = ""
        out[internal] = val

    def _num(k):
        try:
            v = out.get(k, 0)
            return float(str(v).replace(",", "").replace("₹", "").strip() or 0)
        except (ValueError, TypeError):
            return 0.0

    def _str(k):
        v = out.get(k, "")
        return str(v).strip() if v else ""

    def _date(k):
        v = out.get(k, "")
        if not v:
            return ""
        try:
            if isinstance(v, (datetime, pd.Timestamp)):
                return v.strftime("%d-%b-%y")
            s = str(v).strip()
            for fmt in ("%d-%b-%y", "%d-%b-%Y", "%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
                try:
                    return datetime.strptime(s, fmt).strftime("%d-%b-%y")
                except ValueError:
                    pass
            return s
        except Exception:
            return str(v)

    return {
        "clientName":    _str("clientName"),
        "accountHead":   _str("accountHead"),
        "period":        _str("period"),
        "invoiceNo":     _str("invoiceNo"),
        "invoiceDate":   _date("invoiceDate"),
        "amountNumeric": _num("amountNumeric"),
        "modeOfPayment": _str("modeOfPayment"),
        "dueDate":       _date("dueDate"),
        "amtReceived":   _num("amtReceived"),
        "tds":           _num("tds"),
        "outstanding":   _num("outstanding"),
        "mailId":        _str("mailId"),
    }


# ── Login guard ────────────────────────────────────────────────────────────
def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("user"):
            return jsonify({"error": "Unauthorized"}), 401
        return f(*args, **kwargs)
    return decorated


# ══════════════════════════════════════════════════════════════════
#  ROUTES
# ══════════════════════════════════════════════════════════════════

@cam_charges_bp.route('/cam_charges_upload', methods=['POST'])
@login_required
def cam_charges_upload():
    if 'file' not in request.files:
        return jsonify(success=False, error="No file provided"), 400
    f = request.files['file']
    if not f.filename:
        return jsonify(success=False, error="Empty filename"), 400

    tmp_path = DATA_DIR / secure_filename(f.filename)
    try:
        f.save(str(tmp_path))
        df = pd.read_excel(tmp_path).fillna("")
        df.columns = [str(c).strip() for c in df.columns]
        df.to_excel(str(DATA_FILE), index=False)
        records = [_normalize_row(r) for r in df.to_dict("records")]
        return jsonify(success=True, count=len(records), data=records)
    except Exception as e:
        return jsonify(success=False, error=str(e)), 500
    finally:
        if tmp_path.exists() and tmp_path != DATA_FILE:
            try:
                tmp_path.unlink()
            except Exception:
                pass


@cam_charges_bp.route('/get_cam_charges')
@login_required
def get_cam_charges():
    if not DATA_FILE.exists():
        return jsonify(success=True, data=[], count=0)
    try:
        df = pd.read_excel(str(DATA_FILE)).fillna("")
        records = [_normalize_row(r) for r in df.to_dict("records")]
        total_outstanding = sum(abs(r["outstanding"]) for r in records)
        today = datetime.today()
        overdue = sum(
            1 for r in records
            if r["dueDate"] and _parse_date(r["dueDate"]) and _parse_date(r["dueDate"]) < today
        )
        return jsonify(
            success=True, data=records, count=len(records),
            summary={
                "total_records":     len(records),
                "total_outstanding": total_outstanding,
                "overdue_count":     overdue,
            }
        )
    except Exception as e:
        return jsonify(success=False, error=str(e)), 500


@cam_charges_bp.route('/send_reminder', methods=['POST'])
@login_required
def send_reminder():
    """Manual trigger — send a one-off reminder for a specific invoice."""
    data    = request.get_json(force=True) or {}
    to      = data.get("mailId", "").strip()
    subject = data.get("subject", "CAM Invoice Reminder — SLN Terminus").strip()
    body    = data.get("message", "").strip()

    if not to:
        return jsonify(success=False, error="No recipient email"), 400
    if not body:
        return jsonify(success=False, error="No message body"), 400

    if not SMTP_PASS:
        _log_reminder(data.get("invoiceNo", ""), to, trigger_type="manual")
        return jsonify(success=True, note="SMTP not configured — logged only")

    try:
        _send_email(to, subject, body)
        _log_reminder(data.get("invoiceNo", ""), to, trigger_type="manual")
        return jsonify(success=True)
    except Exception as e:
        return jsonify(success=False, error=str(e)), 500


@cam_charges_bp.route('/run_auto_reminders', methods=['POST'])
@login_required
def run_auto_reminders():
    """
    Trigger auto-reminder batch.
    Called by the APScheduler (or manually via admin).
    Checks every overdue invoice against the schedule and sends if due.
    """
    if not DATA_FILE.exists():
        return jsonify(success=True, sent=0, skipped=0, note="No data file")

    try:
        df = pd.read_excel(str(DATA_FILE)).fillna("")
        records = [_normalize_row(r) for r in df.to_dict("records")]
        log     = _load_log()
        today   = datetime.today()
        today.replace(hour=0, minute=0, second=0, microsecond=0)

        sent    = 0
        skipped = 0

        for r in records:
            # Skip settled or no email
            if r["outstanding"] <= 0 or not r["mailId"] or not r["dueDate"]:
                skipped += 1
                continue

            due_date = _parse_date(r["dueDate"])
            if not due_date or due_date >= today:
                skipped += 1
                continue

            days_overdue = (today - due_date).days

            # Check if today is a scheduled reminder day
            if not _should_send_today(days_overdue):
                skipped += 1
                continue

            invoice_key = r["invoiceNo"] or r["clientName"]

            # Check if already sent today for this invoice
            if _already_sent_today(log, invoice_key, today):
                skipped += 1
                continue

            subject = _build_subject(r, days_overdue)
            body    = _build_body(r, days_overdue)

            try:
                if SMTP_PASS:
                    _send_email(r["mailId"], subject, body)
                _log_reminder(invoice_key, r["mailId"], trigger_type="auto",
                              days_overdue=days_overdue, log=log)
                sent += 1
            except Exception as mail_err:
                # Log failure but keep going
                _log_reminder(invoice_key, r["mailId"], trigger_type="auto_failed",
                              days_overdue=days_overdue, error=str(mail_err), log=log)

        _save_log(log)
        return jsonify(success=True, sent=sent, skipped=skipped,
                       date=today.strftime("%Y-%m-%d"))
    except Exception as e:
        return jsonify(success=False, error=str(e)), 500


@cam_charges_bp.route('/cam_charges_export')
@login_required
def cam_charges_export():
    if not DATA_FILE.exists():
        return jsonify(error="No data file"), 404
    return send_file(
        str(DATA_FILE),
        as_attachment=True,
        download_name=f"CAM_Charges_{datetime.now().strftime('%Y-%m-%d')}.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )


@cam_charges_bp.route('/cam_reminder_log')
@login_required
def cam_reminder_log():
    """Return the last 100 reminder log entries."""
    log = _load_log()
    return jsonify(success=True, log=log[-100:], total=len(log))


# ══════════════════════════════════════════════════════════════════
#  AUTO-REMINDER HELPERS
# ══════════════════════════════════════════════════════════════════

def _should_send_today(days_overdue: int) -> bool:
    """Return True if today is a scheduled reminder day."""
    if days_overdue <= 0:
        return False
    if days_overdue > 7:
        return True   # daily after 7 days (1 week)
    return days_overdue in REMINDER_SCHEDULE


def _already_sent_today(log: list, invoice_key: str, today: datetime) -> bool:
    """Check if we already sent a reminder for this invoice today."""
    today_str = today.strftime("%Y-%m-%d")
    for entry in reversed(log):
        if entry.get("invoice") == invoice_key:
            sent_date = entry.get("sentAt", "")[:10]
            if sent_date == today_str:
                return True
            break
    return False


def _build_subject(r: dict, days: int) -> str:
    urgency = "URGENT: " if days > 7 else ""
    return f"{urgency}CAM Invoice Reminder — {r['invoiceNo']} | {days} Days Overdue | SLN Terminus"


def _build_body(r: dict, days: int) -> str:
    owed = abs(r["outstanding"])
    urgency_line = ""
    if days > 7:
        urgency_line = f"\n⚠️  IMPORTANT: This invoice is {days} days overdue. Immediate payment is required to avoid service interruption.\n"
    elif days >= 3:
        urgency_line = f"\nThis invoice is {days} days past due. Please prioritize payment.\n"

    return f"""Dear {r['clientName'] or 'Client'},

Greetings from SLN Terminus Accounts Department.
{urgency_line}
This is an automated reminder that your CAM invoice remains unpaid:

  Invoice No   : {r['invoiceNo'] or '—'}
  Period       : {r['period'] or '—'}
  Invoice Date : {r['invoiceDate'] or '—'}
  Due Date     : {r['dueDate'] or '—'}
  Days Overdue : {days} day{'s' if days != 1 else ''}
  Total Amount : ₹{r['amountNumeric']:,.0f}
  Amt Received : ₹{r['amtReceived']:,.0f}
  Outstanding  : ₹{owed:,.0f}

Please arrange payment immediately to avoid further escalation.

For queries or payment confirmation, contact our accounts team.

Regards,
Accounts Department
SLN Terminus, Hyderabad"""


# ══════════════════════════════════════════════════════════════════
#  SMTP
# ══════════════════════════════════════════════════════════════════

def _send_email(to: str, subject: str, body: str):
    msg = MIMEMultipart("alternative")
    msg["From"]    = SMTP_USER
    msg["To"]      = to
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))
    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as s:
        s.starttls()
        s.login(SMTP_USER, SMTP_PASS)
        s.send_message(msg)


# ══════════════════════════════════════════════════════════════════
#  LOG
# ══════════════════════════════════════════════════════════════════

def _load_log() -> list:
    try:
        if LOG_FILE.exists():
            return json.loads(LOG_FILE.read_text(encoding="utf-8"))
    except Exception:
        pass
    return []


def _save_log(log: list):
    try:
        LOG_FILE.write_text(json.dumps(log, indent=2), encoding="utf-8")
    except Exception:
        pass


def _log_reminder(invoice_no: str, email: str, trigger_type: str = "manual",
                  days_overdue: int = 0, error: str = "", log: list = None):
    entry = {
        "invoice":      invoice_no,
        "email":        email,
        "sentAt":       datetime.now().isoformat(),
        "triggerType":  trigger_type,
        "daysOverdue":  days_overdue,
    }
    if error:
        entry["error"] = error

    if log is not None:
        log.append(entry)
    else:
        # Stand-alone call — load, append, save
        existing = _load_log()
        existing.append(entry)
        _save_log(existing)


# ══════════════════════════════════════════════════════════════════
#  DATE PARSE
# ══════════════════════════════════════════════════════════════════

def _parse_date(s) -> datetime | None:
    if not s:
        return None
    for fmt in ("%d-%b-%y", "%d-%b-%Y", "%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(str(s).strip(), fmt)
        except ValueError:
            pass
    return None

# ══════════════════════════════════════════════════════════════════
#  EMAIL MANAGEMENT ROUTES
# ══════════════════════════════════════════════════════════════════

EMAIL_OVERRIDE_FILE = DATA_DIR / "cam_email_overrides.json"


def _load_email_overrides() -> list:
    """Load extra/override email list (added via UI). Falls back to RECEIVER_EMAILS."""
    try:
        if EMAIL_OVERRIDE_FILE.exists():
            data = json.loads(EMAIL_OVERRIDE_FILE.read_text(encoding="utf-8"))
            if isinstance(data, list) and data:
                return data
    except Exception:
        pass
    return list(RECEIVER_EMAILS)


def _save_email_overrides(emails: list):
    try:
        EMAIL_OVERRIDE_FILE.write_text(
            json.dumps(emails, indent=2), encoding="utf-8"
        )
    except Exception:
        pass


def _all_recipients() -> list:
    """
    Merge: overrides list  +  Mail_ID column from Excel.
    Returns deduplicated sorted list.
    """
    overrides = set(e.lower().strip() for e in _load_email_overrides())
    if DATA_FILE.exists():
        try:
            df = pd.read_excel(str(DATA_FILE)).fillna("")
            df.columns = [str(c).strip() for c in df.columns]
            for col in df.columns:
                if col.strip().lower() in ("mail_id", "mail id", "email", "e-mail"):
                    for v in df[col]:
                        v = str(v).strip()
                        if v and "@" in v:
                            overrides.add(v.lower())
        except Exception:
            pass
    return sorted(overrides)


@cam_charges_bp.route('/cam_email_list')
@login_required
def cam_email_list():
    """GET — all registered recipient emails."""
    return jsonify(success=True, emails=_all_recipients(),
                   overrides=_load_email_overrides())


@cam_charges_bp.route('/cam_email_add', methods=['POST'])
@login_required
def cam_email_add():
    """POST {email} — add an email to the override list."""
    data  = request.get_json(force=True) or {}
    email = str(data.get("email", "")).strip().lower()
    if not email or "@" not in email:
        return jsonify(success=False, error="Invalid email address"), 400
    overrides = _load_email_overrides()
    if email not in [e.lower() for e in overrides]:
        overrides.append(email)
        _save_email_overrides(overrides)
    return jsonify(success=True, emails=overrides)


@cam_charges_bp.route('/cam_email_delete', methods=['POST'])
@login_required
def cam_email_delete():
    """POST {email} — remove an email from the override list."""
    data  = request.get_json(force=True) or {}
    email = str(data.get("email", "")).strip().lower()
    overrides = _load_email_overrides()
    overrides = [e for e in overrides if e.lower() != email]
    _save_email_overrides(overrides)
    return jsonify(success=True, emails=overrides)


@cam_charges_bp.route('/cam_email_update', methods=['POST'])
@login_required
def cam_email_update():
    """POST {old_email, new_email} — rename an email in the override list."""
    data  = request.get_json(force=True) or {}
    old   = str(data.get("old_email", "")).strip().lower()
    new   = str(data.get("new_email", "")).strip().lower()
    if not new or "@" not in new:
        return jsonify(success=False, error="Invalid new email"), 400
    overrides = _load_email_overrides()
    overrides = [new if e.lower() == old else e for e in overrides]
    _save_email_overrides(overrides)
    return jsonify(success=True, emails=overrides)


@cam_charges_bp.route('/cam_scheduler_status')
@login_required
def cam_scheduler_status():
    """GET — last run stats + next scheduled time."""
    STATUS_FILE = DATA_DIR / "cam_scheduler_status.json"
    last = {}
    if STATUS_FILE.exists():
        try:
            last = json.loads(STATUS_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    from datetime import date, timedelta
    now = datetime.now()
    if now.hour >= 9:
        next_day = date.today() + timedelta(days=1)
    else:
        next_day = date.today()
    next_run = next_day.strftime("%d %b %Y") + " at 09:00 AM IST"
    return jsonify(
        success=True,
        last_run=last,
        next_run=next_run,
        smtp_configured=bool(SMTP_PASS),
        schedule="D+1, D+3, D+7, then daily until cleared",
    )


@cam_charges_bp.route('/cam_run_now', methods=['POST'])
@login_required
def cam_run_now():
    """POST — manually fire the scheduler immediately."""
    try:
        from cam_charges_scheduler import run_once
        result = run_once()
        return jsonify(success=True, result=result)
    except ImportError:
        return jsonify(success=False,
                       error="cam_charges_scheduler.py missing from project root"), 500
    except Exception as e:
        return jsonify(success=False, error=str(e)), 500