"""Runtime settings, overridable via environment variables."""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", BASE_DIR / "uploads"))
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR / 'docintel.db'}")
MODEL_PATH = Path(os.getenv("MODEL_PATH", BASE_DIR / "app" / "ml" / "classifier.joblib"))
MAX_UPLOAD_MB = int(os.getenv("MAX_UPLOAD_MB", "20"))
MAX_FILES_PER_UPLOAD = int(os.getenv("MAX_FILES_PER_UPLOAD", "25"))
CORS_ORIGINS = [o.strip() for o in os.getenv("CORS_ORIGINS", "*").split(",")]
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
ALLOWED_EXT = {".pdf", ".png", ".jpg", ".jpeg", ".tiff", ".tif", ".txt"}
