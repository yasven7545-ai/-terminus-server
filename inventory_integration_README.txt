Inventory PDF Reports + Server-side Alerts (Integration Notes)

Files created (place into your project root next to server.py):
 - inventory_routes.py
 - inventory_scheduler.py

Safe integration steps (Option C, non-invasive):
1) Copy both files to the same folder as your existing server.py (they are already placed in /mnt/data; move into your project).
2) In server.py, add these two lines *somewhere after other safe_register calls* (no other edits to logic required):
     safe_register("inventory_routes", "inventory_bp", url_prefix="/inventory")
     import inventory_scheduler
     inventory_scheduler.start()
   The safe_register call registers the blueprint; the start() call launches the background alert worker.
3) Ensure pandas and reportlab are available in your environment:
     pip install pandas reportlab openpyxl
4) Optionally set environment variable INVENTORY_MASTER_FILE to point to your inventory Excel:
     export INVENTORY_MASTER_FILE=/path/to/inventory_master.xlsx
   If not set, the code will look at:
     ./uploads/inventory_master.xlsx
     ./static/data/inventory_master.xlsx
5) Endpoints:
   - GET /inventory/pdf/<department>   -> downloads PDF for department (e.g. /inventory/pdf/Electrical)
   - GET /inventory/alerts             -> returns JSON array of currently flagged alerts
6) Client-side:
   - Add a button that navigates to /inventory/pdf/<dept> to download reports.
   - Your inventory_dashboard.html can poll /inventory/alerts to display current alerts.

Notes:
 - The code is intentionally defensive: it tolerates different column names (Item, Item_Code, Qty, Current_Stock, Min_Stock_Level).
 - No changes were made to your existing server.py logic; you only need to register the blueprint and start scheduler.

If you want, I can prepare a ready-to-paste patch for server.py that only inserts the two lines needed (printed as a small diff) so you can copy-paste safely.