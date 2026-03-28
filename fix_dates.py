import json
import os
from datetime import datetime

def standardize_work_order_dates():
    """Convert all date formats in work_orders.json to YYYY-MM-DD format AND fix key naming"""
    # Path to your work_orders.json (UPDATE THIS IF NEEDED)
    WO_PATH = r'C:\Users\Venu\Desktop\my_dashboard\static\data\work_orders.json'
    
    if not os.path.exists(WO_PATH):
        print(f"❌ Error: File not found at {WO_PATH}")
        return
    
    # Read the JSON file
    with open(WO_PATH, 'r') as f:
        data = json.load(f)
    
    # Process all work orders
    converted_count = 0
    for work_order in data.get('work_orders', []):
        # FIX 1: Clean all key names (remove trailing spaces)
        cleaned_work_order = {}
        for key, value in work_order.items():
            cleaned_key = key.strip()
            cleaned_work_order[cleaned_key] = value
        
        # FIX 2: Clean due_date value
        due_date = cleaned_work_order.get('due_date', '').strip()
        
        # FIX 3: Convert all date formats
        if due_date and due_date.strip():
            try:
                # Handle MM/DD/YYYY format
                if '/' in due_date:
                    parts = due_date.split('/')
                    if len(parts) == 3:
                        month = int(parts[0])
                        day = int(parts[1])
                        year = int(parts[2])
                        
                        # Handle 2-digit years
                        if year < 100:
                            year += 2000
                            
                        # Validate date components
                        if 1 <= month <= 12 and 1 <= day <= 31:
                            # Format as YYYY-MM-DD
                            cleaned_work_order['due_date'] = f"{year}-{month:02d}-{day:02d}"
                            converted_count += 1
                
                # Handle YYYY-MM-DD format (reformat to ensure consistency)
                elif '-' in due_date:
                    parts = due_date.split('-')
                    if len(parts) == 3 and len(parts[0]) == 4:
                        year = int(parts[0])
                        month = int(parts[1])
                        day = int(parts[2])
                        if 1 <= month <= 12 and 1 <= day <= 31:
                            cleaned_work_order['due_date'] = f"{year}-{month:02d}-{day:02d}"
                            converted_count += 1
            except Exception as e:
                print(f"⚠️ Error processing date {due_date}: {str(e)}")
        
        # Replace original work order with cleaned version
        work_order.clear()
        work_order.update(cleaned_work_order)
    
    # Write back to the file
    with open(WO_PATH, 'w') as f:
        json.dump(data, f, indent=2)
    
    print(f"\n✅ SUCCESS: Standardized {converted_count} work order dates")
    print(f"✅ File saved to: {WO_PATH}")
    print(f"✅ Next step: Restart your server and refresh the UI")

# Execute the function
if __name__ == "__main__":
    standardize_work_order_dates()