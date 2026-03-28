# workorders_routes.py

import io
import json
from flask import Blueprint, jsonify, send_file
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors

# Create Blueprint
# Note: It is assumed your main server.py registers this without a prefix, 
# so the routes here must be fully qualified.
workorders_bp = Blueprint("workorders_bp", __name__)

# ==========================================
# WORK ORDERS UTILITIES (for standalone use)
# ==========================================
# NOTE: This mock function is duplicated here for immediate testing.
def read_workorders_safe():
    return [
        {"id": "WO-001", "date": "2025-12-15", "asset": "HT Panel VCB-1", "asset_type": "Vendor", "status": "Open"},
        {"id": "WO-002", "date": "2025-12-15", "asset": "Primary Pumps", "asset_type": "In-house", "status": "In Progress"},
        {"id": "WO-003", "date": "2025-12-16", "asset": "Chiller 3", "asset_type": "Vendor", "status": "Closed"},
        {"id": "WO-004", "date": "2025-12-22", "asset": "Fire Pump", "asset_type": "In-house", "status": "Open"},
        {"id": "WO-005", "date": "2025-11-20", "asset": "AHU-22", "asset_type": "In-house", "status": "Closed"},
        {"id": "WO-006", "date": "2025-12-05", "asset": "Staircase Emergency Doors", "asset_type": "In-house", "status": "Closed"},
        {"id": "WO-007", "date": "2025-12-05", "asset": "Sliding Door", "asset_type": "Vendor", "status": "Open"},
        {"id": "WO-008", "date": "2025-12-07", "asset": "Condenser Pumps Stainers", "asset_type": "In-house", "status": "In Progress"},
        {"id": "WO-009", "date": "2025-12-25", "asset": "Transformer- HT I/C VCB-1", "asset_type": "Vendor", "status": "Open"},
    ]

# Mock initializer functions (to satisfy server.py)
def init_workorders():
    pass
def init_wo():
    pass

# ==========================================
# WORK ORDER API ROUTES (MAPPED TO /api/workorders/*)
# ==========================================

@workorders_bp.route("/api/workorders/load")
def load_workorders():
    wos = read_workorders_safe()
    return jsonify(wos)

@workorders_bp.route("/api/workorders/report/<year>/<month>")
def generate_workorders_report(year, month):
    # This logic handles your month-wise PDF report generation request
    
    # 1. Filter WOs for the requested month
    month_str = f"{year}-{month.zfill(2)}"
    wos = [wo for wo in read_workorders_safe() if wo.get('date', '').startswith(month_str)]

    # 2. Build PDF content
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4) 
    styles = getSampleStyleSheet()
    elements = []

    elements.append(Paragraph(f"Work Order Report: {month_str}", styles['h1']))
    elements.append(Paragraph(f"Total Work Orders Found: {len(wos)}", styles['Normal']))

    if wos:
        # Create table data (Header and rows)
        data = [["WO ID", "Date", "Asset", "Assigned Team", "Status"]]
        for wo in wos:
            data.append([
                wo.get('id', 'N/A'),
                wo.get('date', 'N/A'),
                wo.get('asset', 'N/A'),
                wo.get('asset_type', 'N/A'), 
                wo.get('status', 'N/A')
            ])

        # Style the table
        table = Table(data)
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2C3E50')), 
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#F5F5DC')),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        elements.append(table)

    # 3. Build and return PDF
    doc.build(elements)
    buffer.seek(0)
    
    filename = f"WorkOrders_Report_{year}-{month}.pdf"
    return send_file(
        buffer,
        as_attachment=True,
        download_name=filename,
        mimetype='application/pdf'
    )