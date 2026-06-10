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
    # ── GLOBAL — access ALL properties ──────────────────────────────────────
    "admin":   {"password": "0962",        "role": "Admin",           "properties": ["SLN Terminus","ONEWEST","The District","One Golden Mile","Nine Hills"]},
    "manager": {"password": "1234",        "role": "Management",      "properties": ["SLN Terminus","ONEWEST","The District","One Golden Mile","Nine Hills"]},
    "kk":      {"password": "kk_4321",     "role": "General Manager", "properties": ["SLN Terminus","ONEWEST","The District","One Golden Mile","Nine Hills"]},
    # ── SLN TERMINUS ─────────────────────────────────────────────────────────
    "sln_pm":             {"password": "sln_pm123",   "role": "Property Manager", "properties": ["SLN Terminus"]},
    "sln_exec":           {"password": "sln_exec123", "role": "Executive",        "properties": ["SLN Terminus"]},
    "sln_propertymanager":{"password": "sln_pm123",   "role": "Property Manager", "properties": ["SLN Terminus"]},
    "Super": {"password": "12345",   "role": "Supervisor",  "properties": ["SLN Terminus"]},
    "NVR":   {"password": "nvr123",  "role": "Supervisor",  "properties": ["SLN Terminus"]},
    "JNR":   {"password": "jnr123",  "role": "Supervisor",  "properties": ["SLN Terminus"]},
    "TS":    {"password": "ts1234",  "role": "Supervisor",  "properties": ["SLN Terminus"]},
    "ele":   {"password": "elec123", "role": "Electrician", "properties": ["SLN Terminus"]},
    "Sonu":  {"password": "Sonu123", "role": "Electrician", "properties": ["SLN Terminus"]},
    "Sra1":  {"password": "Sra123",  "role": "Electrician", "properties": ["SLN Terminus"]},
    "TEBI":  {"password": "tebi123", "role": "Electrician", "properties": ["SLN Terminus"]},
    "MLA":   {"password": "mla123",  "role": "Electrician", "properties": ["SLN Terminus"]},
    "Subbu": {"password": "Sub123",  "role": "Electrician", "properties": ["SLN Terminus"]},
    "Thiru": {"password": "Thiru123","role": "Electrician", "properties": ["SLN Terminus"]},
    "plum":  {"password": "plum123", "role": "Plumber",     "properties": ["SLN Terminus"]},
    "hvac":  {"password": "hvac123", "role": "HVAC",        "properties": ["SLN Terminus"]},
    # ── ONEWEST ───────────────────────────────────────────────────────────────
    "ow_pm":             {"password": "ow_pm123",   "role": "Property Manager", "properties": ["ONEWEST"]},
    "ow_exec":           {"password": "ow_exec123", "role": "Executive",        "properties": ["ONEWEST"]},
    "ow_super":          {"password": "sup123",     "role": "Supervisor",       "properties": ["ONEWEST"]},
    "ow_ele":            {"password": "elec123",    "role": "Electrician",      "properties": ["ONEWEST"]},
    "ow_plum":           {"password": "plmb123",    "role": "Plumber",          "properties": ["ONEWEST"]},
    "ow_hvac":           {"password": "hvac123",    "role": "HVAC",             "properties": ["ONEWEST"]},
    "ow_MST":            {"password": "ow_mst123",  "role": "Electrician",      "properties": ["ONEWEST"]},
    "ow_propertymanager":{"password": "ow_pm123",   "role": "Property Manager", "properties": ["ONEWEST"]},
    # ── THE DISTRICT ─────────────────────────────────────────────────────────
    "td_pm":             {"password": "td_pm123",    "role": "Property Manager", "properties": ["The District"]},
    "td_exec":           {"password": "td_exec123",  "role": "Executive",        "properties": ["The District"]},
    "td_supervisor":     {"password": "td_sup123",   "role": "Supervisor",       "properties": ["The District"]},
    "td_electrician":    {"password": "td_elec123",  "role": "Electrician",      "properties": ["The District"]},
    "td_plumber":        {"password": "td_plmb123",  "role": "Plumber",          "properties": ["The District"]},
    "td_hvac":           {"password": "td_hvac123",  "role": "HVAC",             "properties": ["The District"]},
    "td_technician":     {"password": "td_mst123",   "role": "Electrician",      "properties": ["The District"]},
    "td_propertymanager":{"password": "td_pm123",    "role": "Property Manager", "properties": ["The District"]},
    # ── ONE GOLDEN MILE ───────────────────────────────────────────────────────
    "ogm_pm":            {"password": "ogm_pm123",   "role": "Property Manager", "properties": ["One Golden Mile"]},
    "ogm_exec":          {"password": "ogm_exec123",  "role": "Executive",        "properties": ["One Golden Mile"]},
    "ogm_supervisor":    {"password": "ogm_sup123",   "role": "Supervisor",       "properties": ["One Golden Mile"]},
    "ogm_electrician":   {"password": "ogm_elec123",  "role": "Electrician",      "properties": ["One Golden Mile"]},
    "ogm_plumber":       {"password": "ogm_plmb123",  "role": "Plumber",          "properties": ["One Golden Mile"]},
    "ogm_hvac":          {"password": "ogm_hvac123",  "role": "HVAC",             "properties": ["One Golden Mile"]},
    "ogm_technician":    {"password": "ogm_mst123",   "role": "Electrician",      "properties": ["One Golden Mile"]},
    "ogmpm":             {"password": "ogmpm123",     "role": "Property Manager", "properties": ["One Golden Mile"]},
    # ── NINE HILLS ────────────────────────────────────────────────────────────
    "nh_pm":             {"password": "nh_pm123",    "role": "Property Manager", "properties": ["Nine Hills"]},
    "nh_exec":           {"password": "nh_exec123",  "role": "Executive",        "properties": ["Nine Hills"]},
    "nh_supervisor":     {"password": "nh_sup123",   "role": "Supervisor",       "properties": ["Nine Hills"]},
    "nh_electrician":    {"password": "nh_elec123",  "role": "Electrician",      "properties": ["Nine Hills"]},
    "nh_plumber":        {"password": "nh_plmb123",  "role": "Plumber",          "properties": ["Nine Hills"]},
    "nh_hvac":           {"password": "nh_hvac123",  "role": "HVAC",             "properties": ["Nine Hills"]},
    "nh_technician":     {"password": "nh_mst123",   "role": "Electrician",      "properties": ["Nine Hills"]},
    "nh_propertymanager":{"password": "nh_pm123",    "role": "Property Manager", "properties": ["Nine Hills"]},
}

def normalize_mod(val):
    if not val: return ""
    val = val.lower().strip()
    
    if "amc" in val: return "amc_tracker"
    if "cam_review" in val: return "cam_review"
    if "mms" in val: return "mms_dashboard"
    if "inventory" in val: return "store_inventory"
    if "mis" in val: return "mis_view"
    if "hoto" in val or "handover" in val: return "project_handover"
    if "occupancy" in val or "space" in val: return "space_occupancy"
    if "cam" in val: return "cam_billing"
    if "hk" in val or "housekeeping" in val: return "housekeeping"
    if "sec" in val or "security" in val: return "security"
    if "fire" in val: return "fire"
    if "vms" in val: return "vms"
    if "resource" in val: return "resource_mgmt"
    if "audit_documents" in val or "docs" in val or "mvgds" in val or "doc" in val: return "audit_documents"
    if "audit" in val or "epms" in val: return "epms_audit"
    if "pm" in val: return "pm_daily"
    if "issues" in val or "daily" in val: return "issues"
    if "work" in val or "track" in val: return "work_track"
    if "training" in val: return "training"
    if "eb" in val or "ebbilling" in val: return "eb_billing"
    if "budget" in val: return "sln_budget"
    if "kra" in val: return "kra"
    if "energy" in val: return "energy"
    if "ahm" in val: return "ahm_dashboard"
    if "gm_tasks" in val or "mgmt" in val or "management" in val: return "gm_tasks"
    if "way" in val or "forward" in val: return "way_forward"
    if "area" in val: return "area_summary"
    if "hvac" in val: return "hvac_analytics"
    if "sink" in val: return "sinking_fund"
    if "salary" in val: return "salary_breakup"
    if "load" in val: return "load_breakup"
    if "trend" in val: return "trend_analysis"
    
    import re
    val = re.sub(r'^(sln|ow|td|ogm|nh)_', '', val)
    return val

ALL_MODULES = [
    "space_occupancy", "cam_billing", "eb_billing", "cam_review",
    "energy", "mis_view", "kra", "issues",
    "mms_dashboard", "store_inventory", "project_handover",
    "vendor_visit", "work_track", "pm_daily", "housekeeping",
    "security", "fire", "way_forward", "audit_documents",
    "gm_tasks", "sln_budget", "area_summary", "amc_tracker",
    "hvac_analytics", "sinking_fund", "salary_breakup",
    "load_breakup", "trend_analysis", "epms_audit", "vms",
    "training",
]

ROLE_MODULES = {
    "Admin":           ALL_MODULES,
    "admin":           ALL_MODULES,
    "Management":      ALL_MODULES,
    "management":      ALL_MODULES,
    "General Manager": ALL_MODULES,
    "general manager": ALL_MODULES,
    # Property Manager — all modules EXCEPT gm_tasks (Senior Level MGMT)
    "Property Manager": [
        "space_occupancy", "cam_billing", "eb_billing", "sln_budget",
        "kra", "energy", "pm_daily", "mms_dashboard", "ahm_dashboard",
        "issues", "store_inventory", "project_handover", "work_track",
        "housekeeping", "security", "fire", "vms", "resource_mgmt",
        "epms_audit", "audit_documents", "training",
    ],
    # Executive — broad access, property-specific
    "Executive": [
        "energy", "mis_view", "kra", "issues", "mms_dashboard", "store_inventory",
        "project_handover", "pm_daily", "housekeeping",
        "security", "fire", "audit_documents", "training",
    ],
    # Supervisor — operations + energy, no billing/space/kra/project handover
    "Supervisor": [
        "energy", "issues", "mms_dashboard", "store_inventory",
        "housekeeping", "security", "fire",
    ],
    "Electrician": ["issues", "mms_dashboard"],
    "Plumber":     ["issues", "mms_dashboard"],
    "HVAC":        ["issues", "mms_dashboard"],
    "Technician":  ["issues", "mms_dashboard"],
}

PROPERTY_MODULES = {
    # Keys must match data-module values in the live portal HTML templates
    "SLN Terminus": [
        "sln_gm_tasks", "sln_occupancy", "sln_cam", "sln_eb_bill", "sln_budget", "sln_kra", "sln_energy", "sln_pm_daily",
        "sln_mis", "sln_mms_dashboard", "sln_ahm", "sln_issues", "sln_inventory", "sln_hoto", "sln_work_track",
        "sln_hk", "sln_sec", "sln_fire", "sln_vms", "sln_resource", "sln_audit", "sln_docs",
    ],
    "ONEWEST": [
        "ow_occupancy", "ow_cam", "ow_budget", "ow_kra", "ow_energy", "ow_pm_daily",
        "ow_mis", "ow_mms", "ow_ahm", "ow_issues", "ow_inventory", "ow_hoto", "ow_work_track",
        "ow_hk", "ow_sec", "ow_fire", "ow_vms", "ow_resource", "ow_audit", "ow_docs", "ow_training",
    ],
    "The District": [
        "td_occupancy", "td_cam", "td_budget", "td_kra", "td_energy", "td_pm_daily",
        "td_mis", "td_mms", "td_ahm", "td_issues", "td_inventory", "td_hoto", "td_work_track",
        "td_hk", "td_sec", "td_fire", "td_vms", "td_resource", "td_audit", "td_docs",
    ],
    "One Golden Mile": [
        "ogm_occupancy", "ogm_cam", "ogm_budget", "ogm_kra", "ogm_energy", "ogm_pm_daily",
        "ogm_mis", "ogm_mms", "ogm_ahm", "ogm_issues", "ogm_inventory", "ogm_hoto", "ogm_worktrack",
        "ogm_hk", "ogm_sec", "ogm_fire", "ogm_vms", "ogm_resource", "ogm_audit", "ogm_docs",
    ],
    "Nine Hills": [
        "nh_occupancy", "nh_cam", "nh_budget", "nh_kra", "nh_energy", "nh_pm_daily",
        "nh_mis", "nh_mms", "nh_ahm", "nh_issues", "nh_inventory", "nh_hoto", "nh_worktrack",
        "nh_hk", "nh_sec", "nh_fire", "nh_vms", "nh_resource", "nh_audit", "nh_docs",
    ],
}
