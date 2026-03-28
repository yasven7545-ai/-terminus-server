from flask import Flask, render_template, request, redirect, url_for, session, jsonify, send_from_directory
from models import db, User, Issue
from pathlib import Path
import os
import threading
import shutil
import inventory_scheduler
inventory_scheduler.start()
import pandas as pd
import json

from inventory_routes import inventory_bp


from datetime import datetime
from openpyxl import Workbook, load_workbook
from flask import send_file, flash
from ppm_routes import ppm_bp
from flask import Blueprint

from werkzeug.utils import secure_filename



# =====================================================
# 1. CREATE APP
# =====================================================
app = Flask(__name__, static_folder="static", template_folder="templates")
app.secret_key = "supersecretkey"
app.register_blueprint(ppm_bp)

# Register if not already present
if 'inventory_final_v5' not in app.blueprints:
    app.register_blueprint(inventory_bp, url_prefix='/inventory')

inventory_bp = Blueprint('inventory', __name__)



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


# --- CONFIGURATION ---
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

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        redirect_page = request.form.get("redirect")  # <-- NEW

        if username in USERS and USERS[username] == password:
            session["user"] = username

            # Redirect to property dashboard page
            if redirect_page:
                return redirect(redirect_page)

            # Backup fallback
            return redirect(url_for("sln_terminus"))

        return render_template("login.html", error="Invalid username or password")

    return render_template("login.html")

@app.route("/sln_terminus")
def sln_terminus():
    if "user" not in session:
        return redirect(url_for("login"))
    return render_template("sln_terminus.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

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



# =====================================================
# PPM EXCEL IMPORT (NO DEBUG, NO BLUEPRINT, SAFE)
# =====================================================

from datetime import datetime
import pandas as pd
import json
from pathlib import Path
from flask import request, jsonify
from dateutil.relativedelta import relativedelta



PPM_DATA_FILE = Path("static/data/ppm_data.json")

@app.route("/api/ppm/import-excel", methods=["POST"])
def import_ppm_excel():
    if "file" not in request.files:
        return jsonify({"error": "file missing"}), 400

    df = pd.read_excel(request.files["file"])

    assets = []
    schedules = []

    for _, r in df.iterrows():
        asset_id = str(r["Asset ID"]).strip()
        freq = str(r.get("Frequency", "Yearly")).strip()

        last_service = pd.to_datetime(r.get("Last Service"), errors="coerce")
        next_due = pd.to_datetime(r.get("nextDueDate"), errors="coerce")

        last_service = last_service.strftime("%Y-%m-%d") if not pd.isna(last_service) else None
        next_due = next_due.strftime("%Y-%m-%d") if not pd.isna(next_due) else None

        assets.append({
            "id": asset_id,
            "name": str(r["Asset Name"]).strip(),
            "category": str(r.get("In-House/Vendor", "Vendor")).strip(),
            "location": str(r.get("Location", "HT Room")).strip(),
            "lastService": last_service,
            "nextDueDate": next_due,
            "frequency": freq
        })

        if next_due:
            schedules.append({
                "assetId": asset_id,
                "date": next_due,
                "status": "Pending",
                "frequency": freq
            })

    payload = {
        "assets": assets,
        "schedules": schedules
    }

    PPM_DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(PPM_DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)

    return jsonify(success=True)




# =====================================================
# PPM DATA READ API
# =====================================================

@app.route("/api/ppm/data", methods=["GET"])
def get_ppm_data():
    with open(PPM_DATA_FILE, "r", encoding="utf-8-sig") as f:
        data = json.load(f)

    res = jsonify(data)
    res.headers["Cache-Control"] = "no-store"
    return res





PPM_DATA_FILE = Path("static/data/ppm_data.json")

def ensure_ppm_file():
    PPM_DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    if not PPM_DATA_FILE.exists():
        with open(PPM_DATA_FILE, "w", encoding="utf-8") as f:
            json.dump({"assets": [], "schedules": []}, f)

ensure_ppm_file()






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

# =========================
# TENANT AUTH + ROLE
# =========================

from datetime import datetime

TENANT_USERS = {
    "tenant": "123"
}

ISSUES = []

@app.route("/tenant", methods=["GET"])
def tenant_home():
    if "user" not in session:
        return redirect("/login")
    return render_template("tenant.html", issues=ISSUES)

@app.route("/api/tenant/issues", methods=["POST"])
def tenant_create_issue():
    issue = {
        "id": len(ISSUES) + 1,
        "title": request.form["type"],
        "description": request.form["description"],
        "status": "Open",
        "created_at": datetime.now().strftime("%d %b %Y %H:%M")
    }
    ISSUES.append(issue)
    return redirect("/tenant")

@app.route("/tenant/issue/<int:id>", methods=["GET","POST"])
def tenant_issue_detail(id):
    issue = next((i for i in ISSUES if i["id"] == id), None)
    if not issue:
        return "Not found", 404
    return render_template("tenant_issue_detail.html", issue=issue)

# ---------------- AUTH ----------------

@app.route("/login", methods=["GET","POST"])
def login_view():
    if request.method == "POST":
        u = request.form["username"]
        p = request.form["password"]
        user = User.query.filter_by(username=u, password=p).first()
        if user:
            session["user_id"] = user.id
            session["role"] = user.role
            return redirect("/admin" if user.role=="admin" else "/tenant")
    return render_template("login.html")

@app.route("/logout_admin")
def admin_logout():
    session.clear()
    return redirect("/login")

# ---------------- TENANT ----------------

@app.route("/tenant/details", methods=["GET", "POST"])
def tenant_details():
    if session.get("role") != "tenant":
        return redirect("/login")

    if request.method == "POST":
        issue = Issue(
            title=request.form["title"],
            description=request.form["description"],
            tenant_id=session["user_id"]
        )
        db.session.add(issue)
        db.session.commit()

    issues = Issue.query.filter_by(tenant_id=session["user_id"]).all()
    return render_template("tenant.html", issues=issues)

@app.route("/tenant/issue/<int:id>")
def tenant_issue(id):
    issue = Issue.query.get_or_404(id)
    return render_template("issue_detail.html", issue=issue)

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

# =====================================================
# 10. START SERVER
# =====================================================
if __name__ == "__main__":
    ensure_folders()
    app.run(host="0.0.0.0", port=5000, debug=False)
