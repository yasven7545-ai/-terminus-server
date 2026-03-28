# --- Inventory endpoints (add these to your existing server.py safely) ---
# Place these imports at top of your server.py if not already present:
# from flask import send_from_directory, request, jsonify, Blueprint, current_app
# import pandas as pd
# from werkzeug.utils import secure_filename
# import os
# inventory_bp = Blueprint('inventory', __name__)
# and register blueprint: app.register_blueprint(inventory_bp)

from flask import send_from_directory, request, jsonify, Blueprint, current_app
import pandas as pd
from werkzeug.utils import secure_filename
import os
from pathlib import Path

inventory_bp = Blueprint('inventory', __name__)

DATA_DIR = Path(os.getenv('INVENTORY_DIR', 'data'))  # adapt to your existing data folder
DATA_DIR.mkdir(parents=True, exist_ok=True)
MASTER = DATA_DIR / 'inventory_master.xlsx'
TRAN = DATA_DIR / 'inventory_transactions.xlsx'

@inventory_bp.route('/inventory/download_master')
def download_master():
    # Sends the master excel file for download
    if not MASTER.exists():
        # create a minimal template if missing
        df = pd.DataFrame(columns=['Item_Code','Item_Name','Department','Unit','Opening_Stock','Stock_In','Stock_Out','Current_Stock','Min_Stock_Level','Last_Updated','Remarks'])
        df.to_excel(MASTER, index=False)
    return send_from_directory(str(MASTER.parent), MASTER.name, as_attachment=True)

@inventory_bp.route('/inventory/download_transactions')
def download_transactions():
    if not TRAN.exists():
        df = pd.DataFrame(columns=['Date','Item_Code','Item_Name','Department','Type','Quantity','Remarks','Transaction_ID'])
        df.to_excel(TRAN, index=False)
    return send_from_directory(str(TRAN.parent), TRAN.name, as_attachment=True)

@inventory_bp.route('/inventory/upload_master', methods=['POST'])
def upload_master():
    # Accept an uploaded master excel to replace the server copy
    f = request.files.get('file')
    if not f:
        return 'No file', 400
    filename = secure_filename(f.filename)
    save_path = MASTER
    f.save(str(save_path))
    return 'Uploaded', 200

@inventory_bp.route('/inventory/json_master')
def json_master():
    # Return current master sheet as JSON for the dashboard
    if not MASTER.exists():
        return jsonify([])
    try:
        df = pd.read_excel(MASTER, sheet_name=0)
        # ensure expected columns exist
        expected = ['Item_Code','Item_Name','Department','Unit','Opening_Stock','Stock_In','Stock_Out','Current_Stock','Min_Stock_Level','Last_Updated','Remarks']
        for c in expected:
            if c not in df.columns:
                df[c] = ''
        records = df[expected].fillna('').to_dict(orient='records')
        return jsonify(records)
    except Exception as e:
        return jsonify({'error': str(e)}), 500



@inventory_bp.route('/inventory/update', methods=['POST'])
def update_stock():
    data = request.get_json()
    item_code = data.get('item_code')
    tx_type = data.get('type')  # 'IN' or 'OUT'
    quantity = int(data.get('quantity', 0))

    if not MASTER.exists():
        return jsonify({"error": "Master file not found"}), 404

    try:
        # 1. Update Master Excel
        df = pd.read_excel(MASTER)
        if item_code not in df['Item_Code'].values:
            return jsonify({"error": "Item code not found in Master"}), 404

        idx = df[df['Item_Code'] == item_code].index[0]
        
        if tx_type == 'IN':
            df.at[idx, 'Stock_In'] = float(df.at[idx, 'Stock_In'] or 0) + quantity
        else:
            df.at[idx, 'Stock_Out'] = float(df.at[idx, 'Stock_Out'] or 0) + quantity

        # Recalculate Current Stock: Opening + In - Out
        opening = float(df.at[idx, 'Opening_Stock'] or 0)
        s_in = float(df.at[idx, 'Stock_In'] or 0)
        s_out = float(df.at[idx, 'Stock_Out'] or 0)
        df.at[idx, 'Current_Stock'] = opening + s_in - s_out
        df.at[idx, 'Last_Updated'] = datetime.now().strftime("%Y-%m-%d")

        df.to_excel(MASTER, index=False)

        # 2. Log to Transactions Excel
        new_tx = {
            'Date': datetime.now().strftime("%Y-%m-%d %H:%M"),
            'Item_Code': item_code,
            'Item_Name': df.at[idx, 'Item_Name'],
            'Department': df.at[idx, 'Department'],
            'Type': tx_type,
            'Quantity': quantity,
            'Transaction_ID': f"TX{int(datetime.now().timestamp())}"
        }
        
        if TRAN.exists():
            tdf = pd.read_excel(TRAN)
            tdf = pd.concat([tdf, pd.DataFrame([new_tx])], ignore_index=True)
        else:
            tdf = pd.DataFrame([new_tx])
        
        tdf.to_excel(TRAN, index=False)

        return jsonify({"success": True, "new_stock": df.at[idx, 'Current_Stock']})
    except Exception as e:
        return jsonify({"error": str(e)}), 500