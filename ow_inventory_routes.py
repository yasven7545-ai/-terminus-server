"""
ONEWEST INVENTORY MANAGEMENT ROUTES
Independent from SLN Terminus - Uses ow_ prefix throughout
"""
from flask import Blueprint, render_template, request, jsonify, send_file
from pathlib import Path
import pandas as pd
import json
from datetime import datetime
import os

ow_inventory_bp = Blueprint('ow_inventory_bp', __name__)

# ONEWEST Inventory Paths
BASE_DIR = Path(__file__).parent.parent.resolve()
OW_INVENTORY_XLSX = BASE_DIR / "static" / "data" / "ow_store_master.xlsx"
OW_INVENTORY_ALERTS = BASE_DIR / "static" / "data" / "ow_inventory_alerts.json"
OW_INVENTORY_DIR = BASE_DIR / "static" / "data" / "OW" / "inventory"

# Ensure directories exist
OW_INVENTORY_DIR.mkdir(parents=True, exist_ok=True)
OW_INVENTORY_ALERTS.parent.mkdir(parents=True, exist_ok=True)

# Initialize alerts file if not exists
if not OW_INVENTORY_ALERTS.exists():
    with open(OW_INVENTORY_ALERTS, 'w') as f:
        json.dump({"alerts": [], "last_updated": datetime.now().isoformat()}, f, indent=2)


@ow_inventory_bp.route("/ow_inventory_dashboard")
def ow_inventory_dashboard():
    """ONEWEST Inventory Dashboard Page"""
    return render_template("ow_inventory_dashboard.html")


@ow_inventory_bp.route("/ow_api/inventory/items")
def ow_get_inventory_items():
    """API: Get all inventory items from ow_store_master.xlsx"""
    try:
        if not OW_INVENTORY_XLSX.exists():
            return jsonify({
                "success": False,
                "error": "Inventory file not found",
                "items": [],
                "total": 0
            })
        
        df = pd.read_excel(OW_INVENTORY_XLSX, engine='openpyxl')
        
        items = []
        for _, row in df.iterrows():
            item_code = str(row.get('Item_Code', '')).strip()
            if not item_code or item_code.lower() in ['nan', 'none', '']:
                continue
            
            current_stock = float(row.get('Current_Stock', 0)) if pd.notna(row.get('Current_Stock')) else 0
            min_stock = float(row.get('Min_Stock_Level', 0)) if pd.notna(row.get('Min_Stock_Level')) else 0
            
            # Determine stock status
            if current_stock <= 0:
                status = "Out of Stock"
                status_color = "danger"
            elif current_stock < min_stock:
                status = "Low Stock"
                status_color = "warning"
            else:
                status = "In Stock"
                status_color = "success"
            
            items.append({
                "item_code": item_code,
                "item_name": str(row.get('Item_Name', 'Unknown')).strip(),
                "department": str(row.get('Department', 'General')).strip(),
                "unit": str(row.get('Unit', 'Nos')).strip(),
                "opening_stock": float(row.get('Opening_Stock', 0)) if pd.notna(row.get('Opening_Stock')) else 0,
                "stock_in": float(row.get('Stock_In', 0)) if pd.notna(row.get('Stock_In')) else 0,
                "stock_out": float(row.get('Stock_Out', 0)) if pd.notna(row.get('Stock_Out')) else 0,
                "current_stock": current_stock,
                "min_stock_level": min_stock,
                "last_updated": str(row.get('Last_Updated', '')).strip(),
                "remarks": str(row.get('Remarks', '')).strip(),
                "status": status,
                "status_color": status_color
            })
        
        # Get filters
        dept_filter = request.args.get('department', 'all').strip()
        status_filter = request.args.get('status', 'all').strip().lower()
        
        # Apply filters
        if dept_filter != 'all':
            items = [i for i in items if i['department'].lower() == dept_filter.lower()]
        
        if status_filter != 'all':
            items = [i for i in items if i['status'].lower() == status_filter]
        
        # Calculate stats
        total_items = len(items)
        in_stock = len([i for i in items if i['status'] == 'In Stock'])
        low_stock = len([i for i in items if i['status'] == 'Low Stock'])
        out_of_stock = len([i for i in items if i['status'] == 'Out of Stock'])
        departments = list(set([i['department'] for i in items]))
        
        return jsonify({
            "success": True,
            "items": items,
            "total": total_items,
            "in_stock": in_stock,
            "low_stock": low_stock,
            "out_of_stock": out_of_stock,
            "departments": departments,
            "property": "ONEWEST"
        })
    
    except Exception as e:
        print(f"❌ ONEWEST Inventory API Error: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "items": [],
            "total": 0
        }), 500


@ow_inventory_bp.route("/ow_api/inventory/stats")
def ow_get_inventory_stats():
    """API: Get inventory statistics"""
    try:
        if not OW_INVENTORY_XLSX.exists():
            return jsonify({
                "total_items": 0,
                "in_stock": 0,
                "low_stock": 0,
                "out_of_stock": 0,
                "departments": [],
                "property": "ONEWEST"
            })
        
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
        return jsonify({
            "total_items": 0,
            "in_stock": 0,
            "low_stock": 0,
            "out_of_stock": 0,
            "departments": [],
            "property": "ONEWEST"
        }), 500


@ow_inventory_bp.route("/ow_api/inventory/movement", methods=["POST"])
def ow_update_stock_movement():
    """API: Update stock IN/OUT movement"""
    try:
        data = request.get_json()
        item_code = data.get('item_code')
        movement_type = data.get('movement_type')
        quantity = int(data.get('quantity', 0))
        remarks = data.get('remarks', '')
        
        if not item_code or not movement_type or quantity <= 0:
            return jsonify({"success": False, "error": "Invalid data provided"}), 400
        
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
        
        if remarks:
            df.loc[mask, 'Remarks'] = remarks
        
        max_retries = 3
        for attempt in range(max_retries):
            try:
                df.to_excel(OW_INVENTORY_XLSX, index=False)
                break
            except PermissionError:
                if attempt == max_retries - 1:
                    return jsonify({"success": False, "error": "File is locked. Please close Excel and retry."}), 500
                import time
                time.sleep(1)
        
        min_stock = float(df.loc[mask, 'Min_Stock_Level'].iloc[0]) if pd.notna(df.loc[mask, 'Min_Stock_Level'].iloc[0]) else 0
        if new_stock < min_stock:
            ow_log_low_stock_alert(item_code, new_stock, min_stock)
        
        return jsonify({"success": True, "message": f"Stock {movement_type} updated successfully", "new_stock": new_stock})
    
    except Exception as e:
        print(f"❌ ONEWEST Stock Movement Error: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500


@ow_inventory_bp.route("/ow_api/inventory/alerts")
def ow_get_inventory_alerts():
    """API: Get low stock alerts"""
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
        return jsonify({"alerts": [], "total": 0, "error": str(e)}), 500


@ow_inventory_bp.route("/ow_api/inventory/export")
def ow_export_inventory():
    """API: Export inventory to Excel"""
    try:
        if not OW_INVENTORY_XLSX.exists():
            return jsonify({"error": "No inventory data to export"}), 404
        
        filename = f"ONEWEST_Inventory_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        return send_file(
            OW_INVENTORY_XLSX,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name=filename
        )
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@ow_inventory_bp.route("/ow_api/inventory/import-excel", methods=["POST"])
def ow_import_inventory_excel():
    """API: Import inventory from Excel"""
    try:
        file = request.files.get('file')
        if not file:
            return jsonify({"status": "error", "message": "No file uploaded"}), 400
        
        file.save(OW_INVENTORY_XLSX)
        
        df = pd.read_excel(OW_INVENTORY_XLSX)
        count = len([_ for _, row in df.iterrows() if pd.notna(row.get('Item_Code')) and str(row.get('Item_Code')).strip()])
        
        return jsonify({
            "status": "success",
            "message": f"Successfully imported {count} ONEWEST inventory items",
            "count": count
        })
    
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


def ow_log_low_stock_alert(item_code, current_stock, min_stock):
    """Log low stock alert to JSON sfile"""
    try:
        alerts_data = {"alerts": [], "last_updated": ""}
        if OW_INVENTORY_ALERTS.exists():
            with open(OW_INVENTORY_ALERTS, 'r') as f:
                alerts_data = json.load(f)
        
        existing = False
        for alert in alerts_data.get('alerts', []):
            if alert.get('item_code') == item_code:
                alert['current_stock'] = current_stock
                alert['last_triggered'] = datetime.now().isoformat()
                existing = True
                break
        
        if not existing:
            alerts_data['alerts'].append({
                "item_code": item_code,
                "current_stock": current_stock,
                "min_stock_level": min_stock,
                "first_triggered": datetime.now().isoformat(),
                "last_triggered": datetime.now().isoformat()
            })
        
        alerts_data['last_updated'] = datetime.now().isoformat()
        
        with open(OW_INVENTORY_ALERTS, 'w') as f:
            json.dump(alerts_data, f, indent=2)
    
    except Exception as e:
        print(f"❌ Alert logging error: {str(e)}")