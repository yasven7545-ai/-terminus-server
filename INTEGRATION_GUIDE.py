"""
════════════════════════════════════════════════════════════════
  ONEWEST PPM DASHBOARD — SERVER.PY INTEGRATION GUIDE
  Add the lines below to server.py (DO NOT replace existing code)
════════════════════════════════════════════════════════════════

STEP 1 — Register the new blueprint (add near other safe_register calls):
──────────────────────────────────────────────────────────────
safe_register("ow_ppm_routes", "ow_ppm_bp", url_prefix="/ow_api")

STEP 2 — The existing ow_ppm_dashboard route already works (no change needed):
──────────────────────────────────────────────────────────────
@app.route("/ow_ppm_dashboard")
@login_required
@require_property("ONEWEST")
def ow_ppm_dashboard():
    session['active_property'] = 'ONEWEST'
    return render_template("ow_ppm_dashboard.html")

STEP 3 — Add AMC docs serve route (add near other /uploads/ routes):
──────────────────────────────────────────────────────────────
@app.route("/uploads/OW/amc_docs/<filename>")
@login_required
def ow_serve_amc_doc(filename):
    from pathlib import Path
    amc_docs_dir = Path(__file__).parent / "uploads" / "OW" / "amc_docs"
    return send_from_directory(amc_docs_dir, filename)

STEP 4 — File placement:
──────────────────────────────────────────────────────────────
  ow_ppm_routes.py     → same folder as server.py
  ow_ppm_dashboard.html → templates/

STEP 5 — Excel file structure (Asset.xls):
──────────────────────────────────────────────────────────────
  Sheet 1: inhouse_ppm
  Sheet 2: vendor_ppm
  
  Required columns (both sheets):
    Asset Code | Asset Name | Department | Location | Last Service | nextDueDate

  Optional columns:
    Trade | Category | Vendor | Contract ID | Remarks

STEP 6 — OW Data folder structure:
──────────────────────────────────────────────────────────────
  static/data/OW/
    Asset.xls           ← inhouse_ppm + vendor_ppm sheets
    work_orders.json    ← auto-created
    amc_contracts.json  ← auto-created
    technicians.json    ← optional (for dropdown)
    supervisors.json    ← optional (for dropdown)

  uploads/OW/
    ppm/                ← WO photo uploads
    amc_docs/           ← AMC documentation

STEP 7 — IMPORTANT: If existing /ow_api/ppm/assets route conflicts:
──────────────────────────────────────────────────────────────
  The new blueprint registers at /ow_api prefix.
  Existing routes in server.py (ow_api_ppm_assets etc.) will still work.
  The new blueprint adds ?sheet= parameter support.
  
  To avoid 404 errors, ensure blueprint registers BEFORE app.run().

STEP 8 — technicians.json sample:
──────────────────────────────────────────────────────────────
{
  "technicians": [
    {"name": "Ahmed Khan", "trade": "Electrical", "phone": "+971-xx-xxxxxxx"},
    {"name": "Raj Kumar",  "trade": "Plumbing",   "phone": "+971-xx-xxxxxxx"},
    {"name": "Carlos M",   "trade": "HVAC",        "phone": "+971-xx-xxxxxxx"}
  ]
}

STEP 9 — supervisors.json sample:
──────────────────────────────────────────────────────────────
{
  "supervisors": [
    {"name": "Venu Gopal",  "email": "venu@onewest.com",   "phone": "+971-xx-xxxxxxx"},
    {"name": "John Smith",  "email": "john@onewest.com",   "phone": "+971-xx-xxxxxxx"}
  ]
}

════════════════════════════════════════════════════════════════
  NEW FEATURES ADDED IN THIS VERSION:
════════════════════════════════════════════════════════════════

  ✅ TWO PPM CATEGORIES:
     - In-House PPM (reads from inhouse_ppm sheet)
     - Vendor PPM (reads from vendor_ppm sheet)

  ✅ ASSETS VIEW:
     - Tab switcher: In-House / Vendor
     - Department filter chips (Electrical, Plumbing, HVAC, etc.)
     - Color-coded frequency dots (Green=Monthly, Yellow=Quarterly, Orange=Half-Yearly, Red=Yearly)
     - Search + frequency filter
     - Export PDF button

  ✅ CALENDAR VIEW:
     - Current month shown by default
     - Current date auto-selected
     - Click date → shows scheduled PPM tasks
     - Auto-create WO button per asset
     - Displays existing WOs for the selected date

  ✅ WORK ORDERS:
     - Inhouse vs Vendor filter
     - Status filter
     - WO close requires supervisor approval (checkbox)
     - Photo upload (drag & drop, 5 max)
     - Checklist with required items
     - Technician notes
     - PDF export

  ✅ COMPLETED WORK ORDERS:
     - Separate section
     - Shows all closed WOs with photos, checklist, approval notes
     - PDF export

  ✅ AMC TRACKER:
     - Add/Edit contracts
     - Document upload (drag & drop)
     - Days remaining counter
     - Status badges (Active / Expiring / Expired)
     - PDF export

  ✅ OVERVIEW COUNTERS:
     - Total assets (both sheets)
     - Pending PPM / Overdue / Compliance %
     - Inhouse PPM stats (assets, open WOs, overdue)
     - Vendor PPM stats (assets, open WOs, overdue)
     - Charts: Status, Frequency, Department

  ✅ BULK UPLOAD: Upload Excel/CSV to create work orders in bulk

  ✅ TOP BAR:
     - "Back to ONEWEST Portal" button (blinking)
     - Dark/Light mode toggle
     - Live clock

  ✅ DAILY MAIL: Auto at 08:00 AM + manual trigger button

  ✅ BARCODE READY: ow_handleBarcodeScan(assetCode) function
     Future: scan barcode → displays asset details + PPM process

  ✅ MOBILE RESPONSIVE: Full mobile compatibility, no overlap
════════════════════════════════════════════════════════════════
"""