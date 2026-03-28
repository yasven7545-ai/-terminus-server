"""
DAILY MAINTENANCE SCHEDULER - STANDALONE
Generates work orders for assets due today or overdue
Schedule this script using Windows Task Scheduler at 8:30 AM daily
"""
import sys
import os
from datetime import datetime, date, timedelta
from pathlib import Path
import pandas as pd
import json
import traceback

# Add project root to path
BASE_DIR = Path(__file__).parent.resolve()
sys.path.insert(0, str(BASE_DIR))

# File paths
ASSETS_XLSX = BASE_DIR / "static" / "data" / "Assets.xlsx"
WO_JSON = BASE_DIR / "static" / "data" / "work_orders.json"
WO_JSON.parent.mkdir(parents=True, exist_ok=True)

def parse_date_safely(date_value):
    """Safely parse various date formats from Excel"""
    if pd.isna(date_value) or date_value == '' or date_value is None:
        return None
    
    # Try multiple formats
    formats = [
        '%m/%d/%y',    # 1/30/25
        '%m/%d/%Y',    # 1/30/2025
        '%Y-%m-%d',    # 2026-01-30
        '%d-%m-%Y',    # 30-01-2026
    ]
    
    # Try direct conversion first
    try:
        if isinstance(date_value, (datetime, date)):
            return date_value.date() if isinstance(date_value, datetime) else date_value
        
        # Convert Excel serial date (float)
        if isinstance(date_value, (int, float)):
            # Excel date serial starts from 1900-01-01
            base_date = datetime(1899, 12, 30)
            return (base_date + timedelta(days=int(date_value))).date()
        
        # Try string formats
        date_str = str(date_value).strip()
        for fmt in formats:
            try:
                return datetime.strptime(date_str, fmt).date()
            except:
                continue
        
        # Fallback: try pandas parser
        parsed = pd.to_datetime(date_value, errors='coerce')
        if not pd.isna(parsed):
            return parsed.date()
            
    except Exception as e:
        print(f"Date parse warning for '{date_value}': {str(e)}")
        return None
    
    return None

def process_daily_ppm():
    """Generate work orders for assets due today or overdue"""
    print(f"\n[✅] Initializing Daily 8:30 AM PPM Scan...")
    print(f"    Assets File: {ASSETS_XLSX}")
    print(f"    Work Orders File: {WO_JSON}")
    
    # Load existing work orders
    existing_wos = []
    if WO_JSON.exists():
        try:
            with open(WO_JSON, 'r', encoding='utf-8') as f:
                data = json.load(f)
                existing_wos = data.get('work_orders', [])
        except Exception as e:
            print(f"⚠️  Error reading existing work orders: {str(e)}")
    
    # Track existing WOs by asset and date to prevent duplicates
    existing_wo_map = {}
    for wo in existing_wos:
        key = (wo.get('asset_id'), wo.get('due_date'))
        existing_wo_map[key] = wo
    
    # Load assets from Excel
    if not ASSETS_XLSX.exists():
        print(f"❌ ERROR: Assets.xlsx not found at {ASSETS_XLSX}")
        return False
    
    try:
        df = pd.read_excel(ASSETS_XLSX)
        print(f"✅ Loaded {len(df)} assets from Assets.xlsx")
    except Exception as e:
        print(f"❌ ERROR reading Assets.xlsx: {str(e)}")
        traceback.print_exc()
        return False
    
    # Process assets
    today = date.today()
    new_wos = []
    wo_counter = len(existing_wos) + 1
    
    print(f"\n[🔍] Scanning for assets due today ({today}) or overdue...")
    
    for idx, row in df.iterrows():
        asset_id = str(row.get('Asset Code', '')).strip()
        asset_name = str(row.get('Asset Name', 'Unknown Asset')).strip()
        location = str(row.get('Location', 'Unknown Location')).strip()
        next_due_raw = row.get('nextDueDate', '')
        
        # Skip invalid assets
        if not asset_id or asset_id.lower() in ['nan', 'none', '']:
            continue
        
        # Parse due date safely
        next_due_date = parse_date_safely(next_due_raw)
        
        # Skip if date couldn't be parsed
        if next_due_date is None:
            print(f"   ⚠️  Skipping asset {asset_id} - invalid date: '{next_due_raw}'")
            continue
        
        # Check if due today or overdue
        if next_due_date <= today:
            # Create unique key for duplicate check
            wo_key = (asset_id, next_due_date.isoformat())
            
            # Skip if work order already exists for this asset/date
            if wo_key in existing_wo_map:
                print(f"   ⏭️  Skipped (duplicate): {asset_id} - {asset_name}")
                continue
            
            # Determine priority based on criticality
            priority = "Low"
            asset_name_lower = asset_name.lower()
            if "fire" in asset_name_lower or "dg" in asset_name_lower.replace(' ', '') or "transformer" in asset_name_lower:
                priority = "High"
            elif next_due_date < today:
                priority = "High"
            elif next_due_date == today:
                priority = "Medium"
            
            # Determine status
            status = "open"
            if next_due_date < today:
                status = "overdue"
            
            # Generate work order ID
            wo_id = f"WO-PPM-{today.strftime('%Y-%m')}-{str(wo_counter).zfill(4)}"
            wo_counter += 1
            
            # Create work order
            wo = {
                "work_order_id": wo_id,
                "asset_id": asset_id,
                "asset_name": asset_name,
                "location": location,
                "due_date": next_due_date.isoformat(),
                "priority": priority,
                "status": status,
                "created_at": datetime.now().isoformat()
            }
            
            new_wos.append(wo)
            status_icon = "🔴" if status == "overdue" else "🟡" if status == "open" else "🟢"
            print(f"   {status_icon} Created: {wo_id} | {asset_name} | {priority} Priority | Due: {next_due_date}")
    
    # Merge new work orders with existing
    all_wos = existing_wos + new_wos
    
    # Save to JSON file
    try:
        with open(WO_JSON, 'w', encoding='utf-8') as f:
            json.dump({
                "work_orders": all_wos,
                "last_updated": datetime.now().isoformat(),
                "total_count": len(all_wos)
            }, f, indent=2, ensure_ascii=False)
        print(f"\n✅ Generated {len(new_wos)} new work orders")
        print(f"✅ Total work orders: {len(all_wos)}")
        print(f"✅ Saved to {WO_JSON}")
    except Exception as e:
        print(f"❌ ERROR saving work orders: {str(e)}")
        traceback.print_exc()
        return False
    
    # Show summary
    print(f"\n[📊] DAILY PPM SCAN COMPLETE")
    print(f"    • Total Assets Scanned: {len(df)}")
    print(f"    • Assets Due/Overdue: {len(new_wos)}")
    print(f"    • New Work Orders Created: {len(new_wos)}")
    print(f"    • Total Work Orders in System: {len(all_wos)}")
    
    return True

def main():
    """Main execution"""
    print("="*70)
    print(" ⚙️  TERMINUS MMS - DAILY WORK ORDER GENERATOR")
    print("="*70)
    print(f"Execution Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*70)
    
    try:
        success = process_daily_ppm()
        
        if success:
            print("\n✅ DAILY RUN COMPLETED SUCCESSFULLY")
        else:
            print("\n❌ DAILY RUN FAILED - See errors above")
            return 1
            
    except Exception as e:
        print(f"\n❌ CRITICAL ERROR: {str(e)}")
        traceback.print_exc()
        return 1
    
    print("="*70)
    return 0

if __name__ == "__main__":
    sys.exit(main())