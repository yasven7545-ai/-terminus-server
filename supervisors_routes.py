# supervisors_routes.py
from flask import Blueprint, jsonify
from pathlib import Path
import json

supervisors_bp = Blueprint("supervisors", __name__, url_prefix="/api/supervisors")
SUP_FILE = Path.cwd() / "supervisors.json"

def init_supervisors():
    if not SUP_FILE.exists():
        SUP_FILE.write_text("[]", encoding="utf-8")

@supervisors_bp.route("/list", methods=["GET"])
def list_sup():
    try:
        data = json.loads(SUP_FILE.read_text(encoding="utf-8"))
        return jsonify(data)
    except Exception:
        return jsonify([])
