"""
ow_assets_patch.py
==================
Drop this file next to server.py and add ONE line at the bottom of server.py:

    import ow_assets_patch

That's it. This replaces the broken /ow_api/ppm/assets route.
"""
import io, traceback
from pathlib import Path
from flask import request, jsonify, session

# ── Import the app + decorators from the running server module ──
import server as _srv
app              = _srv.app
login_required   = _srv.login_required
require_property = _srv.require_property
pd               = _srv.pd
OW_ASSETS_XLS    = _srv.OW_ASSETS_XLS
OW_ASSETS_XLSX   = _srv.OW_ASSETS_XLSX
OW_DIR           = _srv.OW_DIR


# ── Remove the old broken route ──
app.view_functions.pop('ow_api_ppm_assets', None)
_old_rules = [r for r in app.url_map.iter_rules() if r.endpoint == 'ow_api_ppm_assets']
for r in _old_rules:
    app.url_map._rules.remove(r)
    app.url_map._rules_by_endpoint.pop('ow_api_ppm_assets', None)


# ── Register the fixed route ──
@app.route("/ow_api/ppm/assets")
@login_required
@require_property("ONEWEST")
def ow_api_ppm_assets():
    """Fixed: reads Equipment No. / Equipment Name columns from Asset.xls"""
    try:
        src = None
        for p in [OW_ASSETS_XLS, OW_ASSETS_XLSX]:
            if p.exists():
                src = p
                break
        if not src:
            print(f"[PATCH] No asset file in {OW_DIR}")
            return jsonify({"assets": [], "total": 0})

        print(f"[PATCH] Reading {src.name}")

        with open(src, 'rb') as fh:
            raw = fh.read()
        is_zip = raw[:2] == b'PK'

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
            print(f"[PATCH]   id={id_c} name={nm_c} dept={dp_c} loc={lc_c} ls={ls_c} nd={nd_c}")
            if not id_c:
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

        assets = []
        for sname, idx, ptype in [('inhouse_ppm', 0, 'inhouse'), ('vendor_ppm', 1, 'vendor')]:
            df = None
            for sheet_ref in [sname, idx]:
                for eng in (['openpyxl'] if is_zip else []) + ['xlrd']:
                    try:
                        if eng == 'openpyxl':
                            df = pd.read_excel(io.BytesIO(raw), sheet_name=sheet_ref, engine='openpyxl')
                        else:
                            df = pd.read_excel(src, sheet_name=sheet_ref, engine='xlrd')
                        print(f"[PATCH]   '{sname}' OK via {eng} ref={sheet_ref!r}: {len(df)} rows")
                        break
                    except Exception as e:
                        print(f"[PATCH]   '{sname}' {eng} ref={sheet_ref!r}: {e}")
                if df is not None:
                    break
            if df is not None:
                rows = _df_to_assets(df, ptype)
                print(f"[PATCH]   → {len(rows)} {ptype} assets")
                assets.extend(rows)

        # de-dup
        seen, unique = set(), []
        for a in assets:
            if a['id'] not in seen:
                seen.add(a['id'])
                unique.append(a)

        print(f"[PATCH] /ow_api/ppm/assets → {len(unique)} total")
        return jsonify({"assets": unique, "total": len(unique), "property": "ONEWEST"})

    except Exception as e:
        traceback.print_exc()
        return jsonify({"assets": [], "total": 0, "error": str(e)}), 500


print("[PATCH] ow_assets_patch.py loaded — /ow_api/ppm/assets replaced ✅")