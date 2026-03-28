from flask import Blueprint, jsonify, request
import pandas as pd
import json
import os
from datetime import datetime

from flask import Blueprint
# Change ppm_api to ppm_bp here
ppm_api = Blueprint('ppm_api', __name__)

# Paths defined in your project requirements
ASSET_PATH = r'C:\Users\Venu\Desktop\my_dashboard\static\data\Assets.xlsx'
DATA_JSON = 'ppm_data.json'
WO_JSON = 'work_orders.json'

def get_asset_df():
    """Helper to read the Excel file reliably."""
    if os.path.exists(ASSET_PATH):
        return pd.read_excel(ASSET_PATH)
    return pd.DataFrame()

@ppm_api.route('/api/ppm_stats', methods=['GET'])
def get_ppm_stats():
    """Returns overview counts for the top HUD panels."""
    try:
        df = get_asset_df()
        wo_data = {}
        if os.path.exists(WO_JSON):
            with open(WO_JSON, 'r') as f:
                wo_data = json.load(f)
        
        wos = wo_data.get('work_orders', [])
        
        # Calculate Logic
        stats = {
            "total_assets": len(df),
            "pending_ppm": len([w for w in wos if w['status'] == 'open']),
            "completed_ppm": len([w for w in wos if w['status'] == 'closed']),
            "ppm_overdue": len([w for w in wos if w.get('priority') == 'High' and w['status'] == 'open']),
            "breakdowns": len([w for w in wos if 'Breakdown' in w.get('task', '')])
        }
        return jsonify(stats)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@ppm_api.route('/api/assets_summary', methods=['GET'])
def get_assets_summary():
    """Returns the 'Ticker' data with color-coded frequency logic."""
    try:
        df = get_asset_df()
        if df.empty:
            return jsonify([])

        # Select only necessary columns for the ticker to keep it fast
        summary = []
        for _, row in df.iterrows():
            summary.append({
                "name": str(row.get('Asset Name', row.get('name', 'Unknown'))),
                "frequency": str(row.get('Service Frequency', 'Monthly')),
                "nextDueDate": str(row.get('Next Due Date', 'TBD'))
            })
        
        return jsonify(summary)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@ppm_api.route('/api/work_orders', methods=['GET'])
def get_work_orders():
    """Fetches the main work order feed."""
    if not os.path.exists(WO_JSON):
        return jsonify({"work_orders": []})
    
    with open(WO_JSON, 'r') as f:
        return jsonify(json.load(f))

@ppm_api.route('/api/upload_assets', methods=['POST'])
def upload_assets():
    """Handles the premium Excel upload and refreshes the data matrix."""
    if 'file' not in request.files:
        return "No file part", 400
    
    file = request.files['file']
    if file.filename == '':
        return "No selected file", 400

    if file and file.filename.endswith('.xlsx'):
        # Save the new file to your static path
        file.save(ASSET_PATH)
        
        # Logic to trigger a re-index of the JSON data could go here
        return jsonify({"status": "success", "message": "Neural Matrix Updated"}), 200
    
    return "Invalid file format", 400