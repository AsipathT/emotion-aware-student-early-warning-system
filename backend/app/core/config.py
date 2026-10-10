"""
backend/app/core/config.py

Centralised application settings loaded from environment variables / .env file.
Uses pydantic-settings v2 so every field is validated at startup.
"""

from functools import lru_cache
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """All configuration is sourced from environment variables (or .env file)."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",  # silently discard unknown env vars
    )

    # ── App ───────────────────────────────────────────────────────────────────
    app_env: str = "development"
    debug: bool = False
    secret_key: str = "replace_with_a_long_random_secret_key_min_32_chars"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7

    # ── MongoDB Atlas ─────────────────────────────────────────────────────────
    mongo_uri: str = (
        "mongodb+srv://nidukavikumasipath_db_user:GmKuIN45W0FOhKK0@cluster0.sqmc74m.mongodb.net/lms_db?retryWrites=true&w=majority&appName=Cluster0"
    )
    mongo_db_name: str = "lms_db"

    # Optional test database overrides
    test_mongo_uri: str = ""
    test_db_name: str = ""

    @property
    def MONGODB_URI(self) -> str:
        """Alias for mongo_uri."""
        return self.mongo_uri

    @property
    def DB_NAME(self) -> str:
        """Alias for mongo_db_name."""
        return self.mongo_db_name

    # ── Feature 5: Pseudonymization & Privacy ─────────────────────────────────
    pseudonym_secret_key: str = "lms_pseudonym_hmac_secret_key_2026_super_secure"

    @property
    def PSEUDONYM_SECRET_KEY(self) -> str:
        """Upper-case accessor for Feature 5 privacy hashing."""
        return self.pseudonym_secret_key

    # ── Feature 7: Audit Logging & Proxy Trust ────────────────────────────────
    trusted_proxy: bool = False

    @property
    def TRUSTED_PROXY(self) -> bool:
        """Accessor for trusted proxy configuration."""
        return self.trusted_proxy


    # ── CORS ──────────────────────────────────────────────────────────────────
    cors_origins: str = "http://localhost:5173,http://localhost:3000"

    @property
    def cors_origins_list(self) -> List[str]:
        """Return CORS origins as a Python list for use in middleware."""
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached singleton Settings instance."""
    return Settings()


# Module-level shortcut – safe to import directly in non-DI contexts.
settings: Settings = get_settings()
