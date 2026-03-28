"""
GM TASKS ROUTES
GM Tasks CRUD, mail config API, email helpers (build HTML, send, instant alerts),
and APScheduler jobs (daily 09:00 AM IST + overdue check every 5 min).
"""
from flask import Blueprint, request, jsonify, session
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr
import json
import smtplib
import threading

from decorators import login_required
from config import BASE_DIR, DATA_DIR, _GMAIL_LOCK, _LAST_SMTP_SEND, _MIN_SEND_GAP
import time as _time

gm_tasks_bp = Blueprint("gm_tasks", __name__)

# ── Paths ─────────────────────────────────────────────────────────────────────
GM_TASKS_FILE      = DATA_DIR / "gm_tasks.json"
GM_MAIL_CONFIG_FILE = DATA_DIR / "gm_mail_config.json"

# ── SMTP config ───────────────────────────────────────────────────────────────
GM_SMTP_SERVER  = "smtp.gmail.com"
GM_SMTP_PORT    = 587
GM_SENDER_EMAIL = "maintenance.slnterminus@gmail.com"
GM_SENDER_PASS  = "xaottgrqtqnkouqn"

GM_TASKS_TO = [
    "maintenance.slnterminus@gmail.com",
    "yasven7545@gmail.com",
    "engineering@terminus-global.com",
    "kiran@terminus-global.com",
]
GM_TASKS_CC = []

GM_MAIL_DEFAULTS = {
    "recipients":      ",".join(GM_TASKS_TO),
    "cc":              ",".join(GM_TASKS_CC),
    "time":            "09:00",
    "subject":         "Seniour Level Management — SLN Terminus",
    "inclOpen":        True,
    "inclProg":        True,
    "inclOver":        True,
    "inclDone":        False,
    "inclHighOnly":    False,
    "siteFilter":      "",
    "notifyOnAdd":     True,
    "notifyOnOverdue": True,
}


# ─────────────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _load_gm_tasks():
    if not GM_TASKS_FILE.exists():
        return []
    try:
        with open(GM_TASKS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, list) else []
    except Exception:
        return []


def _save_gm_tasks(tasks):
    GM_TASKS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(GM_TASKS_FILE, "w", encoding="utf-8") as f:
        json.dump(tasks, f, ensure_ascii=False, indent=2)


def _load_gm_mail_cfg():
    cfg = dict(GM_MAIL_DEFAULTS)
    try:
        if GM_MAIL_CONFIG_FILE.exists():
            with open(GM_MAIL_CONFIG_FILE, "r") as f:
                cfg.update(json.load(f))
    except Exception:
        pass
    return cfg


def _resolve_recipients(cfg):
    to_str  = cfg.get("recipients", "")
    cc_str  = cfg.get("cc", "")
    to_list = [e.strip() for e in to_str.split(",") if e.strip()]
    cc_list = [e.strip() for e in cc_str.split(",") if e.strip()]
    if not to_list:
        to_list = list(GM_TASKS_TO)
    return to_list, cc_list


def _filter_tasks_for_mail(tasks, cfg):
    filtered = []
    site_filter = cfg.get("siteFilter", "").strip().lower()
    for t in tasks:
        st = (t.get("status") or "").lower()
        if cfg.get("inclOpen", True)  and st == "open":       filtered.append(t)
        elif cfg.get("inclProg", True) and st == "in progress": filtered.append(t)
        elif cfg.get("inclOver", True) and st == "overdue":     filtered.append(t)
        elif cfg.get("inclDone", False) and st == "completed":  filtered.append(t)
    if cfg.get("inclHighOnly"):
        filtered = [t for t in filtered if (t.get("priority") or "").lower() == "high"]
    if site_filter:
        filtered = [t for t in filtered if site_filter in (t.get("site") or "").lower()]
    return filtered


def _build_gm_email_html(tasks, report_type="daily", trigger_info=""):
    now_str  = datetime.now().strftime("%d %b %Y, %I:%M %p IST")
    open_c   = len([t for t in tasks if (t.get("status") or "").lower() == "open"])
    prog_c   = len([t for t in tasks if (t.get("status") or "").lower() == "in progress"])
    done_c   = len([t for t in tasks if (t.get("status") or "").lower() == "completed"])
    over_c   = len([t for t in tasks if (t.get("status") or "").lower() == "overdue"])
    high_c   = len([t for t in tasks if (t.get("priority") or "").lower() == "high"])

    task_rows = ""
    for idx, t in enumerate(tasks, 1):
        st  = (t.get("status") or "Open")
        pri = (t.get("priority") or "Medium")
        task_rows += f"""<tr style="background:{'#fefce8' if st.lower()=='overdue' else '#fff'}">
          <td style="padding:8px 12px;border-bottom:1px solid #e5e7eb;color:#6b7280;font-size:12px">{idx}</td>
          <td style="padding:8px 12px;border-bottom:1px solid #e5e7eb;font-size:12px;color:#6b7280">{t.get('date','—')}</td>
          <td style="padding:8px 12px;border-bottom:1px solid #e5e7eb;font-weight:500;color:#111827">{t.get('description','—')}</td>
          <td style="padding:8px 12px;border-bottom:1px solid #e5e7eb;color:#6b7280">{t.get('site','—')}</td>
          <td style="padding:8px 12px;border-bottom:1px solid #e5e7eb;color:#6b7280">₹{t.get('estimatedCost','—')}</td>
          <td style="padding:8px 12px;border-bottom:1px solid #e5e7eb;color:#6b7280">{t.get('assignedTo','—')}</td>
          <td style="padding:8px 12px;border-bottom:1px solid #e5e7eb">
            <span style="background:{'#fee2e2' if st.lower()=='overdue' else '#dbeafe'};color:{'#dc2626' if st.lower()=='overdue' else '#1d4ed8'};padding:2px 8px;border-radius:4px;font-size:11px">{st}</span>
          </td>
          <td style="padding:8px 12px;border-bottom:1px solid #e5e7eb">
            <span style="background:{'#fee2e2' if pri.lower()=='high' else '#f3f4f6'};color:{'#dc2626' if pri.lower()=='high' else '#374151'};padding:2px 8px;border-radius:4px;font-size:11px">{pri}</span>
          </td>
          <td style="padding:8px 12px;border-bottom:1px solid #e5e7eb;color:#6b7280;font-size:12px">{t.get('remarks','—')}</td>
        </tr>"""

    return f"""<!DOCTYPE html><html><body style="font-family:sans-serif;background:#f9fafb;margin:0;padding:20px">
<div style="max-width:900px;margin:0 auto;background:#fff;border-radius:12px;border:1px solid #e5e7eb;overflow:hidden">
  <div style="background:#1e3a5f;padding:24px 32px;color:#fff">
    <h2 style="margin:0;font-size:20px">GM Tasks Report</h2>
    <p style="margin:4px 0 0;color:#93c5fd;font-size:13px">{trigger_info or now_str}</p>
  </div>
  <table style="width:100%;border-collapse:collapse">
    <tr>
      <td style="padding:18px 20px;text-align:center;border-right:1px solid #e5e7eb">
        <div style="font-size:30px;font-weight:800;color:#2563eb;line-height:1">{open_c}</div>
        <div style="font-size:10px;color:#6b7280;text-transform:uppercase;letter-spacing:.8px;margin-top:3px">Open</div>
      </td>
      <td style="padding:18px 20px;text-align:center;border-right:1px solid #e5e7eb">
        <div style="font-size:30px;font-weight:800;color:#d97706;line-height:1">{prog_c}</div>
        <div style="font-size:10px;color:#6b7280;text-transform:uppercase;letter-spacing:.8px;margin-top:3px">In Progress</div>
      </td>
      <td style="padding:18px 20px;text-align:center;border-right:1px solid #e5e7eb">
        <div style="font-size:30px;font-weight:800;color:#059669;line-height:1">{done_c}</div>
        <div style="font-size:10px;color:#6b7280;text-transform:uppercase;letter-spacing:.8px;margin-top:3px">Completed</div>
      </td>
      <td style="padding:18px 20px;text-align:center;border-right:1px solid #e5e7eb">
        <div style="font-size:30px;font-weight:800;color:{'#dc2626' if over_c else '#9ca3af'};line-height:1">{over_c}</div>
        <div style="font-size:10px;color:#6b7280;text-transform:uppercase;letter-spacing:.8px;margin-top:3px">Overdue</div>
      </td>
      <td style="padding:18px 20px;text-align:center">
        <div style="font-size:30px;font-weight:800;color:{'#dc2626' if high_c else '#9ca3af'};line-height:1">{high_c}</div>
        <div style="font-size:10px;color:#6b7280;text-transform:uppercase;letter-spacing:.8px;margin-top:3px">High Prio</div>
      </td>
    </tr>
  </table>
  <div style="padding:20px 32px">
    <div style="overflow-x:auto">
      <table style="width:100%;border-collapse:collapse;font-size:13px;min-width:700px">
        <thead><tr style="background:#f8fafc">
          <th style="padding:9px 12px;text-align:left;font-size:10px;text-transform:uppercase;color:#6b7280;border-bottom:2px solid #e5e7eb">#</th>
          <th style="padding:9px 12px;text-align:left;font-size:10px;text-transform:uppercase;color:#6b7280;border-bottom:2px solid #e5e7eb">Date</th>
          <th style="padding:9px 12px;text-align:left;font-size:10px;text-transform:uppercase;color:#6b7280;border-bottom:2px solid #e5e7eb">Description</th>
          <th style="padding:9px 12px;text-align:left;font-size:10px;text-transform:uppercase;color:#6b7280;border-bottom:2px solid #e5e7eb">Site</th>
          <th style="padding:9px 12px;text-align:left;font-size:10px;text-transform:uppercase;color:#6b7280;border-bottom:2px solid #e5e7eb">Cost</th>
          <th style="padding:9px 12px;text-align:left;font-size:10px;text-transform:uppercase;color:#6b7280;border-bottom:2px solid #e5e7eb">Assigned To</th>
          <th style="padding:9px 12px;text-align:left;font-size:10px;text-transform:uppercase;color:#6b7280;border-bottom:2px solid #e5e7eb">Status</th>
          <th style="padding:9px 12px;text-align:left;font-size:10px;text-transform:uppercase;color:#6b7280;border-bottom:2px solid #e5e7eb">Priority</th>
          <th style="padding:9px 12px;text-align:left;font-size:10px;text-transform:uppercase;color:#6b7280;border-bottom:2px solid #e5e7eb">Remarks</th>
        </tr></thead>
        <tbody>{task_rows}</tbody>
      </table>
    </div>
  </div>
  <div style="padding:16px 32px;background:#f9fafb;border-top:1px solid #e5e7eb">
    <p style="color:#9ca3af;font-size:11px;margin:0">
      Auto-generated · {now_str} · Do not reply.
    </p>
  </div>
</div></body></html>"""


def _gm_smtp_send(msg_obj, recipients, caller="GM", retries=3, base_delay=5):
    last_err = None
    for attempt in range(1, retries + 1):
        with _GMAIL_LOCK:
            gap = _time.time() - _LAST_SMTP_SEND["ts"]
            if gap < _MIN_SEND_GAP:
                _time.sleep(_MIN_SEND_GAP - gap)
            try:
                with smtplib.SMTP(GM_SMTP_SERVER, GM_SMTP_PORT, timeout=25) as srv:
                    srv.ehlo(); srv.starttls(); srv.ehlo()
                    srv.login(GM_SENDER_EMAIL, GM_SENDER_PASS)
                    srv.sendmail(GM_SENDER_EMAIL, recipients, msg_obj.as_string())
                _LAST_SMTP_SEND["ts"] = _time.time()
                print(f"✅ [GM-{caller}] Email sent → {recipients} (attempt {attempt})")
                return True
            except smtplib.SMTPAuthenticationError as e:
                print(f"⚠️  [GM-{caller}] Auth error (attempt {attempt}): {e}")
                last_err = e
                _time.sleep(base_delay * attempt * 2)
            except (smtplib.SMTPException, OSError) as e:
                print(f"⚠️  [GM-{caller}] SMTP error (attempt {attempt}): {e}")
                last_err = e
                _time.sleep(base_delay * attempt)
    print(f"❌ [GM-{caller}] All {retries} attempts failed: {last_err}")
    raise last_err


def _send_gm_email(subject_override=None, tasks_override=None,
                   report_type="daily", trigger_info="", cfg=None):
    if cfg is None:
        cfg = _load_gm_mail_cfg()
    to_list, cc_list = _resolve_recipients(cfg)
    subject  = subject_override or cfg.get("subject", GM_MAIL_DEFAULTS["subject"])
    date_str = datetime.now().strftime("%d %b %Y")

    filtered = tasks_override if tasks_override is not None else _filter_tasks_for_mail(_load_gm_tasks(), cfg)
    html_body = _build_gm_email_html(filtered, report_type=report_type, trigger_info=trigger_info)

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"{subject} · {date_str}"
    msg["From"]    = formataddr(("Sr. Level Mgmt Portal", GM_SENDER_EMAIL))
    msg["To"]      = ", ".join(to_list)
    if cc_list:
        msg["Cc"]  = ", ".join(cc_list)
    msg.attach(MIMEText(html_body, "html"))
    _gm_smtp_send(msg, to_list + cc_list, caller=report_type)
    print(f"✅ GM Tasks [{report_type}] → {to_list} at {datetime.now().strftime('%H:%M:%S')}")
    return True, f"Report sent to {len(to_list)} recipient(s).", to_list


# ─────────────────────────────────────────────────────────────────────────────
# GM TASKS CRUD API
# ─────────────────────────────────────────────────────────────────────────────

@gm_tasks_bp.route("/gm_tasks")
@login_required
def gm_tasks_page():
    from flask import render_template
    return render_template("gm_tasks.html")


@gm_tasks_bp.route("/api/gm_tasks", methods=["GET"])
@login_required
def api_gm_tasks_get():
    tasks = _load_gm_tasks()
    return jsonify({"tasks": tasks, "count": len(tasks)})


@gm_tasks_bp.route("/api/gm_tasks", methods=["POST"])
@login_required
def api_gm_tasks_post():
    try:
        body  = request.get_json(force=True) or {}
        tasks = body.get("tasks", [])
        if not isinstance(tasks, list):
            return jsonify({"success": False, "error": "tasks must be a list"}), 400
        _save_gm_tasks(tasks)
        return jsonify({"success": True, "count": len(tasks)})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@gm_tasks_bp.route("/api/gm_tasks/add", methods=["POST"])
@login_required
def api_gm_tasks_add():
    try:
        task = request.get_json(force=True) or {}
        if not task.get("description"):
            return jsonify({"success": False, "error": "description required"}), 400
        if not task.get("id"):
            task["id"] = f"task_{int(datetime.now().timestamp()*1000)}"
        task.setdefault("status",   "Open")
        task.setdefault("priority", "Medium")
        task.setdefault("date",     datetime.now().strftime("%Y-%m-%d"))
        task["updatedAt"] = datetime.now().isoformat()
        tasks = _load_gm_tasks()
        tasks.insert(0, task)
        _save_gm_tasks(tasks)
        return jsonify({"success": True, "task": task, "total": len(tasks)})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@gm_tasks_bp.route("/api/gm_tasks/<task_id>", methods=["PUT"])
@login_required
def api_gm_tasks_update(task_id):
    try:
        updates = request.get_json(force=True) or {}
        tasks   = _load_gm_tasks()
        for i, t in enumerate(tasks):
            if t.get("id") == task_id:
                tasks[i].update(updates)
                tasks[i]["updatedAt"] = datetime.now().isoformat()
                _save_gm_tasks(tasks)
                return jsonify({"success": True, "task": tasks[i]})
        return jsonify({"success": False, "error": "Task not found"}), 404
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@gm_tasks_bp.route("/api/gm_tasks/<task_id>", methods=["DELETE"])
@login_required
def api_gm_tasks_delete(task_id):
    try:
        tasks  = _load_gm_tasks()
        before = len(tasks)
        tasks  = [t for t in tasks if t.get("id") != task_id]
        _save_gm_tasks(tasks)
        return jsonify({"success": True, "deleted": before - len(tasks)})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# ─────────────────────────────────────────────────────────────────────────────
# MAIL CONFIG API
# ─────────────────────────────────────────────────────────────────────────────

@gm_tasks_bp.route("/api/gm_mail_config", methods=["GET"])
@login_required
def api_gm_mail_config_get():
    return jsonify(_load_gm_mail_cfg())


@gm_tasks_bp.route("/api/gm_mail_config", methods=["POST"])
@login_required
def api_gm_mail_config_post():
    try:
        new_cfg = request.get_json(force=True) or {}
        GM_MAIL_CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(GM_MAIL_CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(new_cfg, f, indent=2)
        return jsonify({"success": True, "message": "Mail config saved"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# ─────────────────────────────────────────────────────────────────────────────
# SEND REPORT API
# ─────────────────────────────────────────────────────────────────────────────

@gm_tasks_bp.route("/api/gm_tasks/send_report", methods=["POST"])
@login_required
def api_gm_tasks_send_report():
    try:
        body             = request.get_json(force=True) or {}
        tasks_from_client = body.get("tasks")
        cfg              = _load_gm_mail_cfg()
        if tasks_from_client is not None:
            _save_gm_tasks(tasks_from_client)
            filtered = _filter_tasks_for_mail(tasks_from_client, cfg)
        else:
            filtered = None
        ok, msg, recipients = _send_gm_email(
            tasks_override=filtered, report_type="manual",
            trigger_info=f"Sent manually by {session.get('user','GM')} at {datetime.now().strftime('%H:%M IST')}",
            cfg=cfg,
        )
        return jsonify({"success": ok, "message": msg, "recipients": recipients})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@gm_tasks_bp.route("/api/gm_tasks/add_notify", methods=["POST"])
@login_required
def api_gm_tasks_add_notify():
    """Add a task AND send instant notification email."""
    try:
        task = request.get_json(force=True) or {}
        if not task.get("description"):
            return jsonify({"success": False, "error": "description required"}), 400
        if not task.get("id"):
            task["id"] = f"task_{int(datetime.now().timestamp()*1000)}"
        task.setdefault("status",   "Open")
        task.setdefault("priority", "Medium")
        task.setdefault("date",     datetime.now().strftime("%Y-%m-%d"))
        task["updatedAt"] = datetime.now().isoformat()
        tasks = _load_gm_tasks()
        tasks.insert(0, task)
        _save_gm_tasks(tasks)
        threading.Thread(target=_maybe_notify_new_task, args=(task,), daemon=True).start()
        return jsonify({"success": True, "task": task, "total": len(tasks)})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# ─────────────────────────────────────────────────────────────────────────────
# INSTANT ALERTS
# ─────────────────────────────────────────────────────────────────────────────

def _maybe_notify_new_task(task):
    try:
        cfg = _load_gm_mail_cfg()
        if not cfg.get("notifyOnAdd", True):
            return
        subject = f"🆕 New GM Task Added — {task.get('site','—')} | {task.get('priority','Medium')} Priority"
        _send_gm_email(subject_override=subject, tasks_override=[task],
                       report_type="new_task",
                       trigger_info=f"Task added · Site: {task.get('site','—')} · Assigned: {task.get('assignedTo','—')}",
                       cfg=cfg)
    except Exception as e:
        print(f"⚠️  GM new-task notify error: {e}")


def _maybe_notify_overdue(task):
    try:
        cfg = _load_gm_mail_cfg()
        if not cfg.get("notifyOnOverdue", True):
            return
        subject = f"⚠️ GM Task Overdue — {task.get('site','—')} · {task.get('description','')[:60]}"
        _send_gm_email(subject_override=subject, tasks_override=[task],
                       report_type="overdue",
                       trigger_info=f"Task marked Overdue · Site: {task.get('site','—')}",
                       cfg=cfg)
    except Exception as e:
        print(f"⚠️  GM overdue notify error: {e}")


# ─────────────────────────────────────────────────────────────────────────────
# SCHEDULER
# ─────────────────────────────────────────────────────────────────────────────

def _gm_tasks_daily_job():
    from flask import current_app
    with current_app.app_context():
        try:
            cfg = _load_gm_mail_cfg()
            _send_gm_email(report_type="daily", cfg=cfg)
        except Exception as _e:
            print(f"⚠️  [GM Tasks daily job] {_e}")


def _gm_tasks_overdue_check():
    from flask import current_app
    with current_app.app_context():
        try:
            tasks = _load_gm_tasks()
            cfg   = _load_gm_mail_cfg()
            if not cfg.get("notifyOnOverdue", True):
                return
            _state_file = DATA_DIR / "gm_tasks_overdue_state.json"
            prev = {}
            try:
                if _state_file.exists():
                    with open(_state_file) as f:
                        prev = json.load(f)
            except Exception:
                pass
            curr = {t["id"]: t.get("status","") for t in tasks if t.get("id")}
            newly_overdue = [t for t in tasks
                             if t.get("id") and curr.get(t["id"]) == "Overdue"
                             and prev.get(t["id"]) not in (None, "Overdue")]
            try:
                with open(_state_file, "w") as f:
                    json.dump(curr, f)
            except Exception:
                pass
            for t in newly_overdue:
                try:
                    _maybe_notify_overdue(t)
                except Exception as _ne:
                    print(f"⚠️  [GM Overdue alert] {_ne}")
        except Exception as _e:
            print(f"⚠️  [GM Tasks overdue check] {_e}")


def _setup_gm_tasks_scheduler():
    try:
        from apscheduler.schedulers.background import BackgroundScheduler
        _gm_sched = BackgroundScheduler(timezone="Asia/Kolkata")
        _gm_sched.add_job(func=_gm_tasks_daily_job, trigger="cron",
                          hour=9, minute=0, timezone="Asia/Kolkata",
                          id="gm_tasks_daily", replace_existing=True, misfire_grace_time=120)
        _gm_sched.add_job(func=_gm_tasks_overdue_check, trigger="interval",
                          minutes=5, id="gm_tasks_overdue_check", replace_existing=True)
        _gm_sched.start()
        print("✅ GM Tasks scheduler started — daily 09:00 AM IST + overdue check every 5 min")
    except Exception as _e:
        print(f"⚠️  GM Tasks scheduler failed to start: {_e}")
