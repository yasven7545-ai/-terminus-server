"""
cam_charges_scheduler.py  —  SLN Terminus
Called by APScheduler every day at 09:00 AM IST.

Schedule (days past due date):
  Day +1  → 1st reminder
  Day +3  → 2nd reminder
  Day +7  → 3rd reminder  ← then DAILY every day after this until cleared
"""
from __future__ import annotations
import json, os, smtplib
from datetime import datetime, date, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
import pandas as pd

BASE_DIR    = Path(__file__).parent.resolve()
DATA_DIR    = BASE_DIR / "static" / "data"
DATA_FILE   = DATA_DIR / "cam_charges.xlsx"
LOG_FILE    = DATA_DIR / "cam_mail_log.json"
STATUS_FILE = DATA_DIR / "cam_scheduler_status.json"
EMAIL_OVERRIDES = DATA_DIR / "cam_email_overrides.json"

# ── SMTP ──────────────────────────────────────────────────────────────────
SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 587
SMTP_USER = os.environ.get("CAM_SMTP_USER", "maintenance.slnterminus@gmail.com")
SMTP_PASS = os.environ.get("CAM_SMTP_PASS", "xaottgrqtqnkouqn")
RECEIVER_EMAILS = [
    "maintenance.slnterminus@gmail.com",
    "yasven7545@gmail.com",
    "engineering@terminus-global.com",
]

# ── Schedule ─────────────────────────────────────────────────────────────
REMINDER_DAYS = {1, 3, 7}   # specific trigger days
DAILY_AFTER   = 7            # trigger EVERY DAY after this many days overdue


# ═════════════════════════════════════════════════════════════════════════
#  PUBLIC ENTRY POINT
# ═════════════════════════════════════════════════════════════════════════

def run_once() -> dict:
    ran_at = datetime.now()
    result = {
        "ok": False, "ran_at": ran_at.isoformat(),
        "recipients": 0, "emails_sent": 0,
        "reminders_included": 0, "errors": [],
    }

    if not DATA_FILE.exists():
        result["errors"].append("cam_charges.xlsx not found — upload it first")
        _write_status(result); return result

    try:
        df = pd.read_excel(str(DATA_FILE)).fillna("")
        df.columns = [str(c).strip() for c in df.columns]
        records   = [_norm(r) for r in df.to_dict("records")]
        today     = datetime.combine(date.today(), datetime.min.time())
        today_str = today.strftime("%Y-%m-%d")

        # overdue invoices with a reminder due today
        due_today: list[dict] = []
        for r in records:
            if r["outstanding"] <= 0 or not r["dueDate"]: continue
            dt = _parse_date(r["dueDate"])
            if not dt or dt >= today: continue
            days_over = (today - dt).days
            if _should_remind(days_over):
                r["_days"] = days_over
                due_today.append(r)

        result["reminders_included"] = len(due_today)

        # all recipients = override list + Mail_ID column
        recipients = _all_recipients(records)
        result["recipients"] = len(recipients)

        if not recipients:
            result["errors"].append("No recipient emails found")
            _write_status(result); return result

        log = _load_log()
        for email in recipients:
            if _sent_today(log, email, today_str): continue
            subj, html, plain = _build_email(email, records, due_today, today)
            try:
                if SMTP_PASS:
                    _smtp_send(email, subj, html, plain)
                    result["emails_sent"] += 1
                else:
                    result["errors"].append(f"SMTP not configured; would send to {email}")
                _append_log(log, {"type":"daily","email":email,
                                  "sentAt":ran_at.isoformat(),
                                  "reminders":len(due_today)})
            except Exception as exc:
                result["errors"].append(f"{email}: {exc}")
                _append_log(log, {"type":"failed","email":email,
                                  "sentAt":ran_at.isoformat(),"error":str(exc)})

        _save_log(log)
        result["ok"] = True

    except Exception as exc:
        result["errors"].append(str(exc))

    _write_status(result)
    print(f"[CAM] {ran_at:%Y-%m-%d %H:%M} | sent={result['emails_sent']} "
          f"reminders={result['reminders_included']} errors={len(result['errors'])}")
    return result


# ═════════════════════════════════════════════════════════════════════════
#  RECIPIENT RESOLUTION
# ═════════════════════════════════════════════════════════════════════════

def _all_recipients(records: list[dict]) -> list[str]:
    pool: set[str] = set()
    # 1. hardcoded defaults
    for e in RECEIVER_EMAILS: pool.add(e.lower().strip())
    # 2. override file (added via UI)
    try:
        if EMAIL_OVERRIDES.exists():
            data = json.loads(EMAIL_OVERRIDES.read_text("utf-8"))
            if isinstance(data, list):
                for e in data:
                    if e and "@" in str(e): pool.add(str(e).lower().strip())
    except Exception: pass
    # 3. Mail_ID column from Excel
    for r in records:
        m = str(r.get("mailId","")).strip()
        if m and "@" in m: pool.add(m.lower())
    return sorted(pool)


# ═════════════════════════════════════════════════════════════════════════
#  EMAIL BUILDER
# ═════════════════════════════════════════════════════════════════════════

def _build_email(recipient, all_records, due_today, today):
    total_inv   = len(all_records)
    total_out   = sum(abs(r["outstanding"]) for r in all_records)
    overdue_cnt = len(due_today)
    today_fmt   = today.strftime("%d %b %Y")

    subj = (f"[SLN Terminus] CAM Daily Report — {today_fmt} "
            f"| ₹{total_out:,.0f} Outstanding"
            + (f" | {overdue_cnt} Overdue" if overdue_cnt else ""))

    # ── Plain text ──────────────────────────────────────────────────────
    pl = [
        "SLN Terminus — CAM Daily Report",
        f"Date : {today_fmt}",
        "="*60,
        f"Total Invoices    : {total_inv}",
        f"Total Outstanding : Rs {total_out:,.0f}",
        f"Overdue Reminders : {overdue_cnt}",
        "",
    ]
    if due_today:
        pl += ["OVERDUE INVOICES (reminders due today)", "-"*60]
        for r in due_today:
            pl += [
                f"  Client      : {r['clientName']}",
                f"  Invoice     : {r['invoiceNo']}  |  Period: {r['period']}",
                f"  Due Date    : {r['dueDate']}  |  Overdue: {r['_days']} days",
                f"  Outstanding : Rs {abs(r['outstanding']):,.0f}",
                "",
            ]
    pl += ["─"*60, "SLN Terminus Accounts Dept",
           "Automated email — do not reply."]
    plain = "\n".join(pl)

    # ── Summary cards HTML ───────────────────────────────────────────────
    cards = f"""
<div style="display:flex;gap:14px;flex-wrap:wrap;margin:20px 0;">
  <div style="flex:1;min-width:130px;background:#0d2137;border:1px solid #1a3a5c;border-radius:12px;padding:16px;text-align:center;">
    <div style="font-size:10px;letter-spacing:1px;text-transform:uppercase;color:#7dd3fc;margin-bottom:6px;">Total Invoices</div>
    <div style="font-size:28px;font-weight:800;color:#e8f4fd;">{total_inv}</div>
  </div>
  <div style="flex:1;min-width:130px;background:#0d2718;border:1px solid #1a3a28;border-radius:12px;padding:16px;text-align:center;">
    <div style="font-size:10px;letter-spacing:1px;text-transform:uppercase;color:#6ee7b7;margin-bottom:6px;">Outstanding</div>
    <div style="font-size:20px;font-weight:800;color:#e8f4fd;">₹{total_out:,.0f}</div>
  </div>
  <div style="flex:1;min-width:130px;background:{'#2a0d0d' if overdue_cnt else '#0d2718'};border:1px solid {'#4a1a1a' if overdue_cnt else '#1a3a28'};border-radius:12px;padding:16px;text-align:center;">
    <div style="font-size:10px;letter-spacing:1px;text-transform:uppercase;color:{'#fca5a5' if overdue_cnt else '#6ee7b7'};margin-bottom:6px;">Overdue Today</div>
    <div style="font-size:28px;font-weight:800;color:{'#f87171' if overdue_cnt else '#6ee7b7'};">{overdue_cnt}</div>
  </div>
</div>"""

    # ── Overdue table HTML ───────────────────────────────────────────────
    if due_today:
        rows_h = "".join(f"""
<tr style="border-bottom:1px solid #1e2d3d;">
  <td style="padding:10px 12px;font-weight:600;color:#e2e8f0;">{r['clientName']}</td>
  <td style="padding:10px 12px;color:#94a3b8;font-family:monospace;font-size:12px;">{r['invoiceNo']}</td>
  <td style="padding:10px 12px;color:#94a3b8;">{r['period']}</td>
  <td style="padding:10px 12px;color:#94a3b8;">{r['dueDate']}</td>
  <td style="padding:10px 12px;text-align:center;">
    <span style="background:{'#7f1d1d' if r['_days']>7 else '#78350f'};color:{'#fca5a5' if r['_days']>7 else '#fde68a'};padding:2px 8px;border-radius:10px;font-size:11px;font-weight:700;">{r['_days']}d overdue</span>
  </td>
  <td style="padding:10px 12px;text-align:right;color:#f87171;font-weight:700;font-family:monospace;">₹{abs(r['outstanding']):,.0f}</td>
</tr>""" for r in due_today)
        overdue_sec = f"""
<h3 style="font-size:13px;color:#fca5a5;letter-spacing:.5px;text-transform:uppercase;margin:24px 0 10px;">⚠ Overdue Reminders ({overdue_cnt})</h3>
<table style="width:100%;border-collapse:collapse;background:#0c1a2e;border-radius:10px;overflow:hidden;">
  <thead><tr style="background:#1a2d40;">
    <th style="padding:9px 12px;text-align:left;font-size:10px;color:#64748b;letter-spacing:.8px;text-transform:uppercase;">Client</th>
    <th style="padding:9px 12px;text-align:left;font-size:10px;color:#64748b;letter-spacing:.8px;text-transform:uppercase;">Invoice</th>
    <th style="padding:9px 12px;text-align:left;font-size:10px;color:#64748b;letter-spacing:.8px;text-transform:uppercase;">Period</th>
    <th style="padding:9px 12px;text-align:left;font-size:10px;color:#64748b;letter-spacing:.8px;text-transform:uppercase;">Due Date</th>
    <th style="padding:9px 12px;text-align:center;font-size:10px;color:#64748b;letter-spacing:.8px;text-transform:uppercase;">Status</th>
    <th style="padding:9px 12px;text-align:right;font-size:10px;color:#64748b;letter-spacing:.8px;text-transform:uppercase;">Outstanding</th>
  </tr></thead>
  <tbody>{rows_h}</tbody>
</table>"""
    else:
        overdue_sec = """<div style="background:#0d2718;border:1px solid #1a3a28;border-radius:10px;padding:14px 20px;margin:20px 0;color:#6ee7b7;text-align:center;">✅ No overdue reminders due today</div>"""

    # ── All invoices table ───────────────────────────────────────────────
    all_rows = "".join(_row_html(r, today) for r in all_records)
    all_tbl = f"""
<h3 style="font-size:13px;color:#94a3b8;letter-spacing:.5px;text-transform:uppercase;margin:24px 0 10px;">All Invoices</h3>
<table style="width:100%;border-collapse:collapse;background:#0c1a2e;border-radius:10px;overflow:hidden;">
  <thead><tr style="background:#1a2d40;">
    <th style="padding:9px 12px;text-align:left;font-size:10px;color:#64748b;letter-spacing:.8px;text-transform:uppercase;">Client</th>
    <th style="padding:9px 12px;text-align:left;font-size:10px;color:#64748b;letter-spacing:.8px;text-transform:uppercase;">Invoice</th>
    <th style="padding:9px 12px;text-align:left;font-size:10px;color:#64748b;letter-spacing:.8px;text-transform:uppercase;">Due Date</th>
    <th style="padding:9px 12px;text-align:right;font-size:10px;color:#64748b;letter-spacing:.8px;text-transform:uppercase;">Outstanding</th>
    <th style="padding:9px 12px;text-align:center;font-size:10px;color:#64748b;letter-spacing:.8px;text-transform:uppercase;">Status</th>
  </tr></thead>
  <tbody>{all_rows}</tbody>
</table>"""

    html = f"""<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>CAM Daily Report — {today_fmt}</title></head>
<body style="margin:0;padding:0;background:#060d1a;font-family:'Segoe UI',Arial,sans-serif;color:#e2e8f0;">
<div style="max-width:680px;margin:0 auto;padding:20px;">

  <div style="background:linear-gradient(135deg,#0d1f3c,#0a1628);border:1px solid #1a3a5c;border-radius:14px;padding:24px 28px;margin-bottom:20px;">
    <div style="display:flex;align-items:center;gap:12px;margin-bottom:8px;">
      <div style="width:38px;height:38px;background:#0ea5e9;border-radius:9px;display:flex;align-items:center;justify-content:center;font-size:20px;flex-shrink:0;">📊</div>
      <div>
        <div style="font-size:19px;font-weight:800;color:#e8f4fd;letter-spacing:-.4px;">CAM Daily Report</div>
        <div style="font-size:12px;color:#7dd3fc;margin-top:2px;">SLN Terminus · Common Area Maintenance</div>
      </div>
    </div>
    <div style="margin-top:12px;font-size:12px;color:#7dd3fc;font-family:monospace;">
      📅 {today_fmt} &nbsp;·&nbsp; Auto-generated 9:00 AM IST &nbsp;·&nbsp;
      Schedule: D+1, D+3, D+7, then <strong>daily</strong>
    </div>
  </div>

  {cards}
  {overdue_sec}
  {all_tbl}

  <div style="margin-top:24px;padding:14px 20px;background:#0c1428;border:1px solid #1a2d40;border-radius:10px;text-align:center;">
    <div style="font-size:11px;color:#374151;line-height:1.6;">
      Automated daily email from <strong style="color:#4b5563;">SLN Terminus CAM System</strong><br/>
      Reminders trigger: Day +1, +3, +7 after due date — then daily until cleared.<br/>
      <span style="color:#2d3748;">Do not reply to this email.</span>
    </div>
  </div>
</div></body></html>"""

    return subj, html, plain


def _row_html(r, today):
    owed  = abs(r["outstanding"])
    dt    = _parse_date(r["dueDate"])
    if not r["dueDate"]:
        st = '<span style="color:#4b5563;">—</span>'
    elif owed == 0:
        st = '<span style="background:#14532d;color:#6ee7b7;padding:2px 8px;border-radius:8px;font-size:10px;font-weight:700;">CLEARED</span>'
    elif dt and dt < today:
        d  = (today - dt).days
        st = f'<span style="background:#7f1d1d;color:#fca5a5;padding:2px 8px;border-radius:8px;font-size:10px;font-weight:700;">OVERDUE {d}d</span>'
    else:
        st = '<span style="background:#1e3a5f;color:#93c5fd;padding:2px 8px;border-radius:8px;font-size:10px;font-weight:700;">PENDING</span>'
    return f"""<tr style="border-bottom:1px solid #1e2d3d;">
  <td style="padding:8px 12px;font-size:12px;color:#e2e8f0;">{r['clientName']}</td>
  <td style="padding:8px 12px;font-family:monospace;font-size:11px;color:#94a3b8;">{r['invoiceNo']}</td>
  <td style="padding:8px 12px;font-size:12px;color:#94a3b8;">{r['dueDate'] or '—'}</td>
  <td style="padding:8px 12px;text-align:right;font-weight:700;font-family:monospace;font-size:12px;color:{'#f87171' if owed>0 else '#6ee7b7'};">
    {'₹'+f'{owed:,.0f}' if owed>0 else '✓'}</td>
  <td style="padding:8px 12px;text-align:center;">{st}</td>
</tr>"""


# ═════════════════════════════════════════════════════════════════════════
#  SMTP
# ═════════════════════════════════════════════════════════════════════════

def _smtp_send(to, subj, html, plain):
    msg = MIMEMultipart("alternative")
    msg["From"]    = f"SLN Terminus CAM <{SMTP_USER}>"
    msg["To"]      = to
    msg["Subject"] = subj
    msg.attach(MIMEText(plain, "plain", "utf-8"))
    msg.attach(MIMEText(html,  "html",  "utf-8"))
    with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=30) as s:
        s.ehlo(); s.starttls(); s.login(SMTP_USER, SMTP_PASS)
        s.send_message(msg)


# ═════════════════════════════════════════════════════════════════════════
#  HELPERS
# ═════════════════════════════════════════════════════════════════════════

def _should_remind(days_over: int) -> bool:
    if days_over <= 0: return False
    if days_over > DAILY_AFTER: return True   # daily after 7 days
    return days_over in REMINDER_DAYS


def _parse_date(s) -> datetime | None:
    if not s: return None
    for fmt in ("%d-%b-%y","%d-%b-%Y","%Y-%m-%d","%d/%m/%Y","%d-%m-%Y"):
        try: return datetime.strptime(str(s).strip(), fmt)
        except ValueError: pass
    return None


def _norm(row: dict) -> dict:
    MAP = {
        "client name":"clientName","client":"clientName","name":"clientName",
        "a/c head":"accountHead","account head":"accountHead","ac head":"accountHead",
        "period":"period",
        "invoice no":"invoiceNo","invoice no.":"invoiceNo","invoice number":"invoiceNo","invoice":"invoiceNo",
        "amount":"amountNumeric","invoice date":"invoiceDate",
        "amount (rs)":"amountNumeric","amount(rs)":"amountNumeric","amt":"amountNumeric",
        "cam amount":"amountNumeric","total amount":"amountNumeric",
        "mode of payment":"modeOfPayment","mode":"modeOfPayment","payment mode":"modeOfPayment",
        "due date":"dueDate","due":"dueDate",
        "amt received":"amtReceived","amt recived":"amtReceived","amount received":"amtReceived",
        "tds":"tds","tds deducted":"tds",
        "outstanding":"outstanding","balance":"outstanding","pending":"outstanding",
        "mail_id":"mailId","mail id":"mailId","email":"mailId","e-mail":"mailId",
    }
    out = {}
    for k, v in row.items():
        key = str(k).strip().lower()
        out[MAP.get(key, k)] = "" if (not isinstance(v,str) and pd.isna(v)) else v

    def n(k):
        try: return float(str(out.get(k,0)).replace(",","").replace("₹","").strip() or 0)
        except: return 0.0
    def s(k):
        v = out.get(k,""); return str(v).strip() if v else ""
    def d(k):
        v = out.get(k,"")
        if not v: return ""
        try:
            if isinstance(v, (datetime, pd.Timestamp)): return v.strftime("%d-%b-%y")
            sv = str(v).strip()
            for fmt in ("%d-%b-%y","%d-%b-%Y","%Y-%m-%d","%d/%m/%Y","%d-%m-%Y"):
                try: return datetime.strptime(sv,fmt).strftime("%d-%b-%y")
                except ValueError: pass
            return sv
        except: return str(v)

    return {
        "clientName":s("clientName"), "accountHead":s("accountHead"),
        "period":s("period"), "invoiceNo":s("invoiceNo"),
        "invoiceDate":d("invoiceDate"), "amountNumeric":n("amountNumeric"),
        "modeOfPayment":s("modeOfPayment"), "dueDate":d("dueDate"),
        "amtReceived":n("amtReceived"), "tds":n("tds"),
        "outstanding":n("outstanding"), "mailId":s("mailId"),
    }


def _load_log() -> list:
    try:
        if LOG_FILE.exists(): return json.loads(LOG_FILE.read_text("utf-8"))
    except Exception: pass
    return []


def _save_log(log: list):
    try: LOG_FILE.write_text(json.dumps(log[-500:], indent=2), "utf-8")
    except Exception: pass


def _append_log(log: list, entry: dict): log.append(entry)


def _sent_today(log: list, email: str, today_str: str) -> bool:
    for e in reversed(log):
        if e.get("email","").lower() == email.lower():
            if e.get("sentAt","")[:10] == today_str: return True
            break
    return False


def _write_status(result: dict):
    try:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        STATUS_FILE.write_text(json.dumps(result, indent=2), "utf-8")
    except Exception: pass


if __name__ == "__main__":
    print("Manual test run…")
    import json as _j
    print(_j.dumps(run_once(), indent=2))