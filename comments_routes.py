# comments_routes.py
from flask import Blueprint, request, jsonify, g
import sqlite3
from pathlib import Path
from datetime import datetime

comments_bp = Blueprint("comments", __name__, url_prefix="/api/comments")
DB_PATH = Path.cwd() / "database" / "issues.db"

def get_db():
    db = getattr(g, "_comments_db", None)
    if db is None:
        db = sqlite3.connect(str(DB_PATH))
        db.row_factory = sqlite3.Row
        g._comments_db = db
    return db

@comments_bp.teardown_app_request
def close_db(error=None):
    db = getattr(g, "_comments_db", None)
    if db is not None:
        db.close()

def init_comments():
    # table created by issues init; this just ensures DB exists
    conn = sqlite3.connect(str(DB_PATH))
    conn.close()

@comments_bp.route("/add", methods=["POST"])
def add_comment():
    d = request.get_json() or request.form
    issue_id = d.get("issue_id")
    author = d.get("author", "Unknown")
    comment = d.get("comment", "")
    if not issue_id or not comment:
        return jsonify({"ok": False, "error": "issue_id and comment required"}), 400
    db = get_db()
    db.execute("INSERT INTO comments (issue_id, author, comment, created_at) VALUES (?,?,?,?)",
               (issue_id, author, comment, datetime.utcnow().isoformat()))
    db.commit()
    return jsonify({"ok": True})

@comments_bp.route("/list/<issue_id>", methods=["GET"])
def list_comments(issue_id):
    db = get_db()
    rows = db.execute("SELECT * FROM comments WHERE issue_id=? ORDER BY id ASC", (issue_id,)).fetchall()
    return jsonify([dict(r) for r in rows])
