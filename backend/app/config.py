"""Runtime configuration. Everything can be overridden with environment variables
(see backend/.env.example). No API keys are required: shop search uses the public
OpenStreetMap Overpass and Nominatim services."""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

MODEL_DIR = Path(os.getenv("CROP_DOCTOR_MODEL_DIR", BASE_DIR / "model"))
DATA_DIR = Path(os.getenv("CROP_DOCTOR_DATA_DIR", BASE_DIR / "data"))
DB_PATH = Path(os.getenv("CROP_DOCTOR_DB", DATA_DIR / "crop_doctor.sqlite3"))
UPLOAD_DIR = DATA_DIR / "uploads"
FRONTEND_DIST = Path(os.getenv("CROP_DOCTOR_FRONTEND_DIST", BASE_DIR.parent / "frontend" / "dist"))

# Prediction safety thresholds
MIN_CONFIDENCE = float(os.getenv("CROP_DOCTOR_MIN_CONFIDENCE", "0.70"))
MAX_UPLOAD_BYTES = int(os.getenv("CROP_DOCTOR_MAX_UPLOAD_BYTES", str(10 * 1024 * 1024)))
MIN_IMAGE_SIDE = 96
BLUR_THRESHOLD = float(os.getenv("CROP_DOCTOR_BLUR_THRESHOLD", "15.0"))

# OpenStreetMap services (public, no key). Please respect their usage policies:
# https://operations.osmfoundation.org/policies/nominatim/
# Comma-separated list; tried in order until one answers.
OVERPASS_URLS = [u.strip() for u in os.getenv(
    "OVERPASS_URLS",
    "https://overpass-api.de/api/interpreter,https://overpass.private.coffee/api/interpreter"
).split(",") if u.strip()]
NOMINATIM_URL = os.getenv("NOMINATIM_URL", "https://nominatim.openstreetmap.org")
HTTP_USER_AGENT = os.getenv("CROP_DOCTOR_USER_AGENT", "AICropDoctor/1.0 (farmer assistant prototype)")
SHOP_SEARCH_MAX_RADIUS_M = 50000
HTTP_TIMEOUT_S = float(os.getenv("CROP_DOCTOR_HTTP_TIMEOUT", "30"))
OVERPASS_TIMEOUT_S = float(os.getenv("CROP_DOCTOR_OVERPASS_TIMEOUT", "15"))

SESSION_DAYS = 30
