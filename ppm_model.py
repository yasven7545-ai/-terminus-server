import pandas as pd
import json
import os
from datetime import datetime

# Centralizing paths for high-speed access
BASE_DIR = r'C:\Users\Venu\Desktop\my_dashboard'
ASSET_PATH = os.path.join(BASE_DIR, 'static', 'data', 'Assets.xlsx')
DATA_JSON = os.path.join(BASE_DIR, 'ppm_data.json')
WO_JSON = os.path.join(BASE_DIR, 'work_orders.json')

class AssetModel:
    """Handles the extraction and normalization of Asset data from Excel."""
    
    @staticmethod
    def get_all_assets():
        if not os.path.exists(ASSET_PATH):
            return []
        
        # Load Excel with high-performance engine
        df = pd.read_excel(ASSET_PATH)
        
        # Convert to standard Python dictionary with mapped keys
        assets = []
        for _, row in df.iterrows():
            assets.append({
                "id": str(row.get('Asset ID', row.get('id', ''))),
                "name": str(row.get('Asset Name', row.get('name', 'Unknown'))),
                "category": str(row.get('Category', 'General')),
                "location": str(row.get('Location', 'N/A')),
                "frequency": str(row.get('Service Frequency', 'Monthly')),
                "last_service": str(row.get('Last Service Date', '')),
                "next_due": str(row.get('Next Due Date', ''))
            })
        return assets

class WorkOrderModel:
    """Handles the persistence of the Work Order lifecycle."""
    
    @staticmethod
    def load_orders():
        if not os.path.exists(WO_JSON):
            return {"work_orders": []}
        try:
            with open(WO_JSON, 'r') as f:
                return json.load(f)
        except json.JSONDecodeError:
            return {"work_orders": []}

    @staticmethod
    def save_orders(data):
        with open(WO_JSON, 'w') as f:
            json.dump(data, f, indent=4)

    @staticmethod
    def update_status(wo_id, new_status, technician_remarks=None):
        """Transition a WO from OPEN to CLOSED with audit data."""
        data = WorkOrderModel.load_orders()
        for wo in data['work_orders']:
            if wo['work_order_id'] == wo_id:
                wo['status'] = new_status
                wo['updated_at'] = datetime.now().isoformat()
                if technician_remarks:
                    wo['remarks'] = technician_remarks
                break
        WorkOrderModel.save_orders(data)
        return True

class DashboardModel:
    """Calculates high-level metrics for the Neural HUD."""
    
    @staticmethod
    def get_neural_stats():
        assets = AssetModel.get_all_assets()
        orders = WorkOrderModel.load_orders().get('work_orders', [])
        
        total_assets = len(assets)
        pending = len([w for w in orders if w['status'] == 'open'])
        completed = len([w for w in orders if w['status'] == 'closed'])
        
        # Calculate Compliance %
        compliance = 100 if total_assets == 0 else round(((total_assets - pending) / total_assets) * 100, 1)
        
        return {
            "total_assets": total_assets,
            "pending_ppm": pending,
            "completed_ppm": completed,
            "compliance_rate": compliance
        }