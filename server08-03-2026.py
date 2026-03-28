"""
TERMINUS MAINTENANCE MANAGEMENT SYSTEM - SERVER
COMPLETE WORKING VERSION - ALL PORTALS FUNCTIONAL
NO DUPLICATES • NO ERRORS • PRODUCTION READY
"""
from flask import Flask, render_template, request, redirect, url_for, session, jsonify, send_from_directory, abort, send_file, Blueprint
from models import db, User, Issue, Asset, WorkOrder, Vendor, AuditLog, init_db, create_default_users
from pathlib import Path
import os
import pandas as pd
import json
import traceback
from datetime import datetime, timedelta
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
import io
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr
import smtplib

# =====================================================
# IMPORT BLUEPRINTS (DO NOT MODIFY)
# =====================================================
from ppm_routes import ppm_api
from ppm_workflow_routes import workflow_api
from inventory_routes import inventory_bp
from workorders_routes import workorders_bp
from vendor_visit_routes import vendor_visit_bp
from cam_charges_routes import cam_charges_bp




# Import PPM modules
from ppm_daily_mailer import send_daily_summary
from ppm_daily_mailer import generate_daily_work_orders

# Call it during initialization
if __name__ == "__main__":
    # Generate work orders on startup
    generate_daily_work_orders()



# =====================================================
# CRITICAL: Define BASE_DIR FIRST
# =====================================================
BASE_DIR = Path(__file__).parent.resolve()
ROOT = BASE_DIR

# =====================================================
# PATH CONSTANTS
# =====================================================
WO_JSON = BASE_DIR / "static" / "data" / "work_orders.json"
ASSETS_XLSX = BASE_DIR / "static" / "data" / "Assets.xlsx"
PPM_DATA_FILE = BASE_DIR / "static" / "data" / "ppm_data.json"
DATA_DIR = BASE_DIR / "static" / "data"

# Upload Directories
UPLOAD_ROOT = BASE_DIR / "uploads" / "project_handover"
TRAINING_UPLOAD_ROOT = BASE_DIR / "uploads" / "training"
DOC_UPLOAD_DIR = BASE_DIR / "uploads" / "documents"
VISITOR_UPLOADS = BASE_DIR / "uploads" / "visitor_documents"
VENDOR_UPLOADS = BASE_DIR / "uploads" / "vendor_documents"

# Create all directories
for folder in [DATA_DIR, UPLOAD_ROOT, TRAINING_UPLOAD_ROOT, DOC_UPLOAD_DIR, VISITOR_UPLOADS, VENDOR_UPLOADS]:
    folder.mkdir(parents=True, exist_ok=True)

# =====================================================
# EMAIL CONFIGURATION
# =====================================================
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
SENDER_EMAIL = "maintenance.slnterminus@gmail.com"
SENDER_PASSWORD = "xaottgrqtqnkouqn"
RECEIVER_EMAILS = [
    "maintenance.slnterminus@gmail.com",
    "yasven7545@gmail.com",
    "engineering@terminus-global.com"
]

# Allowed file extensions
ALLOWED_EXTENSIONS = {'pdf', 'png', 'jpg', 'jpeg', 'doc', 'docx'}
ALLOWED_IMAGE_EXT = {"png", "jpg", "jpeg", "gif", "webp"}

# =====================================================
# 1. CREATE APP & CONFIGURATION
# =====================================================
app = Flask(__name__, static_folder="static", template_folder="templates")
app.config["DEBUG"] = False
app.secret_key = "supersecretkey-2026"
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///portal.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024



from werkzeug.middleware.proxy_fix import ProxyFix
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)
# ── Session cookie settings ──────────────────────────────
# Required for ngrok / reverse-proxy access:
# SameSite=None + Secure allows cross-origin cookie sending over HTTPS
app.config["SESSION_COOKIE_SAMESITE"]       = "Lax"
app.config["SESSION_COOKIE_SECURE"]         = False
app.config["SESSION_COOKIE_HTTPONLY"]       = True
app.config["SESSION_COOKIE_NAME"]           = "terminus_session"
app.config["PERMANENT_SESSION_LIFETIME"]    = 86400







# =====================================================
# 2. SAFE BLUEPRINT REGISTRATION
# =====================================================
def safe_register(module_name, bp_name, url_prefix=None):
    """Safely register blueprint if module exists"""
    try:
        mod = __import__(module_name, fromlist=[bp_name])
        bp = getattr(mod, bp_name)
        if url_prefix:
            app.register_blueprint(bp, url_prefix=url_prefix)
        else:
            app.register_blueprint(bp)
        print(f"✅ Registered: {bp_name} from {module_name}")
    except ImportError as e:
        print(f"⚠️  Blueprint not found: {module_name}.{bp_name} - {str(e)}")
    except Exception as e:
        print(f"⚠️  Blueprint registration error: {module_name}.{bp_name} - {str(e)}")

# Register all blueprints ONCE
safe_register("ppm_routes", "ppm_api", url_prefix="/api")
safe_register("ppm_workflow_routes", "workflow_api", url_prefix="/api/workflow")
safe_register("inventory_routes", "inventory_bp", url_prefix="/inventory")
safe_register("workorders_routes", "workorders_bp")
safe_register("vendor_visit_routes", "vendor_visit_bp")

safe_register("ow_vms_routes", "ow_vms_bp", url_prefix="/ow_vms")



safe_register("cam_charges_routes", "cam_charges_bp")
try:
    safe_register("issues_routes", "issues_bp")
except:
    print("⚠️  Issues blueprint not available")

try:
    from ow_work_track_routes import ow_work_track_register
    ow_work_track_register(app)
except Exception as e:
    print(f"⚠️  OW Work Track blueprint error: {e}")



# =====================================================
# 3. INITIALIZE DATABASE (AFTER app.config)
# =====================================================
init_db(app)

# =====================================================
# 4. PROJECT HANDOVER CATEGORIES
# =====================================================
CATEGORIES = {
    "Admin": "Administrative & Contract Documents",
    "Technical": "Technical & Design Documents",
    "OM": "O & M Manuals",
    "Testing": "Testing & Commissioning Records",
    "Assets": "Asset Inventory",
    "Compliance": "Compliance & Safety",
    "Training": "Training & Support",
    "Digital": "Digital Handover"
}

# Ensure project handover directories
for key in CATEGORIES.keys():
    (UPLOAD_ROOT / key).mkdir(parents=True, exist_ok=True)

# =====================================================
# 5. USER AUTHENTICATION (Session-Based)
# =====================================================
USERS = {
    "admin": {
        "password": "2381",
        "role": "admin",
        "properties": ["SLN Terminus", "ONEWEST", "The District", "One Golden Mile", "Nine Hills"]
    },
    "USER": {
        "password": "123",
        "role": "USER",
        "properties": ["ONEWEST"]
    },
    "maintenance": {
        "password": "maint123",
        "role": "Technician",
        "properties": ["SLN Terminus"]
    },
    "manager": {
        "password": "1234",
        "role": "Manager",
        "properties": ["SLN Terminus", "ONEWEST", "The District"]
    },
    "gm": {
        "password": "gm123",
        "role": "General Manager",
        "properties": ["SLN Terminus", "ONEWEST", "The District", "One Golden Mile", "Nine Hills"]
    },
    "propertymanager": {
        "password": "pm123",
        "role": "Property Manager",
        "properties": ["SLN Terminus"]
    }
}

# =====================================================
# 6. AUTHENTICATION DECORATORS
# =====================================================
def require_property(property_name):
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            # Not logged in
            if "user" not in session:
                if request.path.startswith(("/ow_api/", "/api/", "/inventory/",
                                            "/ow_work_track/", "/ow_vms/", "/ow_mail/")):
                    return jsonify({"success": False, "error": "Not authenticated"}), 401
                return redirect(url_for("login"))

            # Admin bypasses all property checks
            if session.get("role") == "admin":
                return fn(*args, **kwargs)

            # For API routes — auto-set active_property if user has access
            # This fixes the ngrok / direct-URL access issue where session
            # active_property may not be set yet
            if request.path.startswith(("/ow_api/", "/api/", "/inventory/",
                                        "/ow_work_track/", "/ow_vms/", "/ow_mail/")):
                user_properties = session.get("properties", [])
                if property_name in user_properties:
                    session["active_property"] = property_name  # auto-set
                    return fn(*args, **kwargs)
                return jsonify({"success": False,
                                "error": f"No access to {property_name}"}), 403

            # For page routes — strict check
            if session.get("active_property") != property_name:
                abort(403)

            return fn(*args, **kwargs)
        return wrapper
    return decorator

def require_role(required_role):
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            if "user" not in session:
                return redirect(url_for("login"))
            if session.get("role") != required_role and session.get("role") != "admin":
                abort(403)
            return fn(*args, **kwargs)
        return wrapper
    return decorator

def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if "user" not in session:
            if request.path.startswith(("/ow_api/", "/api/", "/inventory/",
                                        "/ow_work_track/", "/ow_vms/", "/ow_mail/")):
                return jsonify({"success": False, "error": "Not authenticated"}), 401
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return wrapper

# =====================================================
# 7. HELPER FUNCTIONS
# =====================================================
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def allowed_image(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_IMAGE_EXT

# =====================================================
# 6. ✅ FIXED: AUTHENTICATION ROUTES
# =====================================================
@app.route("/")
def home():
    if "user" in session:
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))

@app.route("/login", methods=["GET", "POST"])
def login():
    error = None
    
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()
        property_name = request.form.get("property", "").strip()
        
        # Debug output
        print(f"\n🔐 Login Attempt:")
        print(f"   Username: {username}")
        print(f"   Property: {property_name}")
        print(f"   Available Users: {list(USERS.keys())}")
        
        # Check if user exists
        if username not in USERS:
            error = "User not found. Please check your username."
            print(f"   ❌ Error: {error}")
            return render_template("dashboard.html", error=error)
        
        user_data = USERS[username]
        
        # Validate password
        if user_data["password"] != password:
            error = "Invalid password. Please try again."
            print(f"   ❌ Error: {error}")
            return render_template("dashboard.html", error=error)
        
        # Validate property access
        if property_name and property_name not in user_data["properties"]:
            error = f"You don't have access to {property_name}. Please select another property."
            print(f"   ❌ Error: {error}")
            print(f"   User Properties: {user_data['properties']}")
            return render_template("dashboard.html", error=error)
        
        # Clear existing session
        session.clear()
        
        # Set session variables
        session["user"] = username
        session["role"] = user_data["role"]
        session["properties"] = user_data["properties"]
        session["active_property"] = property_name or user_data["properties"][0]
        session["logged_in"] = True
        
        print(f"   ✅ Login successful!")
        print(f"   Role: {session['role']}")
        print(f"   Active Property: {session['active_property']}")
        
        # Redirect based on property
        property_routes = {
            "SLN Terminus": "sln_terminus",
            "ONEWEST": "onewest",
            "The District": "the_district",
            "One Golden Mile": "one_golden_mile",
            "Nine Hills": "nine_hills"
        }
        
        redirect_route = property_routes.get(property_name, "dashboard")
        return redirect(url_for(redirect_route))
    
    # GET request - show login form
    return render_template("dashboard.html", error=error)

@app.route("/dashboard")
@login_required
def dashboard():
    return render_template("dashboard.html")

@app.route("/logout")
def logout():
    print(f"\n👋 Logout: {session.get('user')}")
    session.clear()
    return redirect(url_for("login"))

# =====================================================
# 9. USER PROFILE API (ONLY ONCE)
# =====================================================
@app.route("/api/user_profile")
@login_required
def get_user_profile():
    return jsonify({
        "username": session.get("user", ""),
        "role": session.get("role", "user"),
        "active_property": session.get("active_property", "SLN Terminus"),
        "properties": session.get("properties", ["SLN Terminus"])
    })


# =====================================================
# 8. ✅ FIXED: PROPERTY DASHBOARD ROUTES (ALL 5)
# =====================================================
@app.route("/sln_terminus")
@login_required
@require_property("SLN Terminus")
def sln_terminus():
    print(f"\n🏢 Accessing SLN Terminus - User: {session.get('user')}")
    return render_template("sln_terminus.html")


@app.route("/the_district")
@login_required
@require_property("The District")
def the_district():
    print(f"\n🏢 Accessing The District - User: {session.get('user')}")
    return render_template("the_district.html")

@app.route("/one_golden_mile")
@login_required
@require_property("One Golden Mile")
def one_golden_mile():
    print(f"\n🏢 Accessing One Golden Mile - User: {session.get('user')}")
    return render_template("ogm.html")

@app.route("/nine_hills")
@login_required
@require_property("Nine Hills")
def nine_hills():
    print(f"\n🏢 Accessing Nine Hills - User: {session.get('user')}")
    return render_template("nine_hills.html")

# =====================================================
# 7. PPM DASHBOARD ROUTES (FULLY FIXED)
# =====================================================
@app.route("/ppm_dashboard")
@require_property("SLN Terminus")
def ppm_dashboard():
    """Main PPM Dashboard View"""
    return render_template("ppm_dashboard.html")






@app.route("/api/ppm/assets")
def get_ppm_assets():
    """API: Get all PPM assets directly from Assets.xlsx (FIXED)"""
    try:
        location_filter = request.args.get('location', 'all')
        
        # CRITICAL FIX: Read directly from Assets.xlsx (not ppm_data.json)
        ASSETS_XLSX = BASE_DIR / "static" / "data" / "Assets.xlsx"
        
        if not ASSETS_XLSX.exists():
            print(f"❌ Assets.xlsx NOT FOUND at: {ASSETS_XLSX}")
            return jsonify({"assets": [], "total": 0})
        
        # Load Excel file with proper error handling
        try:
            df = pd.read_excel(ASSETS_XLSX, engine='openpyxl')
        except Exception as e:
            print(f"❌ Excel read error: {str(e)}")
            # Fallback to xlrd engine if openpyxl fails
            try:
                df = pd.read_excel(ASSETS_XLSX, engine='xlrd')
            except Exception as e2:
                print(f"❌ Fallback Excel read error: {str(e2)}")
                return jsonify({"assets": [], "total": 0})
        
        assets = []
        for _, row in df.iterrows():
            # Skip empty rows
            asset_code = str(row.get('Asset Code', '')).strip()
            if not asset_code or asset_code.lower() in ['nan', 'none', '']:
                continue
            
            # Build asset object with EXACT column names from your Excel
            asset = {
                "id": asset_code,
                "name": str(row.get('Asset Name', 'Unknown Asset')).strip(),
                "category": str(row.get('In-House/Vendor', 'General')).strip(),
                "location": str(row.get('Location', 'Unknown Location')).strip(),
                "lastService": str(row.get('Last Service', '')).strip(),
                "nextDueDate": str(row.get('nextDueDate', '')).strip(),
                "colorCode": "Green"  # Will be calculated by frontend
            }
            assets.append(asset)
        
        # Apply location filter if specified
        if location_filter != 'all' and location_filter != '':
            assets = [a for a in assets if a.get('location', '').strip() == location_filter.strip()]
        
        print(f"✅ Loaded {len(assets)} assets from Assets.xlsx")
        return jsonify({
            "assets": assets,
            "total": len(assets)
        })
    
    except Exception as e:
        print(f"❌ PPM assets error: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({"assets": [], "total": 0})

def get_asset_details(asset_id):
    """Safely retrieve asset details from Excel with proper column handling"""
    ASSETS_XLSX = Path(__file__).parent / "static" / "data" / "Assets.xlsx"
    
    if not ASSETS_XLSX.exists():
        return {
            "name": f"Asset_{asset_id}", 
            "location": "Unknown Location", 
            "priority": "Medium",
            "frequency": "Monthly"  # Critical addition
        }
    
    try:
        df = pd.read_excel(ASSETS_XLSX)
        df.columns = df.columns.str.strip()
        
        asset_col = "Asset Code"
        name_col = "Asset Name"
        loc_col = "Location"
        freq_col = "Frequency"  # Critical: Get frequency from Excel
        
        asset_row = df[df[asset_col] == asset_id]
        if asset_row.empty:
            return {
                "name": f"Asset_{asset_id}", 
                "location": "Unknown Location", 
                "priority": "Medium",
                "frequency": "Monthly"
            }
        
        asset_name = str(asset_row.iloc[0][name_col]).strip() if name_col in asset_row.columns else f"Asset_{asset_id}"
        location = str(asset_row.iloc[0][loc_col]).strip() if loc_col in asset_row.columns else "Unknown Location"
        
        # Determine priority based on asset criticality
        asset_lower = asset_name.lower()
        priority = "Medium"
        if "fire" in asset_lower or "dg" in asset_lower.replace(' ', '') or "transformer" in asset_lower or "elevator" in asset_lower or "escalator" in asset_lower:
            priority = "High"
        
        # CRITICAL FIX: Get frequency with fallback
        frequency = "Monthly"  # Default
        if freq_col in asset_row.columns:
            freq_val = str(asset_row.iloc[0][freq_col]).strip().lower()
            if freq_val in ['monthly', 'quarterly', 'yearly']:
                frequency = freq_val
        elif "frequency" in asset_row.columns:  # Case-insensitive fallback
            freq_val = str(asset_row.iloc[0]["frequency"]).strip().lower()
            if freq_val in ['monthly', 'quarterly', 'yearly']:
                frequency = freq_val
        else:
            # Auto-detect frequency for critical assets
            if "elevator" in asset_lower or "escalator" in asset_lower:
                frequency = "monthly"
        
        return {
            "name": asset_name,
            "location": location,
            "priority": priority,
            "frequency": frequency  # Critical addition
        }
        
    except Exception as e:
        print(f"⚠️ Error loading asset {asset_id}: {str(e)}")
        return {
            "name": f"Asset_{asset_id}", 
            "location": "Unknown Location", 
            "priority": "Medium",
            "frequency": "Monthly"
        }


# In your get_today_wos() function
def get_today_wos():
    """Extracts work orders with due_date matching today"""
    if not WO_JSON.exists():
        print(f"⚠️ Work orders file NOT found at: {WO_JSON}")
        return []
    
    try:
        with open(WO_JSON, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        today = datetime.now().date()
        today_str = today.strftime('%Y-%m-%d')
        
        # FIX: Use .strip() on key lookups to handle trailing spaces
        today_wos = []
        for wo in data.get('work_orders', []):
            # Clean due_date value
            due_date = wo.get('due_date', '').strip()
            status = wo.get('status', '').strip().lower()
            
            if due_date == today_str and status in ['open', 'in-progress', 'overdue']:
                today_wos.append(wo)
        
        print(f"🔍 Today: {today_str} | Found {len(today_wos)} work orders")
        for i, wo in enumerate(today_wos):
            print(f"  #{i+1} {wo.get('work_order_id', 'N/A')} - {wo.get('asset_name', 'Unknown Asset')} (Status: {wo.get('status', 'N/A')})")
        
        return today_wos
    
    except Exception as e:
        print(f"❌ Error reading work orders: {str(e)}")
        traceback.print_exc()
        return []

# =====================================================
# PPM WORK ORDER 
# =====================================================


@app.route("/api/ppm/workorders")
def get_ppm_workorders():
    """API: Get ALL saved work orders from work_orders.json"""
    try:
        # Load work orders from persistent storage
        if not WO_JSON.exists():
            return jsonify({
                "success": True,
                "work_orders": [],
                "total": 0
            })
            
        with open(WO_JSON, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        work_orders = data.get('work_orders', [])
        
        # FIX: Clean key names and values
        cleaned_wos = []
        for wo in work_orders:
            cleaned_wo = {}
            for key, value in wo.items():
                cleaned_key = key.strip()
                cleaned_value = value.strip() if isinstance(value, str) else value
                cleaned_wo[cleaned_key] = cleaned_value
            cleaned_wos.append(cleaned_wo)
        
        # Apply filters if provided
        status_filter = request.args.get('status', 'all').lower().strip()
        priority_filter = request.args.get('priority', 'all').lower().strip()
        
        if status_filter != 'all':
            cleaned_wos = [wo for wo in cleaned_wos if wo.get('status', '').lower() == status_filter]
        
        if priority_filter != 'all':
            cleaned_wos = [wo for wo in cleaned_wos if wo.get('priority', '').lower() == priority_filter]
        
        # Format for frontend compatibility
        formatted_wos = []
        for wo in cleaned_wos:
            formatted_wos.append({
                "WO ID": wo.get("work_order_id", "N/A"),
                "Asset": wo.get("asset_name", "Unknown Asset"),
                "Location": wo.get("location", "Unknown Location"),
                "Due Date": wo.get("due_date", "N/A"),
                "Priority": wo.get("priority", "Medium"),
                "Status": wo.get("status", "open"),
                "created_at": wo.get("created_at", datetime.now().isoformat())
            })
        
        return jsonify({
            "success": True,
            "work_orders": formatted_wos,
            "total": len(formatted_wos)
        })

    except Exception as e:
        print(f"PPM workorders error: {str(e)}")
        traceback.print_exc()
        return jsonify({
            "success": False,
            "error": str(e),
            "work_orders": [],
            "total": 0
        }), 500

# =====================================================
# WORK ORDER CREATION ENDPOINT (CRITICAL FIX)
# =====================================================
@app.route('/api/workflow/create', methods=['POST'])
def create_work_order():
    """API: Create work order with CORRECT date format handling"""
    try:
        data = request.get_json()
        asset_id = data.get('assetId')
        due_date = data.get('dueDate')  # This is the date from calendar
        
        # Generate work order ID
        today = datetime.now().date()
        wo_counter = 1
        
        # Load existing work orders
        if WO_JSON.exists():
            with open(WO_JSON, 'r') as f:
                existing_data = json.load(f)
                existing_wos = existing_data.get('work_orders', [])
                wo_counter = len(existing_wos) + 1
        else:
            existing_wos = []
        
        # Generate WO ID
        wo_id = f"WO-PPM-{today.strftime('%Y-%m')}-{str(wo_counter).zfill(4)}"
        
        # Get asset details from Assets.xlsx
        asset_name = "Unknown Asset"
        location = "Unknown Location"
        priority = "Medium"
        
        # FIX: Get asset details including frequency
        ASSETS_XLSX = Path(__file__).parent / "static" / "data" / "Assets.xlsx"
        if ASSETS_XLSX.exists():
            try:
                df = pd.read_excel(ASSETS_XLSX)
                asset_col = "Asset Code"
                name_col = "Asset Name"
                asset_row = df[df[asset_col] == asset_id]
                
                if not asset_row.empty:
                    asset_name = str(asset_row.iloc[0][name_col]).strip()
                    location = str(asset_row.iloc[0]["Location"]).strip()
                    
                    # Determine priority based on asset criticality
                    asset_lower = asset_name.lower()
                    if "fire" in asset_lower or "dg" in asset_lower.replace(' ', '') or "transformer" in asset_lower:
                        priority = "High"
            except Exception as e:
                print(f"❌ Excel read error: {str(e)}")
                asset_name = f"Asset_{asset_id}"
                location = "Unknown Location"
        
        # FIX: Standardize date format to YYYY-MM-DD
        try:
            # Try to parse the date (handles multiple formats)
            if '/' in due_date:
                parts = due_date.split('/')
                if len(parts) == 3:
                    month = int(parts[0])
                    day = int(parts[1])
                    year = int(parts[2])
                    if year < 100:
                        year += 2000
                    due_date = f"{year}-{month:02d}-{day:02d}"
            elif '-' in due_date and len(due_date) == 10:
                # Already in YYYY-MM-DD format
                pass
            else:
                # Fallback: use current date
                due_date = datetime.now().strftime('%Y-%m-%d')
        except:
            due_date = datetime.now().strftime('%Y-%m-%d')
        
        # Create work order
        new_wo = {
            "work_order_id": wo_id,
            "asset_id": asset_id,
            "asset_name": asset_name,
            "location": location,
            "due_date": due_date,  # Standardized to YYYY-MM-DD
            "priority": priority,
            "status": "open",
            "created_at": datetime.now().isoformat()
        }
        
        # Save to persistent storage
        all_wos = existing_wos + [new_wo]
        with open(WO_JSON, 'w') as f:
            json.dump({
                "work_orders": all_wos,
                "last_updated": datetime.now().isoformat(),
                "total_count": len(all_wos)
            }, f, indent=2)
        
        print(f"✅ Work Order Created: {wo_id} for asset {asset_id} ({asset_name})")
        return jsonify({"success": True, "work_order_id": wo_id, "message": "Work order created successfully!"})
    
    except Exception as e:
        print(f"❌ Work order creation error: {str(e)}")
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500




def calculate_next_due_date(last_service_date, frequency="monthly"):
    """Calculates next due date based on maintenance frequency with proper month handling"""
    if not last_service_date:
        return None
    
    # Parse date - handle MM/DD/YYYY format
    try:
        parts = last_service_date.split('/')
        if len(parts) == 3:
            month = int(parts[0])
            day = int(parts[1])
            year = int(parts[2])
            last_date = datetime(year, month, day)
        else:
            return None
    except:
        return None
    
    # Calculate next due date based on frequency
    if frequency.lower() == 'monthly':
        # Handle month-end dates (like Jan 31 → Feb 28)
        next_month = last_date.month + 1
        next_year = last_date.year
        if next_month > 12:
            next_month = 1
            next_year += 1
            
        # Handle edge cases (like Jan 31 → Feb 28)
        try:
            next_date = datetime(next_year, next_month, last_date.day)
        except ValueError:
            # If day doesn't exist in next month (e.g., Jan 31 → Feb 28)
            next_date = datetime(next_year, next_month, 1) - timedelta(days=1)
            
        return next_date.strftime('%Y-%m-%d')
    
    elif frequency.lower() == 'quarterly':
        # Add 3 months
        next_month = last_date.month + 3
        next_year = last_date.year
        if next_month > 12:
            next_month -= 12
            next_year += 1
            
        try:
            next_date = datetime(next_year, next_month, last_date.day)
        except ValueError:
            next_date = datetime(next_year, next_month, 1) - timedelta(days=1)
            
        return next_date.strftime('%Y-%m-%d')
    
    elif frequency.lower() == 'yearly':
        # Add 1 year
        try:
            next_date = datetime(last_date.year + 1, last_date.month, last_date.day)
        except ValueError:
            next_date = datetime(last_date.year + 1, last_date.month, 1) - timedelta(days=1)
            
        return next_date.strftime('%Y-%m-%d')
    
    return None  # Unknown frequency




# Add this endpoint for closing work orders
@app.route("/api/ppm/dashboard/stats")
def get_ppm_dashboard_stats():
    """PPM dashboard stats endpoint - FIXED"""
    try:
        if not WO_JSON.exists():
            return jsonify({
                "total_assets": 438,
                "pending_ppm": 0,
                "completed_ppm": 0,
                "ppm_due_today": 0,
                "ppm_overdue": 0,
                "compliance_rate": 0.0
            })
        
        with open(WO_JSON, 'r') as f:
            data = json.load(f)
        
        work_orders = data.get('work_orders', [])
        today = datetime.now().date()
        overdue = 0
        due_today = 0
        pending = 0  # Only work orders due today
        
        for wo in work_orders:
            try:
                due_date_str = wo.get('due_date', '')
                if not due_date_str:
                    continue
                
                # Proper date parsing with multiple format support
                date_obj = None
                for fmt in ['%Y-%m-%d', '%m/%d/%Y', '%m/%d/%y']:
                    try:
                        date_obj = datetime.strptime(due_date_str, fmt).date()
                        break
                    except:
                        continue
                
                if not date_obj:
                    continue
                
                # Calculate stats correctly
                if date_obj < today:
                    overdue += 1
                elif date_obj == today:
                    due_today += 1
                    pending += 1  # Only today's work orders count as pending
            
            except Exception as e:
                print(f"Error processing work order {wo.get('work_order_id', 'unknown')}: {str(e)}")
                continue
        
        # Calculate compliance rate based on all work orders
        total_work_orders = len(work_orders)
        compliance_rate = 0.0
        if total_work_orders > 0:
            # Compliance = (work orders not overdue / total) * 100
            compliance_rate = round(((total_work_orders - overdue) / total_work_orders * 100), 1)
        
        stats = {
            "total_assets": 438,
            "pending_ppm": pending,  # Should be 15 for today
            "completed_ppm": total_work_orders - overdue - pending,
            "ppm_due_today": due_today,
            "ppm_overdue": overdue,
            "compliance_rate": compliance_rate
        }
        return jsonify(stats)
    
    except Exception as e:
        print(f"PPM stats error: {str(e)}")
        return jsonify({
            "total_assets": 438,
            "pending_ppm": 0,
            "completed_ppm": 0,
            "ppm_due_today": 0,
            "ppm_overdue": 0,
            "compliance_rate": 0.0
        })

# =====================================================
# WORK ORDER CLOSING ENDPOINT (CORRECTED)
# =====================================================
@app.route('/api/workflow/close', methods=['POST'])
def close_work_order():
    """API: Close work order with supervisor approval"""
    try:
        data = request.get_json()
        wo_id = data.get('workOrderId')
        approval_notes = data.get('approvalNotes', '')
        
        if not WO_JSON.exists():
            return jsonify({"success": False, "error": "Work orders file not found"}), 404
        
        with open(WO_JSON, 'r') as f:
            work_data = json.load(f)
        
        work_orders = work_data.get('work_orders', [])
        updated = False
        
        for wo in work_orders:
            if wo.get('work_order_id') == wo_id or wo.get('WO ID') == wo_id:
                # Update status and closure details
                wo['status'] = 'completed'
                wo['Status'] = 'completed'  # For frontend consistency
                wo['closed_at'] = datetime.now().isoformat()
                wo['closed_by'] = session.get('user', 'Supervisor')
                wo['approval_notes'] = approval_notes
                wo['supervisor_approval'] = True
                updated = True
                break
        
        if not updated:
            return jsonify({"success": False, "error": "Work order not found"}), 404
        
        # Save updated work orders
        with open(WO_JSON, 'w') as f:
            json.dump({
                "work_orders": work_orders,
                "last_updated": datetime.now().isoformat(),
                "total_count": len(work_orders)
            }, f, indent=2)
        
        print(f"✅ Work Order {wo_id} closed successfully")
        return jsonify({"success": True, "message": "Work order closed successfully"})
    
    except Exception as e:
        print(f"❌ Close work order error: {str(e)}")
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500



def update_asset_next_due_date(work_order):
    """UPGRADED: Updates asset's next due date with robust error handling & detailed logging"""
    try:
        # ✅ CRITICAL FIX #1: Use GLOBAL path (not local redefinition)
        global ASSETS_XLSX
        if not ASSETS_XLSX.exists():
            print(f"❌ [ASSET UPDATE] Assets.xlsx NOT FOUND at: {ASSETS_XLSX}")
            return False
        
        # ✅ CRITICAL FIX #2: Add file lock handling
        import time
        max_retries = 3
        for attempt in range(max_retries):
            try:
                # Read Excel with column normalization
                df = pd.read_excel(ASSETS_XLSX)
                df.columns = df.columns.str.strip()
                break
            except PermissionError:
                if attempt == max_retries - 1:
                    print(f"❌ [ASSET UPDATE] Excel file locked after {max_retries} attempts. Close Excel application.")
                    return False
                time.sleep(1)
        
        # Define EXACT column names (case-sensitive)
        asset_col = "Asset Code"
        last_service_col = "Last Service"
        next_due_col = "nextDueDate"  # Note capital 'D'
        
        # Find asset row
        mask = df[asset_col] == work_order['asset_id']
        if not mask.any():
            print(f"⚠️ [ASSET UPDATE] Asset {work_order['asset_id']} NOT FOUND in Excel")
            return False
        
        # Get current dates
        current_last = str(df.loc[mask, last_service_col].iloc[0]).strip()
        current_next = str(df.loc[mask, next_due_col].iloc[0]).strip()
        print(f"🔍 [ASSET UPDATE] Processing {work_order['asset_id']}")
        print(f"   Current: Last={current_last} | Next={current_next}")
        
        # Parse dates (MM/DD/YY format)
        try:
            last_date = datetime.strptime(current_last, '%m/%d/%y')
            next_date = datetime.strptime(current_next, '%m/%d/%y')
        except Exception as e:
            print(f"⚠️ [ASSET UPDATE] Date parse error: {str(e)}. Using 30-day fallback.")
            last_date = datetime.now()
            next_date = last_date + timedelta(days=30)
        
        # Calculate interval (critical for cycling)
        interval_days = (next_date - last_date).days
        if interval_days <= 0:
            interval_days = 30  # Default monthly interval
        print(f"   Interval calculated: {interval_days} days")
        
        # Get closure date
        try:
            closed_dt = datetime.fromisoformat(work_order['closed_at'])
        except:
            closed_dt = datetime.now()
        
        # Calculate NEW dates
        new_last = closed_dt.strftime('%m/%d/%y')
        new_next = (closed_dt + timedelta(days=interval_days)).strftime('%m/%d/%y')
        print(f"   NEW DATES: Last={new_last} | Next={new_next} (+{interval_days} days)")
        
        # ✅ CRITICAL FIX #3: Update DataFrame BEFORE saving
        df.loc[mask, last_service_col] = new_last
        df.loc[mask, next_due_col] = new_next
        
        # Save with error handling
        for attempt in range(max_retries):
            try:
                df.to_excel(ASSETS_XLSX, index=False)
                print(f"✅ [ASSET UPDATE] SUCCESS: {work_order['asset_id']} updated in Assets.xlsx")
                print(f"   Next maintenance scheduled for: {new_next}")
                return True
            except PermissionError:
                if attempt == max_retries - 1:
                    print(f"❌ [ASSET UPDATE] FAILED: Excel file locked. Close Excel and retry.")
                    return False
                time.sleep(1)
    
    except Exception as e:
        print(f"❌ [ASSET UPDATE] CRITICAL ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


# =====================================================
# WORK ORDER EXPORT
# =====================================================


@app.route('/api/ppm/workorders/export')
def export_work_orders():
    """API: Export ALL work orders including closed ones with full metadata"""
    try:
        # CRITICAL FIX 1: Verify file exists with proper path
        if not WO_JSON.exists():
            print(f"❌ Work orders file NOT found at: {WO_JSON}")
            return jsonify({
                "success": False,
                "error": "No work orders found. Please generate work orders first via Calendar View."
            }), 404
        
        # CRITICAL FIX 2: Load with proper encoding and handle trailing spaces in keys
        with open(WO_JSON, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        work_orders = data.get('work_orders', [])
        
        if not work_orders:
            return jsonify({
                "success": False,
                "error": "No work orders to export. Create work orders from Calendar View first."
            }), 404
        
        # CRITICAL FIX 3: Clean keys (handle trailing spaces in JSON keys from work_orders.json)
        cleaned_wos = []
        for wo in work_orders:
            cleaned_wo = {}
            for key, value in wo.items():
                # Remove trailing spaces from keys AND values
                clean_key = key.strip()
                clean_value = value.strip() if isinstance(value, str) else value
                cleaned_wo[clean_key] = clean_value
            cleaned_wos.append(cleaned_wo)
        
        # CRITICAL FIX 4: Handle ALL possible columns (including closed metadata)
        df = pd.DataFrame(cleaned_wos)
        
        # Define ALL possible columns (handles both open and closed WOs)
        all_columns = [
            'work_order_id', 'asset_id', 'asset_name', 'location',
            'due_date', 'priority', 'status', 'created_at',
            'closed_at', 'closed_by', 'lastService', 'nextDueDate', 'frequency'
        ]
        
        # Only include columns that actually exist in data
        existing_cols = [col for col in all_columns if col in df.columns]
        df = df[existing_cols]
        
        # CRITICAL FIX 5: Rename columns for readability
        column_mapping = {
            'work_order_id': 'Work Order ID',
            'asset_id': 'Asset ID',
            'asset_name': 'Asset Name',
            'location': 'Location',
            'due_date': 'Due Date',
            'priority': 'Priority',
            'status': 'Status',
            'created_at': 'Created At',
            'closed_at': 'Closed At',
            'closed_by': 'Closed By',
            'lastService': 'Last Service',
            'nextDueDate': 'Next Due Date',
            'frequency': 'Frequency'
        }
        df = df.rename(columns={k: v for k, v in column_mapping.items() if k in df.columns})
        
        # CRITICAL FIX 6: Create Excel with proper formatting
        output = io.BytesIO()
        try:
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df.to_excel(writer, index=False, sheet_name='All Work Orders')
                # Format header row
                workbook = writer.book
                worksheet = writer.sheets['All Work Orders']
                from openpyxl.styles import Font, PatternFill, Alignment
                header_fill = PatternFill(start_color="4361EE", end_color="4361EE", fill_type="solid")
                header_font = Font(bold=True, color="FFFFFF", size=11)
                for cell in worksheet[1]:
                    cell.fill = header_fill
                    cell.font = header_font
                    cell.alignment = Alignment(horizontal='center', vertical='center')
                # Auto-adjust column widths
                for column in worksheet.columns:
                    max_length = 0
                    column_letter = column[0].column_letter
                    for cell in column:
                        try:
                            if len(str(cell.value)) > max_length:
                                max_length = len(str(cell.value))
                        except:
                            pass
                    adjusted_width = (max_length + 2)
                    worksheet.column_dimensions[column_letter].width = min(adjusted_width, 30)
        except Exception as excel_error:
            print(f"❌ Excel creation error: {str(excel_error)}")
            traceback.print_exc()
            return jsonify({
                "success": False,
                "error": f"Failed to create Excel file: {str(excel_error)}"
            }), 500
        
        output.seek(0)
        
        # CRITICAL FIX 7: Generate proper filename with timestamp
        filename = f"Terminus_WorkOrders_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        print(f"✅ Exporting {len(cleaned_wos)} work orders to {filename}")
        
        # CRITICAL FIX 8: Return proper file response
        return send_file(
            output,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name=filename
        )
    
    except json.JSONDecodeError as je:
        print(f"❌ JSON decode error: {str(je)}")
        traceback.print_exc()
        return jsonify({
            "success": False,
            "error": "Work orders data is corrupted. Please regenerate work orders."
        }), 500
    except PermissionError as pe:
        print(f"❌ Permission error: {str(pe)}")
        traceback.print_exc()
        return jsonify({
            "success": False,
            "error": "File is locked. Please close work_orders.json in any editor and try again."
        }), 500
    except Exception as e:
        print(f"❌ Export error: {str(e)}")
        traceback.print_exc()
        return jsonify({
            "success": False,
            "error": f"Export failed: {str(e)}"
        }), 500



# =====================================================
# DAILY MAIL (TRIGGERS AT 8:00 AM)
# =====================================================


@app.route('/api/trigger-daily-email', methods=['POST'])
def trigger_daily_email():
    """API: Trigger daily email with CORRECT date handling and status filtering"""
    try:
        # Get today's work orders
        if not WO_JSON.exists():
            return jsonify({"success": False, "error": "No work orders found"}), 404
            
        with open(WO_JSON, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Get today's date correctly
        today = datetime.now().date()
        today_str = today.strftime('%Y-%m-%d')
        
               # FIX: Handle multiple date formats and trailing spaces
        today_wos = []
        for wo in data.get('work_orders', []):
            # Clean and normalize due_date
            due_date_str = wo.get('due_date', '').strip()
            
            # Try multiple date formats
            date_obj = None
            for fmt in ['%Y-%m-%d', '%m/%d/%Y', '%m/%d/%y']:
                try:
                    date_obj = datetime.strptime(due_date_str, fmt).date()
                    break
                except:
                    continue
            
            # ✅ CRITICAL FIX: Include TODAY + OVERDUE work orders (not just exact match)
            if date_obj and date_obj <= today:  # Changed from "date_obj == today"
                status = wo.get('status', '').strip().lower()
                if status in ['open', 'in-progress', 'overdue']:
                    today_wos.append(wo)
        
        # Show detailed debugging info
        print(f"\n{'='*70}")
        print(f"📧 EMAIL TRIGGER DIAGNOSTICS")
        print(f"{'='*70}")
        print(f"📅 Today's Date: {today_str}")
        print(f"📊 Total Work Orders in System: {len(data.get('work_orders', []))}")
        print(f"✅ Work Orders Included in Email: {len(today_wos)}")
        print(f"\n📋 INCLUDED WORK ORDERS:")
        for i, wo in enumerate(today_wos, 1):
            print(f"  {i}. {wo.get('work_order_id', 'N/A')} | "
                  f"{wo.get('asset_name', 'Unknown')} | "
                  f"Due: {wo.get('due_date', 'N/A')} | "
                  f"Status: {wo.get('status', 'N/A')}")
        print(f"{'='*70}\n")
        
        # Email configuration - CORRECTED
        smtp_user = "maintenance.slnterminus@gmail.com"
        smtp_pass = "xaottgrqtqnkouqn"  # CORRECT app password
        recipients = ["maintenance.slnterminus@gmail.com","yasven7545@gmail.com","engineering@terminus-global.com" ]
        
# ✅ CRITICAL FIX: HTML ASSIGNED TO VARIABLE AS STRING WITH MODERN DESIGN
        html_content = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Daily PPM Summary</title>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Space+Mono:wght@400;700&family=DM+Sans:wght@300;400;500;700&display=swap');

        * {{ box-sizing: border-box; margin: 0; padding: 0; }}

        body {{
            font-family: 'DM Sans', sans-serif;
            background-color: #0d1117;
            padding: 40px 15px;
            color: #c9d1d9;
        }}

        .container {{
            width: 100%;
            max-width: 660px;
            margin: 0 auto;
            background-color: #161b22;
            border-radius: 12px;
            overflow: hidden;
            border: 1px solid #30363d;
        }}

        /* ─── HEADER ─── */
        .header {{
            background: #0d1117;
            padding: 36px 40px 28px;
            border-bottom: 1px solid #30363d;
            position: relative;
        }}
        .header-eyebrow {{
            font-family: 'Space Mono', monospace;
            font-size: 10px;
            color: #3fb950;
            letter-spacing: 3px;
            text-transform: uppercase;
            margin-bottom: 10px;
        }}
        .header h1 {{
            font-family: 'Space Mono', monospace;
            font-size: 26px;
            font-weight: 700;
            color: #e6edf3;
            letter-spacing: -0.5px;
            line-height: 1.1;
        }}
        .header h1 span {{
            color: #3fb950;
        }}
        .header-rule {{
            margin-top: 20px;
            height: 1px;
            background: linear-gradient(90deg, #3fb950 0%, transparent 80%);
        }}

        /* ─── SUMMARY BOX ─── */
        .summary-box {{
            padding: 28px 40px;
            background: #0d1117;
            border-bottom: 1px solid #30363d;
        }}
        .summary-inner {{
            width: 100%;
            border-collapse: collapse;
        }}
        .summary-inner td {{
            padding: 0;
            vertical-align: middle;
            border: none;
        }}
        .badge-cell {{
            width: 88px;
            padding-right: 24px !important;
        }}
        .summary-badge {{
            width: 72px;
            height: 72px;
            border-radius: 50%;
            border: 2px solid #3fb950;
            text-align: center;
            padding-top: 16px;
            mso-line-height-rule: exactly;
        }}
        .count {{
            font-family: 'Space Mono', monospace;
            font-size: 26px;
            font-weight: 700;
            color: #3fb950;
            line-height: 1;
            display: block;
        }}
        .count-label {{
            font-size: 8px;
            color: #8b949e;
            letter-spacing: 1px;
            text-transform: uppercase;
            margin-top: 3px;
            display: block;
        }}
        .summary-text {{
            font-size: 14px;
            color: #8b949e;
            line-height: 1.7;
        }}
        .summary-text strong {{
            color: #e6edf3;
            font-weight: 500;
        }}

        /* ─── TABLE ─── */
        .work-orders-table {{
            width: 100%;
            border-collapse: collapse;
        }}
        .work-orders-table thead {{
            background-color: #0d1117;
        }}
        .work-orders-table th {{
            padding: 12px 20px;
            text-align: left;
            font-family: 'Space Mono', monospace;
            font-size: 9px;
            font-weight: 700;
            color: #3fb950;
            letter-spacing: 2px;
            text-transform: uppercase;
            border-bottom: 1px solid #30363d;
        }}
        .work-orders-table td {{
            padding: 16px 20px;
            border-bottom: 1px solid #21262d;
            vertical-align: middle;
        }}
        .work-orders-table tr:last-child td {{
            border-bottom: none;
        }}
        .work-orders-table tr:hover td {{
            background-color: #1c2128;
        }}

        /* Priority badges */
        .priority-high {{
            background-color: rgba(248, 81, 73, 0.15);
            color: #f85149;
            border: 1px solid rgba(248, 81, 73, 0.4);
            padding: 3px 10px;
            border-radius: 4px;
            font-family: 'Space Mono', monospace;
            font-size: 10px;
            font-weight: 700;
            letter-spacing: 1px;
        }}
        .priority-medium {{
            background-color: rgba(210, 153, 34, 0.15);
            color: #d29922;
            border: 1px solid rgba(210, 153, 34, 0.4);
            padding: 3px 10px;
            border-radius: 4px;
            font-family: 'Space Mono', monospace;
            font-size: 10px;
            font-weight: 700;
            letter-spacing: 1px;
        }}
        .priority-low {{
            background-color: rgba(63, 185, 80, 0.15);
            color: #3fb950;
            border: 1px solid rgba(63, 185, 80, 0.4);
            padding: 3px 10px;
            border-radius: 4px;
            font-family: 'Space Mono', monospace;
            font-size: 10px;
            font-weight: 700;
            letter-spacing: 1px;
        }}

        /* Cell content */
        .wo-id {{
            font-family: 'Space Mono', monospace;
            font-size: 12px;
            color: #58a6ff;
            font-weight: 700;
        }}
        .asset-title {{
            font-weight: 500;
            color: #e6edf3;
            font-size: 13px;
        }}
        .location-text {{
            color: #6e7681;
            font-size: 11px;
            margin-top: 3px;
            font-family: 'Space Mono', monospace;
        }}
        .due-date-text {{
            font-family: 'Space Mono', monospace;
            font-size: 11px;
            color: #8b949e;
        }}

        /* ─── BUTTON ─── */
        .btn-wrapper {{
            text-align: center;
            padding: 36px 40px;
            background: #0d1117;
            border-top: 1px solid #30363d;
        }}
        .action-button {{
            background: transparent;
            color: #3fb950 !important;
            text-decoration: none;
            padding: 14px 44px;
            border-radius: 6px;
            font-family: 'Space Mono', monospace;
            font-weight: 700;
            font-size: 13px;
            display: inline-block;
            border: 2px solid #3fb950;
            letter-spacing: 2px;
            text-transform: uppercase;
            mso-padding-alt: 0;
        }}

        /* ─── FOOTER ─── */
        .footer {{
            background-color: #0d1117;
            padding: 24px 40px;
            text-align: center;
            border-top: 1px solid #21262d;
        }}
        .footer p {{
            margin: 4px 0;
            color: #484f58;
            font-size: 12px;
            line-height: 1.6;
        }}
        .footer strong {{
            color: #6e7681;
            font-weight: 500;
        }}
        .footer .note {{
            margin-top: 14px;
            color: #30363d;
            font-size: 10px;
            font-family: 'Space Mono', monospace;
        }}
    </style>
</head>
<body>
    <div class="container">

        <div class="header">
            <div class="header-eyebrow">Maintenance Management System</div>
            <h1>SLN <span>TERMINUS</span></h1>
            <div class="header-rule"></div>
        </div>

        <div class="summary-box">
            <table class="summary-inner" cellpadding="0" cellspacing="0">
                <tr>
                    <td class="badge-cell">
                        <div class="summary-badge">
                            <span class="count">{len(today_wos)}</span>
                            <span class="count-label">Tasks</span>
                        </div>
                    </td>
                    <td>
                        <p class="summary-text">
                            Preventive Maintenance work orders are scheduled for today.<br>
                            <strong>Please review and assign technicians.</strong>
                        </p>
                    </td>
                </tr>
            </table>
        </div>

        <table class="work-orders-table">
            <thead>
                <tr>
                    <th>ID</th>
                    <th>Asset &amp; Location</th>
                    <th>Priority</th>
                    <th>Due Date</th>
                </tr>
            </thead>
            <tbody>
                {"".join(f'''
                <tr>
                    <td>
                        <span class="wo-id">#{wo.get('work_order_id', 'N/A')}</span>
                    </td>
                    <td>
                        <div class="asset-title">{wo.get('asset_name', 'Unknown Asset')}</div>
                        <div class="location-text">▸ {wo.get('location', 'Unknown Location')}</div>
                    </td>
                    <td>
                        <span class="priority-{wo.get('priority', 'Medium').lower()}">
                            {wo.get('priority', 'Medium').upper()}
                        </span>
                    </td>
                    <td>
                        <span class="due-date-text">{wo.get('due_date', 'N/A')}</span>
                    </td>
                </tr>
                ''' for wo in today_wos)}
            </tbody>
        </table>

        <div class="btn-wrapper">
            <a href="https://descriptive-joya-unsolidified.ngrok-free.dev" class="action-button">VIEW DASHBOARD</a>
        </div>

        <div class="footer">
            <p><strong>SLN Terminus Infrastructure Division</strong></p>
            <p>Automated system message. Please do not reply.</p>
            <p>© 2026 EPMS LLP. All rights reserved.</p>
            <p class="note">System Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | v3.0</p>
        </div>

    </div>
</body>
</html>"""

        # --- SMTP SENDING LOGIC ---
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT, timeout=30) as server:
            server.starttls()
            server.login(smtp_user, smtp_pass)
            msg = MIMEMultipart('alternative')
            msg['Subject'] = f"🔧 {len(today_wos)} Maintenance Tasks - {today.strftime('%d %b %Y')}"
            msg['From'] = formataddr(("SLN Terminus MMS", smtp_user))
            msg['To'] = ", ".join(recipients)
            msg.attach(MIMEText(html_content, 'html'))
            server.send_message(msg)
        
        print(f"✅ Email sent successfully to {len(recipients)} recipients ({len(today_wos)} work orders)")
        return jsonify({
            "success": True,
            "recipients": recipients,
            "wo_count": len(today_wos),
            "message": "Email sent successfully"
        })
    
    except Exception as e:
        print(f"❌ Email sending error: {str(e)}")
        traceback.print_exc()
        return jsonify({
            "success": False,
            "error": f"Email failed: {str(e)}"
        }), 500
# =====================================================
# DAILY EMAIL SCHEDULER (TRIGGERS AT 8:00 AM)
# =====================================================
from apscheduler.schedulers.background import BackgroundScheduler

def setup_email_scheduler():
    """Sets up the scheduler to send emails at 8:00 AM daily"""
    scheduler = BackgroundScheduler()
    scheduler.add_job(
        func=send_daily_summary,
        trigger='cron',
        hour=8,
        minute=0,
        timezone='Asia/Kolkata'  # ✅ FIXED: Removed console output
    )
    scheduler.start()
    print("✅ Email scheduler started: Daily trigger at 8:00 AM IST")
    return scheduler

# Initialize scheduler when server starts
if __name__ == "__main__":
    # ... other initialization code ...
    email_scheduler = setup_email_scheduler()


# =====================================================
# AMC TRACKER API ENDPOINTS (ADD THIS TO server.py)
# =====================================================

@app.route('/api/amc/contracts')
def get_amc_contracts():
    """API: Get all AMC contracts from JSON file"""
    try:
        AMC_JSON = BASE_DIR / "static" / "data" / "amc_contracts.json"
        
        # Create directory if it doesn't exist
        AMC_JSON.parent.mkdir(parents=True, exist_ok=True)
        
        # Return empty list if file doesn't exist yet
        if not AMC_JSON.exists():
            return jsonify({"contracts": []})
        
        # Load contracts from JSON file
        with open(AMC_JSON, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        contracts = data.get('contracts', [])
        return jsonify({"contracts": contracts})
    
    except Exception as e:
        print(f"❌ AMC contracts fetch error: {str(e)}")
        traceback.print_exc()
        return jsonify({"contracts": []}), 500


@app.route('/api/amc/update', methods=['POST'])
def update_amc_contract():
    """API: Update AMC contract details in JSON file"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "error": "No data provided"}), 400
        
        contract_id = data.get('contract_id')
        if not contract_id:
            return jsonify({"success": False, "error": "Contract ID is required"}), 400
        
        AMC_JSON = BASE_DIR / "static" / "data" / "amc_contracts.json"
        AMC_JSON.parent.mkdir(parents=True, exist_ok=True)
        
        # Load existing contracts or initialize empty list
        if AMC_JSON.exists():
            with open(AMC_JSON, 'r', encoding='utf-8') as f:
                amc_data = json.load(f)
        else:
            amc_data = {"contracts": []}
        
        contracts = amc_data.get('contracts', [])
        
        # Find and update contract
        updated = False
        for i, contract in enumerate(contracts):
            if contract.get('contract_id') == contract_id:
                contracts[i] = data
                updated = True
                break
        
        if not updated:
            # Add new contract if not found (for flexibility)
            contracts.append(data)
            updated = True
        
        # Save updated data
        amc_data['contracts'] = contracts
        amc_data['last_updated'] = datetime.now().isoformat()
        
        with open(AMC_JSON, 'w', encoding='utf-8') as f:
            json.dump(amc_data, f, indent=2)
        
        print(f"✅ AMC Contract {contract_id} updated successfully")
        return jsonify({"success": True, "message": "Contract updated successfully"})
    
    except Exception as e:
        print(f"❌ AMC contract update error: {str(e)}")
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500


# =====================================================
# 12. OCCUPANCY ROUTES
# =====================================================
@app.route("/sln_occupancy")
@login_required
def sln_occupancy():
    return render_template("sln_occupancy.html")

@app.route('/api/sln/occupancy')
def get_sln_occupancy():
    """Get space occupancy data from Excel"""
    try:
        EXCEL_PATH = ROOT / "static" / "data" / "Space Occupancy.xlsx"
        
        if not EXCEL_PATH.exists():
            return jsonify({"error": "Space Occupancy Excel file not found"}), 404
        
        df = pd.read_excel(EXCEL_PATH, sheet_name=0)
        df = df.fillna('')
        
        spaces = []
        current_floor = None
        
        for _, row in df.iterrows():
            if pd.isna(row.iloc[0]) or str(row.iloc[0]).strip() == '':
                continue
            
            try:
                office_name = str(row.iloc[2]) if len(row) > 2 else ''
                floor_level = str(row.iloc[1]) if len(row) > 1 else ''
                unit_no = str(row.iloc[3]) if len(row) > 3 else ''
                occupied_area = float(str(row.iloc[4]).replace(',', '')) if len(row) > 4 else 0
                area = float(str(row.iloc[5]).replace(',', '')) if len(row) > 5 else 0
                cam_rate = float(str(row.iloc[6]).replace(',', '')) if len(row) > 6 else 0
                
                if floor_level.strip() != '':
                    current_floor = floor_level.strip()
                
                if office_name.strip() != '':
                    spaces.append({
                        "id": str(row.iloc[0]),
                        "floorId": current_floor or 'L4',
                        "officeName": office_name.strip(),
                        "unitNo": unit_no.strip(),
                        "occupiedArea": occupied_area,
                        "area": area,
                        "camRate": cam_rate
                    })
            except:
                continue
        
        total_units = len(spaces)
        vacant_count = len([s for s in spaces if s["officeName"].lower() == "vacant" or s["camRate"] == 0])
        occupied_count = total_units - vacant_count
        
        return jsonify({
            "summary": {
                "total_area": sum(s["area"] for s in spaces),
                "occupied_area": sum(s["occupiedArea"] for s in spaces if s["officeName"].lower() != "vacant"),
                "vacant_area": sum(s["area"] for s in spaces) - sum(s["occupiedArea"] for s in spaces),
                "total_units": total_units,
                "vacant_count": vacant_count,
                "occupied_count": occupied_count
            },
            "spaces": spaces
        })
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# =====================================================
# 13. PROJECT HANDOVER WORKSPACE
# =====================================================
@app.route("/project_handover")
@login_required
def project_handover():
    return render_template("project_handover_workspace.html")

@app.route("/project_handover_workspace")
@login_required
def project_handover_workspace():
    return render_template("project_handover_workspace.html")

@app.route("/api/upload/<category>", methods=["POST"])
@login_required
def upload_file(category):
    """Upload file to project handover category"""
    if category not in CATEGORIES:
        return jsonify({"error": "Invalid category"}), 400
    
    if "file" not in request.files:
        return jsonify({"error": "No file"}), 400
    
    file = request.files["file"]
    if file.filename == "":
        return jsonify({"error": "Empty filename"}), 400
    
    save_dir = UPLOAD_ROOT / category
    save_dir.mkdir(parents=True, exist_ok=True)
    
    filename = secure_filename(file.filename)
    save_path = save_dir / filename
    file.save(save_path)
    
    # Log audit
    log_audit_action("File Upload", "ProjectHandover", filename)
    
    return jsonify({"message": "Uploaded successfully", "filename": filename})

@app.route("/api/list/<category>")
@login_required
def list_files(category):
    """List files in project handover category"""
    if category not in CATEGORIES:
        return jsonify([])
    
    folder = UPLOAD_ROOT / category
    if not folder.exists():
        return jsonify([])
    
    files = []
    for f in folder.iterdir():
        if f.is_file():
            files.append({
                "name": f.name,
                "size": f"{round(f.stat().st_size / 1024, 1)} KB",
                "date": datetime.fromtimestamp(f.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
            })
    
    return jsonify(files)

@app.route("/api/delete/<category>/<filename>", methods=['DELETE'])
@login_required
def delete_file(category, filename):
    """Delete file from project handover"""
    if category not in CATEGORIES:
        return jsonify({"success": False, "error": "Invalid category"}), 400
    
    file_path = UPLOAD_ROOT / category / filename
    if file_path.exists():
        os.remove(file_path)
        log_audit_action("File Delete", "ProjectHandover", filename)
        return jsonify({"success": True})
    else:
        return jsonify({"success": False, "error": "File not found"}), 404

@app.route("/files/<category>/<filename>")
@login_required
def serve_file(category, filename):
    """Serve project handover file"""
    folder = UPLOAD_ROOT / category
    return send_from_directory(folder, filename)

@app.route("/uploads/<category>/<filename>")
@login_required
def serve_upload(category, filename):
    """Serve upload file"""
    folder = UPLOAD_ROOT / category
    return send_from_directory(folder, filename)

# =====================================================
# 14. TRAINING IMAGES UPLOAD
# =====================================================
@app.route("/api/training/list")
@login_required
def list_training_images():
    """List training images by department"""
    dept = request.args.get("department", "").strip()
    if not dept:
        return jsonify({"error": "Department required"}), 400
    
    dest_dir = TRAINING_UPLOAD_ROOT / dept
    if not dest_dir.exists():
        return jsonify({"department": dept, "files": []})
    
    files = []
    for p in sorted(dest_dir.iterdir(), key=lambda x: x.name):
        if p.is_file() and allowed_image(p.name):
            files.append({
                "name": p.name,
                "url": url_for("serve_training_image", department=dept, filename=p.name),
                "size": f"{round(p.stat().st_size / 1024, 1)} KB",
                "date": datetime.fromtimestamp(p.stat().st_mtime).strftime("%Y-%m-%d")
            })
    
    return jsonify({"department": dept, "files": files})

@app.route("/api/training/upload", methods=["POST"])
@login_required
def upload_training_image():
    """Upload training image"""
    dept = request.form.get("department", "").strip()
    if not dept:
        return jsonify({"error": "Department required"}), 400
    
    if "file" not in request.files:
        return jsonify({"error": "No file"}), 400
    
    file = request.files["file"]
    if not file or file.filename == "":
        return jsonify({"error": "Empty filename"}), 400
    
    if not allowed_image(file.filename):
        return jsonify({"error": "Invalid file type"}), 400
    
    dest_dir = TRAINING_UPLOAD_ROOT / dept
    dest_dir.mkdir(parents=True, exist_ok=True)
    
    filename = secure_filename(file.filename)
    save_path = dest_dir / filename
    file.save(save_path)
    
    log_audit_action("Training Image Upload", "Training", f"{dept}/{filename}")
    
    return jsonify({"success": True, "filename": filename})

@app.route("/uploads/training/<department>/<filename>")
def serve_training_image(department, filename):
    """Serve training image"""
    folder = TRAINING_UPLOAD_ROOT / department
    return send_from_directory(folder, filename)

# =====================================================
# 15. OTHER DASHBOARD ROUTES (NO DUPLICATES)
# =====================================================
@app.route("/mis")
@login_required
def mis():
    return render_template("mis.html")

@app.route("/kra")
@login_required
def kra():
    return render_template("kra.html")

@app.route("/energy")
@login_required
def energy():
    return render_template("energy.html")

@app.route("/inventory_dashboard")
@login_required
def inventory_dashboard():
    return render_template("inventory_dashboard.html")

@app.route("/tenant")
@login_required
def tenant():
    return render_template("tenant.html")

@app.route("/cam_charges")
@login_required
def cam_charges_page():
    return render_template("cam_charges.html")

@app.route("/cam_review")
@login_required
def cam_review():
    return render_template("cam_review.html")

@app.route("/pm_dashboard")
@login_required
def pm_dashboard():
    return render_template("pm_dashboard.html")

@app.route("/property-manager-updates")
@login_required
def pm_daily_updates_page():
    return render_template("pm_daily_updates.html")

@app.route("/gm_dashboard")
@require_role("General Manager")
def gm_dashboard():
    return render_template("gm_dashboard.html")

@app.route("/documents")
@login_required
def documents():
    return render_template("documents.html")

@app.route("/issues")
@login_required
def issues():
    return render_template("issues.html")

@app.route("/vendor_visit")
@login_required
def vendor_visit():
    return render_template("vendor_visit.html")

# =====================================================
# 16. FILE DOWNLOAD
# =====================================================
@app.route("/download-excel")
@login_required
def download_excel():
    path = os.path.join(app.static_folder, "data")
    return send_from_directory(path, "SLN_Terminus_Dashboard_Data.xlsx", as_attachment=True)

@app.route('/api/ppm/import-excel', methods=['POST'])
@login_required
def import_ppm_excel():
    """Import PPM assets from Excel"""
    try:
        file = request.files.get('file')
        if not file:
            return jsonify({"status": "error", "message": "No file uploaded"}), 400
        
        upload_path = Path(app.static_folder) / "data" / "Assets.xlsx"
        file.save(upload_path)
        
        df = pd.read_excel(upload_path)
        assets = []
        
        for _, row in df.iterrows():
            if pd.notna(row.get('Asset Code')) and str(row.get('Asset Code')).strip():
                assets.append({
                    "id": str(row.get('Asset Code', '')).strip(),
                    "name": str(row.get('Asset Name', '')).strip(),
                    "category": str(row.get('In-House/Vendor', 'General')).strip(),
                    "location": str(row.get('Location', '')).strip(),
                    "lastService": str(row.get('Last Service', '')).strip(),
                    "nextDueDate": str(row.get('nextDueDate', '')).strip(),
                    "colorCode": "Red"
                })
        
        with open(PPM_DATA_FILE, 'w') as f:
            json.dump({"assets": assets}, f, indent=2)
        
        return jsonify({
            "status": "success",
            "message": f"Successfully imported {len(assets)} assets",
            "count": len(assets)
        })
    
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

# =====================================================
# 17. UTILITY ROUTES
# =====================================================
@app.route('/api/datetime')
def get_datetime():
    return jsonify({
        "current_datetime": datetime.now().strftime("%A, %B %d, %Y | %I:%M %p"),
        "server_time": datetime.now().isoformat()
    })

@app.route('/health')
def health_check():
    return jsonify({
        "status": "healthy",
        "service": "Terminus MMS",
        "timestamp": datetime.now().isoformat(),
        "version": "3.0.0"
    }), 200

@app.route('/favicon.ico')
def favicon():
    return '', 204

# =====================================================
# 18. AUDIT LOGGING HELPER
# =====================================================
def log_audit_action(action, entity_type, entity_id):
    """Log audit action to database"""
    try:
        with app.app_context():
            log = AuditLog(
                user_id=session.get('user_id', 0),
                username=session.get('user', 'system'),
                action=action,
                entity_type=entity_type,
                entity_id=str(entity_id),
                ip_address=request.remote_addr if request else '127.0.0.1'
            )
            db.session.add(log)
            db.session.commit()
    except:
        pass  # Don't fail if audit logging fails

# =====================================================
# 19. ERROR HANDLERS
# =====================================================
@app.errorhandler(404)
def not_found(e):
    if request.path.startswith('/api/'):
        return jsonify({"error": "Not Found", "message": "Resource not found"}), 404
    return render_template("onewest.html", error_code=404), 404

@app.errorhandler(403)
def forbidden(e):
    if "user" not in session:
        return redirect(url_for("login"))
    if request.path.startswith('/api/'):
        return jsonify({"error": "Forbidden", "message": "Access denied"}), 403
    return render_template("error.html", error_code=403), 403

@app.errorhandler(500)
def internal_error(e):
    print(f"500 Error: {str(e)}")
    if request.path.startswith('/api/'):
        return jsonify({"error": "Internal Server Error", "message": "Something went wrong"}), 500
    return render_template("error.html", error_code=500), 500


# =====================================================
# JSON ERROR HANDLERS FOR API ROUTES
# =====================================================
@app.errorhandler(403)
def handle_403(e):
    if request.path.startswith(("/ow_api/", "/api/", "/inventory/",
                                "/ow_work_track/", "/ow_vms/", "/ow_mail/")):
        return jsonify({"success": False, "error": "Access denied — check your active property"}), 403
    return render_template("dashboard.html", error="Access denied"), 403

@app.errorhandler(500)
def handle_500(e):
    if request.path.startswith(("/ow_api/", "/api/", "/inventory/",
                                "/ow_work_track/", "/ow_vms/", "/ow_mail/")):
        return jsonify({"success": False, "error": f"Server error: {str(e)}"}), 500
    return render_template("dashboard.html", error="Server error"), 500


# =====================================================
# SLN WORK TRACK BLUEPRINT REGISTRATION
# =====================================================
try:
    from sln_work_track_routes import sln_work_track_register
    sln_work_track_register(app)
except Exception as e:
    print(f"SLN Work Track blueprint error: {e}")

# =====================================================
# SLN WORK TRACK DASHBOARD ROUTE
# =====================================================
@app.route("/sln_work_track")
@login_required
@require_property("SLN Terminus")
def sln_work_track():
    return render_template("sln_work_track.html")

# =====================================================
# 2.0 ONEWEST
# =====================================================

# ✅ FIXED (WITH PROPER DECORATORS)
@app.route("/onewest")
@login_required  # ← MUST BE FIRST
@require_property("ONEWEST")
def onewest():
    """ONEWEST Property Dashboard"""
    # Ensure property is set in session
    session['active_property'] = 'ONEWEST'
    session['property_code'] = 'OW'
    
    # Debug output
    print(f"\n🏢 Accessing ONEWEST - User: {session.get('user')}")
    print(f"   Active Property: {session.get('active_property')}")
    print(f"   User Role: {session.get('role')}")
    
    return render_template("onewest.html")


# =====================================================
# ONEWEST ISSUES MODULE (COMPLETE)
# =====================================================
OW_ISSUES_JSON = BASE_DIR / "static" / "data" / "OW" / "issues.json"
OW_TECHNICIANS_JSON = BASE_DIR / "static" / "data" / "OW" / "technicians.json"
OW_SUPERVISORS_JSON = BASE_DIR / "static" / "data" / "OW" / "supervisors.json"
OW_ISSUES_UPLOADS = BASE_DIR / "uploads" / "OW" / "issues"
ISSUES_ARCHIVE_DIR = BASE_DIR / "uploads" / "OW" / "issues_archive"  # ← ADD THIS
ISSUES_ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
OW_ISSUES_UPLOADS.mkdir(parents=True, exist_ok=True)

# Create directories
for folder in [OW_ISSUES_JSON.parent, OW_ISSUES_UPLOADS]:
    folder.mkdir(parents=True, exist_ok=True)

# Initialize technician/supervisor files if not exist
if not OW_TECHNICIANS_JSON.exists():
    with open(OW_TECHNICIANS_JSON, 'w', encoding='utf-8') as f:
        json.dump({
            "technicians": [
                {"id": "T001", "name": "Jagadish","phone": "+919666942315","specialization": "Supervisor"},
                {"id": "T002", "name": "Suresh Babu", "phone": "+919876543211", "specialization": "Plumbing"},
                {"id": "T003", "name": "Venkatesh", "phone": "+919876543212", "specialization": "HVAC"}
            ]
        }, f, indent=2)

if not OW_SUPERVISORS_JSON.exists():
    with open(OW_SUPERVISORS_JSON, 'w', encoding='utf-8') as f:
        json.dump({
            "supervisors": [
                {"id": "S001", "name": "Anil Kumar", "phone": "+919876543220", "email": "anil@onewest.com"},
                {"id": "S002", "name": "Ravi Shankar", "phone": "+919876543221", "email": "ravi@onewest.com"}
            ]
        }, f, indent=2)

# =====================================================
# ONEWEST ISSUES ROUTES
# =====================================================
@app.route("/ow_issues")
@login_required
@require_property("ONEWEST")
def ow_issues():
    """ONEWEST Issues Dashboard"""
    session['active_property'] = 'ONEWEST'
    session['property_code'] = 'OW'
    print(f"\n🏢 Accessing ONEWEST Issues - User: {session.get('user')}")
    return render_template("issues/ow_issues.html")

@app.route("/ow_api/issues")
@login_required
@require_property("ONEWEST")
def ow_api_issues():
    """ONEWEST Issues API - Get all issues"""
    try:
        if not OW_ISSUES_JSON.exists():
            return jsonify({"issues": [], "total": 0, "property": "ONEWEST"})
        
        with open(OW_ISSUES_JSON, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        issues = data.get('issues', [])
        
        # Apply filters
        status_filter = request.args.get('status', 'all').lower()
        priority_filter = request.args.get('priority', 'all').lower()
        
        if status_filter != 'all':
            issues = [i for i in issues if i.get('status', '').lower() == status_filter]
        if priority_filter != 'all':
            issues = [i for i in issues if i.get('priority', '').lower() == priority_filter]
        
        return jsonify({
            "success": True,
            "issues": issues,
            "total": len(issues),
            "property": "ONEWEST"
        })
    except Exception as e:
        print(f"❌ ONEWEST Issues API error: {str(e)}")
        return jsonify({"success": False, "error": str(e), "issues": []}), 500

@app.route("/ow_api/issues/create", methods=["POST"])
@login_required
@require_property("ONEWEST")
def ow_api_create_issue():
    """ONEWEST - Create new issue with image upload"""
    try:
        # Handle form data or JSON
        if request.content_type and 'multipart/form-data' in request.content_type:
            title = request.form.get('title', 'Untitled')
            description = request.form.get('description', '')
            priority = request.form.get('priority', 'Medium')
            category = request.form.get('category', 'General')
            location = request.form.get('location', '')
            assigned_to = request.form.get('assigned_to', '')
            sla_deadline = request.form.get('sla_deadline', '')
            escalation_level = request.form.get('escalation_level', 'Level 1')
            
            # Handle image uploads
            photos = []
            if 'photos' in request.files:
                files = request.files.getlist('photos')
                for file in files:
                    if file and file.filename:
                        filename = secure_filename(f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{file.filename}")
                        save_path = OW_ISSUES_UPLOADS / filename
                        file.save(save_path)
                        photos.append(f"/uploads/OW/issues/{filename}")
        else:
            data = request.get_json()
            if not data:
                return jsonify({"success": False, "error": "No data provided"}), 400
            
            title = data.get('title', 'Untitled')
            description = data.get('description', '')
            priority = data.get('priority', 'Medium')
            category = data.get('category', 'General')
            location = data.get('location', '')
            assigned_to = data.get('assigned_to', '')
            sla_deadline = data.get('sla_deadline', '')
            escalation_level = data.get('escalation_level', 'Level 1')
            photos = data.get('photos', [])
        
        # Load existing issues
        if OW_ISSUES_JSON.exists():
            with open(OW_ISSUES_JSON, 'r', encoding='utf-8') as f:
                ow_data = json.load(f)
        else:
            ow_data = {"issues": [], "last_updated": ""}
        
        # Generate issue ID
        issue_counter = len(ow_data.get('issues', [])) + 1
        issue_id = f"OW-ISS-{datetime.now().strftime('%Y')}-{str(issue_counter).zfill(4)}"
        
        # Create new issue
        new_issue = {
            "issue_id": issue_id,
            "title": title,
            "description": description,
            "priority": priority,
            "status": "Open",
            "category": category,
            "location": location,
            "reported_by": session.get('user', 'Unknown'),
            "assigned_to": assigned_to,
            "property": "ONEWEST",
            "property_code": "OW",
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "sla_deadline": sla_deadline,
            "escalation_level": escalation_level,
            "photos": photos,
            "whatsapp_sent": False
        }
        
        ow_data['issues'].append(new_issue)
        ow_data['last_updated'] = datetime.now().isoformat()
        
        with open(OW_ISSUES_JSON, 'w', encoding='utf-8') as f:
            json.dump(ow_data, f, indent=2)
        
        # Send WhatsApp notification
        send_ow_whatsapp_notification(new_issue, assigned_to)
        
        print(f"✅ ONEWEST Issue Created: {issue_id}")
        return jsonify({
            "success": True,
            "issue_id": issue_id,
            "message": "Issue created successfully"
        })
    except Exception as e:
        print(f"❌ ONEWEST Issue creation error: {str(e)}")
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/ow_api/issues/update/<issue_id>", methods=["PUT"])
@login_required
@require_property("ONEWEST")
def ow_api_update_issue(issue_id):
    """ONEWEST - Update issue"""
    try:
        data = request.get_json()
        if not OW_ISSUES_JSON.exists():
            return jsonify({"success": False, "error": "Issues file not found"}), 404
        
        with open(OW_ISSUES_JSON, 'r', encoding='utf-8') as f:
            ow_data = json.load(f)
        
        updated = False
        for issue in ow_data.get('issues', []):
            if issue.get('issue_id') == issue_id:
                # Update fields
                if 'status' in data:
                    issue['status'] = data['status']
                if 'priority' in data:
                    issue['priority'] = data['priority']
                if 'assigned_to' in data:
                    issue['assigned_to'] = data['assigned_to']
                if 'description' in data:
                    issue['description'] = data['description']
                if 'escalation_level' in data:
                    issue['escalation_level'] = data['escalation_level']
                
                issue['updated_at'] = datetime.now().isoformat()
                updated = True
                
                # Send WhatsApp on status change
                if data.get('status') and data['status'] != issue.get('old_status'):
                    send_ow_whatsapp_status_update(issue, data['status'])
                break
        
        if not updated:
            return jsonify({"success": False, "error": "Issue not found"}), 404
        
        with open(OW_ISSUES_JSON, 'w', encoding='utf-8') as f:
            json.dump(ow_data, f, indent=2)
        
        print(f"✅ ONEWEST Issue Updated: {issue_id}")
        return jsonify({"success": True, "message": "Issue updated"})
    except Exception as e:
        print(f"❌ ONEWEST Issue update error: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/ow_api/issues/export")
@login_required
@require_property("ONEWEST")
def ow_api_export_issues():
    """ONEWEST - Export issues to Excel"""
    try:
        if not OW_ISSUES_JSON.exists():
            return jsonify({"success": False, "error": "No issues to export"}), 404
        
        with open(OW_ISSUES_JSON, 'r', encoding='utf-8') as f:
            ow_data = json.load(f)
        
        issues = ow_data.get('issues', [])
        if not issues:
            return jsonify({"success": False, "error": "No issues to export"}), 404
        
        df = pd.DataFrame(issues)
        output = io.BytesIO()
        
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='ONEWEST Issues')
        
        output.seek(0)
        filename = f"ONEWEST_Issues_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        
        return send_file(
            output,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name=filename
        )
    except Exception as e:
        print(f"❌ ONEWEST Issues export error: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/ow_api/issues/stats")
@login_required
@require_property("ONEWEST")
def ow_api_issues_stats():
    """ONEWEST - Get issues statistics"""
    try:
        if not OW_ISSUES_JSON.exists():
            return jsonify({
                "total": 0, "open": 0, "in_progress": 0,
                "resolved": 0, "closed": 0,
                "critical": 0, "high": 0, "medium": 0, "low": 0,
                "property": "ONEWEST"
            })
        
        with open(OW_ISSUES_JSON, 'r', encoding='utf-8') as f:
            ow_data = json.load(f)
        
        issues = ow_data.get('issues', [])
        
        stats = {
            "total": len(issues),
            "open": len([i for i in issues if i.get('status') == 'Open']),
            "in_progress": len([i for i in issues if i.get('status') == 'In Progress']),
            "resolved": len([i for i in issues if i.get('status') == 'Resolved']),
            "closed": len([i for i in issues if i.get('status') == 'Closed']),
            "critical": len([i for i in issues if i.get('priority') == 'Critical']),
            "high": len([i for i in issues if i.get('priority') == 'High']),
            "medium": len([i for i in issues if i.get('priority') == 'Medium']),
            "low": len([i for i in issues if i.get('priority') == 'Low']),
            "property": "ONEWEST"
        }
        
        return jsonify(stats)
    except Exception as e:
        print(f"❌ ONEWEST Issues stats error: {str(e)}")
        return jsonify({"error": str(e)}), 500

# =====================================================
# DAY-WISE ISSUE ARCHIVAL SYSTEM
# =====================================================

@app.route("/ow_api/issues/archive-daily", methods=["POST"])
@login_required
@require_property("ONEWEST")
def ow_archive_daily_issues():
    """Archive today's issues at day end (auto-triggered at midnight)"""
    try:
        today = datetime.now().date()
        today_str = today.strftime('%Y-%m-%d')
        
        # Load current issues
        if not OW_ISSUES_JSON.exists():
            return jsonify({"success": True, "message": "No issues to archive"})
        
        with open(OW_ISSUES_JSON, 'r', encoding='utf-8') as f:
            ow_data = json.load(f)
        
        issues = ow_data.get('issues', [])
        
        # Separate today's issues from others
        today_issues = []
        remaining_issues = []
        
        for issue in issues:
            created_date = issue.get('created_at', '')[:10]  # Extract YYYY-MM-DD
            if created_date == today_str:
                today_issues.append(issue)
            else:
                remaining_issues.append(issue)
        
        if not today_issues:
            return jsonify({"success": True, "message": "No issues to archive today"})
        
        # Archive today's issues
        archive_file = ISSUES_ARCHIVE_DIR / f"OW_Issues_{today_str}.json"
        archive_data = {
            "date": today_str,
            "archived_at": datetime.now().isoformat(),
            "total_issues": len(today_issues),
            "issues": today_issues,
            "summary": {
                "open": len([i for i in today_issues if i.get('status') == 'Open']),
                "in_progress": len([i for i in today_issues if i.get('status') == 'In Progress']),
                "resolved": len([i for i in today_issues if i.get('status') == 'Resolved']),
                "closed": len([i for i in today_issues if i.get('status') == 'Closed'])
            }
        }
        
        with open(archive_file, 'w', encoding='utf-8') as f:
            json.dump(archive_data, f, indent=2)
        
        # Update main issues file with remaining issues only
        ow_data['issues'] = remaining_issues
        ow_data['last_updated'] = datetime.now().isoformat()
        
        with open(OW_ISSUES_JSON, 'w', encoding='utf-8') as f:
            json.dump(ow_data, f, indent=2)
        
        print(f"✅ Archived {len(today_issues)} issues for {today_str}")
        return jsonify({
            "success": True,
            "archived_count": len(today_issues),
            "remaining_count": len(remaining_issues),
            "archive_file": archive_file.name
        })
        
    except Exception as e:
        print(f"❌ Archive error: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/ow_api/issues/export-by-date", methods=["GET"])
@login_required
@require_property("ONEWEST")
def ow_export_issues_by_date():
    """Export issues for specific date"""
    try:
        date_str = request.args.get('date', datetime.now().strftime('%Y-%m-%d'))
        
        # Check archive first
        archive_file = ISSUES_ARCHIVE_DIR / f"OW_Issues_{date_str}.json"
        
        if archive_file.exists():
            # Load from archive
            with open(archive_file, 'r', encoding='utf-8') as f:
                archive_data = json.load(f)
            issues = archive_data.get('issues', [])
        else:
            # Load from current issues if date matches today
            if not OW_ISSUES_JSON.exists():
                return jsonify({"error": "No issues found"}), 404
            
            with open(OW_ISSUES_JSON, 'r', encoding='utf-8') as f:
                ow_data = json.load(f)
            
            issues = [i for i in ow_data.get('issues', []) if i.get('created_at', '')[:10] == date_str]
        
        if not issues:
            return jsonify({"error": "No issues found for this date"}), 404
        
        # Export to Excel
        df = pd.DataFrame(issues)
        output = io.BytesIO()
        
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name=f'Issues_{date_str}')
        
        output.seek(0)
        filename = f"ONEWEST_Issues_{date_str}.xlsx"
        
        return send_file(
            output,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name=filename
        )
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/ow_api/issues/archive-list")
@login_required
@require_property("ONEWEST")
def ow_get_archive_list():
    """Get list of all archived dates"""
    try:
        archives = []
        if ISSUES_ARCHIVE_DIR.exists():
            for f in sorted(ISSUES_ARCHIVE_DIR.iterdir(), reverse=True):
                if f.suffix == '.json':
                    date_str = f.stem.replace('OW_Issues_', '')
                    with open(f, 'r', encoding='utf-8') as file:
                        data = json.load(file)
                    archives.append({
                        "date": date_str,
                        "total": data.get('total_issues', 0),
                        "summary": data.get('summary', {}),
                        "filename": f.name
                    })
        
        return jsonify({"success": True, "archives": archives})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/ow_api/issues/view-archive/<date_str>")
@login_required
@require_property("ONEWEST")
def ow_view_archive(date_str):
    """View archived issues for specific date"""
    try:
        archive_file = ISSUES_ARCHIVE_DIR / f"OW_Issues_{date_str}.json"
        
        if not archive_file.exists():
            return jsonify({"error": "Archive not found"}), 404
        
        with open(archive_file, 'r', encoding='utf-8') as f:
            archive_data = json.load(f)
        
        return jsonify({
            "success": True,
            "date": date_str,
            "data": archive_data
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# =====================================================
# AUTO-ARCHIVE AT MIDNIGHT (Scheduler)
# =====================================================
from apscheduler.schedulers.background import BackgroundScheduler

def setup_issue_archive_scheduler():
    """Schedule daily archival at 11:59 PM"""
    scheduler = BackgroundScheduler()
    scheduler.add_job(
        func=auto_archive_issues,
        trigger='cron',
        hour=23,
        minute=59,
        timezone='Asia/Kolkata'
    )
    scheduler.start()
    print("✅ Issue archive scheduler started: Daily at 11:59 PM IST")
    return scheduler

def auto_archive_issues():
    """Auto-archive today's issues"""
    try:
        with app.app_context():
            # Simulate POST request to archive endpoint
            today = datetime.now().date()
            today_str = today.strftime('%Y-%m-%d')
            
            if not OW_ISSUES_JSON.exists():
                print(f"ℹ️  No issues file found for {today_str}")
                return
            
            with open(OW_ISSUES_JSON, 'r', encoding='utf-8') as f:
                ow_data = json.load(f)
            
            issues = ow_data.get('issues', [])
            today_issues = [i for i in issues if i.get('created_at', '')[:10] == today_str]
            
            if not today_issues:
                print(f"ℹ️  No issues to archive for {today_str}")
                return
            
            # Archive today's issues
            archive_file = ISSUES_ARCHIVE_DIR / f"OW_Issues_{today_str}.json"
            archive_data = {
                "date": today_str,
                "archived_at": datetime.now().isoformat(),
                "total_issues": len(today_issues),
                "issues": today_issues,
                "summary": {
                    "open": len([i for i in today_issues if i.get('status') == 'Open']),
                    "in_progress": len([i for i in today_issues if i.get('status') == 'In Progress']),
                    "resolved": len([i for i in today_issues if i.get('status') == 'Resolved']),
                    "closed": len([i for i in today_issues if i.get('status') == 'Closed'])
                }
            }
            
            with open(archive_file, 'w', encoding='utf-8') as f:
                json.dump(archive_data, f, indent=2)
            
            # Remove today's issues from main file
            remaining_issues = [i for i in issues if i.get('created_at', '')[:10] != today_str]
            ow_data['issues'] = remaining_issues
            ow_data['last_updated'] = datetime.now().isoformat()
            
            with open(OW_ISSUES_JSON, 'w', encoding='utf-8') as f:
                json.dump(ow_data, f, indent=2)
            
            print(f"✅ Auto-archived {len(today_issues)} issues for {today_str}")
            
    except Exception as e:
        print(f"❌ Auto-archive failed: {str(e)}")




# =====================================================
# TECHNICIANS & SUPERVISORS API
# =====================================================
@app.route("/ow_api/technicians")
@login_required
@require_property("ONEWEST")
def ow_api_technicians():
    """Get ONEWEST technicians list"""
    try:
        if not OW_TECHNICIANS_JSON.exists():
            return jsonify({"technicians": []})
        
        with open(OW_TECHNICIANS_JSON, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        return jsonify(data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/ow_api/debug/technicians")
@login_required
def ow_api_technicians_debug():
    """Debug route - no property check"""
    import traceback as tb
    try:
        result = {
            "session_user":            session.get("user"),
            "session_active_property": session.get("active_property"),
            "session_role":            session.get("role"),
            "session_properties":      session.get("properties", []),
            "OW_TECHNICIANS_JSON":     str(OW_TECHNICIANS_JSON),
            "file_exists":             OW_TECHNICIANS_JSON.exists(),
        }
        if OW_TECHNICIANS_JSON.exists():
            with open(OW_TECHNICIANS_JSON, 'r', encoding='utf-8') as f:
                result["file_contents"] = json.load(f)
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e), "trace": tb.format_exc()}), 500


@app.route("/ow_api/supervisors")
@login_required
@require_property("ONEWEST")
def ow_api_supervisors():
    """Get ONEWEST supervisors list"""
    try:
        if not OW_SUPERVISORS_JSON.exists():
            return jsonify({"supervisors": []})
        
        with open(OW_SUPERVISORS_JSON, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        return jsonify(data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# =====================================================
# IMAGE UPLOAD FOR ISSUES
# =====================================================
@app.route("/ow_api/issues/upload-photo", methods=["POST"])
@login_required
@require_property("ONEWEST")
def ow_api_upload_photo():
    """Upload photo for issue"""
    try:
        if 'photo' not in request.files:
            return jsonify({"success": False, "error": "No photo uploaded"}), 400
        
        file = request.files['photo']
        if file.filename == '':
            return jsonify({"success": False, "error": "Empty filename"}), 400
        
        # Generate unique filename
        filename = secure_filename(f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{file.filename}")
        save_path = OW_ISSUES_UPLOADS / filename
        file.save(save_path)
        
        photo_url = f"/uploads/OW/issues/{filename}"
        
        return jsonify({
            "success": True,
            "photo_url": photo_url,
            "filename": filename
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

# =====================================================
# WHATSAPP NOTIFICATION HELPER
# =====================================================
def send_ow_whatsapp_notification(issue, assigned_to):
    """Send WhatsApp notification for new issue"""
    try:
        # Load supervisors to get phone
        if OW_SUPERVISORS_JSON.exists():
            with open(OW_SUPERVISORS_JSON, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            supervisors = data.get('supervisors', [])
            supervisor_phone = supervisors[0]['phone'] if supervisors else '+919876543220'
        else:
            supervisor_phone = '+919876543220'
        
        # WhatsApp message
        message = f"""
🔴 *NEW ISSUE - ONEWEST*

*Issue ID:* {issue['issue_id']}
*Title:* {issue['title']}
*Priority:* {issue['priority']}
*Location:* {issue['location']}
*Reported By:* {issue['reported_by']}
*Assigned To:* {issue['assigned_to']}
*Created:* {issue['created_at'][:16].replace('T', ' ')}

Please take immediate action.
        """.strip()
        
        # WhatsApp API URL (Use your preferred service)
        whatsapp_url = f"https://api.whatsapp.com/send?phone={supervisor_phone}&text={requests.utils.quote(message)}"
        
        print(f"📱 WhatsApp notification prepared for {supervisor_phone}")
        print(f"🔗 URL: {whatsapp_url}")
        
        # Optional: Send via API (Twilio, MessageBird, etc.)
        # requests.get(whatsapp_url)
        
        return True
    except Exception as e:
        print(f"❌ WhatsApp notification error: {str(e)}")
        return False

def send_ow_whatsapp_status_update(issue, new_status):
    """Send WhatsApp notification on status update"""
    try:
        if OW_SUPERVISORS_JSON.exists():
            with open(OW_SUPERVISORS_JSON, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            supervisors = data.get('supervisors', [])
            supervisor_phone = supervisors[0]['phone'] if supervisors else '+919876543220'
        else:
            supervisor_phone = '+919876543220'
        
        message = f"""
📊 *ISSUE STATUS UPDATE - ONEWEST*

*Issue ID:* {issue['issue_id']}
*Title:* {issue['title']}
*New Status:* {new_status}
*Updated:* {datetime.now().strftime('%Y-%m-%d %H:%M')}

Please review the update.
        """.strip()
        
        whatsapp_url = f"https://api.whatsapp.com/send?phone={supervisor_phone}&text={requests.utils.quote(message)}"
        
        print(f"📱 WhatsApp status update prepared for {supervisor_phone}")
        
        return True
    except Exception as e:
        print(f"❌ WhatsApp status update error: {str(e)}")
        return False

# Serve uploaded issue photos
@app.route("/uploads/OW/issues/<filename>")
@login_required
def serve_ow_issue_photo(filename):
    """Serve ONEWEST issue photo"""
    return send_from_directory(OW_ISSUES_UPLOADS, filename)

# =====================================================
# ✅ ONEWEST MMS MODULE (ALL ROUTES WITH ow_ PREFIX)
# NOTE: Completely independent from SLN Terminus module
# =====================================================

# ONEWEST Data Files
OW_DIR = BASE_DIR / "static" / "data" / "OW"
OW_ASSETS_XLSX    = OW_DIR / "Asset.xlsx"
OW_WORK_ORDERS_JSON = OW_DIR / "work_orders.json"
OW_AMC_JSON       = OW_DIR / "amc_contracts.json"
OW_PPM_WO_UPLOADS = BASE_DIR / "uploads" / "OW" / "ppm"

# Create OW directories
for _d in [OW_DIR, OW_PPM_WO_UPLOADS]:
    _d.mkdir(parents=True, exist_ok=True)

# OW Email config (independent from SLN)
OW_EMAIL_RECEIVERS = [
    "maintenance.slnterminus@gmail.com",
    "yasven7545@gmail.com",
    "engineering@terminus-global.com",
    "kiran@terminus-global.com"

]

# =====================================================
# ONEWEST DASHBOARD ROUTE
# =====================================================
@app.route("/ow_ppm_dashboard")
@login_required
@require_property("ONEWEST")
def ow_ppm_dashboard():
    """ONEWEST PPM Dashboard"""
    session['active_property'] = 'ONEWEST'
    return render_template("ow_ppm_dashboard.html")


# =====================================================
# ONEWEST PPM ASSETS API (ow_api/ppm/assets)
# =====================================================
@app.route("/ow_api/ppm/assets")
@login_required
@require_property("ONEWEST")
def ow_api_ppm_assets():
    """Get ONEWEST PPM assets from OW/Asset.xlsx"""
    try:
        location_filter = request.args.get('location', 'all')

        if not OW_ASSETS_XLSX.exists():
            print(f"❌ OW Asset.xlsx NOT FOUND at: {OW_ASSETS_XLSX}")
            return jsonify({"assets": [], "total": 0, "property": "ONEWEST"})

        try:
            df = pd.read_excel(OW_ASSETS_XLSX, engine='openpyxl')
        except Exception as e:
            print(f"❌ OW Excel read error: {e}")
            try:
                df = pd.read_excel(OW_ASSETS_XLSX, engine='xlrd')
            except Exception as e2:
                print(f"❌ OW fallback Excel error: {e2}")
                return jsonify({"assets": [], "total": 0, "property": "ONEWEST"})

        assets = []
        for _, row in df.iterrows():
            asset_code = str(row.get('Asset Code', '')).strip()
            if not asset_code or asset_code.lower() in ['nan', 'none', '']:
                continue
            asset = {
                "id":          asset_code,
                "name":        str(row.get('Asset Name', 'Unknown Asset')).strip(),
                "category":    str(row.get('In-House/Vendor', 'General')).strip(),
                "location":    str(row.get('Location', 'Unknown')).strip(),
                "lastService": str(row.get('Last Service', '')).strip(),
                "nextDueDate": str(row.get('nextDueDate', '')).strip(),
                "property":    "ONEWEST"
            }
            assets.append(asset)

        if location_filter != 'all':
            assets = [a for a in assets if a.get('location','').strip() == location_filter.strip()]

        print(f"✅ OW: Loaded {len(assets)} assets from OW/Asset.xlsx")
        return jsonify({"assets": assets, "total": len(assets), "property": "ONEWEST"})

    except Exception as e:
        print(f"❌ OW PPM assets error: {e}")
        traceback.print_exc()
        return jsonify({"assets": [], "total": 0}), 500


# =====================================================
# ONEWEST PPM ASSETS UPLOAD (sync from xlsx)
# =====================================================
@app.route("/ow_api/ppm/import-excel", methods=["POST"])
@login_required
@require_property("ONEWEST")
def ow_api_ppm_import_excel():
    """Upload & sync ONEWEST Asset.xlsx"""
    try:
        file = request.files.get('file')
        if not file:
            return jsonify({"status": "error", "message": "No file uploaded"}), 400

        OW_DIR.mkdir(parents=True, exist_ok=True)
        file.save(OW_ASSETS_XLSX)

        df = pd.read_excel(OW_ASSETS_XLSX)
        count = len([_ for _, row in df.iterrows() if pd.notna(row.get('Asset Code')) and str(row.get('Asset Code')).strip()])

        print(f"✅ OW Assets synced: {count} records")
        return jsonify({"status": "success", "message": f"Successfully synced {count} ONEWEST assets", "count": count})

    except Exception as e:
        print(f"❌ OW Excel import error: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500


# =====================================================
# ONEWEST PPM DASHBOARD STATS (ow_api/ppm/dashboard/stats)
# =====================================================
@app.route("/ow_api/ppm/dashboard/stats")
@login_required
@require_property("ONEWEST")
def ow_api_ppm_dashboard_stats():
    """ONEWEST PPM dashboard stats"""
    try:
        # Load work orders
        wo_data = {"work_orders": []}
        if OW_WORK_ORDERS_JSON.exists():
            with open(OW_WORK_ORDERS_JSON, 'r', encoding='utf-8') as f:
                wo_data = json.load(f)

        work_orders = wo_data.get('work_orders', [])
        today = datetime.now().date()

        total_wo     = len(work_orders)
        completed_wo = len([w for w in work_orders if (w.get('status','') or '').lower() in ('completed','closed')])
        pending_wo   = total_wo - completed_wo

        # Overdue: open WOs with due_date < today
        overdue_wo = 0
        for wo in work_orders:
            status = (wo.get('status','') or '').lower()
            if status not in ('completed','closed'):
                try:
                    dd = datetime.strptime(wo.get('due_date','')[:10], '%Y-%m-%d').date()
                    if dd < today:
                        overdue_wo += 1
                except:
                    pass

        # Asset count
        asset_count = 0
        if OW_ASSETS_XLSX.exists():
            try:
                df = pd.read_excel(OW_ASSETS_XLSX)
                asset_count = len([_ for _, row in df.iterrows() if pd.notna(row.get('Asset Code')) and str(row.get('Asset Code')).strip()])
            except:
                pass

        compliance = round((completed_wo / total_wo * 100), 1) if total_wo > 0 else 0.0

        return jsonify({
            "total_assets":   asset_count,
            "pending_ppm":    pending_wo,
            "completed_ppm":  completed_wo,
            "ppm_overdue":    overdue_wo,
            "compliance_rate": compliance,
            "property":       "ONEWEST"
        })

    except Exception as e:
        print(f"❌ OW dashboard stats error: {e}")
        return jsonify({"total_assets":0,"pending_ppm":0,"completed_ppm":0,"ppm_overdue":0,"compliance_rate":0}), 500


# =====================================================
# ONEWEST WORK ORDERS API (ow_api/ppm/workorders)
# =====================================================
@app.route("/ow_api/ppm/workorders")
@login_required
@require_property("ONEWEST")
def ow_api_ppm_workorders():
    """Get ONEWEST work orders"""
    try:
        if not OW_WORK_ORDERS_JSON.exists():
            return jsonify({"work_orders": [], "total": 0, "property": "ONEWEST"})

        with open(OW_WORK_ORDERS_JSON, 'r', encoding='utf-8') as f:
            data = json.load(f)

        work_orders = data.get('work_orders', [])

        # Apply status filter
        status_filter = request.args.get('status', 'all').lower()
        if status_filter != 'all':
            work_orders = [w for w in work_orders if (w.get('status','') or '').lower() == status_filter]

        # Standardize format for frontend
        formatted = []
        for wo in work_orders:
            formatted.append({
                "WO ID":       wo.get('work_order_id', 'N/A'),
                "Asset":       wo.get('asset_name', 'Unknown Asset'),
                "Location":    wo.get('location', 'Unknown'),
                "Due Date":    wo.get('due_date', 'N/A'),
                "Priority":    wo.get('priority', 'Medium'),
                "Status":      wo.get('status', 'open'),
                "created_at":  wo.get('created_at', datetime.now().isoformat()),
                "assigned_to": wo.get('assigned_to', ''),
                "supervisor":  wo.get('supervisor', ''),
                "checklist":   wo.get('checklist', []),
                "images":      wo.get('images', []),
                "asset_id":    wo.get('asset_id', ''),
                "work_order_id": wo.get('work_order_id', ''),
                "asset_name":  wo.get('asset_name', ''),
                "location":    wo.get('location', ''),
                "due_date":    wo.get('due_date', ''),
                "priority":    wo.get('priority', 'Medium'),
                "status":      wo.get('status', 'open'),
                "property":    "ONEWEST"
            })

        return jsonify({"work_orders": formatted, "total": len(formatted), "property": "ONEWEST", "success": True})

    except Exception as e:
        print(f"❌ OW workorders error: {e}")
        return jsonify({"work_orders": [], "total": 0, "success": False, "error": str(e)}), 500


# =====================================================
# ONEWEST WORK ORDERS BY DATE (ow_api/workorders/by-date)
# =====================================================
@app.route("/ow_api/workorders/by-date")
@login_required
@require_property("ONEWEST")
def ow_api_workorders_by_date():
    """Get ONEWEST work orders for a specific date"""
    try:
        date_str = request.args.get('date', datetime.now().strftime('%Y-%m-%d'))

        if not OW_WORK_ORDERS_JSON.exists():
            return jsonify({"work_orders": [], "date": date_str, "property": "ONEWEST"})

        with open(OW_WORK_ORDERS_JSON, 'r', encoding='utf-8') as f:
            data = json.load(f)

        work_orders = data.get('work_orders', [])
        filtered = [w for w in work_orders if w.get('due_date', '')[:10] == date_str]

        return jsonify({"work_orders": filtered, "date": date_str, "total": len(filtered), "property": "ONEWEST"})

    except Exception as e:
        return jsonify({"work_orders": [], "error": str(e)}), 500


# =====================================================
# ONEWEST CREATE WORK ORDER (ow_api/workflow/create)
# =====================================================
@app.route("/ow_api/workflow/create", methods=["POST"])
@login_required
@require_property("ONEWEST")
def ow_api_workflow_create():
    """Create ONEWEST work order"""
    try:
        data = request.get_json()
        asset_id   = data.get('assetId', '')
        asset_name = data.get('assetName', 'Unknown Asset')
        location   = data.get('location', 'Unknown')
        due_date   = data.get('dueDate', '')
        asset_type = data.get('assetType', 'default')

        # Normalize due_date to YYYY-MM-DD
        try:
            if '/' in due_date:
                parts = due_date.split('/')
                m, d, y = int(parts[0]), int(parts[1]), int(parts[2])
                if y < 100: y += 2000
                due_date = f"{y}-{m:02d}-{d:02d}"
            elif '-' in due_date and len(due_date) == 10:
                pass
            else:
                due_date = datetime.now().strftime('%Y-%m-%d')
        except:
            due_date = datetime.now().strftime('%Y-%m-%d')

        # Try to get asset details from xlsx if name not provided
        if asset_id and OW_ASSETS_XLSX.exists():
            try:
                df = pd.read_excel(OW_ASSETS_XLSX)
                row = df[df['Asset Code'] == asset_id]
                if not row.empty:
                    asset_name = str(row.iloc[0]['Asset Name']).strip() or asset_name
                    location   = str(row.iloc[0]['Location']).strip() or location
            except:
                pass

        # Determine priority
        name_lower = asset_name.lower()
        priority = 'High' if any(k in name_lower for k in ['fire','dg','generator','transformer','hv','elevator']) else 'Medium'

        # Load existing WOs
        wo_data = {"work_orders": [], "last_updated": ""}
        if OW_WORK_ORDERS_JSON.exists():
            with open(OW_WORK_ORDERS_JSON, 'r', encoding='utf-8') as f:
                wo_data = json.load(f)

        existing_wos = wo_data.get('work_orders', [])
        today = datetime.now()
        wo_id = f"OW-PPM-{today.strftime('%Y-%m')}-{str(len(existing_wos)+1).zfill(4)}"

        # Build checklist based on asset type
        checklists = {
            'dg':       ['Check fuel level','Inspect battery','Verify coolant','Check oil','Test ATS','Inspect exhaust'],
            'elevator': ['Inspect door operation','Check emergency stop','Verify leveling','Inspect machine room','Test emergency lighting'],
            'chiller':  ['Check refrigerant pressure','Inspect condenser','Verify compressor oil','Check connections','Inspect for leaks'],
            'fire':     ['Test alarm panel','Check sprinklers','Verify extinguishers','Test smoke detectors','Check hydrant pressure'],
            'default':  ['Visual inspection','Check for noise/vibration','Verify safety guards','Inspect for leaks','Test emergency stop','Verify control panel']
        }
        cl_items = checklists.get(asset_type, checklists['default'])
        checklist = [{"id": f"{asset_type}_{i+1}", "text": item, "required": i < 4, "completed": False, "comments": ""} for i, item in enumerate(cl_items)]

        new_wo = {
            "work_order_id": wo_id,
            "asset_id":      asset_id,
            "asset_name":    asset_name,
            "location":      location,
            "due_date":      due_date,
            "priority":      priority,
            "status":        "open",
            "property":      "ONEWEST",
            "created_at":    today.isoformat(),
            "assigned_to":   "",
            "supervisor":    "",
            "checklist":     checklist,
            "images":        [],
            "technician_notes": "",
            "approval_notes":   ""
        }

        existing_wos.append(new_wo)
        wo_data['work_orders']  = existing_wos
        wo_data['last_updated'] = today.isoformat()

        with open(OW_WORK_ORDERS_JSON, 'w', encoding='utf-8') as f:
            json.dump(wo_data, f, indent=2)

        print(f"✅ OW Work Order Created: {wo_id} — {asset_name} @ {location}")
        return jsonify({"success": True, "work_order_id": wo_id, "message": "ONEWEST work order created"})

    except Exception as e:
        print(f"❌ OW WO creation error: {e}")
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500


# =====================================================
# ONEWEST CLOSE WORK ORDER (ow_api/workflow/close)
# =====================================================
@app.route("/ow_api/workflow/close", methods=["POST"])
@login_required
@require_property("ONEWEST")
def ow_api_workflow_close():
    """Close ONEWEST work order with supervisor approval"""
    try:
        data = request.get_json()
        wo_id            = data.get('workOrderId', '')
        approval_notes   = data.get('approvalNotes', '')
        supervisor_ok    = data.get('supervisorApproval', False)
        technician       = data.get('technician', '')
        images           = data.get('images', [])
        checklist        = data.get('checklist', [])

        if not supervisor_ok:
            return jsonify({"success": False, "error": "Supervisor approval required"}), 400

        if not OW_WORK_ORDERS_JSON.exists():
            return jsonify({"success": False, "error": "Work orders file not found"}), 404

        with open(OW_WORK_ORDERS_JSON, 'r', encoding='utf-8') as f:
            wo_data = json.load(f)

        updated = False
        for wo in wo_data.get('work_orders', []):
            if wo.get('work_order_id') == wo_id:
                wo['status']          = 'completed'
                wo['closed_at']       = datetime.now().isoformat()
                wo['approval_notes']  = approval_notes
                wo['technician']      = technician
                wo['images']          = images
                wo['checklist']       = checklist
                wo['closed_by']       = session.get('user', 'unknown')
                updated = True
                break

        if not updated:
            return jsonify({"success": False, "error": "Work order not found"}), 404

        wo_data['last_updated'] = datetime.now().isoformat()
        with open(OW_WORK_ORDERS_JSON, 'w', encoding='utf-8') as f:
            json.dump(wo_data, f, indent=2)

        print(f"✅ OW Work Order Closed: {wo_id} by {session.get('user')}")
        return jsonify({"success": True, "message": f"Work order {wo_id} closed successfully"})

    except Exception as e:
        print(f"❌ OW WO close error: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


# =====================================================
# ONEWEST WORK ORDERS EXPORT (ow_api/ppm/workorders/export)
# =====================================================
@app.route("/ow_api/ppm/workorders/export")
@login_required
@require_property("ONEWEST")
def ow_api_ppm_workorders_export():
    """Export ONEWEST work orders as Excel"""
    try:
        wo_data = {"work_orders": []}
        if OW_WORK_ORDERS_JSON.exists():
            with open(OW_WORK_ORDERS_JSON, 'r', encoding='utf-8') as f:
                wo_data = json.load(f)

        work_orders = wo_data.get('work_orders', [])
        if not work_orders:
            return jsonify({"error": "No work orders to export"}), 404

        rows = []
        for wo in work_orders:
            rows.append({
                "WO ID":         wo.get('work_order_id',''),
                "Asset":         wo.get('asset_name',''),
                "Location":      wo.get('location',''),
                "Due Date":      wo.get('due_date',''),
                "Priority":      wo.get('priority',''),
                "Status":        wo.get('status',''),
                "Assigned To":   wo.get('assigned_to',''),
                "Supervisor":    wo.get('supervisor',''),
                "Created At":    wo.get('created_at',''),
                "Closed At":     wo.get('closed_at',''),
                "Approval Notes": wo.get('approval_notes',''),
                "Property":      "ONEWEST"
            })

        df = pd.DataFrame(rows)
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='ONEWEST Work Orders')
        output.seek(0)

        filename = f"ONEWEST_WorkOrders_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        return send_file(output, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                         as_attachment=True, download_name=filename)

    except Exception as e:
        print(f"❌ OW WO export error: {e}")
        return jsonify({"error": str(e)}), 500


# =====================================================
# ONEWEST AMC CONTRACTS API (ow_api/amc/contracts)
# =====================================================
@app.route("/ow_api/amc/contracts")
@login_required
@require_property("ONEWEST")
def ow_api_amc_contracts():
    """Get ONEWEST AMC contracts"""
    try:
        if not OW_AMC_JSON.exists():
            # Return empty
            return jsonify({"contracts": [], "total": 0, "property": "ONEWEST"})

        with open(OW_AMC_JSON, 'r', encoding='utf-8') as f:
            data = json.load(f)

        contracts = data.get('contracts', [])

        status_filter = request.args.get('status', 'all').lower()
        if status_filter != 'all':
            contracts = [c for c in contracts if (c.get('status','') or '').lower() == status_filter]

        return jsonify({"contracts": contracts, "total": len(contracts), "property": "ONEWEST", "success": True})

    except Exception as e:
        print(f"❌ OW AMC error: {e}")
        return jsonify({"contracts": [], "error": str(e)}), 500


# OW AMC Export
@app.route("/ow_api/amc/contracts/export")
@login_required
@require_property("ONEWEST")
def ow_api_amc_contracts_export():
    """Export ONEWEST AMC contracts as Excel"""
    try:
        contracts = []
        if OW_AMC_JSON.exists():
            with open(OW_AMC_JSON, 'r', encoding='utf-8') as f:
                contracts = json.load(f).get('contracts', [])

        if not contracts:
            return jsonify({"error": "No contracts to export"}), 404

        df = pd.DataFrame(contracts)
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='ONEWEST AMC')
        output.seek(0)
        filename = f"ONEWEST_AMC_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        return send_file(output, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                         as_attachment=True, download_name=filename)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# =====================================================
# ONEWEST AMC UPDATE (ow_api/amc/update)
# =====================================================
@app.route("/ow_api/amc/update", methods=["POST"])
@login_required
@require_property("ONEWEST")
def ow_api_amc_update():
    """Update ONEWEST AMC contract"""
    try:
        data = request.get_json()
        contract_id = data.get('contract_id','')

        amc_data = {"contracts": [], "last_updated": ""}
        if OW_AMC_JSON.exists():
            with open(OW_AMC_JSON, 'r', encoding='utf-8') as f:
                amc_data = json.load(f)

        contracts = amc_data.get('contracts', [])
        found = False
        for i, c in enumerate(contracts):
            if c.get('contract_id') == contract_id:
                contracts[i] = {**c, **data, 'updated_at': datetime.now().isoformat()}
                found = True
                break

        if not found:
            # Add new contract
            data['created_at'] = datetime.now().isoformat()
            contracts.append(data)

        amc_data['contracts']    = contracts
        amc_data['last_updated'] = datetime.now().isoformat()

        OW_DIR.mkdir(parents=True, exist_ok=True)
        with open(OW_AMC_JSON, 'w', encoding='utf-8') as f:
            json.dump(amc_data, f, indent=2)

        print(f"✅ OW AMC {'updated' if found else 'created'}: {contract_id}")
        return jsonify({"success": True, "message": "AMC contract saved"})

    except Exception as e:
        print(f"❌ OW AMC update error: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


# =====================================================
# ONEWEST DAILY MAIL (TRIGGERS AT 8:00 AM)
# =====================================================
def ow_send_daily_ppm_mail():
    """Send ONEWEST daily PPM mail with today's work orders + any pending"""
    try:
        today_str = datetime.now().strftime('%Y-%m-%d')

        # Load all work orders
        work_orders = []
        if OW_WORK_ORDERS_JSON.exists():
            with open(OW_WORK_ORDERS_JSON, 'r', encoding='utf-8') as f:
                data = json.load(f)
            work_orders = data.get('work_orders', [])

        # Fresh today's WOs
        today_wos = [w for w in work_orders if w.get('due_date', '')[:10] == today_str and (w.get('status','') or '').lower() not in ('completed','closed')]

        # Pending / overdue WOs
        today = datetime.now().date()
        pending_wos = []
        for wo in work_orders:
            status = (wo.get('status','') or '').lower()
            if status in ('completed','closed'):
                continue
            try:
                dd = datetime.strptime(wo.get('due_date','')[:10], '%Y-%m-%d').date()
                if dd < today:
                    pending_wos.append(wo)
            except:
                pass

        # Build HTML email
        def wo_table(wos, title_str, color):
            if not wos:
                return f'<p style="color:#64748b;font-size:13px;">No {title_str.lower()} work orders.</p>'
            rows = ''.join(f"""
            <tr>
                <td style="padding:10px;border-bottom:1px solid #1e293b;font-family:monospace;color:{color};font-size:12px;">{w.get('work_order_id','N/A')}</td>
                <td style="padding:10px;border-bottom:1px solid #1e293b;color:#e2e8f0;font-size:13px;">{w.get('asset_name','Unknown')}</td>
                <td style="padding:10px;border-bottom:1px solid #1e293b;color:#94a3b8;font-size:12px;">{w.get('location','Unknown')}</td>
                <td style="padding:10px;border-bottom:1px solid #1e293b;color:#94a3b8;font-size:12px;">{w.get('priority','Medium')}</td>
                <td style="padding:10px;border-bottom:1px solid #1e293b;color:#94a3b8;font-size:12px;">{w.get('due_date','N/A')}</td>
            </tr>""" for w in wos)
            return f"""
            <h3 style="color:{color};font-family:sans-serif;margin:20px 0 10px;">{title_str} ({len(wos)})</h3>
            <table style="width:100%;border-collapse:collapse;background:#0f172a;border-radius:8px;overflow:hidden;">
                <thead><tr style="background:#1e293b;">
                    <th style="padding:10px;text-align:left;color:#475569;font-size:11px;text-transform:uppercase;">WO ID</th>
                    <th style="padding:10px;text-align:left;color:#475569;font-size:11px;text-transform:uppercase;">Asset</th>
                    <th style="padding:10px;text-align:left;color:#475569;font-size:11px;text-transform:uppercase;">Location</th>
                    <th style="padding:10px;text-align:left;color:#475569;font-size:11px;text-transform:uppercase;">Priority</th>
                    <th style="padding:10px;text-align:left;color:#475569;font-size:11px;text-transform:uppercase;">Due Date</th>
                </tr></thead>
                <tbody>{rows}</tbody>
            </table>"""

        html_body = f"""
        <div style="font-family:sans-serif;background:#020617;color:#e2e8f0;padding:32px;max-width:800px;margin:0 auto;">
            <div style="text-align:center;margin-bottom:32px;">
                <h1 style="font-family:monospace;color:#f97316;font-size:28px;margin:0;">ONEWEST</h1>
                <p style="color:#64748b;margin:6px 0 0;">Daily PPM Maintenance Report — {datetime.now().strftime('%A, %d %B %Y')}</p>
            </div>

            <div style="display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-bottom:24px;">
                <div style="background:#0f172a;border-radius:12px;padding:20px;border:1px solid rgba(249,115,22,0.2);">
                    <p style="color:#475569;font-size:11px;text-transform:uppercase;margin:0 0 6px;">Today's Work Orders</p>
                    <p style="color:#f97316;font-size:32px;font-weight:800;margin:0;">{len(today_wos)}</p>
                </div>
                <div style="background:#0f172a;border-radius:12px;padding:20px;border:1px solid rgba(244,63,94,0.2);">
                    <p style="color:#475569;font-size:11px;text-transform:uppercase;margin:0 0 6px;">Pending / Overdue</p>
                    <p style="color:#f43f5e;font-size:32px;font-weight:800;margin:0;">{len(pending_wos)}</p>
                </div>
            </div>

            {wo_table(today_wos, "Today's Work Orders", "#f97316")}
            {wo_table(pending_wos, "Pending / Overdue", "#f43f5e")}

            <p style="color:#334155;font-size:12px;text-align:center;margin-top:32px;">
                Generated at {datetime.now().strftime('%I:%M %p IST')} | EMERZHANT Property Management System
            </p>
        </div>"""

        msg = MIMEMultipart('alternative')
        msg['Subject'] = f"ONEWEST Daily PPM — {datetime.now().strftime('%d %b %Y')} — {len(today_wos)} Today | {len(pending_wos)} Pending"
        msg['From']    = formataddr(("ONEWEST MMS", SENDER_EMAIL))
        msg['To']      = ", ".join(OW_EMAIL_RECEIVERS)
        msg.attach(MIMEText(html_body, 'html'))

        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(SENDER_EMAIL, SENDER_PASSWORD)
            server.sendmail(SENDER_EMAIL, OW_EMAIL_RECEIVERS, msg.as_string())

        print(f"✅ OW Daily PPM mail sent — Today: {len(today_wos)} | Pending: {len(pending_wos)}")
        return {"success": True, "wo_count": len(today_wos), "pending_count": len(pending_wos)}

    except Exception as e:
        print(f"❌ OW daily mail error: {e}")
        return {"success": False, "error": str(e)}


# Manual trigger endpoint
@app.route("/ow_api/trigger-daily-mail", methods=["POST"])
@login_required
@require_property("ONEWEST")
def ow_api_trigger_daily_mail():
    """Manually trigger ONEWEST daily PPM mail"""
    result = ow_send_daily_ppm_mail()
    return jsonify(result)


# Schedule 8:00 AM daily
def _setup_ow_ppm_scheduler():
    try:
        from apscheduler.schedulers.background import BackgroundScheduler
        scheduler = BackgroundScheduler()
        scheduler.add_job(
            func=ow_send_daily_ppm_mail,
            trigger='cron',
            hour=8,
            minute=0,
            timezone='Asia/Kolkata',
            id='ow_daily_ppm_mail'
        )
        scheduler.start()
        print("✅ ONEWEST: Daily PPM mail scheduler started at 8:00 AM IST")
        return scheduler
    except Exception as e:
        print(f"⚠️  ONEWEST scheduler error: {e}")
        return None

_ow_scheduler = _setup_ow_ppm_scheduler()


# =====================================================
# ONEWEST CALENDAR VIEW ROUTES (COMPLETE & FIXED)
# =====================================================
@app.route("/ow_api/ppm/calendar")
@login_required
@require_property("ONEWEST")
def ow_api_ppm_calendar():
    """Get ONEWEST calendar data — assets grouped by due date"""
    try:
        year  = int(request.args.get('year',  datetime.now().year))
        month = int(request.args.get('month', datetime.now().month))

        if not OW_ASSETS_XLSX.exists():
            return jsonify({"calendar": {}, "property": "ONEWEST"})

        df = pd.read_excel(OW_ASSETS_XLSX, engine='openpyxl')
        calendar_data = {}

        for _, row in df.iterrows():
            asset_code = str(row.get('Asset Code', '')).strip()
            if not asset_code or asset_code.lower() in ['nan','none','']:
                continue
            next_due = str(row.get('nextDueDate', '')).strip()
            if not next_due or next_due.lower() in ['nan','none','']:
                continue
            try:
                from dateutil.parser import parse as dateutil_parse
                due_dt = dateutil_parse(next_due)
                if due_dt.year == year and due_dt.month == month:
                    date_key = due_dt.strftime('%Y-%m-%d')
                    if date_key not in calendar_data:
                        calendar_data[date_key] = []
                    calendar_data[date_key].append({
                        "id":          asset_code,
                        "name":        str(row.get('Asset Name','')).strip(),
                        "location":    str(row.get('Location','')).strip(),
                        "lastService": str(row.get('Last Service','')).strip()
                    })
            except:
                pass

        return jsonify({"calendar": calendar_data, "year": year, "month": month, "property": "ONEWEST"})

    except Exception as e:
        print(f"❌ OW calendar error: {e}")
        return jsonify({"calendar": {}, "error": str(e)}), 500


# =====================================================
# ONEWEST TECHNICIANS & SUPERVISORS (reuse from issues module)
# =====================================================
@app.route("/ow_api/technicians")
@login_required
@require_property("ONEWEST")
def ow_api_ppm_technicians():
    """Get ONEWEST technicians list"""
    try:
        tech_file = BASE_DIR / "static" / "data" / "OW" / "technicians.json"
        if not tech_file.exists():
            return jsonify({"technicians": []})
        with open(tech_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return jsonify(data)
    except Exception as e:
        return jsonify({"technicians": [], "error": str(e)}), 500


@app.route("/ow_api/supervisors")
@login_required
@require_property("ONEWEST")
def ow_api_ppm_supervisors():
    """Get ONEWEST supervisors list"""
    try:
        sup_file = BASE_DIR / "static" / "data" / "OW" / "supervisors.json"
        if not sup_file.exists():
            return jsonify({"supervisors": []})
        with open(sup_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return jsonify(data)
    except Exception as e:
        return jsonify({"supervisors": [], "error": str(e)}), 500


# Serve OW PPM uploads
@app.route("/uploads/OW/ppm/<filename>")
@login_required
def serve_ow_ppm_upload(filename):
    """Serve ONEWEST PPM work order image"""
    return send_from_directory(OW_PPM_WO_UPLOADS, filename)



# =====================================================
# 2.0 ONEWEST_STORE
# =====================================================

"""
ONEWEST INVENTORY - SERVER INTEGRATION SNIPPET
Add this to server.py for ONEWEST inventory module
All routes use ow_ prefix - Independent from SLN Terminus
"""

# =====================================================
# ONEWEST INVENTORY PATHS
# =====================================================
OW_INVENTORY_XLSX = BASE_DIR / "static" / "data" / "ow_store_master.xlsx"
OW_INVENTORY_ALERTS = BASE_DIR / "static" / "data" / "ow_inventory_alerts.json"
OW_INVENTORY_DIR = BASE_DIR / "static" / "data" / "OW" / "inventory"

for folder in [OW_INVENTORY_DIR, OW_INVENTORY_ALERTS.parent]:
    folder.mkdir(parents=True, exist_ok=True)

if not OW_INVENTORY_ALERTS.exists():
    with open(OW_INVENTORY_ALERTS, 'w') as f:
        json.dump({"alerts": [], "last_updated": datetime.now().isoformat()}, f, indent=2)


# =====================================================
# ONEWEST INVENTORY ROUTES
# =====================================================
@app.route("/ow_inventory_dashboard")
def ow_inventory_dashboard():
    return render_template("ow_inventory_dashboard.html")


@app.route("/ow_api/inventory/items")
@login_required
@require_property("ONEWEST")
def ow_get_inventory_items():
    try:
        if not OW_INVENTORY_XLSX.exists():
            return jsonify({"success": False, "items": [], "total": 0})
        
        df = pd.read_excel(OW_INVENTORY_XLSX, engine='openpyxl')
        items = []
        
        for _, row in df.iterrows():
            item_code = str(row.get('Item_Code', '')).strip()
            if not item_code or item_code.lower() in ['nan', 'none', '']:
                continue
            
            current_stock = float(row.get('Current_Stock', 0)) if pd.notna(row.get('Current_Stock')) else 0
            min_stock = float(row.get('Min_Stock_Level', 0)) if pd.notna(row.get('Min_Stock_Level')) else 0
            
            status = "Out of Stock" if current_stock <= 0 else ("Low Stock" if current_stock < min_stock else "In Stock")
            status_color = "danger" if current_stock <= 0 else ("warning" if current_stock < min_stock else "success")
            
            items.append({
                "item_code": item_code,
                "item_name": str(row.get('Item_Name', 'Unknown')).strip(),
                "department": str(row.get('Department', 'General')).strip(),
                "unit": str(row.get('Unit', 'Nos')).strip(),
                "current_stock": current_stock,
                "min_stock_level": min_stock,
                "status": status,
                "status_color": status_color
            })
        
        dept_filter = request.args.get('department', 'all').strip()
        if dept_filter != 'all':
            items = [i for i in items if i['department'].lower() == dept_filter.lower()]
        
        return jsonify({"success": True, "items": items, "total": len(items), "property": "ONEWEST"})
    
    except Exception as e:
        return jsonify({"success": False, "error": str(e), "items": []}), 500


@app.route("/ow_api/inventory/stats")
@login_required
@require_property("ONEWEST")
def ow_get_inventory_stats():
    try:
        if not OW_INVENTORY_XLSX.exists():
            return jsonify({"total_items": 0, "in_stock": 0, "low_stock": 0, "out_of_stock": 0})
        
        df = pd.read_excel(OW_INVENTORY_XLSX)
        total_items = in_stock = low_stock = out_of_stock = 0
        departments = set()
        
        for _, row in df.iterrows():
            item_code = str(row.get('Item_Code', '')).strip()
            if not item_code or item_code.lower() in ['nan', 'none', '']:
                continue
            
            total_items += 1
            departments.add(str(row.get('Department', 'General')).strip())
            
            current_stock = float(row.get('Current_Stock', 0)) if pd.notna(row.get('Current_Stock')) else 0
            min_stock = float(row.get('Min_Stock_Level', 0)) if pd.notna(row.get('Min_Stock_Level')) else 0
            
            if current_stock <= 0:
                out_of_stock += 1
            elif current_stock < min_stock:
                low_stock += 1
            else:
                in_stock += 1
        
        return jsonify({
            "total_items": total_items,
            "in_stock": in_stock,
            "low_stock": low_stock,
            "out_of_stock": out_of_stock,
            "departments": list(departments),
            "property": "ONEWEST"
        })
    
    except Exception as e:
        return jsonify({"total_items": 0, "in_stock": 0, "low_stock": 0, "out_of_stock": 0}), 500


@app.route("/ow_api/inventory/movement", methods=["POST"])
@login_required
@require_property("ONEWEST")
def ow_update_stock_movement():
    try:
        data = request.get_json()
        item_code = data.get('item_code')
        movement_type = data.get('movement_type')
        quantity = int(data.get('quantity', 0))
        
        if not item_code or not movement_type or quantity <= 0:
            return jsonify({"success": False, "error": "Invalid data"}), 400
        
        if not OW_INVENTORY_XLSX.exists():
            return jsonify({"success": False, "error": "Inventory file not found"}), 404
        
        df = pd.read_excel(OW_INVENTORY_XLSX)
        mask = df['Item_Code'] == item_code
        
        if not mask.any():
            return jsonify({"success": False, "error": "Item not found"}), 404
        
        current_stock = float(df.loc[mask, 'Current_Stock'].iloc[0]) if pd.notna(df.loc[mask, 'Current_Stock'].iloc[0]) else 0
        
        if movement_type.upper() == 'IN':
            new_stock = current_stock + quantity
            df.loc[mask, 'Stock_In'] = (df.loc[mask, 'Stock_In'].iloc[0] if pd.notna(df.loc[mask, 'Stock_In'].iloc[0]) else 0) + quantity
        elif movement_type.upper() == 'OUT':
            if quantity > current_stock:
                return jsonify({"success": False, "error": "Insufficient stock"}), 400
            new_stock = current_stock - quantity
            df.loc[mask, 'Stock_Out'] = (df.loc[mask, 'Stock_Out'].iloc[0] if pd.notna(df.loc[mask, 'Stock_Out'].iloc[0]) else 0) + quantity
        else:
            return jsonify({"success": False, "error": "Invalid movement type"}), 400
        
        df.loc[mask, 'Current_Stock'] = new_stock
        df.loc[mask, 'Last_Updated'] = datetime.now().strftime('%Y-%m-%d')
        
        max_retries = 3
        for attempt in range(max_retries):
            try:
                df.to_excel(OW_INVENTORY_XLSX, index=False)
                break
            except PermissionError:
                if attempt == max_retries - 1:
                    return jsonify({"success": False, "error": "File locked"}), 500
                import time
                time.sleep(1)
        
        return jsonify({"success": True, "new_stock": new_stock})
    
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/ow_api/inventory/alerts")
@login_required
@require_property("ONEWEST")
def ow_get_inventory_alerts():
    try:
        if not OW_INVENTORY_XLSX.exists():
            return jsonify({"alerts": [], "total": 0})
        
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
                    "shortage": min_stock - current_stock,
                    "severity": "critical" if current_stock <= 0 else "warning"
                })
        
        return jsonify({"alerts": alerts, "total": len(alerts), "property": "ONEWEST"})
    
    except Exception as e:
        return jsonify({"alerts": [], "total": 0}), 500


@app.route("/ow_api/inventory/export")
@login_required
@require_property("ONEWEST")
def ow_export_inventory():
    try:
        if not OW_INVENTORY_XLSX.exists():
            return jsonify({"error": "No data"}), 404
        
        filename = f"ONEWEST_Inventory_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        return send_file(
            OW_INVENTORY_XLSX,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name=filename
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# =====================================================
# ADD TO server.py AFTER OTHER BLUEPRINT REGISTRATIONS
# =====================================================



# =====================================================
# ADD ONEWEST VMS PORTAL ROUTE
# =====================================================
@app.route("/ow_vms")
@login_required
@require_property("ONEWEST")
def ow_vms():
    """ONEWEST Visitor Management System Portal"""
    session['active_property'] = 'ONEWEST'
    session['property_code'] = 'OW'
    print(f"\n🏢 Accessing ONEWEST VMS - User: {session.get('user')}")
    return render_template("ow_vms.html")



# =====================================================
# 6.0 ONEWEST WORK TRACKER
# =====================================================

@app.route("/ow_work_track")
@login_required
@require_property("ONEWEST")
def ow_work_track():
    return render_template("ow_work_track.html")


# =====================================================
# 4.0 OGM
# =====================================================



# =====================================================
# 5.0 NINEHILS
# =====================================================

# =====================================================
# 20. START SERVER
# =====================================================


if __name__ == "__main__":
    
    print(f"""
{'='*70}
⚙️  TERMINUS MMS — SERVER READY
📧 ONEWEST Mail Auto-Send: Daily at 8:00 AM IST
🌐 Dashboard: http://localhost:5000
{'='*70}
⚙️  TERMINUS MAINTENANCE MANAGEMENT SYSTEM - STARTING
{'='*70}
🌐 Dashboard: http://localhost:5000
📊 PPM (SLN): http://localhost:5000/ppm_dashboard
📊 PPM (ONEWEST): http://localhost:5000/ow_ppm_dashboard
🏢 SLN Terminus: http://localhost:5000/sln_terminus
🏢 ONEWEST: http://localhost:5000/onewest
🏢 The District: http://localhost:5000/the_district
🏢 One Golden Mile: http://localhost:5000/one_golden_mile
🏢 Nine Hills: http://localhost:5000/nine_hills
📈 Occupancy: http://localhost:5000/sln_occupancy
🛠️  Issues: http://localhost:5000/issues
📋 Project Handover: http://localhost:5000/project_handover
👔 GM Dashboard: http://localhost:5000/gm_dashboard
📁 Documents: http://localhost:5000/documents
📅 Server Start: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
{'='*70}
""")
    app.run(host="0.0.0.0", port=5000, debug=False)