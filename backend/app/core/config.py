"""
backend/app/core/config.py

Centralised application settings loaded from environment variables / .env file.
Uses pydantic-settings v2 so every field is validated at startup; the app will
refuse to start if a required variable is missing or has the wrong type.
"""

from functools import lru_cache
from typing import List

from pydantic import field_validator, model_validator
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
    secret_key: str
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7

    # ── PostgreSQL ────────────────────────────────────────────────────────────
    postgres_user: str
    postgres_password: str
    postgres_db: str
    postgres_host: str = "db"
    postgres_port: int = 5432

    # Assembled at validation time – do NOT set in .env (see model_validator).
    database_url: str = ""
    # Sync DSN used exclusively by Alembic (psycopg2).
    sync_database_url: str = ""

    # ── CORS ──────────────────────────────────────────────────────────────────
    # Stored as a raw string from .env; parsed into a list by the validator.
    # Format in .env:  CORS_ORIGINS=http://localhost:5173,http://localhost:3000
    cors_origins: str = "http://localhost:5173,http://localhost:3000"

    @property
    def cors_origins_list(self) -> List[str]:
        """Return CORS origins as a Python list for use in middleware."""
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @model_validator(mode="after")
    def assemble_database_urls(self) -> "Settings":
        """
        Build the async (asyncpg) and sync (psycopg2) connection strings from
        individual POSTGRES_* variables so callers never have to construct them
        manually.
        """
        base = (
            f"{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )
        self.database_url = f"postgresql+asyncpg://{base}"
        self.sync_database_url = f"postgresql+psycopg2://{base}"
        return self


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """
    Return a cached singleton Settings instance.
    Use dependency injection in FastAPI:
        settings: Settings = Depends(get_settings)
    """
    return Settings()


# Module-level shortcut – safe to import directly in non-DI contexts.
settings: Settings = get_settings()
