import pandas as pd
import os
from datetime import datetime
from pathlib import Path
from flask import Blueprint, request, jsonify, send_from_directory

from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors

inventory_bp = Blueprint('inventory_final_production_v3', __name__)

DATA_DIR = Path("static/data")
DATA_DIR.mkdir(parents=True, exist_ok=True)
MASTER = DATA_DIR / 'inventory_master.xlsx'
TRAN = DATA_DIR / 'inventory_transactions.xlsx'

def clean_codes(series):
    return series.astype(str).str.strip().str.lstrip("'")

def safe_float(val):
    """Convert any value to float safely, returning 0.0 for NaN/None/invalid."""
    try:
        f = float(val)
        return 0.0 if pd.isna(f) else f
    except:
        return 0.0

def ensure_files():
    if not MASTER.exists():
        cols = ['Item_Code','Item_Name','Department','Unit','Opening_Stock','Stock_In','Stock_Out','Current_Stock','Min_Stock_Level']
        pd.DataFrame(columns=cols).to_excel(MASTER, index=False)
    if not TRAN.exists():
        cols = ['Timestamp','Item_Code','Item_Name','Type','Qty','Remarks']
        pd.DataFrame(columns=cols).to_excel(TRAN, index=False)

@inventory_bp.route('/json_master')
def json_master():
    ensure_files()
    try:
        df = pd.read_excel(MASTER).fillna(0)
        df['Item_Code'] = clean_codes(df['Item_Code'])
        return jsonify(df.to_dict(orient='records'))
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@inventory_bp.route('/update', methods=['POST'])
def update_stock():
    ensure_files()
    data = request.get_json()
    code = str(data.get('item_code', '')).strip().lstrip("'")

    try:
        qty     = float(data.get('quantity', 0))
        mode    = data.get('type')
        remarks = data.get('remarks', 'Dashboard Movement')

        df = pd.read_excel(MASTER)
        df['Item_Code'] = clean_codes(df['Item_Code'])

        if code not in df['Item_Code'].values:
            return jsonify({"success": False, "error": f"Item '{code}' not found in master"}), 404

        idx = df[df['Item_Code'] == code].index[0]

        # Use safe_float to handle NaN in any numeric column
        opening     = safe_float(df.at[idx, 'Opening_Stock'])
        current_in  = safe_float(df.at[idx, 'Stock_In'])
        current_out = safe_float(df.at[idx, 'Stock_Out'])

        if mode == 'IN':
            new_in  = current_in + qty
            new_out = current_out
        else:
            new_in  = current_in
            new_out = current_out + qty

        new_balance = opening + new_in - new_out

        df.at[idx, 'Stock_In']      = new_in
        df.at[idx, 'Stock_Out']     = new_out
        df.at[idx, 'Current_Stock'] = new_balance

        df.to_excel(MASTER, index=False)

        # Log transaction
        tdf = pd.read_excel(TRAN) if TRAN.exists() else pd.DataFrame()
        new_log = {
            'Timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            'Item_Code': code,
            'Item_Name': str(df.at[idx, 'Item_Name']),
            'Type': mode, 'Qty': qty, 'Remarks': remarks
        }
        pd.concat([tdf, pd.DataFrame([new_log])], ignore_index=True).to_excel(TRAN, index=False)

        return jsonify({"success": True, "new_stock": float(new_balance)})

    except PermissionError:
        return jsonify({"success": False, "error": "FILE LOCKED: Close inventory_master.xlsx in Excel first"}), 500
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@inventory_bp.route('/upload_master', methods=['POST'])
def upload_master():
    f = request.files.get('file')
    if f:
        f.save(str(MASTER))
        return jsonify({"success": True})
    return jsonify({"success": False, "error": "No file"}), 400

@inventory_bp.route('/download_master')
def download_master():
    if MASTER.exists():
        return send_from_directory(DATA_DIR, MASTER.name, as_attachment=True)
    return "File not found", 404
@inventory_bp.route('/download_transactions')
def download_transactions():
    if TRAN.exists():
        return send_from_directory(DATA_DIR, TRAN.name, as_attachment=True)
    return "No transactions file yet", 404


@inventory_bp.route('/export_pdf')
def export_pdf():
    """Export current inventory as a styled PDF report."""
    ensure_files()
    import io
    from flask import send_file
    from reportlab.platypus import (SimpleDocTemplate, Table, TableStyle,
                                    Paragraph, Spacer, HRFlowable)
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib import colors
    from reportlab.lib.units import mm
    from reportlab.lib.enums import TA_CENTER, TA_LEFT

    try:
        df = pd.read_excel(MASTER).fillna(0)
        df['Item_Code'] = clean_codes(df['Item_Code'])
    except Exception as e:
        return f"Error reading master: {e}", 500

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=landscape(A4),
        leftMargin=15*mm, rightMargin=15*mm,
        topMargin=18*mm, bottomMargin=15*mm,
        title="Inventory Report — SLN Terminus"
    )

    styles = getSampleStyleSheet()
    heading = ParagraphStyle('H', fontSize=16, fontName='Helvetica-Bold',
                             textColor=colors.HexColor('#1e293b'), spaceAfter=2,
                             alignment=TA_CENTER)
    sub = ParagraphStyle('S', fontSize=9, fontName='Helvetica',
                         textColor=colors.HexColor('#64748b'), alignment=TA_CENTER, spaceAfter=8)
    dept_head = ParagraphStyle('D', fontSize=11, fontName='Helvetica-Bold',
                               textColor=colors.HexColor('#2563eb'), spaceBefore=10, spaceAfter=4)

    story = []
    story.append(Paragraph("Inventory Report — SLN Terminus MMS", heading))
    story.append(Paragraph(
        f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}  |  Total Items: {len(df)}", sub))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor('#e2e8f0'), spaceAfter=8))

    # Summary block
    low_count  = int((df['Current_Stock'] <= df['Min_Stock_Level']).sum())
    ok_count   = len(df) - low_count
    depts_count = df['Department'].nunique()
    summary_data = [
        ['Total Items', 'In Stock (OK)', 'Low Stock', 'Departments'],
        [str(len(df)), str(ok_count), str(low_count), str(depts_count)]
    ]
    st = Table(summary_data, colWidths=[60*mm]*4)
    st.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#f8fafc')),
        ('TEXTCOLOR',  (0,0), (-1,0), colors.HexColor('#64748b')),
        ('FONTNAME',   (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE',   (0,0), (-1,0), 8),
        ('BACKGROUND', (0,1), (-1,1), colors.HexColor('#f0f9ff')),
        ('FONTNAME',   (0,1), (-1,1), 'Helvetica-Bold'),
        ('FONTSIZE',   (0,1), (-1,1), 14),
        ('TEXTCOLOR',  (0,1), (0,1), colors.HexColor('#2563eb')),
        ('TEXTCOLOR',  (1,1), (1,1), colors.HexColor('#10b981')),
        ('TEXTCOLOR',  (2,1), (2,1), colors.HexColor('#ef4444')),
        ('TEXTCOLOR',  (3,1), (3,1), colors.HexColor('#f59e0b')),
        ('ALIGN',      (0,0), (-1,-1), 'CENTER'),
        ('VALIGN',     (0,0), (-1,-1), 'MIDDLE'),
        ('BOX',        (0,0), (-1,-1), 0.5, colors.HexColor('#e2e8f0')),
        ('INNERGRID',  (0,0), (-1,-1), 0.5, colors.HexColor('#e2e8f0')),
        ('TOPPADDING', (0,0), (-1,-1), 6),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
    ]))
    story.append(st)
    story.append(Spacer(1, 8*mm))

    # Per-department tables
    col_names  = ['Item Code', 'Item Name', 'Unit', 'Opening', 'In', 'Out', 'Current', 'Min', 'Status']
    col_widths = [28*mm, 70*mm, 14*mm, 18*mm, 18*mm, 18*mm, 22*mm, 18*mm, 18*mm]

    for dept, grp in df.groupby('Department'):
        story.append(Paragraph(f"  {dept}", dept_head))
        tbl_data = [col_names]
        for _, row in grp.iterrows():
            cur  = safe_float(row.get('Current_Stock', 0))
            minv = safe_float(row.get('Min_Stock_Level', 0))
            status = 'LOW' if cur <= minv else 'OK'
            tbl_data.append([
                str(row.get('Item_Code', '')),
                str(row.get('Item_Name', '')),
                str(row.get('Unit', '')),
                str(int(safe_float(row.get('Opening_Stock', 0)))),
                str(int(safe_float(row.get('Stock_In', 0)))),
                str(int(safe_float(row.get('Stock_Out', 0)))),
                str(int(cur)), str(int(minv)), status,
            ])

        rstyles = [
            ('BACKGROUND',    (0,0), (-1,0),  colors.HexColor('#1e3a5f')),
            ('TEXTCOLOR',     (0,0), (-1,0),  colors.white),
            ('FONTNAME',      (0,0), (-1,0),  'Helvetica-Bold'),
            ('FONTSIZE',      (0,0), (-1,-1), 8),
            ('ALIGN',         (0,0), (-1,-1), 'CENTER'),
            ('ALIGN',         (1,1), (1,-1),  'LEFT'),
            ('FONTNAME',      (0,1), (-1,-1), 'Helvetica'),
            ('ROWBACKGROUNDS',(0,1), (-1,-1), [colors.white, colors.HexColor('#f8fafc')]),
            ('BOX',           (0,0), (-1,-1), 0.5, colors.HexColor('#cbd5e1')),
            ('INNERGRID',     (0,0), (-1,-1), 0.3, colors.HexColor('#e2e8f0')),
            ('TOPPADDING',    (0,0), (-1,-1), 4),
            ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ]
        for r_i, r in enumerate(tbl_data[1:], 1):
            if r[-1] == 'LOW':
                rstyles += [
                    ('TEXTCOLOR',  (8,r_i), (8,r_i), colors.HexColor('#ef4444')),
                    ('FONTNAME',   (8,r_i), (8,r_i), 'Helvetica-Bold'),
                    ('BACKGROUND', (0,r_i), (-1,r_i), colors.HexColor('#fef2f2')),
                ]
            else:
                rstyles.append(('TEXTCOLOR', (8,r_i), (8,r_i), colors.HexColor('#10b981')))

        t = Table(tbl_data, colWidths=col_widths, repeatRows=1)
        t.setStyle(TableStyle(rstyles))
        story.append(t)
        story.append(Spacer(1, 5*mm))

    doc.build(story)
    buf.seek(0)
    return send_file(
        buf, mimetype='application/pdf', as_attachment=True,
        download_name=f"Inventory_Report_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf"
    )