"""
CONFIG — Shared globals imported by server.py AND all blueprint files.
Avoids circular imports by keeping everything that blueprints need here.
"""

import threading
import time as _time
import smtplib
from pathlib import Path

# ── Threading / rate-limit helpers (used by _smtp_send) ──────────────────────
_GMAIL_LOCK     = threading.Lock()
_LAST_SMTP_SEND = {"ts": 0.0}
_MIN_SEND_GAP   = 6   # seconds between sends

# ── Path constants ────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).parent.resolve()
ROOT     = BASE_DIR

WO_JSON           = BASE_DIR / "static" / "data" / "work_orders.json"
ASSETS_XLSX       = BASE_DIR / "static" / "data" / "Assets.xlsx"
PPM_DATA_FILE     = BASE_DIR / "static" / "data" / "ppm_data.json"
DATA_DIR          = BASE_DIR / "static" / "data"
PPM_CHECKLIST_DIR = BASE_DIR / "uploads" / "ppm_checklists"

UPLOAD_ROOT          = BASE_DIR / "uploads" / "project_handover"
TRAINING_UPLOAD_ROOT = BASE_DIR / "uploads" / "training"
DOC_UPLOAD_DIR       = BASE_DIR / "uploads" / "documents"
VISITOR_UPLOADS      = BASE_DIR / "uploads" / "visitor_documents"
VENDOR_UPLOADS       = BASE_DIR / "uploads" / "vendor_documents"

for _folder in [DATA_DIR, UPLOAD_ROOT, TRAINING_UPLOAD_ROOT, DOC_UPLOAD_DIR,
                VISITOR_UPLOADS, VENDOR_UPLOADS, PPM_CHECKLIST_DIR]:
    _folder.mkdir(parents=True, exist_ok=True)

# ── Email ─────────────────────────────────────────────────────────────────────
SMTP_SERVER     = "smtp.gmail.com"
SMTP_PORT       = 587
SENDER_EMAIL    = "maintenance.slnterminus@gmail.com"
SENDER_PASSWORD = "xaottgrqtqnkouqn"
RECEIVER_EMAILS = [
    "maintenance.slnterminus@gmail.com",
    "yasven7545@gmail.com",
    "engineering@terminus-global.com",
]

# ── File extensions ───────────────────────────────────────────────────────────
ALLOWED_EXTENSIONS = {"pdf", "png", "jpg", "jpeg", "doc", "docx"}
ALLOWED_IMAGE_EXT  = {"png", "jpg", "jpeg", "gif", "webp"}

# ── Project handover categories ───────────────────────────────────────────────
CATEGORIES = {
    "Admin":      "Administrative & Contract Documents",
    "Technical":  "Technical & Design Documents",
    "OM":         "O & M Manuals",
    "Testing":    "Testing & Commissioning Records",
    "Assets":     "Asset Inventory",
    "Compliance": "Compliance & Safety",
    "Training":   "Training & Support",
    "Digital":    "Digital Handover",
    "Snags":      "Snag List & Punch Items",
}
for _key in CATEGORIES:
    (UPLOAD_ROOT / _key).mkdir(parents=True, exist_ok=True)

# ── SMTP helper ───────────────────────────────────────────────────────────────
def _smtp_send(msg_obj, recipients, caller="unknown", retries=3, base_delay=4):
    """Thread-safe SMTP send with retry and minimum inter-send gap."""
    last_err = None
    for attempt in range(1, retries + 1):
        with _GMAIL_LOCK:
            gap = _time.time() - _LAST_SMTP_SEND["ts"]
            if gap < _MIN_SEND_GAP:
                _time.sleep(_MIN_SEND_GAP - gap)
            try:
                with smtplib.SMTP(SMTP_SERVER, SMTP_PORT, timeout=25) as srv:
                    srv.ehlo(); srv.starttls(); srv.ehlo()
                    srv.login(SENDER_EMAIL, SENDER_PASSWORD)
                    srv.sendmail(SENDER_EMAIL, recipients, msg_obj.as_string())
                _LAST_SMTP_SEND["ts"] = _time.time()
                print(f"✅ [{caller}] Email sent → {recipients} (attempt {attempt})")
                return True
            except smtplib.SMTPAuthenticationError as e:
                print(f"⚠️  [{caller}] SMTP auth error (attempt {attempt}): {e}")
                last_err = e
                _time.sleep(base_delay * attempt * 2)
            except (smtplib.SMTPException, OSError) as e:
                print(f"⚠️  [{caller}] SMTP error (attempt {attempt}): {e}")
                last_err = e
                _time.sleep(base_delay * attempt)
    print(f"❌ [{caller}] All {retries} attempts failed. Last error: {last_err}")
    raise last_err

# ── Users ─────────────────────────────────────────────────────────────────────
USERS = {
    # GLOBAL
    "admin":    {"password": "0962",         "role": "Admin",            "properties": ["SLN Terminus","ONEWEST","The District","One Golden Mile","Nine Hills"]},
    "manager":  {"password": "1234",         "role": "Management",       "properties": ["SLN Terminus","ONEWEST","The District","One Golden Mile","Nine Hills"]},
    "gm":       {"password": "gm123",        "role": "General Manager",  "properties": ["SLN Terminus","ONEWEST","The District","One Golden Mile","Nine Hills"]},
    # SLN Terminus
    "sln_pm":   {"password": "sln_pm123",    "role": "Property Manager", "properties": ["SLN Terminus"]},
    "sln_exec": {"password": "sln_exec123",  "role": "Executive",        "properties": ["SLN Terminus"]},
    "Super":    {"password": "12345",        "role": "Supervisor",       "properties": ["SLN Terminus"]},
    "ele":      {"password": "elec123",      "role": "Electrician",      "properties": ["SLN Terminus"]},
    "plum":     {"password": "plum123",      "role": "Plumber",          "properties": ["SLN Terminus"]},
    "hvac":     {"password": "hvac123",      "role": "HVAC",             "properties": ["SLN Terminus"]},
    # ONEWEST
    "ow_pm":    {"password": "ow_pm123",     "role": "Property Manager", "properties": ["ONEWEST"]},
    "ow_exec":  {"password": "ow_exec123",   "role": "Executive",        "properties": ["ONEWEST"]},
    "ow_sup":   {"password": "ow_sup123",    "role": "Supervisor",       "properties": ["ONEWEST"]},
    # The District
    "td_pm":    {"password": "td_pm123",     "role": "Property Manager", "properties": ["The District"]},
    # One Golden Mile
    "ogm_pm":   {"password": "ogm_pm123",   "role": "Property Manager", "properties": ["One Golden Mile"]},
    # Nine Hills
    "nh_pm":    {"password": "nh_pm123",     "role": "Property Manager", "properties": ["Nine Hills"]},
}

ALL_MODULES = [
    "energy","ow_energy","mis_reports","kra","issues","mms_dashboard",
    "store_inventory","work_track","gm_tasks","project_handover","pm_daily",
    "housekeeping","security","fire","cam_billing","space_occupancy",
    "audit_documents","sln_budget","area_summary","amc_tracker","hvac_analytics",
    "sinking_fund","salary_breakup","load_breakup","trend_analysis",
    "vendor_visit","ow_kra","ow_hk","ow_sec","ow_fire",
]

ROLE_MODULES = {
    "Admin":            ALL_MODULES,
    "admin":            ALL_MODULES,
    "Management":       ALL_MODULES,
    "General Manager":  ALL_MODULES,
    "Property Manager": ALL_MODULES,
    "Executive": [
        "energy","ow_energy","mis_reports","kra","issues","mms_dashboard",
        "store_inventory","project_handover","pm_daily","housekeeping",
        "security","fire","audit_documents","ow_sec",
    ],
    "Supervisor":  ["energy","issues","mms_dashboard","store_inventory","housekeeping","security","fire","ow_sec"],
    "Electrician": ["issues","mms_dashboard"],
    "Plumber":     ["issues","mms_dashboard"],
    "HVAC":        ["issues","mms_dashboard"],
    "Technician":  ["issues","mms_dashboard"],
}

PROPERTY_MODULES = {
    "SLN Terminus": [
        "issues","mms_dashboard","store_inventory","work_track","gm_tasks","pm_daily",
        "housekeeping","security","fire","cam_billing","energy","ow_energy",
        "space_occupancy","mis_reports","kra","project_handover","audit_documents",
        "sln_budget","area_summary","amc_tracker","hvac_analytics","sinking_fund",
        "salary_breakup","load_breakup","trend_analysis",
    ],
    "ONEWEST": [
        "issues","mms_dashboard","store_inventory","work_track","vendor_visit",
        "audit_documents","gm_tasks","space_occupancy","project_handover","pm_daily",
        "ow_kra","ow_hk","ow_sec","ow_fire",
    ],
    "The District":    ["gm_tasks"],
    "One Golden Mile": ["pm_daily","gm_tasks"],
    "Nine Hills":      ["gm_tasks"],
}
