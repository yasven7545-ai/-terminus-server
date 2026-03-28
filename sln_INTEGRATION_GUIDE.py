"""
╔══════════════════════════════════════════════════════════════════════════════╗
║  SLN TERMINUS MMS  —  INTEGRATION GUIDE                                     ║
║  File: sln_INTEGRATION_GUIDE.py                                              ║
║  Purpose: Step-by-step setup without breaking existing routes/functions      ║
╚══════════════════════════════════════════════════════════════════════════════╝

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 FOLDER STRUCTURE  (add new, keep old)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  my_dashboard/                         ← project root (server.py lives here)
  ├── server.py                         ← DO NOT MODIFY existing code
  ├── sln_mms_routes.py                 ← NEW  ← copy here
  ├── sln_INTEGRATION_GUIDE.py          ← NEW  ← this file (docs only)
  │
  ├── templates/
  │   ├── sln_mms_dashboard.html        ← NEW  ← copy here
  │   └── ... (existing templates untouched)
  │
  └── static/
      └── data/
          ├── Assets.xlsx               ← SHARED with SLN PPM (same file)
          ├── supervisors.json          ← SHARED
          ├── technicians.json          ← SHARED
          ├── sln_work_orders.json      ← NEW  (auto-created on first WO)
          └── sln_amc_contracts.json    ← NEW  (auto-created on first AMC save)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 STEP 1 — COPY FILES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  Copy the following into your project root  (C:\\Users\\Venu\\Desktop\\my_dashboard\\):
    • sln_mms_routes.py
    • sln_INTEGRATION_GUIDE.py  (this file — docs only, not imported)

  Copy into  templates\\ :
    • sln_mms_dashboard.html

  The data files (Assets.xlsx, supervisors.json, technicians.json) already
  exist at  static\\data\\  — no action needed.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 STEP 2 — REGISTER BLUEPRINT IN server.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  Add the following TWO lines into server.py  — place them AFTER the existing
  safe_register() calls (around line 160), before  init_db(app) :

  ┌─────────────────────────────────────────────────────────────────────────┐
  │  # SLN MMS Dashboard                                                    │
  │  safe_register("sln_mms_routes", "sln_mms_bp")                         │
  └─────────────────────────────────────────────────────────────────────────┘

  That's it — the blueprint registers ALL /sln_api/mms/* endpoints plus
  the /sln_mms_dashboard  page route.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 STEP 3 — ADD LINK IN sln_terminus.html  (optional)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  To add a navigation button that opens the MMS dashboard from your SLN Terminus
  portal, insert this HTML snippet in your sln_terminus.html  sidebar or module
  grid:

  ┌─────────────────────────────────────────────────────────────────────────┐
  │  <a href="/sln_mms_dashboard"                                           │
  │     data-module="mms_dashboard"                                         │
  │     class="module-card">                                                │
  │    <i data-lucide="wrench"></i>                                         │
  │    MMS Dashboard                                                        │
  │  </a>                                                                   │
  └─────────────────────────────────────────────────────────────────────────┘

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 STEP 4 — UPDATE server.py STARTUP PRINT  (optional cosmetic)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  Inside the startup print block in server.py, add:
    📊 MMS (SLN):           http://localhost:5000/sln_mms_dashboard

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 API ENDPOINT REFERENCE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  All endpoints are prefixed with  /sln_api/mms/

  GET   /sln_api/mms/assets                  — list all assets from Assets.xlsx
  POST  /sln_api/mms/assets/import           — upload new Assets.xlsx
  GET   /sln_api/mms/stats                   — dashboard KPI counts
  GET   /sln_api/mms/workorders              — list work orders (?status=, ?priority=)
  GET   /sln_api/mms/workorders/by-date      — WOs for a specific date (?date=YYYY-MM-DD)
  GET   /sln_api/mms/workorders/export       — download WOs as Excel
  POST  /sln_api/mms/workflow/create         — create new work order
  POST  /sln_api/mms/workflow/update         — update WO fields
  POST  /sln_api/mms/workflow/close          — close/complete WO
  POST  /sln_api/mms/workorders/upload-image — attach image to WO
  GET   /sln_api/mms/technicians             — list all technicians
  GET   /sln_api/mms/supervisors             — list all supervisors
  GET   /sln_api/mms/amc/contracts           — list AMC contracts (?status=)
  POST  /sln_api/mms/amc/update              — create / update AMC contract
  POST  /sln_api/mms/amc/bulk-import         — import many contracts at once
  GET   /sln_api/mms/amc/contracts/export    — download AMC contracts as Excel
  POST  /sln_api/mms/trigger-daily-mail      — trigger daily mail for SLN Terminus

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 WHAT IS NOT CHANGED / TOUCHED
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  ✅  server.py             — only ONE safe_register line is added
  ✅  ppm_routes.py         — untouched  (OW routes use /ow_api/ppm/*)
  ✅  ppm_workflow_routes.py— untouched
  ✅  inventory_routes.py   — untouched
  ✅  workorders_routes.py  — untouched
  ✅  Any existing template — untouched
  ✅  work_orders.json      — untouched  (SLN uses sln_work_orders.json)
  ✅  ppm_data.json         — untouched

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 DATA FILES PATHS (absolute, Windows)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  C:\\Users\\Venu\\Desktop\\my_dashboard\\static\\data\\Assets.xlsx
  C:\\Users\\Venu\\Desktop\\my_dashboard\\static\\data\\supervisors.json
  C:\\Users\\Venu\\Desktop\\my_dashboard\\static\\data\\technicians.json
  C:\\Users\\Venu\\Desktop\\my_dashboard\\static\\data\\sln_work_orders.json   ← auto-created
  C:\\Users\\Venu\\Desktop\\my_dashboard\\static\\data\\sln_amc_contracts.json ← auto-created
"""

# This file is documentation only — nothing to execute.
if __name__ == "__main__":
    print(__doc__)