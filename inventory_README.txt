
Files created in /mnt/data:
- inventory_master.xlsx        (template master inventory file)
- inventory_transactions.xlsx  (transactions template)
- inventory_dashboard.html     (dark theme front-end to place in your web root)
- inventory_server_snippet.py  (Flask blueprint snippet - add to your server.py)

Notes:
1) The HTML expects these endpoints (add the blueprint or routes as provided):
   - GET /inventory/json_master         -> returns JSON array of inventory rows
   - GET /inventory/download_master     -> download current master Excel
   - POST /inventory/upload_master      -> upload new master Excel (multipart/form-data 'file')
   - GET /inventory/download_transactions -> download transactions Excel

2) The HTML will redirect 'Back' to sln_terminus.html (as requested).
3) The server snippet is safe to add: it's a blueprint; register it with app.register_blueprint(inventory_bp).
4) Adjust DATA_DIR/MASTER path if your app stores files elsewhere (the snippet uses environment var INVENTORY_DIR if set).

