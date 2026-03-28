"""
═══════════════════════════════════════════════════════════════
SLN HK MODULE — SERVER.PY INTEGRATION SNIPPET
═══════════════════════════════════════════════════════════════
Add the lines below to your existing server.py

FILE PLACEMENT:
  • sln_hk_routes.py  → same folder as server.py
  • sln_hk.html       → templates/  folder
  • Excel data file   → auto-created at static/data/sln_hk_data.xlsx
═══════════════════════════════════════════════════════════════
"""

# ── ADD THIS LINE with your other safe_register calls ─────────
safe_register("sln_hk_routes", "sln_hk_bp")

# ── ADD THIS to the startup print block ───────────────────────
# 🧹 HK Dashboard:          http://localhost:5000/sln_hk/

# ══════════════════════════════════════════════════════════════
# ROUTE MAP  (all prefixed /sln_hk)
# ══════════════════════════════════════════════════════════════
# GET  /sln_hk/                        → sln_hk_dashboard (HTML page)
# GET  /sln_hk/api/sln_hk_kpi         → KPI summary JSON
# GET  /sln_hk/api/sln_hk_tasks       → all tasks
# POST /sln_hk/api/sln_hk_tasks       → add task
# PUT  /sln_hk/api/sln_hk_tasks/<id>  → update task
# DEL  /sln_hk/api/sln_hk_tasks/<id>  → delete task
# GET  /sln_hk/api/sln_hk_checklist   → all checklist entries
# POST /sln_hk/api/sln_hk_checklist   → add checklist entry
# PUT  /sln_hk/api/sln_hk_checklist/<id> → update checklist entry
# GET  /sln_hk/api/sln_hk_staff       → staff directory
# GET  /sln_hk/api/sln_hk_rooms       → all rooms
# PUT  /sln_hk/api/sln_hk_rooms/<id>  → update room status
# GET  /sln_hk/api/sln_hk_inventory   → HK inventory
# POST /sln_hk/api/sln_hk_inventory/update → stock IN/OUT
# GET  /sln_hk/api/sln_hk_chart_data  → chart data
# GET  /sln_hk/api/sln_hk_export      → download Excel