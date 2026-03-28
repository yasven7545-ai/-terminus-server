"""
ONEWEST INVENTORY SCHEDULER
Daily low stock alerts at 8:00 AM - Independent from SLN Terminus
"""
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime
import pandas as pd
import json
from pathlib import Path
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr

BASE_DIR = Path(__file__).parent.parent.resolve()
OW_INVENTORY_XLSX = BASE_DIR / "static" / "data" / "ow_store_master.xlsx"

SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
SENDER_EMAIL = "maintenance.slnterminus@gmail.com"
SENDER_PASSWORD = "xaottgrqtqnkouqn"
OW_INVENTORY_RECEIVERS = [
    "maintenance.slnterminus@gmail.com",
    "yasven7545@gmail.com",
    "engineering@terminus-global.com"
]


def ow_send_inventory_alert_email():
    """Send daily low stock alert email for ONEWEST"""
    try:
        if not OW_INVENTORY_XLSX.exists():
            print("⚠️ ONEWEST Inventory file not found")
            return {"success": False, "error": "File not found"}
        
        df = pd.read_excel(OW_INVENTORY_XLSX)
        alerts = []
        
        for _, row in df.iterrows():
            item_code = str(row.get('Item_Code', '')).strip()
            if not item_code or item_code.lower() in ['nan', 'none', '']:
                continue
            
            current_stock = float(row.get('Current_Stock', 0)) if pd.notna(row.get('Current_Stock')) else 0
            min_stock = float(row.get('Min_Stock_Level', 0)) if pd.notna(row.get('Min_Stock_Level')) else 0
            
            if current_stock < min_stock:
                alerts.append({
                    "item_code": item_code,
                    "item_name": str(row.get('Item_Name', 'Unknown')).strip(),
                    "department": str(row.get('Department', 'General')).strip(),
                    "current_stock": current_stock,
                    "min_stock_level": min_stock,
                    "shortage": min_stock - current_stock
                })
        
        if not alerts:
            print("✅ ONEWEST: No low stock alerts today")
            return {"success": True, "alerts_count": 0}
        
        alert_rows = ""
        for alert in alerts:
            severity_color = "#dc3545" if alert['current_stock'] <= 0 else "#ffc107"
            alert_rows += f"""
            <tr>
                <td style="padding:10px;border:1px solid #dee2e6;">{alert['item_code']}</td>
                <td style="padding:10px;border:1px solid #dee2e6;">{alert['item_name']}</td>
                <td style="padding:10px;border:1px solid #dee2e6;">{alert['department']}</td>
                <td style="padding:10px;border:1px solid #dee2e6;color:{severity_color};font-weight:bold;">
                    {alert['current_stock']} / {alert['min_stock_level']}
                </td>
                <td style="padding:10px;border:1px solid #dee2e6;">{alert['shortage']}</td>
            </tr>
            """
        
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; background: #f8f9fa; padding: 20px; }}
                .container {{ max-width: 800px; margin: 0 auto; background: white; border-radius: 8px; overflow: hidden; }}
                .header {{ background: #fd7e14; color: white; padding: 20px; text-align: center; }}
                .content {{ padding: 20px; }}
                table {{ width: 100%; border-collapse: collapse; margin: 20px 0; }}
                th {{ background: #343a40; color: white; padding: 12px; text-align: left; }}
                .footer {{ background: #343a40; color: white; padding: 15px; text-align: center; font-size: 12px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>📦 ONEWEST Inventory Alert</h1>
                    <p>Daily Low Stock Report - {datetime.now().strftime('%d %B %Y')}</p>
                </div>
                <div class="content">
                    <p><strong>Total Alerts:</strong> {len(alerts)}</p>
                    <table>
                        <thead>
                            <tr>
                                <th>Item Code</th>
                                <th>Item Name</th>
                                <th>Department</th>
                                <th>Stock (Current/Min)</th>
                                <th>Shortage</th>
                            </tr>
                        </thead>
                        <tbody>{alert_rows}</tbody>
                    </table>
                </div>
                <div class="footer">
                    <p>ONEWEST Property Management System</p>
                    <p>Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
                </div>
            </div>
        </body>
        </html>
        """
        
        msg = MIMEMultipart('alternative')
        msg['Subject'] = f"📦 ONEWEST Inventory Alert - {len(alerts)} Low Stock Items"
        msg['From'] = formataddr(("ONEWEST Inventory", SENDER_EMAIL))
        msg['To'] = ", ".join(OW_INVENTORY_RECEIVERS)
        msg.attach(MIMEText(html_content, 'html'))
        
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT, timeout=30) as server:
            server.starttls()
            server.login(SENDER_EMAIL, SENDER_PASSWORD)
            server.send_message(msg)
        
        print(f"✅ ONEWEST Inventory alert email sent ({len(alerts)} alerts)")
        return {"success": True, "alerts_count": len(alerts)}
    
    except Exception as e:
        print(f"❌ ONEWEST Inventory email error: {str(e)}")
        return {"success": False, "error": str(e)}


def ow_setup_inventory_scheduler():
    """Setup daily inventory alert scheduler at 8:00 AM"""
    try:
        scheduler = BackgroundScheduler()
        scheduler.add_job(
            func=ow_send_inventory_alert_email,
            trigger='cron',
            hour=8,
            minute=0,
            timezone='Asia/Kolkata',
            id='ow_inventory_daily_alert'
        )
        scheduler.start()
        print("✅ ONEWEST Inventory scheduler started: Daily at 8:00 AM IST")
        return scheduler
    except Exception as e:
        print(f"⚠️ ONEWEST Inventory scheduler error: {e}")
        return None


_ow_inventory_scheduler = ow_setup_inventory_scheduler()