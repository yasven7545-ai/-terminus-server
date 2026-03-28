from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "static" / "data"

PPM_DATA_FILE = DATA_DIR / "ppm_data.json"
PPM_DASHBOARD_FILE = DATA_DIR / "ppm_dashboard.json"
