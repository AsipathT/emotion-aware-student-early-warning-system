"""Settings, read from environment variables or backend/.env."""
import os
import secrets
from pathlib import Path

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BACKEND_DIR / ".env")

DATA_DIR = BACKEND_DIR / "data"
MODEL_DIR = BACKEND_DIR / "model"
MODEL_PATH = Path(os.getenv("MODEL_PATH") or MODEL_DIR / "c4_intervention_model.joblib")
TRAINING_DATA_PATH = Path(os.getenv("TRAINING_DATA_PATH") or MODEL_DIR / "C4_ML_Training_Dataset_500_IT23_v2.xlsx")

# Without JWT_SECRET a random secret is used: safe, but everyone is logged out when the server restarts.
JWT_SECRET_IS_RANDOM = not os.getenv("JWT_SECRET")
JWT_SECRET = os.getenv("JWT_SECRET") or secrets.token_urlsafe(32)
JWT_EXPIRE_HOURS = float(os.getenv("JWT_EXPIRE_HOURS", "8"))

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-5-mini")
OPENAI_TIMEOUT_SECONDS = float(os.getenv("OPENAI_TIMEOUT_SECONDS", "60"))

CORS_ORIGINS = [o.strip() for o in os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",") if o.strip()]
