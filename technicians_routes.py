# technicians_routes.py
import json
from pathlib import Path
from flask import Blueprint, jsonify

technicians_bp = Blueprint("technicians", __name__)

TECH_FILE = Path("technicians.json")

@technicians_bp.route("/api/technicians", methods=["GET"])
def get_technicians():
    if TECH_FILE.exists():
        try:
            data = json.loads(TECH_FILE.read_text(encoding="utf-8"))
            # normalize {mobile → phone}
            for t in data:
                if "phone" not in t and "mobile" in t:
                    t["phone"] = t["mobile"]
            return jsonify(data)
        except Exception:
            return jsonify([])
    return jsonify([])
