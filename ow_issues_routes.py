"""
ONEWEST ISSUES ROUTES
Full CRUD for ONEWEST issues: create, read, update, close, reopen, export,
photo upload, archive (daily + scheduler), WhatsApp notification helpers.
"""
from flask import Blueprint, request, jsonify, session, send_file
from datetime import datetime
from werkzeug.utils import secure_filename
import json
import traceback
import pandas as pd
import io

from decorators import login_required, require_property
from config import BASE_DIR

ow_issues_bp = Blueprint("ow_issues", __name__)

# ── Paths ─────────────────────────────────────────────────────────────────────
OW_ISSUES_JSON    = BASE_DIR / "static" / "data" / "OW" / "issues.json"
OW_TECHNICIANS_JSON = BASE_DIR / "static" / "data" / "OW" / "technicians.json"
OW_SUPERVISORS_JSON = BASE_DIR / "static" / "data" / "OW" / "supervisors.json"
OW_ISSUES_UPLOADS = BASE_DIR / "uploads" / "OW" / "issues"
ISSUES_ARCHIVE_DIR = BASE_DIR / "uploads" / "OW" / "issues_archive"

ISSUES_ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
OW_ISSUES_UPLOADS.mkdir(parents=True, exist_ok=True)
OW_ISSUES_JSON.parent.mkdir(parents=True, exist_ok=True)


# ═════════════════════════════════════════════════════════════════════════════
# WHATSAPP NOTIFICATION HELPERS
# ═════════════════════════════════════════════════════════════════════════════

def send_ow_whatsapp_notification(issue, assigned_to):
    try:
        supervisors = []
        if OW_SUPERVISORS_JSON.exists():
            with open(OW_SUPERVISORS_JSON, "r", encoding="utf-8") as f:
                supervisors = json.load(f).get("supervisors", [])
        phone = supervisors[0]["phone"] if supervisors else "+919876543220"
        message = (f"🔴 *NEW ISSUE - ONEWEST*\n"
                   f"*Issue ID:* {issue['issue_id']}\n"
                   f"*Title:* {issue['title']}\n"
                   f"*Priority:* {issue['priority']}\n"
                   f"*Location:* {issue['location']}\n"
                   f"*Reported By:* {issue['reported_by']}\n"
                   f"*Assigned To:* {issue['assigned_to']}\n"
                   f"*Created:* {issue['created_at'][:16].replace('T',' ')}\n"
                   "Please take immediate action.")
        print(f"📱 WhatsApp notification prepared for {phone}")
        return True
    except Exception as e:
        print(f"❌ WhatsApp notification error: {str(e)}")
        return False


def send_ow_whatsapp_status_update(issue, new_status):
    try:
        supervisors = []
        if OW_SUPERVISORS_JSON.exists():
            with open(OW_SUPERVISORS_JSON, "r", encoding="utf-8") as f:
                supervisors = json.load(f).get("supervisors", [])
        phone = supervisors[0]["phone"] if supervisors else "+919876543220"
        message = (f"📊 *ISSUE STATUS UPDATE - ONEWEST*\n"
                   f"*Issue ID:* {issue['issue_id']}\n"
                   f"*Title:* {issue['title']}\n"
                   f"*New Status:* {new_status}\n"
                   f"*Updated:* {datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
                   "Please review the update.")
        print(f"📱 WhatsApp status update prepared for {phone}")
        return True
    except Exception as e:
        print(f"❌ WhatsApp status update error: {str(e)}")
        return False


# ═════════════════════════════════════════════════════════════════════════════
# ISSUES CRUD
# ═════════════════════════════════════════════════════════════════════════════

@ow_issues_bp.route("/ow_api/issues")
@login_required
@require_property("ONEWEST")
def ow_api_issues():
    try:
        if not OW_ISSUES_JSON.exists():
            return jsonify({"issues": [], "total": 0, "property": "ONEWEST"})
        with open(OW_ISSUES_JSON, "r", encoding="utf-8") as f:
            data = json.load(f)
        issues = data.get("issues", [])
        sf = request.args.get("status",   "all").lower()
        pf = request.args.get("priority", "all").lower()
        if sf != "all": issues = [i for i in issues if i.get("status","").lower() == sf]
        if pf != "all": issues = [i for i in issues if i.get("priority","").lower() == pf]
        return jsonify({"success": True, "issues": issues, "total": len(issues), "property": "ONEWEST"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e), "issues": []}), 500


@ow_issues_bp.route("/ow_api/issues/create", methods=["POST"])
@login_required
@require_property("ONEWEST")
def ow_api_create_issue():
    try:
        if request.content_type and "multipart/form-data" in request.content_type:
            title            = request.form.get("title", "Untitled")
            description      = request.form.get("description", "")
            priority         = request.form.get("priority", "Medium")
            category         = request.form.get("category", "General")
            location         = request.form.get("location", "")
            assigned_to      = request.form.get("assigned_to", "")
            sla_deadline     = request.form.get("sla_deadline", "")
            escalation_level = request.form.get("escalation_level", "Level 1")
            photos = []
            if "photos" in request.files:
                for file in request.files.getlist("photos"):
                    if file and file.filename:
                        fn = secure_filename(f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{file.filename}")
                        file.save(OW_ISSUES_UPLOADS / fn)
                        photos.append(f"/uploads/OW/issues/{fn}")
        else:
            data             = request.get_json() or {}
            title            = data.get("title", "Untitled")
            description      = data.get("description", "")
            priority         = data.get("priority", "Medium")
            category         = data.get("category", "General")
            location         = data.get("location", "")
            assigned_to      = data.get("assigned_to", "")
            sla_deadline     = data.get("sla_deadline", "")
            escalation_level = data.get("escalation_level", "Level 1")
            photos           = data.get("photos", [])

        if OW_ISSUES_JSON.exists():
            with open(OW_ISSUES_JSON, "r", encoding="utf-8") as f:
                ow_data = json.load(f)
        else:
            ow_data = {"issues": [], "last_updated": ""}

        counter  = len(ow_data.get("issues", [])) + 1
        issue_id = f"OW-ISS-{datetime.now().strftime('%Y')}-{str(counter).zfill(4)}"

        new_issue = {
            "issue_id": issue_id, "id": issue_id,
            "title": title, "description": description,
            "priority": priority, "status": "Open",
            "category": category, "location": location,
            "reported_by": session.get("user", "Unknown"),
            "assigned_to": assigned_to,
            "property": "ONEWEST", "property_code": "OW",
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "sla_deadline": sla_deadline,
            "escalation_level": escalation_level,
            "photos": photos, "whatsapp_sent": False,
        }

        ow_data["issues"].append(new_issue)
        ow_data["last_updated"] = datetime.now().isoformat()

        with open(OW_ISSUES_JSON, "w", encoding="utf-8") as f:
            json.dump(ow_data, f, indent=2)

        send_ow_whatsapp_notification(new_issue, assigned_to)
        return jsonify({"success": True, "issue_id": issue_id, "message": "Issue created successfully"})
    except Exception as e:
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500


@ow_issues_bp.route("/ow_api/issues/update/<issue_id>", methods=["PUT"])
@login_required
@require_property("ONEWEST")
def ow_api_update_issue(issue_id):
    try:
        data = request.get_json()
        if not OW_ISSUES_JSON.exists():
            return jsonify({"success": False, "error": "Issues file not found"}), 404
        with open(OW_ISSUES_JSON, "r", encoding="utf-8") as f:
            ow_data = json.load(f)
        updated = False
        for issue in ow_data.get("issues", []):
            if issue.get("issue_id") == issue_id:
                old_status = issue.get("status", "")
                for field in ("status", "priority", "assigned_to", "description",
                              "escalation_level", "resolution_notes"):
                    if field in data:
                        issue[field] = data[field]
                if "status" in data and data["status"] != old_status:
                    issue.setdefault("status_history", []).append({
                        "from": old_status, "to": data["status"],
                        "changed_at": datetime.now().isoformat(),
                        "changed_by": session.get("user", "system"),
                    })
                    send_ow_whatsapp_status_update(issue, data["status"])
                issue["updated_at"] = datetime.now().isoformat()
                updated = True
                break
        if not updated:
            return jsonify({"success": False, "error": "Issue not found"}), 404
        with open(OW_ISSUES_JSON, "w", encoding="utf-8") as f:
            json.dump(ow_data, f, indent=2)
        return jsonify({"success": True, "message": "Issue updated"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@ow_issues_bp.route("/ow_api/issues/close", methods=["POST"])
@login_required
@require_property("ONEWEST")
def ow_api_close_issue():
    try:
        data     = request.get_json()
        issue_id = data.get("issue_id")
        reason   = data.get("reason", "").strip()
        if not issue_id:
            return jsonify({"success": False, "error": "issue_id required"}), 400
        with open(OW_ISSUES_JSON, "r", encoding="utf-8") as f:
            db = json.load(f)
        found = False
        for iss in db.get("issues", []):
            if iss.get("id") == issue_id or iss.get("issue_id") == issue_id:
                iss["status"]    = "Closed"
                iss["closed_at"] = datetime.now().isoformat()
                iss["closed_by"] = session.get("user", "unknown")
                if reason:
                    iss["resolution_notes"] = reason
                iss.setdefault("status_history", []).append({
                    "status": "Closed", "timestamp": datetime.now().isoformat(),
                    "by": session.get("user", "unknown"), "note": reason or "Closed",
                })
                found = True
                break
        if not found:
            return jsonify({"success": False, "error": "Issue not found"}), 404
        with open(OW_ISSUES_JSON, "w", encoding="utf-8") as f:
            json.dump(db, f, indent=2, ensure_ascii=False)
        return jsonify({"success": True, "message": "Issue closed"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@ow_issues_bp.route("/ow_api/issues/reopen", methods=["POST"])
@login_required
@require_property("ONEWEST")
def ow_api_reopen_issue():
    try:
        data     = request.get_json()
        issue_id = data.get("issue_id")
        reason   = data.get("reason", "").strip()
        if not issue_id:
            return jsonify({"success": False, "error": "issue_id required"}), 400
        if not reason:
            return jsonify({"success": False, "error": "Reopen reason is required"}), 400
        with open(OW_ISSUES_JSON, "r", encoding="utf-8") as f:
            db = json.load(f)
        found = False
        for iss in db.get("issues", []):
            if iss.get("id") == issue_id or iss.get("issue_id") == issue_id:
                iss["status"]           = "Open"
                iss["reopened_at"]      = datetime.now().isoformat()
                iss["reopened_by"]      = session.get("user", "unknown")
                iss["resolution_notes"] = f"[Reopened] {reason}"
                iss.setdefault("status_history", []).append({
                    "status": "Open", "timestamp": datetime.now().isoformat(),
                    "by": session.get("user", "unknown"), "note": f"Reopened: {reason}",
                })
                found = True
                break
        if not found:
            return jsonify({"success": False, "error": "Issue not found"}), 404
        with open(OW_ISSUES_JSON, "w", encoding="utf-8") as f:
            json.dump(db, f, indent=2, ensure_ascii=False)
        return jsonify({"success": True, "message": "Issue reopened"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@ow_issues_bp.route("/ow_api/issues/export")
@login_required
@require_property("ONEWEST")
def ow_api_export_issues():
    try:
        if not OW_ISSUES_JSON.exists():
            return jsonify({"success": False, "error": "No issues to export"}), 404
        with open(OW_ISSUES_JSON, "r", encoding="utf-8") as f:
            ow_data = json.load(f)
        issues = ow_data.get("issues", [])
        if not issues:
            return jsonify({"success": False, "error": "No issues to export"}), 404
        df  = pd.DataFrame(issues)
        out = io.BytesIO()
        with pd.ExcelWriter(out, engine="openpyxl") as writer:
            df.to_excel(writer, index=False, sheet_name="ONEWEST Issues")
        out.seek(0)
        filename = f"ONEWEST_Issues_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        return send_file(out, mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                         as_attachment=True, download_name=filename)
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@ow_issues_bp.route("/ow_api/issues/stats")
@login_required
@require_property("ONEWEST")
def ow_api_issues_stats():
    try:
        if not OW_ISSUES_JSON.exists():
            return jsonify({"total":0,"open":0,"in_progress":0,"resolved":0,"closed":0,
                            "critical":0,"high":0,"medium":0,"low":0,"property":"ONEWEST"})
        with open(OW_ISSUES_JSON, "r", encoding="utf-8") as f:
            issues = json.load(f).get("issues", [])
        return jsonify({
            "total":       len(issues),
            "open":        len([i for i in issues if i.get("status") == "Open"]),
            "in_progress": len([i for i in issues if i.get("status") == "In Progress"]),
            "resolved":    len([i for i in issues if i.get("status") == "Resolved"]),
            "closed":      len([i for i in issues if i.get("status") == "Closed"]),
            "critical":    len([i for i in issues if i.get("priority") == "Critical"]),
            "high":        len([i for i in issues if i.get("priority") == "High"]),
            "medium":      len([i for i in issues if i.get("priority") == "Medium"]),
            "low":         len([i for i in issues if i.get("priority") == "Low"]),
            "property":    "ONEWEST",
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ═════════════════════════════════════════════════════════════════════════════
# PHOTO UPLOAD & SERVE
# ═════════════════════════════════════════════════════════════════════════════

@ow_issues_bp.route("/ow_api/issues/upload-photo", methods=["POST"])
@login_required
@require_property("ONEWEST")
def ow_api_upload_photo():
    try:
        if "photo" not in request.files:
            return jsonify({"success": False, "error": "No photo uploaded"}), 400
        file = request.files["photo"]
        if file.filename == "":
            return jsonify({"success": False, "error": "Empty filename"}), 400
        filename = secure_filename(f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{file.filename}")
        file.save(OW_ISSUES_UPLOADS / filename)
        return jsonify({"success": True, "photo_url": f"/uploads/OW/issues/{filename}",
                        "filename": filename})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@ow_issues_bp.route("/uploads/OW/issues/<filename>")
@login_required
def serve_ow_issue_photo(filename):
    from flask import send_from_directory
    return send_from_directory(OW_ISSUES_UPLOADS, filename)


# ═════════════════════════════════════════════════════════════════════════════
# ARCHIVE
# ═════════════════════════════════════════════════════════════════════════════

@ow_issues_bp.route("/ow_api/issues/archive-daily", methods=["POST"])
@login_required
@require_property("ONEWEST")
def ow_archive_daily_issues():
    try:
        today_str = datetime.now().date().strftime("%Y-%m-%d")
        if not OW_ISSUES_JSON.exists():
            return jsonify({"success": True, "message": "No issues to archive"})
        with open(OW_ISSUES_JSON, "r", encoding="utf-8") as f:
            ow_data = json.load(f)
        issues        = ow_data.get("issues", [])
        today_issues  = [i for i in issues if i.get("created_at","")[:10] == today_str]
        remaining     = [i for i in issues if i.get("created_at","")[:10] != today_str]
        if not today_issues:
            return jsonify({"success": True, "message": "No issues to archive today"})
        archive_file = ISSUES_ARCHIVE_DIR / f"OW_Issues_{today_str}.json"
        archive_data = {
            "date": today_str, "archived_at": datetime.now().isoformat(),
            "total_issues": len(today_issues), "issues": today_issues,
            "summary": {
                "open":        len([i for i in today_issues if i.get("status") == "Open"]),
                "in_progress": len([i for i in today_issues if i.get("status") == "In Progress"]),
                "resolved":    len([i for i in today_issues if i.get("status") == "Resolved"]),
                "closed":      len([i for i in today_issues if i.get("status") == "Closed"]),
            },
        }
        with open(archive_file, "w", encoding="utf-8") as f:
            json.dump(archive_data, f, indent=2)
        ow_data["issues"]       = remaining
        ow_data["last_updated"] = datetime.now().isoformat()
        with open(OW_ISSUES_JSON, "w", encoding="utf-8") as f:
            json.dump(ow_data, f, indent=2)
        return jsonify({"success": True, "archived_count": len(today_issues),
                        "remaining_count": len(remaining), "archive_file": archive_file.name})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@ow_issues_bp.route("/ow_api/issues/export-by-date")
@login_required
@require_property("ONEWEST")
def ow_export_issues_by_date():
    try:
        date_str     = request.args.get("date", datetime.now().strftime("%Y-%m-%d"))
        archive_file = ISSUES_ARCHIVE_DIR / f"OW_Issues_{date_str}.json"
        if archive_file.exists():
            with open(archive_file, "r", encoding="utf-8") as f:
                issues = json.load(f).get("issues", [])
        else:
            if not OW_ISSUES_JSON.exists():
                return jsonify({"error": "No issues found"}), 404
            with open(OW_ISSUES_JSON, "r", encoding="utf-8") as f:
                issues = [i for i in json.load(f).get("issues",[]) if i.get("created_at","")[:10] == date_str]
        if not issues:
            return jsonify({"error": "No issues found for this date"}), 404
        df  = pd.DataFrame(issues)
        out = io.BytesIO()
        with pd.ExcelWriter(out, engine="openpyxl") as writer:
            df.to_excel(writer, index=False, sheet_name=f"Issues_{date_str}")
        out.seek(0)
        return send_file(out, mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                         as_attachment=True, download_name=f"ONEWEST_Issues_{date_str}.xlsx")
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@ow_issues_bp.route("/ow_api/issues/archive-list")
@login_required
@require_property("ONEWEST")
def ow_get_archive_list():
    try:
        archives = {}
        if ISSUES_ARCHIVE_DIR.exists():
            for af in sorted(ISSUES_ARCHIVE_DIR.iterdir(), reverse=True):
                if af.suffix == ".json":
                    d = af.stem.replace("OW_Issues_", "")
                    try:
                        with open(af, "r", encoding="utf-8") as fh:
                            data = json.load(fh)
                        archives[d] = {"date": d, "total": data.get("total_issues",0),
                                       "summary": data.get("summary",{}), "source": "archive"}
                    except Exception:
                        pass
        if OW_ISSUES_JSON.exists():
            try:
                with open(OW_ISSUES_JSON, "r", encoding="utf-8") as fh:
                    ow_data = json.load(fh)
                for issue in ow_data.get("issues", []):
                    d = issue.get("created_at","")[:10]
                    if not d: continue
                    if d not in archives:
                        archives[d] = {"date": d, "total": 0,
                                       "summary": {"open":0,"in_progress":0,"resolved":0,"closed":0},
                                       "source": "live"}
                    if archives[d].get("source") == "live":
                        archives[d]["total"] += 1
                        st = issue.get("status","Open").lower().replace(" ","_")
                        archives[d]["summary"][st] = archives[d]["summary"].get(st,0) + 1
            except Exception:
                pass
        result = sorted(archives.values(), key=lambda x: x["date"], reverse=True)
        return jsonify({"success": True, "archives": result})
    except Exception as e:
        return jsonify({"success": False, "error": str(e), "archives": []}), 500


@ow_issues_bp.route("/ow_api/issues/view-archive/<date_str>")
@login_required
@require_property("ONEWEST")
def ow_view_archive(date_str):
    try:
        archive_file = ISSUES_ARCHIVE_DIR / f"OW_Issues_{date_str}.json"
        if archive_file.exists():
            with open(archive_file, "r", encoding="utf-8") as f:
                return jsonify({"success": True, "date": date_str, "data": json.load(f)})
        if not OW_ISSUES_JSON.exists():
            return jsonify({"success": False, "error": "No issues data found"}), 404
        with open(OW_ISSUES_JSON, "r", encoding="utf-8") as f:
            ow_data = json.load(f)
        date_issues = [i for i in ow_data.get("issues",[]) if i.get("created_at","")[:10] == date_str]
        if not date_issues:
            return jsonify({"success": False, "error": f"No issues found for {date_str}"}), 404
        return jsonify({"success": True, "date": date_str, "data": {
            "date": date_str, "archived_at": None,
            "total_issues": len(date_issues), "issues": date_issues,
            "summary": {
                "open":        len([i for i in date_issues if i.get("status") == "Open"]),
                "in_progress": len([i for i in date_issues if i.get("status") == "In Progress"]),
                "resolved":    len([i for i in date_issues if i.get("status") == "Resolved"]),
                "closed":      len([i for i in date_issues if i.get("status") == "Closed"]),
            },
        }})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# ═════════════════════════════════════════════════════════════════════════════
# AUTO-ARCHIVE SCHEDULER
# ═════════════════════════════════════════════════════════════════════════════

def auto_archive_issues():
    try:
        from flask import current_app
        with current_app.app_context():
            today_str = datetime.now().date().strftime("%Y-%m-%d")
            if not OW_ISSUES_JSON.exists():
                return
            with open(OW_ISSUES_JSON, "r", encoding="utf-8") as f:
                ow_data = json.load(f)
            issues       = ow_data.get("issues", [])
            today_issues = [i for i in issues if i.get("created_at","")[:10] == today_str]
            if not today_issues:
                return
            archive_file = ISSUES_ARCHIVE_DIR / f"OW_Issues_{today_str}.json"
            with open(archive_file, "w", encoding="utf-8") as f:
                json.dump({"date": today_str, "archived_at": datetime.now().isoformat(),
                            "total_issues": len(today_issues), "issues": today_issues,
                            "summary": {
                                "open":        len([i for i in today_issues if i.get("status") == "Open"]),
                                "in_progress": len([i for i in today_issues if i.get("status") == "In Progress"]),
                                "resolved":    len([i for i in today_issues if i.get("status") == "Resolved"]),
                                "closed":      len([i for i in today_issues if i.get("status") == "Closed"]),
                            }}, f, indent=2)
            remaining = [i for i in issues if i.get("created_at","")[:10] != today_str]
            ow_data["issues"]       = remaining
            ow_data["last_updated"] = datetime.now().isoformat()
            with open(OW_ISSUES_JSON, "w", encoding="utf-8") as f:
                json.dump(ow_data, f, indent=2)
            print(f"✅ Auto-archived {len(today_issues)} issues for {today_str}")
    except Exception as e:
        print(f"❌ Auto-archive failed: {str(e)}")


def setup_issue_archive_scheduler():
    from apscheduler.schedulers.background import BackgroundScheduler
    scheduler = BackgroundScheduler()
    scheduler.add_job(func=auto_archive_issues, trigger="cron",
                      hour=23, minute=59, timezone="Asia/Kolkata")
    scheduler.start()
    print("✅ Issue archive scheduler started: Daily at 11:59 PM IST")
    return scheduler
