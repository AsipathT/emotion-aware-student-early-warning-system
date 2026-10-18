"""
Configuration settings for Component 2 service and LMS integration.
"""

import os
from pathlib import Path
from src.config import component_root


class Settings:
    """Runtime service configuration read from environment variables."""

    @property
    def LMS_BASE_URL(self) -> str:
        return os.environ.get("LMS_BASE_URL", "http://localhost:8000").rstrip("/")

    @property
    def C2_COMPONENT_KEY(self) -> str:
        return os.environ.get("C2_COMPONENT_KEY", "")

    @property
    def C2_MODEL_PATH(self) -> Path:
        raw = os.environ.get("C2_MODEL_PATH")
        if raw and raw.strip():
            p = Path(raw.strip())
            return p if p.is_absolute() else (component_root() / p).resolve()
        return (component_root() / "models" / "c2_deploy.joblib").resolve()


settings = Settings()
