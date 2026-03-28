"""
PPM DAILY EMAIL SCHEDULER - MINIMAL WORKING VERSION
Fixes: Syntax errors, duplicate functions, indentation errors
"""
import smtplib
import json
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr, formatdate, make_msgid
from datetime import datetime, date
from pathlib import Path
import traceback
import pandas as pd

# ======================================
# EMAIL CONFIGURATION (CORRECTED - NO TRAILING SPACES)
# ======================================
SMTP_SERVER = "smtp.gmail.com"  # ✅ REMOVED TRAILING SPACE
SMTP_PORT = 587
SENDER_EMAIL = "maintenance.slnterminus@gmail.com"  # ✅ REMOVED TRAILING SPACE
SENDER_PASSWORD = "xaottgrqtqnkouqn"  # CORRECT APP PASSWORD
RECEIVER_EMAILS = [
    "",
    "",
    "",
    "",
    ""
]  # ✅ CLEAN LIST - NO TRAILING COMMAS OR SPACES

# ======================================
# PATH CONFIGURATION
# ======================================
SCRIPT_DIR = Path(__file__).parent.resolve()
WO_JSON = SCRIPT_DIR / "static" / "data" / "work_orders.json"
ASSETS_XLSX = SCRIPT_DIR / "static" / "data" / "Assets.xlsx"

# ======================================
# CORE FUNCTIONS
# ======================================
def parse_excel_date(date_str):
    """Safely parse MM/DD/YY format from Excel"""
    if not date_str or date_str == 'nan' or date_str.lower() in ['n/a', 'none']:
        return None
    try:
        return datetime.strptime(date_str.strip(), '%m/%d/%y')
    except:
        try:
            return datetime.strptime(date_str.strip(), '%m/%d/%Y')
        except:
            return None

def generate_daily_work_orders():
    """Generates work orders for assets due today OR overdue"""
    if not ASSETS_XLSX.exists():
        print(f"⚠️ Assets.xlsx not found at: {ASSETS_XLSX}")
        return 0
    
    existing_wos = []
    if WO_JSON.exists():
        try:
            with open(WO_JSON, 'r') as f:
                data = json.load(f)
                existing_wos = data.get('work_orders', [])
        except Exception as e:
            print(f"⚠️ Error loading existing work orders: {e}")

    existing_wo_map = {}
    for wo in existing_wos:
        key = (wo.get('asset_id'), wo.get('due_date'))
        existing_wo_map[key] = wo

    try:
        df = pd.read_excel(ASSETS_XLSX)
        df.columns = df.columns.str.strip()
        
        today = date.today()
        new_wos = []
        wo_counter = len(existing_wos) + 1
        
        for _, row in df.iterrows():
            asset_id = str(row.get('Asset Code', '')).strip()
            if not asset_id or asset_id.lower() in ['nan', 'none', '']:
                continue
            
            next_due_str = str(row.get('nextDueDate', '')).strip()
            next_due_date = parse_excel_date(next_due_str)
            
            # ✅ CRITICAL FIX: Include assets due today OR overdue (past due dates)
            if not next_due_date or next_due_date.date() > today:
                continue
            
            wo_key = (asset_id, next_due_date.strftime('%Y-%m-%d'))
            if wo_key in existing_wo_map:
                continue
            
            asset_name = str(row.get('Asset Name', 'Unknown Asset')).strip()
            location = str(row.get('Location', 'Unknown Location')).strip()
            priority = "Medium"
            
            asset_lower = asset_name.lower()
            if "fire" in asset_lower or "dg" in asset_lower.replace(' ', '') or "transformer" in asset_lower or "elevator" in asset_lower or "escalator" in asset_lower:
                priority = "High"
            
            wo_id = f"WO-PPM-{today.strftime('%Y-%m')}-{str(wo_counter).zfill(4)}"
            new_wo = {
                "work_order_id": wo_id,
                "asset_id": asset_id,
                "asset_name": asset_name,
                "location": location,
                "due_date": next_due_date.strftime('%Y-%m-%d'),
                "priority": priority,
                "status": "open",
                "created_at": datetime.now().isoformat()
            }
            
            new_wos.append(new_wo)
            wo_counter += 1
            print(f"✅ Generated WO {wo_id} for {asset_name}")
        
        all_wos = existing_wos + new_wos
        with open(WO_JSON, 'w') as f:
            json.dump({
                "work_orders": all_wos,
                "last_updated": datetime.now().isoformat(),
                "total_count": len(all_wos)
            }, f, indent=2)
        
        print(f"✅ Generated {len(new_wos)} new work orders. Total: {len(all_wos)}")
        return len(new_wos)
        
    except Exception as e:
        print(f"❌ Error generating work orders: {str(e)}")
        traceback.print_exc()
        return 0

def get_today_wos():
    """Get work orders with due_date <= today AND status in [open, in-progress, overdue]"""
    if not WO_JSON.exists():
        return []
    
    try:
        with open(WO_JSON, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        today = date.today()
        work_orders = []
        
        for wo in data.get('work_orders', []):
            due_date_str = wo.get('due_date', '')
            if not due_date_str:
                continue
            
            try:
                due_date = datetime.strptime(due_date_str, '%Y-%m-%d').date()
            except:
                continue
            
            # ✅ CRITICAL FIX: Include work orders due today OR overdue (past due dates)
            status = wo.get('status', '').lower()
            if due_date <= today and status in ['open', 'in-progress', 'overdue']:
                work_orders.append(wo)
        
        return work_orders
    
    except Exception as e:
        print(f"❌ Error reading work orders: {str(e)}")
        traceback.print_exc()
        return []

def build_html_email(work_orders):
    """Build professional HTML email"""
    today = datetime.now().strftime('%A, %d %B %Y')
    table_rows = ""
    
    for wo in work_orders:
        priority = wo.get('priority', 'Medium').upper()
        priority_badge = f'<span style="background-color: #f59e0b; color: white; padding: 3px 8px; border-radius: 4px; font-weight: bold;">{priority}</span>'
        if priority == 'HIGH':
            priority_badge = '<span style="background-color: #ef4444; color: white; padding: 3px 8px; border-radius: 4px; font-weight: bold;">HIGH</span>'
        elif priority == 'LOW':
            priority_badge = '<span style="background-color: #10b981; color: white; padding: 3px 8px; border-radius: 4px; font-weight: bold;">LOW</span>'
        
        status = wo.get('status', 'Open').upper()
        status_badge = f'<span style="background-color: #3b82f6; color: white; padding: 2px 6px; border-radius: 3px; font-size: 12px;">{status}</span>'
        if status == 'OVERDUE':
            status_badge = '<span style="background-color: #ef4444; color: white; padding: 2px 6px; border-radius: 3px; font-size: 12px;">OVERDUE</span>'
        elif status == 'IN-PROGRESS':
            status_badge = '<span style="background-color: #f59e0b; color: white; padding: 2px 6px; border-radius: 3px; font-size: 12px;">IN PROGRESS</span>'
        
        table_rows += f"""
        <tr style="border-bottom:1px solid #eee">
            <td style="padding:8px;font-weight:bold">{wo.get('work_order_id', 'N/A')}</td>
            <td style="padding:8px">{wo.get('asset_name', 'Unknown')}</td>
            <td style="padding:8px">{wo.get('location', 'N/A')}</td>
            <td style="padding:8px;text-align:center;background:{'#fee' if wo.get('priority')=='High' else '#ffecb3' if wo.get('priority')=='Medium' else '#c8e6c9'}">
                {priority_badge}
            </td>
            <td style="padding:8px;text-align:center">{status_badge}</td>
        </tr>
        """

    return f"""
    <div style="font-family:Arial,sans-serif;max-width:700px;margin:20px auto">
        <div style="background:#0c4a6e;color:white;padding:20px;text-align:center;border-radius:8px 8px 0 0">
            <h1 style="margin:0;font-size:28px">SLN TERMINUS</h1>
            <p style="margin:5px 0 0 0;opacity:0.9">Daily Maintenance Schedule</p>
        </div>
        <div style="background:#f8fafc;padding:25px;border:1px solid #e2e8f0;border-top:0;border-radius:0 0 8px 8px">
            <p style="font-size:18px;margin:0 0 15px 0"><strong>{len(work_orders)} tasks require attention today</strong></p>
            <table style="width:100%;border-collapse:collapse;margin:20px 0">
                <thead>
                    <tr style="background:#1e3a8a;color:white">
                        <th style="padding:10px;text-align:left">WORK ORDER</th>
                        <th style="padding:10px;text-align:left">ASSET</th>
                        <th style="padding:10px;text-align:left">LOCATION</th>
                        <th style="padding:10px;text-align:center">PRIORITY</th>
                        <th style="padding:10px;text-align:center">STATUS</th>
                    </tr>
                </thead>
                <tbody>{table_rows}</tbody>
            </table>
            <div style="text-align:center;margin-top:25px">
                <a href="http://localhost:5000/ppm_dashboard" 
                  style="background:#0c4a6e;color:white;text-decoration:none;padding:12px 35px;border-radius:6px;font-weight:bold;display:inline-block">
                   VIEW DASHBOARD
                </a>
            </div>
            <div style="margin-top:30px;padding-top:15px;border-top:1px solid #eee;color:#64748b;font-size:12px">
                <p style="margin:3px 0">SLN Terminus Infrastructure Division</p>
                <p style="margin:3px 0">System Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}</p>
            </div>
        </div>
    </div>
    """

def send_daily_summary():
    """Sends daily PPM work order summary email with RFC 5322 compliant headers"""
    try:
        wos = get_today_wos()
        if not wos:
            msg = "No work orders due today or overdue. Email skipped."
            print(f"📧 Mailer: {msg}")
            return (True, msg)
        
        # ✅ CRITICAL FIX: RFC 5322 COMPLIANT HEADERS
        msg = MIMEMultipart('alternative')
        msg['Subject'] = f"🔴 ACTION REQUIRED: {len(wos)} Maintenance Tasks Due or Overdue - {datetime.now().strftime('%d %b %Y')}"
        msg['From'] = formataddr(("SLN Terminus MMS", SENDER_EMAIL))
        msg['To'] = ", ".join(RECEIVER_EMAILS)  # ✅ SINGLE To header (RFC 5322 compliant)
        msg['Date'] = formatdate(localtime=True)  # ✅ REQUIRED by RFC 5322
        msg['Message-ID'] = make_msgid(domain='slnterminus.com')  # ✅ REQUIRED by RFC 5322
        msg['X-Priority'] = "1"  # High priority
        
        # Build HTML email
        html_content = build_html_email(wos)
        msg.attach(MIMEText(html_content, 'html'))
        
        # Send email
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT, timeout=30) as server:
            server.starttls()
            server.login(SENDER_EMAIL, SENDER_PASSWORD)
            server.sendmail(
                SENDER_EMAIL,
                RECEIVER_EMAILS,  # ✅ Send to ALL recipients in ONE call
                msg.as_string()
            )
        
        success_msg = f"✅ Email sent successfully to {len(RECEIVER_EMAILS)} recipients ({len(wos)} work orders)"
        print(success_msg)
        return (True, success_msg)
    
    except Exception as e:
        error_msg = f"❌ Email sending failed: {str(e)}"
        print(error_msg)
        traceback.print_exc()
        return (False, error_msg)

# ======================================
# CLI EXECUTION
# ======================================
if __name__ == "__main__":
    print("=" * 70)
    print("⚙️  SLN TERMINUS DAILY PPM SCHEDULER")
    print("=" * 70)
    print(f"Execution Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Assets File: {ASSETS_XLSX}")
    print(f"Work Orders File: {WO_JSON}")
    print("=" * 70)
    
    success, message = send_daily_summary()
    
    print("\n" + "=" * 70)
    print(message)
    print("=" * 70)
    
    exit(0 if success else 1)
