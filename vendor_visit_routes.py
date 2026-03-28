from flask import Blueprint, request, jsonify
import sqlite3
from datetime import datetime
from twilio.rest import Client

# ---------------- CONFIG ----------------
TWILIO_SID = "ACd73eaebb461a85a8511876a149d1e65f"
TWILIO_TOKEN = "e5014a47e914974567c6496b141c006c"
WHATSAPP_FROM = "whatsapp:+14155238886"

DB = "vendor_visits.db"

vendor_visit_bp = Blueprint("vendor_visit_bp", __name__)

def get_db():
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    return con

# ---------------- WHATSAPP ----------------
def send_whatsapp(phone, vendor, date, status):
    if not phone:
        return

    client = Client(TWILIO_SID, TWILIO_TOKEN)
    client.messages.create(
        from_=WHATSAPP_FROM,
        to=f"whatsapp:+91{phone}",
        body=f"""Vendor Visit Approved ✅

Vendor: {vendor}
Date: {date}
Status: {status}
"""
    )

# ---------------- AUDIT ----------------
def log_audit(visit_id, action, user="WB"):
    with get_db() as con:
        con.execute("""
            INSERT INTO vendor_visit_audit
            (visit_id, action, by_user, action_time)
            VALUES (?, ?, ?, ?)
        """, (
            visit_id,
            action,
            user,
            datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        ))

# ---------------- SAVE ----------------
@vendor_visit_bp.route("/api/vendor_visit/save", methods=["POST"])
def save_visit():
    d = request.json

    with get_db() as con:
        con.execute("""
            INSERT INTO vendor_visits
            (date, vendor, category, in_time, out_time, status,
             phone, photo, id_photo, signature)
            VALUES (?,?,?,?,?,?,?,?,?,?)
        """, (
            d.get("date"),
            d.get("vendor"),
            d.get("category"),
            d.get("inTime"),
            d.get("outTime"),
            d.get("status", "Pending"),
            d.get("phone"),
            d.get("photo"),
            d.get("idPhoto"),
            d.get("signature")
        ))

    return jsonify({"ok": True})

# ---------------- LIST ----------------
@vendor_visit_bp.route("/api/vendor_visit/list", methods=["GET"])
def list_visits():
    with get_db() as con:
        rows = con.execute("""
            SELECT
              id, date, vendor, category,
              in_time, out_time, status,
              phone, photo, id_photo, signature
            FROM vendor_visits
            ORDER BY id DESC
        """).fetchall()

    return jsonify([dict(r) for r in rows])

# ---------------- APPROVE ----------------
@vendor_visit_bp.route("/api/vendor_visit/approve", methods=["POST"])
def approve_visit():
    data = request.json
    vid = data.get("id")

    with get_db() as con:
        row = con.execute("""
            SELECT phone, vendor, date, status
            FROM vendor_visits
            WHERE id=?
        """, (vid,)).fetchone()

        if not row:
            return jsonify({"error": "Invalid ID"}), 404

        phone, vendor, date, status = row

        if status == "Approved":
            return jsonify({"ok": True})  # already approved

        con.execute("""
            UPDATE vendor_visits
            SET status='Approved'
            WHERE id=?
        """, (vid,))

    # ---------------- ASYNC WHATSAPP ----------------
    import threading

    if phone and len(str(phone)) == 10:
        threading.Thread(
            target=send_whatsapp,
            args=(phone, vendor, date, "Approved"),
            daemon=True
        ).start()

    # ---------------- AUDIT LOG ----------------
    log_audit(vid, "APPROVED")

    return jsonify({"ok": True})
