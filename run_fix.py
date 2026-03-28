"""
run_fix.py - Run this INSTEAD of server.py to apply the asset fix automatically.

Usage:
    python run_fix.py

This starts your normal Flask server but with the asset route fixed.
"""
import sys, os

# ── Make sure we're in the right directory ──
script_dir = os.path.dirname(os.path.abspath(__file__))
os.chdir(script_dir)
sys.path.insert(0, script_dir)

print("=" * 60)
print("OW ASSET FIX - Starting patched server")
print("=" * 60)

# ── Test asset reading BEFORE starting Flask ──
from pathlib import Path
import pandas as pd, io

OW_DIR = Path("static/data/OW")
src = OW_DIR / "Asset.xls"
if not src.exists():
    src = OW_DIR / "Asset.xlsx"

print(f"\n[PRE-CHECK] Asset file: {src} exists={src.exists()}")

if src.exists():
    with open(src, 'rb') as f:
        raw = f.read()
    print(f"[PRE-CHECK] File size: {len(raw):,} bytes, magic: {raw[:4].hex()}")
    
    # Test read
    try:
        df = pd.read_excel(src, sheet_name='inhouse_ppm', engine='xlrd')
        print(f"[PRE-CHECK] inhouse_ppm: {len(df)} rows, cols: {list(df.columns[:5])}")
        # Count non-empty Equipment No.
        if 'Equipment No.' in df.columns:
            valid = df['Equipment No.'].dropna().astype(str).str.strip()
            valid = valid[valid.str.lower() != 'nan']
            print(f"[PRE-CHECK] Valid 'Equipment No.' entries: {len(valid)}")
            print(f"[PRE-CHECK] Sample: {list(valid[:3])}")
    except Exception as e:
        print(f"[PRE-CHECK] ERROR: {e}")

print("\n[INFO] Starting Flask server with patched route...\n")

# ── Load server normally ──
import importlib
srv = importlib.import_module('server')
app = srv.app

# ── Patch the broken route ──
def _pick(cols, *names):
    for n in names:
        if n in cols: return n
    return None

def _df_to_assets(df, ppm_type):
    cols = list(df.columns)
    id_c = _pick(cols, 'Equipment No.', 'Asset Code', 'Equipment No')
    nm_c = _pick(cols, 'Equipment Name', 'Asset Name')
    dp_c = _pick(cols, 'Trade', 'Department', 'Equipment Type', 'Category')
    lc_c = _pick(cols, 'Location')
    ls_c = _pick(cols, 'Last Service', 'Last Service Of PPM')
    nd_c = _pick(cols, 'Next DueDate', 'nextDueDate', 'Next Due Date')
    print(f"[PATCH] _df_to_assets: id={id_c} name={nm_c} dept={dp_c} loc={lc_c} ls={ls_c} nd={nd_c}")
    if not id_c:
        print("[PATCH] ERROR: No ID column found!")
        return []
    out = []
    for _, row in df.iterrows():
        eid = str(row[id_c]).strip()
        if not eid or eid.lower() in ('nan', 'none', ''):
            continue
        def v(c):
            if not c: return ''
            s = str(row[c]).strip()
            return '' if s.lower() in ('nan', 'none') else s
        dept = v(dp_c) or 'General'
        out.append({
            "id": eid, "asset_code": eid,
            "name": v(nm_c) or eid, "asset_name": v(nm_c) or eid,
            "department": dept, "trade": dept, "category": dept,
            "location": v(lc_c) or 'ONEWEST',
            "lastService": v(ls_c), "last_service": v(ls_c),
            "nextDueDate": v(nd_c), "next_due": v(nd_c),
            "ppm_type": ppm_type, "property": "ONEWEST",
        })
    return out

from flask import request, jsonify

# Remove old route
app.view_functions.pop('ow_api_ppm_assets', None)
rules_to_remove = [r for r in list(app.url_map.iter_rules()) 
                   if r.endpoint == 'ow_api_ppm_assets']
for r in rules_to_remove:
    app.url_map._rules.remove(r)
app.url_map._rules_by_endpoint.pop('ow_api_ppm_assets', None)
print(f"[PATCH] Removed {len(rules_to_remove)} old route(s)")

@app.route("/ow_api/ppm/assets")
@srv.login_required
@srv.require_property("ONEWEST")
def ow_api_ppm_assets():
    try:
        src = None
        for p in [srv.OW_ASSETS_XLS, srv.OW_ASSETS_XLSX]:
            if p.exists():
                src = p
                break
        if not src:
            return jsonify({"assets": [], "total": 0, "error": "No file"})

        print(f"[PATCH] /ow_api/ppm/assets reading: {src.name}")
        with open(src, 'rb') as fh:
            raw = fh.read()
        is_zip = raw[:2] == b'PK'

        assets = []
        for sname, idx, ptype in [('inhouse_ppm', 0, 'inhouse'), ('vendor_ppm', 1, 'vendor')]:
            df = None
            for ref in [sname, idx]:
                for eng in (['openpyxl'] if is_zip else []) + ['xlrd']:
                    try:
                        if eng == 'openpyxl':
                            df = pd.read_excel(io.BytesIO(raw), sheet_name=ref, engine='openpyxl')
                        else:
                            df = pd.read_excel(src, sheet_name=ref, engine='xlrd')
                        print(f"[PATCH]   '{sname}' OK ({eng}, ref={ref!r}): {len(df)} rows")
                        break
                    except Exception as e:
                        pass
                if df is not None:
                    break
            if df is not None:
                rows = _df_to_assets(df, ptype)
                print(f"[PATCH]   → {len(rows)} assets")
                assets.extend(rows)

        seen, unique = set(), []
        for a in assets:
            if a['id'] not in seen:
                seen.add(a['id'])
                unique.append(a)
        print(f"[PATCH] Total: {len(unique)}")
        return jsonify({"assets": unique, "total": len(unique), "property": "ONEWEST"})
    except Exception as e:
        import traceback; traceback.print_exc()
        return jsonify({"assets": [], "total": 0, "error": str(e)}), 500

print("[PATCH] ✅ /ow_api/ppm/assets route replaced\n")

# ── Start Flask (same as server.py does) ──
if hasattr(srv, 'socketio'):
    srv.socketio.run(app, host='0.0.0.0', port=5000, debug=False, allow_unsafe_werkzeug=True)
else:
    app.run(host='0.0.0.0', port=5000, debug=False)