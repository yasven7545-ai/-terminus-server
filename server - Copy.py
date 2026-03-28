from flask import Flask, render_template, request, redirect, url_for, session, jsonify, send_from_directory, abort
from models import db, User, Issue
from pathlib import Path
import os
import threading
import shutil
import inventory_scheduler
inventory_scheduler.start()
import pandas as pd
import json
import traceback
import csv
import io
import cam_charges_scheduler
import threading
import sqlite3
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from ppm_workflow_routes import workflow_bp
from workorders_routes import workorders_bp
from email.message import EmailMessage
from inventory_routes import inventory_bp
from apscheduler.schedulers.background import BackgroundScheduler
from ppm_daily_mailer import send_today_schedule
from functools import wraps
from ppm_routes import ppm_bp

SMTP_USER = "yasven7545@gmail.com"
SMTP_PASS = "olnjzafwxzdeblpa"   # Gmail App Password

from datetime import datetime
from openpyxl import Workbook, load_workbook
from flask import send_file, flash
from ppm_routes import ppm_bp
from flask import Blueprint

from werkzeug.utils import secure_filename

from vendor_visit_routes import vendor_visit_bp


from cam_charges_routes import cam_charges_bp

from twilio.rest import Client

from apscheduler.schedulers.background import BackgroundScheduler
from ppm_daily_mailer import send_today_schedule



# =====================================================
# 1. CREATE APP
# =====================================================
app = Flask(__name__, static_folder="static", template_folder="templates")




# 1. Scheduler ni okka sare define cheyandi
scheduler = BackgroundScheduler(timezone="Asia/Kolkata")

# 2. Job add chesetappudu args lekunda ila unchandi
scheduler.add_job(
    func=send_today_schedule, 
    trigger="cron", 
    hour=8, 
    minute=30
)

# 3. Last lo okkasare start cheyandi
scheduler.start()



app.config["DEBUG"] = True

app.secret_key = "supersecretkey"
app.register_blueprint(ppm_bp, url_prefix='/api')

# Register if not already present
if 'inventory_final_v5' not in app.blueprints:
    app.register_blueprint(inventory_bp, url_prefix='/inventory')

inventory_bp = Blueprint('inventory', __name__)

app.register_blueprint(cam_charges_bp)


app.register_blueprint(workflow_bp)



app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///portal.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False


db.init_app(app)
with app.app_context():
    db.create_all()


with app.app_context():
    db.create_all()


BASE_DIR = Path(__file__).parent.resolve()
ROOT = BASE_DIR


import ppm_routes

# --- DB & PATH CONFIG ---


DATA_DIR = Path("static/data")
DATA_DIR.mkdir(parents=True, exist_ok=True)
MASTER_FILE = DATA_DIR / "inventory_master.xlsx"
TRANSACTION_FILE = DATA_DIR / "inventory_transactions.xlsx"

def ensure_files():
    """Ensures Excel files exist with correct headers."""
    if not MASTER_FILE.exists():
        df = pd.DataFrame(columns=["Item_Code","Item_Name","Department","Unit","Opening_Stock","Stock_In","Stock_Out","Current_Stock","Min_Stock_Level","Last_Updated"])
        df.to_excel(MASTER_FILE, index=False)
    
    if not TRANSACTION_FILE.exists():
        df = pd.DataFrame(columns=["Timestamp", "Item_Code", "Item_Name", "Department", "Change_Type", "Quantity", "Remarks"])
        df.to_excel(TRANSACTION_FILE, index=False)
# =====================================================
# 2. SAFE BLUEPRINT REGISTER
# =====================================================
def safe_register(module_name, bp_name, url_prefix=None):
    try:
        mod = __import__(module_name)
        bp = getattr(mod, bp_name)
        if url_prefix:
            app.register_blueprint(bp, url_prefix=url_prefix)
        else:
            app.register_blueprint(bp)
        print(f"[OK] Registered: {bp_name} from {module_name}")
    except Exception as e:
        print(f"[WARN] Could not register {bp_name} from {module_name}: {e}")

# =====================================================
# 3. REGISTER EXISTING BLUEPRINTS (DO NOT MODIFY)
# =====================================================
safe_register("issues_routes", "issues_bp")
safe_register("workorders_routes", "workorders_bp")
safe_register("comments_routes", "comments_bp")
safe_register("supervisors_routes", "supervisors_bp")
safe_register("technicians_routes", "technicians_bp")


safe_register("ppm_plans_backend", "ppm_plans_bp")
safe_register("ppm_mapping_backend", "ppm_mapping_bp")
safe_register("work_orders_backend", "work_orders_bp")
safe_register("vendor_visit_routes", "vendor_visit_bp")



from ppm_workflow_routes import workflow_bp
from workorders_routes import workorders_bp  # ← Ee line ni add cheyandi


# -----------------------------------------------------
# Older system DB initializers — keep untouched
# -----------------------------------------------------
try:
    from issues_routes import init_db
    init_db()
except Exception as e:
    print("init_db() not executed:", e)

try:
    from workorders_routes import init_workorders, init_wo
    init_workorders()
    init_wo()
except Exception as e:
    print("init_workorders/init_wo() not executed:", e)

# =====================================================
# 4. REGISTER NEW PPM MODULE (FULLY ISOLATED)
# =====================================================

# ❗ FIXED: the correct blueprint is "ppm_bp", not "PPM_BP"


# =====================================================
# 5. START OLD SCHEDULER (NO CHANGES)
# =====================================================
try:
    from scheduler import start_scheduler
    start_scheduler()
    print("[OK] Old Scheduler started")
except Exception as e:
    print("[WARN] Old Scheduler not started:", e)






threading.Thread(
    target=cam_charges_scheduler.run_scheduler,
    daemon=True
).start()



TWILIO_SID = "ACxxxxxxxx"
TWILIO_TOKEN = "xxxxxxxx"
TWILIO_FROM = "whatsapp:+917981397300"  # Twilio sandbox

def send_whatsapp(mobile, vendor, date):
    client = Client(TWILIO_SID, TWILIO_TOKEN)
    client.messages.create(
        from_=TWILIO_FROM,
        to=f"whatsapp:+91{mobile}",
        body=f"Vendor visit approved\nVendor: {vendor}\nDate: {date}"
    )





# =====================================================
# 6. START NEW PPM SCHEDULER (ISOLATED)
# =====================================================
try:
    import ppm_scheduler
    threading.Thread(target=ppm_scheduler.start_ppm_scheduler, daemon=True).start()
    print("[OK] PPM Scheduler started")
except Exception as e:
    print("[WARN] PPM Scheduler not started:", e)

# =====================================================
# 7. PROJECT HANDOVER SETTINGS (UNCHANGED)
# =====================================================
UPLOAD_ROOT = BASE_DIR / "uploads" / "project_handover"

CATEGORIES = {
    "Admin": "Administrative & Contract Documents",
    "Technical": "Technical & Design Documents",
    "OM": "O&M Manuals",
    "Testing": "Testing & Commissioning Records",
    "Assets": "Asset Inventory",
    "Compliance": "Compliance & Safety",
    "Training": "Training & Support",
    "Digital": "Digital Handover"
}

USERS = {
    "admin": "123",
    "manager": "1234",
    "user": "12345"
}

# Training Upload Root (MISSING EARLIER — REQUIRED)
TRAINING_UPLOAD_ROOT = BASE_DIR / "uploads" / "training"


def ensure_folders():
    UPLOAD_ROOT.mkdir(parents=True, exist_ok=True)
    for key in CATEGORIES.keys():
        (UPLOAD_ROOT / key).mkdir(parents=True, exist_ok=True)


# =====================================================
# 8. inventory_routes.py inventory_scheduler.py
# =====================================================


safe_register("inventory_routes", "inventory_bp", url_prefix="/inventory")








# =====================================================
# 9. ROUTES (UNCHANGED)
# =====================================================

@app.route("/")
def home():
    return redirect(url_for("dashboard"))

@app.route("/dashboard")
def dashboard():
    return render_template("dashboard.html")




def require_property(property_name):
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            if "user" not in session:
                return redirect(url_for("dashboard"))

            if session.get("active_property") != property_name:
                abort(403)

            return fn(*args, **kwargs)
        return wrapper
    return decorator



USERS = {
    "admin": {
        "password": "123",
        "role": "admin",
        "properties": ["SLN Terminus", "ONEWEST", "The District", "One Golden Mile", "Nine Hills"]
    },
    "manager1": {
        "password": "1234",
        "role": "manager",
        "properties": ["SLN Terminus", "ONEWEST", "The District", "One Golden Mile", "Nine Hills"]
    }
}



@app.route("/login", methods=["POST"])
def login():
    u = request.form.get("username")
    p = request.form.get("password")
    prop = request.form.get("property")
    redirect_page = request.form.get("redirect") or "/dashboard"

    user = USERS.get(u)
    if not user or user["password"] != p:
        abort(401)

    if prop not in user["properties"]:
        abort(403)

    session.clear()
    session["user"] = u
    session["role"] = user["role"]
    session["properties"] = user["properties"]
    session["active_property"] = prop

    return redirect(redirect_page)


@app.route("/api/user_profile")
def get_user_profile():
    if "user" not in session:
        return jsonify({"error": "Unauthorized"}), 401

    return jsonify({
        "username": session["user"],
        "role": session["role"],
        "active_property": session["active_property"],
        "properties": session["properties"]
    })



@app.route("/sln_terminus")
@require_property("SLN Terminus")
def sln_terminus():
    return render_template("sln_terminus.html")


@app.route("/ogm")
@require_property("One Golden Mile")
def ogm():
    return render_template("ogm.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("dashboard"))


@app.route("/download-excel")
def download_excel():
    path = os.path.join(app.static_folder, "data")
    return send_from_directory(path, "SLN_Terminus_Dashboard_Data.xlsx", as_attachment=True)

@app.route("/project_handover")
def project_handover():
    return render_template("project_handover_workspace.html")

@app.route("/project_handover_workspace")
def project_handover_workspace():
    return render_template("project_handover_workspace.html")

@app.route("/api/upload/<category>", methods=["POST"])
def upload_file(category):
    if category not in CATEGORIES:
        return jsonify({"error": "invalid category"}), 400

    if "file" not in request.files:
        return jsonify({"error": "no file"}), 400

    file = request.files["file"]
    if file.filename == "":
        return jsonify({"error": "empty filename"}), 400

    save_dir = UPLOAD_ROOT / category
    save_dir.mkdir(parents=True, exist_ok=True)

    save_path = save_dir / file.filename
    file.save(save_path)
    return jsonify({"message": "uploaded"})

@app.route("/files/<category>/<filename>")
def serve_file(category, filename):
    folder = UPLOAD_ROOT / category
    return send_from_directory(folder, filename)

@app.route("/uploads/<category>/<filename>")
def serve_upload(category, filename):
    folder = UPLOAD_ROOT / category
    return send_from_directory(folder, filename)

@app.route("/api/list/<category>")
def list_files(category):
    if category not in CATEGORIES:
        return jsonify([])
    
    folder = UPLOAD_ROOT / category
    if not folder.exists():
        return jsonify([])
    
    files = []
    for f in folder.iterdir():
        if f.is_file():
            # Ikkada dictionary pampistunnam kabatti frontend lo .name pani chestundi
            files.append({
                "name": f.name,
                "size": f"{round(f.stat().st_size / 1024, 1)} KB",
                "date": datetime.fromtimestamp(f.stat().st_mtime).strftime("%Y-%m-%d")
            })
    return jsonify(files)




@app.route("/api/delete/<category>/<filename>", methods=['DELETE'])
def delete_file(category, filename):
    try:
        if category not in CATEGORIES:
            return jsonify({"success": False, "error": "Invalid category"}), 400
        
        file_path = UPLOAD_ROOT / category / filename
        if file_path.exists():
            os.remove(file_path)
            return jsonify({"success": True})
        else:
            return jsonify({"success": False, "error": "File not found"}), 404
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500



# --- SLN TERMINUS OCCUPANCY API ---

# Ensure this matches your actual file path

# Ensure your EXCEL_PATH is correct at the top of server.py
EXCEL_PATH = r'C:\Users\Venu\Desktop\my_dashboard\static\data\SLN_Terminus_Dashboard_Data.xlsx'



@app.route('/sln_occupancy')
def sln_occupancy_page():
    return render_template('sln_occupancy.html')



@app.route("/mis")
def mis():
    return render_template("mis.html")


@app.route("/kra")
def kra():
    return render_template("kra.html")

@app.route("/energy")
def energy():
    return render_template("energy.html")

@app.route("/inventory_dashboard")
def inventory_dashboard():
    return render_template("inventory_dashboard.html")
# inventory_routes.py (add this at the bottom of your existing routes)

@inventory_bp.route('/dashboard')
def inventory_dashboard():
    # This will render the HTML file from your /templates folder
    return render_template("inventory_dashboard.html")


@app.route("/issues")
def issues():
    return render_template("issues.html")

@app.route("/ppm_dashboard")
def ppm_dashboard():
    return render_template("ppm_dashboard.html")


from pathlib import Path
import json

PPM_DATA_FILE = Path("static/data/ppm_data.json")

if not PPM_DATA_FILE.exists():
    PPM_DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(PPM_DATA_FILE, "w", encoding="utf-8") as f:
        json.dump({"assets": [], "schedules": []}, f)





# ============================================
# FIXED: PPM EXCEL IMPORT (NO ENDPOINT CONFLICT)
# ============================================
# File Configuration
DATA_DIR = Path("static/data")
DATA_DIR.mkdir(parents=True, exist_ok=True)
PPM_DATA_FILE = DATA_DIR / "ppm_data.json"

# --- 1. DASHBOARD VIEW ---
@app.route("/sln_terminus")
def view_dashboard(): # Function name changed to avoid collision
    return render_template("ppm_dashboard.html")

@app.route("/api/ppm/load", methods=["GET"])
def load_data():
    if PPM_DATA_FILE.exists():
        with open(PPM_DATA_FILE, "r") as f:
            return jsonify(json.load(f))
    return jsonify({"assets": [], "schedules": []})

# ============================================
# FIXED: PPM EXCEL IMPORT (NO ENDPOINT CONFLICT)
# ============================================
@app.route('/api/ppm/import-excel', methods=['POST'])
def import_excel():
    file = request.files.get('file')
    if not file: return jsonify({"status": "error"}), 400
    df = pd.read_excel(file)

    assets = []
    schedules = []

    for _, row in df.iterrows():
        asset_obj = {
            "id ": str(row.get('Asset Code', '')),
            "name ": str(row.get('Asset Name', '')),
            "category ": str(row.get('In-House/Vendor', '')),
            "location ": str(row.get('Location', '')),
            "lastService ": str(row.get('Last Service', '')),
            "nextDueDate ": str(row.get('nextDueDate', ''))
        }
        assets.append(asset_obj)
        
        if row.get('nextDueDate'):
            schedules.append({
                "assetId ": asset_obj["id "],
                "date ": str(row.get('nextDueDate')).split(' ')[0]
            })

    # FIXED: Changed DATA_FILE → PPM_DATA_FILE (critical fix)
    with open(PPM_DATA_FILE, 'w') as f:  # ✅ CORRECTED VARIABLE
        json.dump({"assets ": assets, "schedules ": schedules}, f)
        
    return jsonify({"status ": "success"})














@app.route("/tenant")
def tenant():
    return render_template("tenant.html")




@app.route('/inventory/json_master')
def inventory_json_master():
    path = Path("static/data/inventory_master.xlsx")
    if not path.exists():
        return jsonify([])

    df = pd.read_excel(path)
    df = df.fillna("")
    return jsonify(df.to_dict(orient="records"))

    # Ensure required columns exist
    required_cols = [
        "Opening_Stock", "Stock_In", "Stock_Out",
        "Item_Code", "Item_Name", "Department", "Unit",
        "Min_Stock_Level", "Last_Updated", "Remarks"
    ]

    for col in required_cols:
        if col not in df.columns:
            # For missing numeric columns → fill 0
            if col in ["Opening_Stock", "Stock_In", "Stock_Out", "Min_Stock_Level"]:
                df[col] = 0
            else:
                df[col] = ""

    # Auto-calc Current Stock
    df["Current_Stock"] = (
        df["Opening_Stock"].astype(float) +
        df["Stock_In"].astype(float) -
        df["Stock_Out"].astype(float)
    )

    # Columns required by your inventory_dashboard.html
    send_cols = [
        "Item_Code", "Item_Name", "Department", "Unit",
        "Current_Stock", "Min_Stock_Level",
        "Last_Updated", "Remarks"
    ]

    return df[send_cols].to_json(orient='records')


@inventory_bp.route('/inventory/json_master')
def json_master():
    if not MASTER_FILE.exists(): return jsonify([])
    df = pd.read_excel(MASTER_FILE).fillna(0)
    return jsonify(df.to_dict(orient='records'))


@inventory_bp.route('/inventory/update', methods=['POST'])
def inventory_update():
    ensure_files()
    data = request.get_json()
    item_code = data.get("item_code")
    qty_change = float(data.get("quantity", 0))
    change_type = data.get("type") # IN or OUT
    
    try:
        df = pd.read_excel(MASTER_FILE)
        if item_code not in df['Item_Code'].values:
            return jsonify({"success": False, "error": "Item Code not found"}), 404

        idx = df[df['Item_Code'] == item_code].index[0]

        # Apply stock update logic
        if change_type == "IN":
            df.at[idx, "Stock_In"] = float(df.at[idx].get("Stock_In", 0)) + qty_change
        else:
            df.at[idx, "Stock_Out"] = float(df.at[idx].get("Stock_Out", 0)) + qty_change

        # Recalculate Current Stock
        df.at[idx, "Current_Stock"] = (float(df.at[idx]["Opening_Stock"]) + 
                                       float(df.at[idx]["Stock_In"]) - 
                                       float(df.at[idx]["Stock_Out"]))
        df.at[idx, "Last_Updated"] = datetime.now().strftime("%Y-%m-%d %H:%M")
        df.to_excel(MASTER_FILE, index=False)

        # Log Transaction
        tdf = pd.read_excel(TRANSACTION_FILE)
        new_row = {
            "Timestamp": datetime.now(),
            "Item_Code": item_code,
            "Item_Name": df.at[idx, "Item_Name"],
            "Department": df.at[idx, "Department"],
            "Change_Type": change_type,
            "Quantity": qty_change,
            "Remarks": "Dashboard Update"
        }
        pd.concat([tdf, pd.DataFrame([new_row])], ignore_index=True).to_excel(TRANSACTION_FILE, index=False)

        return jsonify({"success": True, "new_stock": df.at[idx, "Current_Stock"]})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500




# =====================================================
# Training images API (NEW - safe & isolated)
# =====================================================

ALLOWED_IMAGE_EXT = {"png", "jpg", "jpeg", "gif", "webp"}

def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_IMAGE_EXT

@app.route("/api/training/upload", methods=["POST"])
def upload_training_image():
    """
    POST form-data:
      - department (string)
      - file (file)
    Response: JSON { message, filename }
    """
    if "file" not in request.files:
        return jsonify({"error": "no file part"}), 400
    dept = request.form.get("department", "").strip()
    if not dept:
        return jsonify({"error": "department required"}), 400

    file = request.files["file"]
    if file.filename == "":
        return jsonify({"error": "empty filename"}), 400

    if not allowed_file(file.filename):
        return jsonify({"error": "file type not allowed"}), 400

    safe_name = secure_filename(file.filename)
    # Create department folder
    dest_dir = TRAINING_UPLOAD_ROOT / dept
    dest_dir.mkdir(parents=True, exist_ok=True)
    save_path = dest_dir / safe_name

    # If same name exists, append a counter
    if save_path.exists():
        base, ext = os.path.splitext(safe_name)
        counter = 1
        while True:
            candidate = f"{base}_{counter}{ext}"
            candidate_path = dest_dir / candidate
            if not candidate_path.exists():
                save_path = candidate_path
                safe_name = candidate
                break
            counter += 1

    file.save(save_path)
    return jsonify({"message": "uploaded", "filename": safe_name})

@app.route("/api/training/list")
def list_training_images():
    """
    Query params:
      - department (required) e.g. /api/training/list?department=MEP
    Returns JSON: { department, files: [ {name, url} ] }
    """
    dept = request.args.get("department", "").strip()
    if not dept:
        return jsonify({"error": "department required"}), 400

    dest_dir = TRAINING_UPLOAD_ROOT / dept
    if not dest_dir.exists():
        return jsonify({"department": dept, "files": []})

    files = []
    for p in sorted(dest_dir.iterdir(), key=lambda x: x.name):
        if p.is_file() and allowed_file(p.name):
            url = url_for("serve_training_image", department=dept, filename=p.name)
            files.append({"name": p.name, "url": url})
    return jsonify({"department": dept, "files": files})

@app.route("/uploads/training/<department>/<filename>")
def serve_training_image(department, filename):
    folder = TRAINING_UPLOAD_ROOT / department
    return send_from_directory(folder, filename)


@app.route("/api/training/delete", methods=["POST", "DELETE"])
def delete_training_image():
    """
    Handles image deletion from training uploads.
    """
    data = request.get_json()
    image_url = data.get("url")
    
    if not image_url:
        return jsonify({"error": "No image URL provided"}), 400

    # Convert the web URL to a local file system path
    # e.g., /uploads/training/MEP/img.jpg -> uploads/training/MEP/img.jpg
    # Using .lstrip('/') ensures it looks in the correct local directory
    relative_path = image_url.lstrip('/')
    file_path = ROOT / relative_path

    if file_path.exists() and file_path.is_file():
        try:
            os.remove(file_path)
            return jsonify({"message": "File deleted successfully"})
        except Exception as e:
            return jsonify({"error": f"Delete failed: {str(e)}"}), 500
    
    return jsonify({"error": "File not found on server"}), 404

# ================================
# 1. Transaction File Management
# ================================
TRANSACTION_FILE = Path("inventory_transactions.xlsx")

def ensure_transaction_file():
    if not TRANSACTION_FILE.exists():
        df = pd.DataFrame(columns=[
            "Timestamp", "Item_Code", "Item_Name", "Department",
            "Change_Type", "Quantity", "Remarks"
        ])
        df.to_excel(TRANSACTION_FILE, index=False)

# ================================
# 2. Add Transaction Endpoint
# ================================
@inventory_bp.route('/inventory/add_transaction', methods=['POST'])
def inventory_add_transaction():
    ensure_files()
    data = request.get_json()
    
    item_code = data.get("item_code") # Match frontend keys
    qty_change = float(data.get("quantity", 0))
    change_type = data.get("type")   # IN / OUT
    remarks = data.get("remarks", "")

    try:
        df = pd.read_excel(MASTER_FILE)
        if item_code not in df['Item_Code'].values:
            return jsonify({"success": False, "error": "Item not found"}), 404

        idx = df[df['Item_Code'] == item_code].index[0]

        # 1. Update In/Out math
        if change_type == "IN":
            df.at[idx, "Stock_In"] = float(df.at[idx].get("Stock_In", 0) or 0) + qty_change
        elif change_type == "OUT":
            df.at[idx, "Stock_Out"] = float(df.at[idx].get("Stock_Out", 0) or 0) + qty_change

        # 2. Recalculate Current Stock (Opening + In - Out)
        df.at[idx, "Current_Stock"] = float(df.at[idx]["Opening_Stock"]) + float(df.at[idx]["Stock_In"]) - float(df.at[idx]["Stock_Out"])
        df.at[idx, "Last_Updated"] = datetime.now().strftime("%Y-%m-%d %H:%M")

        # 3. Save Master
        df.to_excel(MASTER_FILE, index=False)

        # 4. Log to Transactions
        tdf = pd.read_excel(TRANSACTION_FILE)
        new_log = {
            "Timestamp": datetime.now(),
            "Item_Code": item_code,
            "Item_Name": df.at[idx, "Item_Name"],
            "Department": df.at[idx, "Department"],
            "Change_Type": change_type,
            "Quantity": qty_change,
            "Remarks": remarks
        }
        tdf = pd.concat([tdf, pd.DataFrame([new_log])], ignore_index=True)
        tdf.to_excel(TRANSACTION_FILE, index=False)

        return jsonify({"success": True, "new_stock": df.at[idx, "Current_Stock"]})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
# ================================
# 3. Transactions JSON
# ================================
@app.route('/inventory/transactions')
def inventory_transactions():
    ensure_transaction_file()
    df = pd.read_excel(TRANSACTION_FILE)
    return df.to_json(orient="records")

# ================================
# 4. Low-stock Alerts
# ================================
@app.route('/inventory/alerts')
def inventory_low_alerts():
    master_path = Path("inventory_master.xlsx")
    if not master_path.exists():
        return jsonify([])

    df = pd.read_excel(master_path)

    df["Current_Stock"] = (
        df["Opening_Stock"] +
        df["Stock_In"] -
        df["Stock_Out"]
    )

    low = df[df["Current_Stock"] <= df["Min_Stock_Level"]]

    return low.to_json(orient="records")



# ================================
# 5. Department-wise PDF Report
# ================================
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors

@inventory_bp.route('/inventory/report/<dept>')
def inventory_pdf(dept):
    if not MASTER_FILE.exists(): return "Master file missing", 404
    
    df = pd.read_excel(MASTER_FILE)
    if dept != "All":
        df = df[df["Department"] == dept]

    pdf_filename = f"Inventory_Report_{dept}.pdf"
    pdf_path = DATA_DIR / pdf_filename
    
    doc = SimpleDocTemplate(str(pdf_path), pagesize=A4)
    elements = []
    styles = getSampleStyleSheet()
    
    elements.append(Paragraph(f"Inventory Report - {dept}", styles['Title']))
    
    # Format table data
    data = [["Code", "Item Name", "Dept", "Stock"]]
    for _, row in df.iterrows():
        data.append([row['Item_Code'], row['Item_Name'], row['Department'], row['Current_Stock']])
    
    table = Table(data)
    table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.hexColor("#0ea5e9")),
        ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
        ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
        ('FONTSIZE', (0,0), (-1,-1), 10),
        ('PADDING', (0,0), (-1,-1), 6)
    ]))
    
    elements.append(table)
    doc.build(elements)
    return send_from_directory(DATA_DIR, pdf_filename, as_attachment=True)


# ================================
# 6. Low-stock Helper (for scheduler)
# ================================
def get_low_stock_items():
    master_path = Path("inventory_master.xlsx")
    if not master_path.exists():
        return []

    df = pd.read_excel(master_path)
    df["Current_Stock"] = (
        df["Opening_Stock"] +
        df["Stock_In"] -
        df["Stock_Out"]
    )

    low = df[df["Current_Stock"] <= df["Min_Stock_Level"]]
    return low




# --- Route: return JSON data of server-saved CAM file ---
@app.route('/cam_charges_data')
def cam_charges_data():
    rows = read_cam_charges_excel(CAM_CHARGES_PATH)
    return jsonify({'rows': rows})


# --- Route: Download server CAM file (or generate from posted JSON) ---
@app.route('/cam_charges_download', methods=['GET', 'POST'])
def cam_charges_download():
    # GET -> return server-stored file if exists
    if request.method == 'GET':
        if not os.path.exists(CAM_CHARGES_PATH):
            return jsonify({'success': False, 'error': 'No CAM charges file on server'}), 404
        return send_file(CAM_CHARGES_PATH, as_attachment=True)

    # POST -> accept JSON rows and stream back an xlsx
    data = request.get_json(silent=True)

    if not data or 'rows' not in data:
        return jsonify({'success': False, 'error': 'No data provided'}), 400

    tmp_io = io.BytesIO()

    # Convert rows -> excel in memory
    wb = Workbook()
    ws = wb.active
    ws.title = 'CAM Charges'

    headers = [
        'Unit',
        'Initial Amount Collected',
        'Pending Amount',
        'Pending Tenant Details',
        'Pending From (DD/MM/YYYY)',
        'Remarks'
    ]
    ws.append(headers)

    for r in data['rows']:
        ws.append([
            r.get('Unit', ''),
            r.get('Initial Amount Collected', ''),
            r.get('Pending Amount', ''),
            r.get('Pending Tenant Details', ''),
            r.get('Pending From (DD/MM/YYYY)', ''),
            r.get('Remarks', '')
        ])

    wb.save(tmp_io)
    tmp_io.seek(0)

    fname = f'cam_charges_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx'
    return send_file(
        tmp_io,
        as_attachment=True,
        download_name=fname,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )


# --- Upload CAM charges Excel ---
@app.route('/cam_charges_upload', methods=['POST'])
def cam_charges_upload():
    f = request.files.get('file')
    if not f:
        return jsonify({'success': False, 'error': 'No file uploaded'}), 400

    filename = secure_filename(f.filename)

    if not filename.lower().endswith('.xlsx'):
        return jsonify({'success': False, 'error': 'Only .xlsx files allowed'}), 400

    try:
        save_path = CAM_CHARGES_PATH
        f.save(save_path)

        rows = read_cam_charges_excel(save_path)
        return jsonify({'success': True, 'rows': rows})
    except Exception as e:
        app.logger.exception('Failed to save CAM charges file')
        return jsonify({'success': False, 'error': str(e)}), 500


# --- Fetch CAM Charges JSON ---
@app.route('/get_cam_charges', methods=['GET'])
def get_cam_charges():
    if not os.path.exists(CAM_CHARGES_PATH):
        return jsonify({'success': False, 'error': 'CAM Charges file not found'}), 404

    rows = read_cam_charges_excel(CAM_CHARGES_PATH)
    return jsonify({'success': True, 'data': rows}), 200

@app.route('/cam_charges')
def cam_charges_page():
    return render_template('cam_charges.html')




DB = "vendor_visit.db"

def init_vendor_db():
    with sqlite3.connect(DB) as con:
        con.execute("""
        CREATE TABLE IF NOT EXISTS visits (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT,
            vendor TEXT,
            company TEXT,
            phone TEXT,
            email TEXT,
            category TEXT,
            work_type TEXT,
            asset TEXT,
            purpose TEXT,
            contact_person TEXT,
            intime TEXT,
            outtime TEXT,
            status TEXT,
            photo TEXT,
            id_photo TEXT,
            signature TEXT
        )
        """)
    conn.commit()
    conn.close()

init_db()

@app.route('/vendor_visit')
def vendor_visit_page():
    return render_template('vendor_visit.html')


@app.route("/api/vendor_visit/save", methods=["POST"])
def save_visit():
    d = request.get_json(force=True)

    conn = sqlite3.connect(DB)
    c = conn.cursor()

    c.execute("""
    INSERT INTO vendor_visits
    (vendor, company, phone, email, category, workType, asset,
     purpose, contactPerson, date, inTime, outTime, status,
     photo, idPhoto, signature)
    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, (
        d.get("vendor",""),
        d.get("company",""),
        d.get("phone",""),
        d.get("email",""),
        d.get("category",""),
        d.get("workType",""),
        d.get("asset",""),
        d.get("purpose",""),
        d.get("contactPerson",""),
        d.get("date",""),
        d.get("inTime",""),
        d.get("outTime",""),
        d.get("status","Pending"),
        d.get("photo",""),
        d.get("idPhoto",""),
        d.get("signature","")
    ))

    conn.commit()
    conn.close()
    return jsonify({"success": True})


def send_approval_mail(to_email, vendor, date, category):
    msg = EmailMessage()
    msg["Subject"] = "Vendor Visit Approved"
    msg["From"] = SMTP_USER
    msg["To"] = to_email

    msg.set_content(f"""
Vendor Visit Approved

Vendor   : {vendor}
Category : {category}
Date     : {date}

Status   : APPROVED
""")

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as s:
        s.login(SMTP_USER, SMTP_PASS)
        s.send_message(msg)


def send_email(to, vendor, date, in_t, out_t):
    msg = MIMEMultipart("alternative")
    msg["Subject"] = "Vendor Visit Approved"
    msg["From"] = "noreply@yourdomain.com"
    msg["To"] = to

    html = f"""
    <html>
    <body style="font-family:Arial">
      <h3>Vendor Visit Approved</h3>
      <table border="1" cellpadding="8">
        <tr><td>Vendor</td><td>{vendor}</td></tr>
        <tr><td>Date</td><td>{date}</td></tr>
        <tr><td>In Time</td><td>{in_t}</td></tr>
        <tr><td>Out Time</td><td>{out_t}</td></tr>
        <tr><td>Status</td><td><b>Approved</b></td></tr>
      </table>
      <br>
      <p>Security Desk</p>
    </body>
    </html>
    """

    msg.attach(MIMEText(html, "html"))

    with smtplib.SMTP("smtp.gmail.com", 587) as s:
        s.starttls()
        s.login("yourmail@gmail.com", "APP_PASSWORD")
        s.send_message(msg)



# ---------------- ADMIN ----------------

@app.route("/admin")
def admin():
    if session.get("role") != "admin":
        return redirect("/login")

    issues = Issue.query.all()
    return render_template("admin.html", issues=issues)

@app.route("/admin/update/<int:id>/<status>")
def update_issue(id, status):
    if session.get("role") != "admin":
        return redirect("/login")

    issue = Issue.query.get_or_404(id)
    issue.status = status
    db.session.commit()
    return redirect("/admin")


# =========================
# ADMIN MOBILE TRIAGE
# =========================

@app.route("/admin")
def admin_dashboard():
    return render_template("admin_mobile.html", issues=ISSUES)

@app.route("/admin/update/<int:id>/<status>")
def admin_update_issue(id, status):
    for i in ISSUES:
        if i["id"] == id:
            i["status"] = status
    return redirect("/admin")





PPM_DATA_FILE = Path("static/data/ppm_data.json")

if not PPM_DATA_FILE.exists():
    PPM_DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(PPM_DATA_FILE, "w", encoding="utf-8") as f:
        json.dump({"assets": [], "schedules": []}, f)






@app.route("/api/folder/<category>", methods=["GET"])
def list_project_handover_files(category):
    if category not in CATEGORIES:
        return jsonify([])

    folder = UPLOAD_ROOT / category
    if not folder.exists():
        return jsonify([])

    files = []
    for f in sorted(folder.iterdir(), key=lambda x: x.name.lower()):
        if f.is_file():
            files.append({
                "name": f.name,
                "url": url_for("serve_upload", category=category, filename=f.name)
            })

    return jsonify(files)





# server.py

# --- OGM CAM MODULE START ---
@app.route('/ogm_cam')
def ogm_cam():
    return render_template('ogm_cam.html')


# Updated Path to look inside static/data
CAM_FILE_PATH = os.path.join(app.root_path, 'static', 'data', 'SLNT CAM ACTUALS- REV 1.0.xlsx')

@app.route("/my_dashboard")
def my_dashboard():
    try:
        # Load the 'Consolidated' sheet skipping header noise
        df = pd.read_excel(CAM_FILE_PATH, sheet_name='Consolidated', skiprows=4)
        
        # Select first 4 columns: Sl_no, Description, Per Month, Per SFT
        df = df.iloc[:, [0, 1, 2, 3]]
        df.columns = ['Sl_no', 'Description', 'Per_month', 'Per_sft']
        
        # Clean data: only rows with numeric Serial Numbers (ignores 'Total' rows)
        df = df.dropna(subset=['Description'])
        df = df[df['Sl_no'].apply(lambda x: str(x).strip().isdigit())]
        
        # Numeric conversions
        df['Per_month'] = pd.to_numeric(df['Per_month'], errors='coerce').fillna(0)
        df['Per_sft'] = pd.to_numeric(df['Per_sft'], errors='coerce').fillna(0)
        
        total_monthly = df['Per_month'].sum()
        total_area = 490749 
        avg_cam = total_monthly / total_area if total_area > 0 else 0
        
        return render_template(
            "my_dashboard.html", 
            items=df.to_dict(orient='records'),
            total_cost=total_monthly,
            per_sft_avg=avg_cam
        )
    except Exception as e:
        return f"File Error: Make sure 'SLNT CAM ACTUALS- REV 1.0.xlsx' is in static/data/. Error: {str(e)}"

@app.route("/cam_input/<sheet_name>")
def cam_input(sheet_name):
    try:
        df = pd.read_excel(CAM_FILE_PATH, sheet_name=sheet_name)
        table_html = df.to_html(index=False, na_rep='')
        return render_template("cam_input.html", sheet_name=sheet_name, table_html=table_html)
    except Exception as e:
        return f"Error loading {sheet_name}: {str(e)}"



# ... (keep your existing imports) ...

@app.route("/update_excel", methods=["POST"])
def update_excel():
    try:
        req_data = request.get_json()
        sheet_name = req_data.get('sheet_name')
        new_values = req_data.get('data')

        excel_path = "static/data/SLNT CAM ACTUALS- REV 1.0.xlsx"
        
        # 1. Read existing structure to get column names
        df_template = pd.read_excel(excel_path, sheet_name=sheet_name)
        
        # 2. Convert raw strings from web inputs back to Numbers where possible
        processed_data = []
        for row in new_values:
            processed_row = []
            for item in row:
                # Try to convert to float, if fails (like "Total" text), keep as string
                try:
                    processed_row.append(float(item.replace(',', '')))
                except:
                    processed_row.append(item)
            processed_data.append(processed_row)

        df_new = pd.DataFrame(processed_data, columns=df_template.columns)

        # 3. Save back to Excel
        with pd.ExcelWriter(excel_path, engine='openpyxl', mode='a', if_sheet_exists='replace') as writer:
            df_new.to_excel(writer, sheet_name=sheet_name, index=False)

        return jsonify({"status": "success"}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500



# INTERNAL DATA STORE
# Replaces the physical file. Changes here persist until the server restarts.
internal_db = {
    'summary': [
        {'Month': 'Jun`23', 'Electricity': 1250.00, 'Water': 450.00, 'Security': 3000, 'Total': 4700},
        {'Month': 'Jul`23', 'Electricity': 1300.00, 'Water': 460.00, 'Security': 3000, 'Total': 4760},
        {'Month': 'Aug`23', 'Electricity': 1100.00, 'Water': 420.00, 'Security': 3000, 'Total': 4520},
    ],
    'fm_incl': [
        {'Month': 'Jun`23', 'HVAC_Service': 800, 'Elevator_Maint': 1200, 'Cleaning': 1500},
        {'Month': 'Jul`23', 'HVAC_Service': 850, 'Elevator_Maint': 1200, 'Cleaning': 1500},
    ],
    'fm_excl': [
        {'Month': 'Jun`23', 'Admin_Fee': 500, 'Insurance': 1100, 'Legal': 200},
        {'Month': 'Jul`23', 'Admin_Fee': 500, 'Insurance': 1100, 'Legal': 0},
    ]
}

@app.route('/')
def index():
    # UPDATED: Points to your renamed file ogm_cam.html
    return render_template('ogm_cam.html')

@app.route('/api/dashboard-data', methods=['GET'])
def get_cam_data():
    # Use the internal_db we created earlier
    return jsonify(internal_db)

@app.route('/api/update-data', methods=['POST'])
def update_cam_data():
    try:
        data = request.json
        data_type = data.get('dataType') # summary, fm_incl, or fm_excl
        updates = data.get('updates')

        if data_type not in internal_db:
            return jsonify({"status": "error", "message": "Module not found"}), 404

        # Process updates into the in-memory dictionary
        for update in updates:
            row_idx = int(update['row'])
            col_name = update['col']
            new_val = update['value']

            # Dynamic type casting for cleaner data
            try:
                if "." in new_val:
                    new_val = float(new_val)
                else:
                    new_val = int(new_val)
            except ValueError:
                pass # Stay as string if not a number

            # Apply change
            if 0 <= row_idx < len(internal_db[data_type]):
                internal_db[data_type][row_idx][col_name] = new_val

        return jsonify({"status": "success", "message": "Synchronized with Server"})
    except Exception as e:
        return jsonify({"status": "success"})



# --- CONSOLIDATED WORKING CODE FOR server.py ---

# 1. Keep your ALL_SPACES list as is (Line 1396)
ALL_SPACES = [
    {"floor": "L-01", "area": 1200, "status": "occupied", "occupant": "Stark Industries", "cam": "4,500", "fit": "Executive Lounge", "owner": "N/A", "contact": "N/A"},
    {"floor": "L-02", "area": 850, "status": "vacant", "occupant": "None", "cam": "0", "fit": "Shell & Core", "owner": "Venu Properties", "contact": "+1-900-SPACE"},
    {"floor": "L-03", "area": 2500, "status": "occupied", "occupant": "Wayne Enterprises", "cam": "9,200", "fit": "Industrial Tech", "owner": "N/A", "contact": "N/A"},
    {"floor": "L-04", "area": 1100, "status": "vacant", "occupant": "None", "cam": "0", "fit": "Retail Standard", "owner": "Venu Properties", "contact": "+1-800-SPACE"},
]

@app.route('/space_ogm')
@app.route('/space_ogm/<view_type>')
def space_ogm_dashboard(view_type='home'):
    # 1. Filter logic using the ALL_SPACES list defined in your code
    if view_type == 'occupied':
        filtered_spaces = [s for s in ALL_SPACES if s['status'] == 'occupied']
    elif view_type == 'vacant':
        filtered_spaces = [s for s in ALL_SPACES if s['status'] == 'vacant']
    else:
        view_type = 'home'
        filtered_spaces = ALL_SPACES

    # 2. Define 'count' so line 107 in your HTML can work
    current_count = len(filtered_spaces)

    # 3. Pass ALL required variables to the template
    return render_template(
        'space_ogm.html', 
        spaces=filtered_spaces, 
        view_type=view_type, 
        count=current_count
    )
 




#Update EXCEL_PATH to point to your new file
EXCEL_PATH = r'C:\Users\Venu\Desktop\my_dashboard\static\data\Space Occupancy.xlsx'

@app.route('/api/sln/occupancy')
def get_sln_occupancy():
    try:
        # Read the first sheet (assume it's 'Sheet1' or the only sheet)
        df = pd.read_excel(EXCEL_PATH, sheet_name=0)  # Use index 0 for first sheet
        df = df.fillna('')  # Replace NaN with empty string

        spaces = []
        current_floor = None

        # Process each row
        for _, row in df.iterrows():
            # Skip empty rows
            if str(row.iloc[0]).strip() == '' and str(row.iloc[1]).strip() == '':
                continue

            # Detect if this is a new section (e.g., "CAM CHARGES DETAILS" or "Store Name")
            if str(row.iloc[0]).strip().upper() == 'SL NO' and str(row.iloc[1]).strip().upper() == 'FLOOR LEVEL':
                # This is header for Table 1
                continue
            elif str(row.iloc[0]).strip().upper() == 'SL NO' and str(row.iloc[1]).strip().upper() == 'STORE NAME':
                # This is header for Table 2
                continue

            # Extract values based on column positions
            sl_no = str(row.iloc[0]) if len(row) > 0 else ''
            floor_level = str(row.iloc[1]) if len(row) > 1 else ''
            office_name = str(row.iloc[2]) if len(row) > 2 else ''
            unit_no = str(row.iloc[3]) if len(row) > 3 else ''
            occupied_area = str(row.iloc[4]) if len(row) > 4 else '0'
            area = str(row.iloc[5]) if len(row) > 5 else '0'
            cam_rate = str(row.iloc[6]) if len(row) > 6 else '0'

            # Clean numeric fields
            def clean_number(val):
                if val == '' or pd.isna(val):
                    return 0
                try:
                    return float(str(val).replace(',', '').replace('"', '').strip())
                except:
                    return 0

            occupied_area = clean_number(occupied_area)
            area = clean_number(area)
            cam_rate = clean_number(cam_rate)

            # If Floor Level is not empty, use it
            if floor_level.strip() != '':
                current_floor = floor_level.strip()
            # Else, try to infer from Unit No (e.g., LG, L1, L2, etc.)
            elif unit_no.strip() != '':
                # Extract floor from unit no (e.g., LG-04 → LG, L1-02 → L1)
                parts = unit_no.split('-')
                if len(parts) > 0 and parts[0].strip() != '':
                    current_floor = parts[0].strip()

            # Only add if we have at least an office name or store name
            if office_name.strip() != '' or (len(row) > 1 and str(row.iloc[1]).strip() != ''):
                spaces.append({
                    "id": sl_no,
                    "floorId": current_floor or 'L4',  # Fallback to L4 if no floor detected
                    "officeName": office_name.strip(),
                    "unitNo": unit_no.strip(),
                    "occupiedArea": occupied_area,
                    "area": area,
                    "camRate": cam_rate,
                    "camRateDate": ""  # Add date column if available in future
                })

        # Calculate summary stats
        total_units = len(spaces)
        vacant_count = len([s for s in spaces if s["officeName"].lower() == "vacant" or s["camRate"] == 0])
        occupied_count = total_units - vacant_count
        fitout_count = 0  # Adjust if you have fit-out logic

        total_area = sum(s["area"] for s in spaces)
        occupied_area_sum = sum(s["occupiedArea"] for s in spaces if s["officeName"].lower() != "vacant")
        vacant_area_sum = total_area - occupied_area_sum

        return jsonify({
            "summary": {
                "total_area": total_area,
                "occupied_area": occupied_area_sum,
                "vacant_area": vacant_area_sum,
                "fitout_area": 0,
                "total_units": total_units,
                "vacant_count": vacant_count,
                "occupied_count": occupied_count,
                "fitout_count": fitout_count
            },
            "spaces": spaces
        })

    except Exception as e:
        print("ERROR in /api/sln/occupancy:", str(e))
        return jsonify({
            "error": "Failed to load occupancy data",
            "details": str(e)
        }), 500

@app.route('/api/sln/occupancy/update', methods=['POST'])
def update_sln_occupancy():
    try:
        data = request.get_json()
        spaces = data.get('spaces', [])
        
        # Convert to DataFrame
        df = pd.DataFrame(spaces)
        
        # Ensure correct column order
        df = df[[
            'id', 'floorId', 'officeName', 'unitNo',
            'occupiedArea', 'area', 'camRate', 'camRateDate'
        ]]
        
        # Save back to Excel (overwrite the first sheet)
        excel_path = r'C:\Users\Venu\Desktop\my_dashboard\static\data\Space Occupancy.xlsx'
        
        # Read original Excel to preserve formatting
        with pd.ExcelFile(excel_path) as xls:
            sheets = {sheet_name: xls.parse(sheet_name) for sheet_name in xls.sheet_names}
        
        # Replace the first sheet with updated data
        sheets[list(sheets.keys())[0]] = df
        
        # Write back to Excel
        with pd.ExcelWriter(excel_path, engine='openpyxl') as writer:
            for sheet_name, sheet_df in sheets.items():
                sheet_df.to_excel(writer, sheet_name=sheet_name, index=False)
        
        return jsonify({"success": True})
    except Exception as e:
        print("Save error:", str(e))
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/pm_dashboard")
def pm_dashboard():
    return render_template("pm_dashboard.html")


# =====================================================
# --- Daily Updates Backend Start ---
# =====================================================


@app.route('/property-manager-updates')
def pm_daily_updates_page_new(): 
    return render_template('pm_daily_updates.html')


# Database path (Mee existing database ki connect avvadaniki)
DB_PATH = 'instance/terminus.db' # Mee DB location batti deenni chusukondi

# --- FINAL FIX FOR DAILY UPDATES ---


def get_db_connection():
    
    db_path = os.path.join(app.instance_path, 'terminus.db')
    
   
    if not os.path.exists(app.instance_path):
        os.makedirs(app.instance_path)
        
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    
   
    conn.execute('''
        CREATE TABLE IF NOT EXISTS property_manager_updates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category TEXT NOT NULL,
            description TEXT NOT NULL,
            status TEXT DEFAULT 'Pending',
            timestamp DATETIME
        )
    ''')
    conn.commit()
    return conn


@app.route('/property-manager-updates')
def pm_daily_updates_page_final():
    try:
        # Ee file 'templates' folder lo undali
        return render_template('pm_daily_updates.html')
    except Exception as e:
        print(f"Template Error: {e}")
        return f"Template Not Found: {e}", 500

@app.route('/api/property-manager-updates', methods=['GET'])
def get_pm_updates_api_final():
    try:
        conn = get_db_connection()
        updates = conn.execute('SELECT * FROM property_manager_updates ORDER BY timestamp DESC').fetchall()
        conn.close()
        return jsonify([dict(row) for row in updates])
    except Exception as e:
        print(f"Database Fetch Error: {e}") # Deeni valla terminal lo error kanipisthundi
        return jsonify({"error": str(e)}), 500


@app.route('/api/property-manager-updates', methods=['POST'])
def add_pm_update_final():
    try:
        data = request.get_json()
        conn = get_db_connection()
        conn.execute('''
            INSERT INTO property_manager_updates (category, description, status, timestamp)
            VALUES (?, ?, ?, ?)
        ''', (data.get('category'), data.get('description'), data.get('status', 'Pending'), datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        conn.commit()
        conn.close()
        return jsonify({"success": True})
    except Exception as e:
        print("Post Error:", str(e))
        return jsonify({"success": False, "error": str(e)}), 500

# 4. API: Update delete cheyadaniki (Optional)
@app.route('/api/property-manager-updates/<int:id>', methods=['DELETE'])
def delete_pm_update(id):
    try:
        conn = get_db_connection()
        conn.execute('DELETE FROM property_manager_updates WHERE id = ?', (id,))
        conn.commit()
        conn.close()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

# --- Daily Updates Backend End ---


db_path = 'instance/terminus.db' 





# =====================================================
# 10. START SERVER
# =====================================================
if __name__ == "__main__":
    ensure_folders()
    app.run(host="0.0.0.0", port=5000, debug=False)