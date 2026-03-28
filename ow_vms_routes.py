"""
OW VMS ROUTES — ONEWEST Visitor Management System
Complete version with:
  - Email notifications (SMTP via existing server config)
  - WhatsApp deep-link notifications
  - SMS via fast2sms (free Indian SMS gateway)
  - Host / Tenant directory with phone + email
  - All routes prefixed /ow_vms
"""

from flask import (
    Blueprint, render_template, request, redirect,
    url_for, session, jsonify, send_from_directory, abort
)
from functools import wraps
from datetime import datetime
from pathlib import Path
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr
import json, uuid, os, smtplib, threading

try:
    import requests as _requests
except ImportError:
    _requests = None

ow_vms_bp = Blueprint("ow_vms", __name__, template_folder="templates")

BASE_DIR     = Path(__file__).parent.resolve()
VMS_DIR      = BASE_DIR / "static" / "data" / "vms"
VMS_DIR.mkdir(parents=True, exist_ok=True)

VISITORS_FILE  = VMS_DIR / "visitors.json"
BLACKLIST_FILE = VMS_DIR / "blacklist.json"
AUDIT_FILE     = VMS_DIR / "audit.json"
HOSTS_FILE     = VMS_DIR / "hosts.json"
NOTIF_LOG_FILE = VMS_DIR / "notifications.json"

VMS_UPLOADS = BASE_DIR / "uploads" / "vms"
VMS_UPLOADS.mkdir(parents=True, exist_ok=True)

ALLOWED_IMG_EXT = {"png", "jpg", "jpeg", "gif", "webp"}

VMS_SMTP_SERVER  = "smtp.gmail.com"
VMS_SMTP_PORT    = 587
VMS_SENDER_EMAIL = "maintenance.slnterminus@gmail.com"
VMS_SENDER_PASS  = "xaottgrqtqnkouqn"
VMS_ADMIN_EMAIL  = "maintenance.slnterminus@gmail.com"

# ── SMS — Fast2SMS ────────────────────────────────────────
# ▶ STEP 1: Sign up free at https://fast2sms.com
# ▶ STEP 2: Go to Dashboard → Dev API → copy your API key
# ▶ STEP 3: Paste it below OR set env var FAST2SMS_KEY
FAST2SMS_API_KEY = os.environ.get("FAST2SMS_KEY", "")  # ← PASTE YOUR KEY HERE

# ── WhatsApp — CallMeBot (FREE, zero setup fee) ───────────
# ▶ Each host must activate once (takes 30 seconds):
#   1. Save this number as a contact: +34 644 66 49 44
#   2. Send WhatsApp message to it: "I allow callmebot to send me messages"
#   3. You will receive a reply with your personal apikey (e.g. 1234567)
#   4. In VMS → Hosts/Tenants → Edit host → paste apikey in "CallMeBot Key" field
CALLMEBOT_ENABLED = True

# ── Twilio WhatsApp (paid but more reliable) ──────────────
# Uncomment + fill if using Twilio instead of CallMeBot
TWILIO_ENABLED = False
TWILIO_SID     = os.environ.get("TWILIO_SID", "")
TWILIO_TOKEN   = os.environ.get("TWILIO_TOKEN", "")
TWILIO_WA_FROM = "whatsapp:+14155238886"

DEFAULT_HOSTS = [
    {"id":"H001","name":"Mr. Kiran Kumar","unit":"101","floor":"1","phone":"+919963570009","email":"kiran@terminus-global.com","whatsapp":"919963570009","callmebot_apikey":"","type":"Tenant","active":True},
    {"id":"H002","name":"Mr. Madhav Reddy","unit":"205","floor":"2","phone":"+918374502323","email":"ravi@onewest.com","whatsapp":"918374502323","callmebot_apikey":"","type":"Host","active":True},
    {"id":"H003","name":"Mr. Venu","unit":"310","floor":"3","phone":"+917981397300","email":"yasven7545@gmail.com","whatsapp":"917981397300","callmebot_apikey":"","type":"Tenant","active":True},
    {"id":"H004","name":"MEP Desk","unit":"G-01","floor":"Ground","phone":"+918142295959","email":"maintenance.slnterminus@gmail.com","whatsapp":"918142295959","callmebot_apikey":"","type":"Security","active":True},
]

# ── Persistence ──────────────────────────────────────────
def _load(path):
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except: pass
    return []

def _save(path, data):
    try:
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        return True
    except Exception as e:
        print(f"❌ VMS save: {e}"); return False

def _new_id(p="V"):
    return f"{p}-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"

def _now_iso():
    return datetime.now().isoformat(timespec="seconds")

def _now_disp():
    return datetime.now().strftime("%d %b %Y, %I:%M %p")

def _audit(action, detail):
    log = _load(AUDIT_FILE)
    log.append({"ts":_now_iso(),"user":session.get("user","system"),"action":action,"detail":detail})
    _save(AUDIT_FILE, log[-2000:])

def _get_hosts():
    h = _load(HOSTS_FILE)
    if not h:
        _save(HOSTS_FILE, DEFAULT_HOSTS); return DEFAULT_HOSTS
    return h

def _find_host(name_or_id):
    q = (name_or_id or "").strip().lower()
    for h in _get_hosts():
        if (h.get("id","").lower()==q or h.get("name","").lower()==q
                or h.get("unit","").lower()==q or h.get("phone","").replace("+","").endswith(q)):
            return h
    return {}

def _log_notif(vid, channel, recipient, status, detail=""):
    log = _load(NOTIF_LOG_FILE)
    log.append({"ts":_now_iso(),"vid":vid,"channel":channel,"recipient":recipient,"status":status,"detail":str(detail)[:300]})
    _save(NOTIF_LOG_FILE, log[-3000:])

# ── Email ─────────────────────────────────────────────────
def _send_email(to_emails, subject, html_body, vid=""):
    if not to_emails: return
    def _do():
        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"]    = formataddr(("ONEWEST VMS", VMS_SENDER_EMAIL))
            msg["To"]      = ", ".join(to_emails)
            all_r = list(set(to_emails + [VMS_ADMIN_EMAIL]))
            msg.attach(MIMEText(html_body, "html", "utf-8"))
            with smtplib.SMTP(VMS_SMTP_SERVER, VMS_SMTP_PORT, timeout=20) as s:
                s.ehlo(); s.starttls(); s.login(VMS_SENDER_EMAIL, VMS_SENDER_PASS)
                s.sendmail(VMS_SENDER_EMAIL, all_r, msg.as_string())
            print(f"✅ VMS Email → {to_emails}")
            _log_notif(vid, "EMAIL", str(to_emails), "sent", subject)
        except Exception as e:
            print(f"❌ VMS Email: {e}")
            _log_notif(vid, "EMAIL", str(to_emails), "failed", str(e))
    threading.Thread(target=_do, daemon=True).start()

# ── SMS — Fast2SMS ────────────────────────────────────────
def _send_sms(phone, message, vid=""):
    """Send SMS via Fast2SMS. Free tier = 50 SMS.
       Get key: fast2sms.com → Dashboard → Dev API"""
    if not _requests:
        _log_notif(vid, "SMS", phone, "skipped", "requests lib missing"); return
    if not FAST2SMS_API_KEY or FAST2SMS_API_KEY.startswith("YOUR_"):
        print(f"⚠️  SMS skipped — add FAST2SMS_KEY. Msg: {message}")
        _log_notif(vid, "SMS", phone, "skipped", "No API key configured"); return
    # Fast2SMS needs 10-digit Indian mobile number
    clean = phone.strip().replace("+91","").replace("+","").replace(" ","").replace("-","")
    if not clean.isdigit() or len(clean) != 10:
        print(f"⚠️  SMS skipped — invalid number: {phone}")
        _log_notif(vid, "SMS", phone, "skipped", f"Invalid number: {phone}"); return
    def _do():
        try:
            resp = _requests.post(
                "https://www.fast2sms.com/dev/bulkV2",
                headers={"authorization": FAST2SMS_API_KEY, "Content-Type": "application/json"},
                json={"route": "q", "message": message, "language": "english",
                      "flash": 0, "numbers": clean},
                timeout=15
            )
            d = resp.json()
            if d.get("return") is True:
                print(f"✅ SMS sent → {phone}")
                _log_notif(vid, "SMS", phone, "sent", message[:100])
            else:
                err = d.get("message", str(d))
                print(f"❌ SMS failed → {phone}: {err}")
                _log_notif(vid, "SMS", phone, "failed", str(err)[:200])
        except Exception as e:
            print(f"❌ SMS error: {e}")
            _log_notif(vid, "SMS", phone, "error", str(e))
    threading.Thread(target=_do, daemon=True).start()

# ── WhatsApp — CallMeBot (FREE) ───────────────────────────
def _send_whatsapp(phone, message, callmebot_apikey="", vid=""):
    """
    Send WhatsApp via CallMeBot — completely free, no account needed.
    Each host must activate once by messaging +34 644 66 49 44:
      'I allow callmebot to send me messages'
    They receive their personal apikey back.
    Store it as 'callmebot_apikey' in their host record.

    Fallback: if TWILIO_ENABLED=True and Twilio keys set, uses Twilio.
    """
    if not _requests:
        _log_notif(vid, "WHATSAPP", phone, "skipped", "requests lib missing"); return

    # ── Twilio path ───────────────────────────────────────
    if TWILIO_ENABLED and TWILIO_SID and TWILIO_TOKEN:
        def _do_twilio():
            try:
                from twilio.rest import Client
                clean = phone.strip().replace(" ","")
                if not clean.startswith("+"): clean = "+91" + clean.lstrip("0")
                client = Client(TWILIO_SID, TWILIO_TOKEN)
                msg = client.messages.create(
                    body=message, from_=TWILIO_WA_FROM,
                    to=f"whatsapp:{clean}"
                )
                print(f"✅ Twilio WA sent → {phone} | {msg.sid}")
                _log_notif(vid, "WHATSAPP", phone, "sent", f"Twilio:{msg.sid}")
            except Exception as e:
                print(f"❌ Twilio WA error: {e}")
                _log_notif(vid, "WHATSAPP", phone, "error", str(e))
        threading.Thread(target=_do_twilio, daemon=True).start()
        return

    # ── CallMeBot path ────────────────────────────────────
    if not CALLMEBOT_ENABLED:
        _log_notif(vid, "WHATSAPP", phone, "skipped", "CallMeBot disabled"); return

    if not callmebot_apikey:
        print(f"⚠️  WhatsApp skipped — no CallMeBot apikey for {phone}")
        print(f"   Host must WhatsApp '+34 644 66 49 44' saying:")
        print(f"   'I allow callmebot to send me messages'")
        print(f"   Then add the received apikey to their host record.")
        _log_notif(vid, "WHATSAPP", phone, "skipped",
                   "No CallMeBot apikey — host must activate first"); return

    def _do_callmebot():
        try:
            from urllib.parse import quote
            clean = phone.strip().replace(" ","")
            if not clean.startswith("+"): clean = "+91" + clean.lstrip("0")
            resp = _requests.get(
                "https://api.callmebot.com/whatsapp.php",
                params={
                    "phone":  clean,
                    "text":   message,
                    "apikey": callmebot_apikey
                },
                timeout=15
            )
            if resp.status_code == 200 and "Message Sent" in resp.text:
                print(f"✅ CallMeBot WA sent → {phone}")
                _log_notif(vid, "WHATSAPP", phone, "sent", message[:100])
            else:
                print(f"❌ CallMeBot WA failed → {phone}: {resp.text[:200]}")
                _log_notif(vid, "WHATSAPP", phone, "failed", resp.text[:200])
        except Exception as e:
            print(f"❌ CallMeBot WA error: {e}")
            _log_notif(vid, "WHATSAPP", phone, "error", str(e))
    threading.Thread(target=_do_callmebot, daemon=True).start()

# ── HTML email bodies ─────────────────────────────────────
def _wrap_email(title, color, body_html):
    return f"""<div style="font-family:Arial,sans-serif;max-width:560px;margin:auto;border:1px solid #ddd;border-radius:8px;overflow:hidden">
  <div style="background:#0a0a0a;padding:18px 24px"><span style="color:#c8a96e;font-size:17px;font-weight:700">ONEWEST · VMS</span></div>
  <div style="padding:24px"><div style="background:{color}15;border-left:4px solid {color};padding:14px;border-radius:4px;margin-bottom:18px"><h2 style="color:{color};margin:0">{title}</h2></div>{body_html}</div>
  <div style="background:#f5f5f5;padding:10px 24px;font-size:11px;color:#999">ONEWEST Property Management · Auto-generated</div></div>"""

def _rows(pairs):
    rows = ""
    for label, val in pairs:
        rows += f'<tr><td style="padding:6px 0;color:#666;width:130px">{label}</td><td style="padding:6px 0">{val}</td></tr>'
    return f'<table style="width:100%;border-collapse:collapse">{rows}</table>'

def _btn(text, url, bg, fg="#fff"):
    return f'<a href="{url}" style="background:{bg};color:{fg};padding:11px 22px;text-decoration:none;border-radius:6px;font-weight:700;display:inline-block;margin-top:16px;margin-right:8px">{text}</a>'

# ── Notify dispatcher ─────────────────────────────────────────────────────
def _notify(event, visitor, host=None):
    vid     = visitor.get("id","")
    host    = host or _find_host(visitor.get("host",""))
    h_email = host.get("email","")
    h_phone = host.get("phone","")
    h_wa    = host.get("whatsapp", h_phone.replace("+",""))
    h_cmkey = host.get("callmebot_apikey","")
    v_email = visitor.get("email","")
    v_phone = visitor.get("phone","")
    base    = request.url_root.rstrip("/") + "/ow_vms"
    n       = visitor.get("name","")
    co      = visitor.get("company","")
    gate    = visitor.get("gate","gate")
    purpose = visitor.get("purpose","—")
    vehicle = visitor.get("vehicle_no","—")

    if event == "arrival":
        subj = f"[ONEWEST VMS] Visitor Awaiting Approval — {n}"
        body = _rows([("Visitor",f"<strong>{n}</strong>"),("Company",co or "—"),
                      ("Phone",visitor.get("phone","—")),("Purpose",purpose),
                      ("Vehicle",vehicle),("Gate",gate),("Time",_now_disp())])
        body += (_btn("✓ APPROVE",base+f"/api/visitors/{vid}/approve","#2dd4a0","#000")
               + _btn("✗ REJECT", base+f"/api/visitors/{vid}/reject","#ff5f6b"))
        _send_email([h_email] if h_email else [], subj,
                    _wrap_email("Visitor Awaiting Approval","#f59e0b",body), vid)
        if h_phone:
            _send_sms(h_phone,
                f"ONEWEST VMS: {n} ({co}) is at {gate} to meet you. Login: {base}", vid)
        if h_wa:
            wa = (f"🔔 *ONEWEST VMS*\n\n"
                  f"*{n}* is at *{gate}* to meet you.\n"
                  f"Company: {co or chr(0x2014)}\n"
                  f"Phone: {visitor.get('phone','')}\n"
                  f"Purpose: {purpose}\nVehicle: {vehicle}\n\n"
                  f"✅ Approve: {base}/api/visitors/{vid}/approve\n"
                  f"❌ Reject:  {base}/api/visitors/{vid}/reject")
            _send_whatsapp(h_wa, wa, callmebot_apikey=h_cmkey, vid=vid)

    elif event == "approved":
        subj = f"[ONEWEST VMS] Entry Approved — {n}"
        body = _rows([("Visitor",f"<strong>{n}</strong>"),
                      ("Host",visitor.get("host","—")),("Approved At",_now_disp())])
        _send_email(list(filter(None,[h_email,v_email])), subj,
                    _wrap_email("✓ Entry Approved","#2dd4a0",body), vid)
        if v_phone:
            _send_sms(v_phone,
                f"ONEWEST VMS: Your entry is APPROVED. Proceed to {gate}. -ONEWEST Security", vid)
        if h_wa:
            wa = (f"✅ *ONEWEST VMS*\n\n"
                  f"Entry *APPROVED* for *{n}*\n"
                  f"They will enter shortly.\n{_now_disp()}")
            _send_whatsapp(h_wa, wa, callmebot_apikey=h_cmkey, vid=vid)

    elif event == "rejected":
        reason = visitor.get("rejection_reason","Host rejected")
        subj = f"[ONEWEST VMS] Entry Rejected — {n}"
        body = _rows([("Visitor",f"<strong>{n}</strong>"),
                      ("Reason",f"<span style='color:#c0392b'>{reason}</span>"),
                      ("Rejected At",_now_disp())])
        _send_email(list(filter(None,[h_email,v_email])), subj,
                    _wrap_email("✗ Entry Rejected","#ff5f6b",body), vid)
        if v_phone:
            _send_sms(v_phone,
                f"ONEWEST VMS: Entry REJECTED. Reason: {reason}. -ONEWEST Security", vid)
        if h_wa:
            wa = (f"❌ *ONEWEST VMS*\n\n"
                  f"Entry *REJECTED* for *{n}*\n"
                  f"Reason: {reason}\n{_now_disp()}")
            _send_whatsapp(h_wa, wa, callmebot_apikey=h_cmkey, vid=vid)

    elif event == "checkin":
        subj = f"[ONEWEST VMS] Visitor Checked In — {n}"
        body = _rows([("Visitor",f"<strong>{n}</strong>"),
                      ("Your Unit",host.get("unit","—")),("Time",_now_disp())])
        body += "<p style='margin-top:12px;color:#555'>Please be available to receive your visitor.</p>"
        _send_email([h_email] if h_email else [], subj,
                    _wrap_email("🚪 Visitor Checked In","#2dd4a0",body), vid)
        if h_phone:
            _send_sms(h_phone,
                f"ONEWEST VMS: {n} CHECKED IN at {datetime.now().strftime('%I:%M %p')}. -Security", vid)
        if h_wa:
            wa = (f"🚪 *ONEWEST VMS*\n\n"
                  f"*{n}* has *checked in* at {_now_disp()}.\n"
                  f"Please be ready at Unit {host.get('unit','')}.")
            _send_whatsapp(h_wa, wa, callmebot_apikey=h_cmkey, vid=vid)

    elif event == "checkout":
        subj = f"[ONEWEST VMS] Visitor Checked Out — {n}"
        entry = visitor.get("entry_time","")
        dur = "—"
        try:
            dur_s = (datetime.now()-datetime.fromisoformat(entry)).seconds
            dur = f"{dur_s//3600}h {(dur_s%3600)//60}m"
        except: pass
        body = _rows([("Visitor",f"<strong>{n}</strong>"),("Check-In",entry),
                      ("Check-Out",_now_disp()),("Duration",dur)])
        _send_email([h_email] if h_email else [], subj,
                    _wrap_email("🚶 Visitor Checked Out","#c8a96e",body), vid)
        if h_phone:
            _send_sms(h_phone,
                f"ONEWEST VMS: {n} CHECKED OUT at {datetime.now().strftime('%I:%M %p')}. "
                f"Duration: {dur}. -Security", vid)
        if h_wa:
            wa = (f"🚶 *ONEWEST VMS*\n\n"
                  f"*{n}* checked out at {_now_disp()}.\nDuration: {dur}")
            _send_whatsapp(h_wa, wa, callmebot_apikey=h_cmkey, vid=vid)

# ── Auth ──────────────────────────────────────────────────
def ow_vms_login_required(f):
    @wraps(f)
    def w(*a,**k):
        if "user" not in session: return redirect(url_for("login"))
        return f(*a,**k)
    return w

def ow_vms_require_onewest(f):
    @wraps(f)
    def w(*a,**k):
        if session.get("active_property")!="ONEWEST" and session.get("role")!="admin": abort(403)
        return f(*a,**k)
    return w

def _guard(f): return ow_vms_login_required(ow_vms_require_onewest(f))

# ═════════════════════════════════════════════════════════
# ROUTES  (portal root served by server.py @app.route /ow_vms)
# ═════════════════════════════════════════════════════════

# ── Hosts ─────────────────────────────────────────────────
@ow_vms_bp.route("/api/hosts", methods=["GET"], strict_slashes=False)
@_guard
def ow_vms_list_hosts():
    hosts = _get_hosts()
    q = request.args.get("q","").strip().lower()
    if q:
        hosts = [h for h in hosts if q in h.get("name","").lower() or q in h.get("unit","").lower() or q in h.get("phone","").lower()]
    return jsonify({"success":True,"hosts":hosts})

@ow_vms_bp.route("/api/hosts/add", methods=["POST"], strict_slashes=False)
@_guard
def ow_vms_add_host():
    data = request.get_json(silent=True) or {}
    if not data.get("name") or not data.get("phone"):
        return jsonify({"success":False,"error":"Name and phone required"}), 400
    hosts = _get_hosts()
    if any(h.get("phone")==data["phone"] for h in hosts):
        return jsonify({"success":False,"error":"Phone already exists"}), 400
    ph = data.get("phone","").strip()
    entry = {"id":_new_id("H"),"name":data.get("name","").strip(),"unit":data.get("unit","").strip(),
             "floor":data.get("floor","").strip(),"phone":ph,"email":data.get("email","").strip(),
             "whatsapp":data.get("whatsapp",ph.replace("+","")).strip(),
             "callmebot_apikey":data.get("callmebot_apikey","").strip(),
             "type":data.get("type","Tenant"),"active":True,
             "added_by":session.get("user",""),"added_at":_now_iso()}
    hosts.append(entry)
    _save(HOSTS_FILE, hosts)
    _audit("HOST_ADD",f"{entry['name']} | {entry['unit']} | {entry['phone']}")
    return jsonify({"success":True,"host":entry}), 201

@ow_vms_bp.route("/api/hosts/<hid>", methods=["PUT"], strict_slashes=False)
@_guard
def ow_vms_update_host(hid):
    data = request.get_json(silent=True) or {}
    hosts = _get_hosts()
    for h in hosts:
        if h["id"]==hid:
            for k in ["name","unit","floor","phone","email","whatsapp","callmebot_apikey","type","active"]:
                if k in data: h[k]=data[k]
            h["updated_by"]=session.get("user",""); h["updated_at"]=_now_iso()
            _save(HOSTS_FILE, hosts); _audit("HOST_UPDATE",f"{hid}|{h['name']}")
            return jsonify({"success":True,"host":h})
    return jsonify({"success":False,"error":"Not found"}), 404

@ow_vms_bp.route("/api/hosts/<hid>", methods=["DELETE"], strict_slashes=False)
@_guard
def ow_vms_delete_host(hid):
    hosts = _get_hosts()
    new   = [h for h in hosts if h["id"]!=hid]
    if len(new)==len(hosts): return jsonify({"success":False,"error":"Not found"}), 404
    _save(HOSTS_FILE, new); _audit("HOST_DELETE",hid)
    return jsonify({"success":True})

# ── Visitors ──────────────────────────────────────────────
@ow_vms_bp.route("/api/visitors", methods=["GET"], strict_slashes=False)
@_guard
def ow_vms_list_visitors():
    visitors = _load(VISITORS_FILE)
    sf = request.args.get("status","").strip()
    df = request.args.get("date","").strip()
    q  = request.args.get("q","").strip().lower()
    if sf: visitors=[v for v in visitors if v.get("status")==sf]
    if df: visitors=[v for v in visitors if v.get("visit_date","").startswith(df)]
    if q:  visitors=[v for v in visitors if q in v.get("id","").lower() or q in v.get("name","").lower()
                     or q in v.get("company","").lower() or q in v.get("phone","").lower()
                     or q in v.get("vehicle_no","").lower() or q in v.get("host","").lower()]
    return jsonify({"success":True,"visitors":list(reversed(visitors)),"total":len(visitors)})

@ow_vms_bp.route("/api/visitors/pre-register", methods=["POST"], strict_slashes=False)
@_guard
def ow_vms_pre_register():
    data = request.get_json(silent=True) or {}
    miss = [f for f in ["name","phone","visit_date"] if not data.get(f)]
    if miss: return jsonify({"success":False,"error":f"Missing: {', '.join(miss)}"}), 400
    vid  = _new_id("V")
    host = _find_host(data.get("host",""))
    rec  = {"id":vid,"name":data.get("name","").strip(),"company":data.get("company","").strip(),
            "phone":data.get("phone","").strip(),"email":data.get("email","").strip(),
            "host":data.get("host",host.get("name",session.get("user",""))).strip(),
            "host_id":host.get("id",""),"purpose":data.get("purpose","").strip(),
            "vehicle_no":data.get("vehicle_no","").strip(),"visit_date":data.get("visit_date","").strip(),
            "visit_time":data.get("visit_time","").strip(),"gate":data.get("gate","Main Gate").strip(),
            "status":"pre-approved","qr_token":uuid.uuid4().hex,
            "photo_url":"","id_scan_url":"","entry_time":"","exit_time":"",
            "blacklisted":False,"created_at":_now_iso(),"created_by":session.get("user","")}
    bl = _load(BLACKLIST_FILE)
    if any(b.get("phone")==rec["phone"] for b in bl):
        rec["status"]="blocked"; rec["blacklisted"]=True
    visitors = _load(VISITORS_FILE); visitors.append(rec); _save(VISITORS_FILE, visitors)
    _audit("PRE_REGISTER",f"{rec['name']}|{rec['phone']}|{vid}")
    return jsonify({"success":True,"visitor":rec}), 201

@ow_vms_bp.route("/api/visitors/walk-in", methods=["POST"], strict_slashes=False)
@ow_vms_login_required
def ow_vms_walk_in():
    data = request.get_json(silent=True) or {}
    if not data.get("name") or not data.get("phone"):
        return jsonify({"success":False,"error":"Name and phone required"}), 400
    vid  = _new_id("W")
    host = _find_host(data.get("host",""))
    rec  = {"id":vid,"name":data.get("name","").strip(),"company":data.get("company","").strip(),
            "phone":data.get("phone","").strip(),"email":data.get("email","").strip(),
            "host":data.get("host","").strip(),"host_id":host.get("id",""),
            "purpose":data.get("purpose","").strip(),"vehicle_no":data.get("vehicle_no","").strip(),
            "visit_date":datetime.now().strftime("%Y-%m-%d"),"visit_time":datetime.now().strftime("%H:%M"),
            "gate":data.get("gate","Main Gate").strip(),"status":"pending",
            "qr_token":uuid.uuid4().hex,"photo_url":data.get("photo_url",""),
            "id_scan_url":"","entry_time":"","exit_time":"",
            "blacklisted":False,"created_at":_now_iso(),"created_by":session.get("user","security")}
    bl = _load(BLACKLIST_FILE)
    if any(b.get("phone")==rec["phone"] for b in bl):
        rec["status"]="blocked"; rec["blacklisted"]=True
    else:
        _notify("arrival", rec, host)
    visitors = _load(VISITORS_FILE); visitors.append(rec); _save(VISITORS_FILE, visitors)
    _audit("WALK_IN",f"{rec['name']}|{rec['phone']}|{vid}")
    return jsonify({"success":True,"visitor":rec}), 201

@ow_vms_bp.route("/api/visitors/<vid>/approve", methods=["GET","POST"], strict_slashes=False)
@ow_vms_login_required
def ow_vms_approve(vid):
    visitors = _load(VISITORS_FILE)
    for v in visitors:
        if v["id"]==vid:
            if v.get("blacklisted"): return jsonify({"success":False,"error":"Blacklisted"}), 403
            v["status"]="approved"; v["approved_by"]=session.get("user",""); v["approved_at"]=_now_iso()
            _save(VISITORS_FILE, visitors); _audit("APPROVED",f"{v['name']}|{vid}")
            _notify("approved", v, _find_host(v.get("host","")))
            if request.method=="GET":
                return f"""<html><body style="font-family:Arial;text-align:center;padding:60px;background:#f0fdf4">
                    <div style="max-width:400px;margin:auto;background:#fff;padding:40px;border-radius:12px;box-shadow:0 4px 20px rgba(0,0,0,.1)">
                    <div style="font-size:48px">✅</div>
                    <h2 style="color:#2dd4a0">Entry Approved</h2>
                    <p><strong>{v['name']}</strong> approved to enter ONEWEST.</p>
                    <p style="color:#888;font-size:13px">Host, visitor &amp; security have been notified.</p>
                    <a href="/ow_vms" style="display:inline-block;margin-top:16px;background:#0a0a0a;color:#c8a96e;padding:10px 24px;text-decoration:none;border-radius:6px">Open VMS Portal</a>
                    </div></body></html>"""
            return jsonify({"success":True,"visitor":v})
    return jsonify({"success":False,"error":"Not found"}), 404

@ow_vms_bp.route("/api/visitors/<vid>/reject", methods=["GET","POST"], strict_slashes=False)
@ow_vms_login_required
def ow_vms_reject(vid):
    data   = request.get_json(silent=True) or {}
    reason = data.get("reason","") or request.args.get("reason","Host rejected entry")
    visitors = _load(VISITORS_FILE)
    for v in visitors:
        if v["id"]==vid:
            v["status"]="rejected"; v["rejection_reason"]=reason
            v["rejected_by"]=session.get("user",""); v["rejected_at"]=_now_iso()
            _save(VISITORS_FILE, visitors); _audit("REJECTED",f"{v['name']}|{vid}|{reason}")
            _notify("rejected", v, _find_host(v.get("host","")))
            if request.method=="GET":
                return f"""<html><body style="font-family:Arial;text-align:center;padding:60px;background:#fff5f5">
                    <div style="max-width:400px;margin:auto;background:#fff;padding:40px;border-radius:12px;box-shadow:0 4px 20px rgba(0,0,0,.1)">
                    <div style="font-size:48px">❌</div>
                    <h2 style="color:#ff5f6b">Entry Rejected</h2>
                    <p><strong>{v['name']}</strong>'s entry has been denied.</p>
                    <p style="color:#888;font-size:13px">Reason: {reason}</p>
                    <a href="/ow_vms" style="display:inline-block;margin-top:16px;background:#0a0a0a;color:#c8a96e;padding:10px 24px;text-decoration:none;border-radius:6px">Open VMS Portal</a>
                    </div></body></html>"""
            return jsonify({"success":True,"visitor":v})
    return jsonify({"success":False,"error":"Not found"}), 404

@ow_vms_bp.route("/api/visitors/<vid>/checkin", methods=["POST"], strict_slashes=False)
@ow_vms_login_required
def ow_vms_checkin(vid):
    visitors = _load(VISITORS_FILE)
    for v in visitors:
        if v["id"]==vid:
            if v.get("status") not in ("approved","pre-approved"):
                return jsonify({"success":False,"error":f"Cannot check-in — status '{v['status']}'"}), 400
            v["status"]="checked-in"; v["entry_time"]=_now_iso(); v["checked_in_by"]=session.get("user","")
            _save(VISITORS_FILE, visitors); _audit("CHECKED_IN",f"{v['name']}|{vid}")
            _notify("checkin", v, _find_host(v.get("host","")))
            return jsonify({"success":True,"visitor":v})
    return jsonify({"success":False,"error":"Not found"}), 404

@ow_vms_bp.route("/api/visitors/<vid>/checkout", methods=["POST"], strict_slashes=False)
@ow_vms_login_required
def ow_vms_checkout(vid):
    visitors = _load(VISITORS_FILE)
    for v in visitors:
        if v["id"]==vid:
            v["status"]="checked-out"; v["exit_time"]=_now_iso(); v["checked_out_by"]=session.get("user","")
            _save(VISITORS_FILE, visitors); _audit("CHECKED_OUT",f"{v['name']}|{vid}")
            _notify("checkout", v, _find_host(v.get("host","")))
            return jsonify({"success":True,"visitor":v})
    return jsonify({"success":False,"error":"Not found"}), 404

@ow_vms_bp.route("/api/visitors/<vid>/photo", methods=["POST"], strict_slashes=False)
@ow_vms_login_required
def ow_vms_upload_photo(vid):
    file  = request.files.get("file")
    ftype = request.form.get("type","photo")
    if not file or not file.filename: return jsonify({"success":False,"error":"No file"}), 400
    ext = file.filename.rsplit(".",1)[-1].lower()
    if ext not in ALLOWED_IMG_EXT: return jsonify({"success":False,"error":"Invalid type"}), 400
    fname = f"{vid}_{ftype}_{uuid.uuid4().hex[:6]}.{ext}"
    file.save(VMS_UPLOADS/fname)
    url = f"/ow_vms/uploads/{fname}"
    visitors = _load(VISITORS_FILE)
    for v in visitors:
        if v["id"]==vid:
            v["id_scan_url" if ftype=="id_scan" else "photo_url"]=url
            _save(VISITORS_FILE, visitors); _audit("PHOTO",f"{vid}|{ftype}")
            return jsonify({"success":True,"url":url})
    return jsonify({"success":False,"error":"Not found"}), 404

@ow_vms_bp.route("/uploads/<filename>", strict_slashes=False)
@ow_vms_login_required
def ow_vms_serve_upload(filename):
    return send_from_directory(VMS_UPLOADS, filename)

@ow_vms_bp.route("/api/verify-qr/<token>", methods=["GET"], strict_slashes=False)
@ow_vms_login_required
def ow_vms_verify_qr(token):
    for v in _load(VISITORS_FILE):
        if v.get("qr_token")==token or v.get("id")==token:
            if v.get("blacklisted"): return jsonify({"success":False,"error":"BLACKLISTED","visitor":v}), 403
            return jsonify({"success":True,"visitor":v})
    return jsonify({"success":False,"error":"Invalid token"}), 404

# ── Blacklist ─────────────────────────────────────────────
@ow_vms_bp.route("/api/blacklist", methods=["GET"], strict_slashes=False)
@_guard
def ow_vms_list_blacklist():
    return jsonify({"success":True,"blacklist":_load(BLACKLIST_FILE)})

@ow_vms_bp.route("/api/blacklist/add", methods=["POST"], strict_slashes=False)
@_guard
def ow_vms_add_blacklist():
    data = request.get_json(silent=True) or {}
    if not data.get("phone"): return jsonify({"success":False,"error":"Phone required"}), 400
    bl = _load(BLACKLIST_FILE)
    if any(b["phone"]==data["phone"] for b in bl): return jsonify({"success":False,"error":"Already blacklisted"})
    entry = {"id":_new_id("BL"),"phone":data.get("phone","").strip(),"name":data.get("name","").strip(),
             "reason":data.get("reason","").strip(),"added_by":session.get("user",""),"added_at":_now_iso()}
    bl.append(entry); _save(BLACKLIST_FILE, bl)
    visitors = _load(VISITORS_FILE)
    for v in visitors:
        if v.get("phone")==entry["phone"]:
            v["blacklisted"]=True
            if v["status"] in ("pending","pre-approved","approved"): v["status"]="blocked"
    _save(VISITORS_FILE, visitors); _audit("BL_ADD",f"{entry['name']}|{entry['phone']}")
    return jsonify({"success":True,"entry":entry}), 201

@ow_vms_bp.route("/api/blacklist/remove/<bid>", methods=["DELETE"], strict_slashes=False)
@_guard
def ow_vms_remove_blacklist(bid):
    bl  = _load(BLACKLIST_FILE)
    new = [b for b in bl if b["id"]!=bid]
    if len(new)==len(bl): return jsonify({"success":False,"error":"Not found"}), 404
    _save(BLACKLIST_FILE, new); _audit("BL_REMOVE",bid)
    return jsonify({"success":True})

# ── Notifications log ─────────────────────────────────────
@ow_vms_bp.route("/api/notifications", methods=["GET"], strict_slashes=False)
@_guard
def ow_vms_notif_log():
    log = list(reversed(_load(NOTIF_LOG_FILE)[-500:]))
    vid = request.args.get("vid","")
    if vid: log=[l for l in log if l.get("vid")==vid]
    return jsonify({"success":True,"log":log})

# ── Reports / Stats ───────────────────────────────────────
@ow_vms_bp.route("/api/report/daily", methods=["GET"], strict_slashes=False)
@_guard
def ow_vms_daily_report():
    date = request.args.get("date",datetime.now().strftime("%Y-%m-%d"))
    vis  = [v for v in _load(VISITORS_FILE) if v.get("visit_date","").startswith(date)]
    return jsonify({"success":True,"report":{"date":date,"total":len(vis),
        "pre_approved":sum(1 for v in vis if v.get("status")=="pre-approved"),
        "approved":sum(1 for v in vis if v.get("status")=="approved"),
        "checked_in":sum(1 for v in vis if v.get("status")=="checked-in"),
        "checked_out":sum(1 for v in vis if v.get("status")=="checked-out"),
        "rejected":sum(1 for v in vis if v.get("status")=="rejected"),
        "blocked":sum(1 for v in vis if v.get("status")=="blocked"),
        "visitors":vis}})

@ow_vms_bp.route("/api/audit-log", methods=["GET"], strict_slashes=False)
@_guard
def ow_vms_audit_log():
    return jsonify({"success":True,"log":list(reversed(_load(AUDIT_FILE)[-500:]))})

@ow_vms_bp.route("/api/stats", methods=["GET"], strict_slashes=False)
@_guard
def ow_vms_stats():
    visitors = _load(VISITORS_FILE)
    today   = datetime.now().strftime("%Y-%m-%d")
    tv      = [v for v in visitors if v.get("visit_date","").startswith(today)]
    on_site = [v for v in visitors if v.get("status")=="checked-in"]
    return jsonify({"success":True,"stats":{
        "today_total":len(tv),"on_site":len(on_site),
        "pending":sum(1 for v in tv if v.get("status")=="pending"),
        "pre_approved":sum(1 for v in tv if v.get("status")=="pre-approved"),
        "checked_in":sum(1 for v in tv if v.get("status")=="checked-in"),
        "checked_out":sum(1 for v in tv if v.get("status")=="checked-out"),
        "rejected":sum(1 for v in tv if v.get("status")=="rejected"),
        "blacklisted":len(_load(BLACKLIST_FILE)),"all_time":len(visitors)}})

@ow_vms_bp.route("/health", strict_slashes=False)
def ow_vms_health():
    return jsonify({"success":True,"module":"ow_vms","property":"ONEWEST",
        "smtp":VMS_SENDER_EMAIL,"sms_ready":bool(FAST2SMS_API_KEY and not FAST2SMS_API_KEY.startswith("YOUR_")),
        "hosts":len(_get_hosts()),"timestamp":_now_iso()})
# ═══════════════════════════════════════════════════════════
# NOTIFICATION CONFIG & TEST  (runtime key management)
# ═══════════════════════════════════════════════════════════
@ow_vms_bp.route("/api/notify-config", methods=["GET","POST"], strict_slashes=False)
@_guard
def ow_vms_notify_config():
    """GET: return current config status. POST: update keys at runtime."""
    global FAST2SMS_API_KEY, TWILIO_ENABLED, TWILIO_SID, TWILIO_TOKEN
    if request.method == "POST":
        data = request.get_json(silent=True) or {}
        if "fast2sms_key" in data:
            FAST2SMS_API_KEY = data["fast2sms_key"].strip()
        if "twilio_sid" in data:
            TWILIO_SID = data["twilio_sid"].strip()
        if "twilio_token" in data:
            TWILIO_TOKEN = data["twilio_token"].strip()
        if "twilio_enabled" in data:
            TWILIO_ENABLED = bool(data["twilio_enabled"])
        _audit("NOTIFY_CONFIG", f"Updated by {session.get('user','')}")
        return jsonify({"success": True, "message": "Config updated (runtime only — restart to reset)"})

    sms_ok  = bool(FAST2SMS_API_KEY and not FAST2SMS_API_KEY.startswith("YOUR_"))
    wa_ok   = TWILIO_ENABLED and bool(TWILIO_SID and TWILIO_TOKEN)
    hosts   = _get_hosts()
    cb_count = sum(1 for h in hosts if h.get("callmebot_apikey","").strip())
    return jsonify({
        "success": True,
        "sms": {
            "provider": "Fast2SMS",
            "configured": sms_ok,
            "key_set": sms_ok,
            "signup_url": "https://fast2sms.com"
        },
        "whatsapp": {
            "provider": "CallMeBot" if not TWILIO_ENABLED else "Twilio",
            "callmebot_enabled": CALLMEBOT_ENABLED,
            "hosts_with_key": cb_count,
            "total_hosts": len(hosts),
            "twilio_enabled": TWILIO_ENABLED,
            "twilio_configured": wa_ok,
            "activation_number": "+34 644 66 49 44",
            "activation_message": "I allow callmebot to send me messages"
        }
    })


@ow_vms_bp.route("/api/notify-test", methods=["POST"], strict_slashes=False)
@_guard
def ow_vms_notify_test():
    """Send a real test SMS and/or WhatsApp to any number to verify config."""
    data    = request.get_json(silent=True) or {}
    channel = data.get("channel","")   # "sms" | "whatsapp" | "both"
    phone   = data.get("phone","").strip()
    cb_key  = data.get("callmebot_apikey","").strip()

    if not phone:
        return jsonify({"success": False, "error": "Phone number required"}), 400

    msg = (f"TEST — ONEWEST VMS notification is working! "
           f"Sent at {_now_disp()} by {session.get('user','admin')}.")
    results = {}

    if channel in ("sms","both"):
        sms_ok = bool(FAST2SMS_API_KEY and not FAST2SMS_API_KEY.startswith("YOUR_"))
        if sms_ok:
            _send_sms(phone, msg, vid="TEST")
            results["sms"] = "queued — check server console for delivery status"
        else:
            results["sms"] = "SKIPPED — Fast2SMS key not configured"

    if channel in ("whatsapp","both"):
        if cb_key or (TWILIO_ENABLED and TWILIO_SID):
            _send_whatsapp(phone, f"*TEST* — ONEWEST VMS\n{msg}", callmebot_apikey=cb_key, vid="TEST")
            results["whatsapp"] = "queued — check server console + phone"
        else:
            results["whatsapp"] = ("SKIPPED — no CallMeBot apikey provided and Twilio not configured. "
                                   "Add apikey to host record or enable Twilio.")

    _audit("NOTIFY_TEST", f"channel={channel} phone={phone} by {session.get('user','')}")
    return jsonify({"success": True, "results": results})