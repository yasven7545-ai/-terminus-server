"""
TERMINUS MAINTENANCE MANAGEMENT SYSTEM - DATABASE MODELS
Complete SQLAlchemy models with init_db function
"""
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import json

# ✅ CRITICAL: Only ONE db instance in models.py
db = SQLAlchemy()


# =====================================================
# 1. USER MODEL
# =====================================================
class User(db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(30), nullable=False, default='user')
    department = db.Column(db.String(100))
    email = db.Column(db.String(120))
    phone = db.Column(db.String(20))
    properties = db.Column(db.Text)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime)
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    def get_properties(self):
        return json.loads(self.properties) if self.properties else []
    
    def __repr__(self):
        return f'<User {self.username}>'	


# =====================================================
# 2. ISSUE MODEL
# =====================================================
class Issue(db.Model):
    __tablename__ = 'issues'
    
    id = db.Column(db.Integer, primary_key=True)
    issue_id = db.Column(db.String(30), unique=True, nullable=False)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)
    issue_type = db.Column(db.String(50))
    priority = db.Column(db.String(20), default='Medium')
    status = db.Column(db.String(30), default='Open')
    location = db.Column(db.String(100))
    property_name = db.Column(db.String(100), default='SLN Terminus')
    
    tenant_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    assigned_to = db.Column(db.Integer, db.ForeignKey('users.id'))
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    resolved_at = db.Column(db.DateTime)
    
    def __repr__(self):
        return f'<Issue {self.issue_id}>'

# =====================================================
# 3. ASSET MODEL (For PPM)
# =====================================================
class Asset(db.Model):
    """Assets for PPM scheduling"""
    __tablename__ = 'assets'
    
    id = db.Column(db.Integer, primary_key=True)
    asset_code = db.Column(db.String(50), unique=True, nullable=False)
    asset_name = db.Column(db.String(150), nullable=False)
    category = db.Column(db.String(50))
    location = db.Column(db.String(100))
    floor = db.Column(db.String(20))
    property_name = db.Column(db.String(100), default='SLN Terminus')
    
    maintenance_frequency = db.Column(db.String(20), default='Monthly')
    last_service_date = db.Column(db.Date)
    next_due_date = db.Column(db.Date)
    color_code = db.Column(db.String(20), default='Green')
    status = db.Column(db.String(20), default='Active')
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f'<Asset {self.asset_code}>'


# =====================================================
# 4. WORK ORDER MODEL
# =====================================================
class WorkOrder(db.Model):
    """PPM Work Orders"""
    __tablename__ = 'work_orders'
    
    id = db.Column(db.Integer, primary_key=True)
    work_order_id = db.Column(db.String(30), unique=True, nullable=False)
    wo_type = db.Column(db.String(30), default='PPM')
    
    asset_id = db.Column(db.Integer, db.ForeignKey('assets.id'))
    asset_name = db.Column(db.String(150))
    location = db.Column(db.String(100))
    
    assigned_to = db.Column(db.Integer, db.ForeignKey('users.id'))
    assigned_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    
    due_date = db.Column(db.Date, nullable=False)
    priority = db.Column(db.String(20), default='Medium')
    status = db.Column(db.String(30), default='Open')
    
    description = db.Column(db.Text)
    checklist = db.Column(db.Text)
    remarks = db.Column(db.Text)
    
    started_at = db.Column(db.DateTime)
    completed_at = db.Column(db.DateTime)
    closed_at = db.Column(db.DateTime)
    closed_by = db.Column(db.String(80))
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f'<WorkOrder {self.work_order_id}>'


# =====================================================
# 5. VENDOR MODEL
# =====================================================
class Vendor(db.Model):
    """Vendor/Contractor management"""
    __tablename__ = 'vendors'
    
    id = db.Column(db.Integer, primary_key=True)
    vendor_id = db.Column(db.String(30), unique=True, nullable=False)
    company_name = db.Column(db.String(150), nullable=False)
    contact_person = db.Column(db.String(100))
    email = db.Column(db.String(120))
    phone = db.Column(db.String(20))
    service_category = db.Column(db.String(50))
    
    contract_start = db.Column(db.Date)
    contract_end = db.Column(db.Date)
    status = db.Column(db.String(20), default='Active')
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f'<Vendor {self.vendor_id}>'


# =====================================================
# 6. AUDIT LOG MODEL
# =====================================================
class AuditLog(db.Model):
    """System audit trail"""
    __tablename__ = 'audit_logs'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    username = db.Column(db.String(80))
    action = db.Column(db.String(100), nullable=False)
    entity_type = db.Column(db.String(50))
    entity_id = db.Column(db.String(50))
    ip_address = db.Column(db.String(50))
    status = db.Column(db.String(20), default='Success')
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    
    def __repr__(self):
        return f'<AuditLog {self.id}>'



# =====================================================
# ✅ DATABASE INITIALIZATION FUNCTION
# =====================================================
def init_db(app):
    """Initialize database - MUST be called AFTER app.config"""
    db.init_app(app)
    
    with app.app_context():
        db.create_all()
        print("✅ Database tables created successfully")


def create_default_users():
    """Create default users - MUST be called within app context"""
    with app.app_context():
        admin = User.query.filter_by(username='admin').first()
        if not admin:
            admin = User(
                username='admin',
                role='admin',
                email='admin@terminus-global.com',
                properties=json.dumps(["SLN Terminus", "ONEWEST", "The District"]),
                is_active=True
            )
            admin.set_password('admin123')
            db.session.add(admin)
            
            supervisor = User(
                username='supervisor',
                role='supervisor',
                email='supervisor@terminus-global.com',
                properties=json.dumps(["SLN Terminus"]),
                is_active=True
            )
            supervisor.set_password('supervisor123')
            db.session.add(supervisor)
            
            technician = User(
                username='technician',
                role='technician',
                email='technician@terminus-global.com',
                properties=json.dumps(["SLN Terminus"]),
                is_active=True
            )
            technician.set_password('technician123')
            db.session.add(technician)
            
            db.session.commit()
            print("✅ Default users created successfully")