================================================================================
ONEWEST INVENTORY MANAGEMENT SYSTEM
================================================================================

📁 FILE STRUCTURE (ALL WITH ow_ PREFIX)
---------------------------------------
static/data/
├── ow_store_master.xlsx          # Main inventory data file
├── ow_inventory_alerts.json      # Low stock alerts log
└── OW/inventory/                 # ONEWEST inventory uploads

templates/
└── ow_inventory_dashboard.html   # ONEWEST inventory dashboard

routes/
└── ow_inventory_routes.py        # ONEWEST inventory API routes (ow_ prefix)

================================================================================

🔗 API ENDPOINTS (ALL PREFIXED WITH ow_)
-----------------------------------------
GET  /ow_inventory_dashboard          - Inventory dashboard page
GET  /ow_api/inventory/items          - Get all inventory items
GET  /ow_api/inventory/stats          - Get inventory statistics
GET  /ow_api/inventory/alerts         - Get low stock alerts
POST /ow_api/inventory/movement       - Update stock IN/OUT
GET  /ow_api/inventory/export         - Export to Excel
POST /ow_api/inventory/import-excel   - Import from Excel

================================================================================

📊 EXCEL COLUMNS (ow_store_master.xlsx)
---------------------------------------
Item_Code          - Unique item identifier (e.g., E-0001, P-0001, H-0001)
Item_Name          - Item description
Department         - Department category (Electrical, Plumbing, HVAC, etc.)
Unit               - Unit of measurement (Nos, Meter, Kg, etc.)
Opening_Stock      - Initial stock quantity
Stock_In           - Total stock received
Stock_Out          - Total stock issued
Current_Stock      - Available stock (calculated)
Min_Stock_Level    - Minimum stock threshold for alerts
Last_Updated       - Last modification date
Remarks            - Additional notes

================================================================================

⚠️ IMPORTANT NOTES
------------------
1. ONEWEST inventory is COMPLETELY INDEPENDENT from SLN Terminus
2. All routes use 'ow_' prefix to avoid conflicts
3. NO synchronization with sln_terminus
4. Excel file path: static/data/ow_store_master.xlsx
5. Auto-refresh: Dashboard refreshes every 60 seconds
6. Low stock alerts trigger when Current_Stock < Min_Stock_Level
7. Email alerts sent daily at 8:00 AM IST

================================================================================

🔧 INTEGRATION WITH server.py
-----------------------------
Add this import at the top of server.py:
    from ow_inventory_routes import ow_inventory_bp

Register blueprint:
    app.register_blueprint(ow_inventory_bp, url_prefix="/ow_api")

Add scheduler initialization:
    from ow_inventory_scheduler import ow_setup_inventory_scheduler
    ow_inventory_scheduler = ow_setup_inventory_scheduler()

================================================================================

📱 RESPONSIVE DESIGN
--------------------
- Mobile-friendly layout (works on all screen sizes)
- Desktop-optimized tables
- No overlapping elements
- Touch-friendly buttons
- Collapsible sections for mobile

================================================================================

🎨 BACK TO PORTAL BUTTON
------------------------
- Located at top-left of dashboard
- Links to: /onewest
- Blinking animation for visibility
- Color: Orange (#fd7e14)

================================================================================

📧 EMAIL CONFIGURATION
----------------------
SMTP Server: smtp.gmail.com
SMTP Port: 587
Sender: maintenance.slnterminus@gmail.com
Receivers: maintenance.slnterminus@gmail.com, yasven7545@gmail.com, 
           engineering@terminus-global.com

================================================================================

🚀 QUICK START
--------------
1. Place ow_store_master.xlsx in static/data/
2. Add routes to server.py
3. Create ow_inventory_dashboard.html template
4. Run server.py
5. Access: http://localhost:5000/ow_inventory_dashboard

================================================================================