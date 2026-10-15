"""
backend/app/core/config.py

Centralised application settings loaded from environment variables / .env file.
Uses pydantic-settings v2 so every field is validated at startup.
"""

import json
from functools import lru_cache
from typing import Dict, List

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
    ENABLE_SCHEDULER: bool = False

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


    # ── Feature 21 & 23: Component API Authentication & Limits ───────────────
    component_api_keys: str = ""
    ingest_max_batch: int = 1000
    ingest_max_body_bytes: int = 5 * 1024 * 1024  # 5 MB

    @property
    def COMPONENT_API_KEYS(self) -> Dict[str, str]:
        """Parsed mapping of component scopes to secret API keys."""
        if not self.component_api_keys:
            return {}
        try:
            val = json.loads(self.component_api_keys)
            if isinstance(val, dict):
                return {str(k).lower().strip(): str(v).strip() for k, v in val.items()}
        except Exception:
            pass
        return {}

    @property
    def INGEST_MAX_BATCH(self) -> int:
        """Maximum number of records accepted in a single ingestion batch."""
        return self.ingest_max_batch

    @property
    def INGEST_MAX_BODY_BYTES(self) -> int:
        """Maximum raw request payload size in bytes for ingestion endpoints."""
        return self.ingest_max_body_bytes


    # ── Feature 22: Weekly Scheduler & Pipeline Orchestrator ──────────────────
    scheduler_enabled: bool = False
    scheduler_tick_minutes: int = 15
    scheduler_grace_hours: int = 1
    scheduler_lookback_weeks: int = 2
    scheduler_max_weeks_per_tick: int = 20
    scheduler_excluded_course_sources: str = "oulad,demo"
    pipeline_coverage_threshold: float = 0.9
    pipeline_stage_timeout_hours: int = 24
    pipeline_c4_min_tier: str = "medium"
    component_webhooks: str = ""
    webhook_signing_secret: str = ""
    webhook_timeout_seconds: float = 5.0
    webhook_max_retries: int = 3

    @property
    def SCHEDULER_ENABLED(self) -> bool:
        return self.scheduler_enabled

    @property
    def SCHEDULER_TICK_MINUTES(self) -> int:
        return self.scheduler_tick_minutes

    @property
    def SCHEDULER_GRACE_HOURS(self) -> int:
        return self.scheduler_grace_hours

    @property
    def SCHEDULER_LOOKBACK_WEEKS(self) -> int:
        return self.scheduler_lookback_weeks

    @property
    def SCHEDULER_MAX_WEEKS_PER_TICK(self) -> int:
        return self.scheduler_max_weeks_per_tick

    @property
    def SCHEDULER_EXCLUDED_COURSE_SOURCES(self) -> List[str]:
        if not self.scheduler_excluded_course_sources:
            return []
        return [s.strip().lower() for s in self.scheduler_excluded_course_sources.split(",") if s.strip()]

    @property
    def PIPELINE_COVERAGE_THRESHOLD(self) -> float:
        return self.pipeline_coverage_threshold

    @property
    def PIPELINE_STAGE_TIMEOUT_HOURS(self) -> int:
        return self.pipeline_stage_timeout_hours

    @property
    def PIPELINE_C4_MIN_TIER(self) -> str:
        return self.pipeline_c4_min_tier.lower().strip()

    @property
    def COMPONENT_WEBHOOKS(self) -> Dict[str, str]:
        if not self.component_webhooks:
            return {}
        try:
            val = json.loads(self.component_webhooks)
            if isinstance(val, dict):
                return {str(k).lower().strip(): str(v).strip() for k, v in val.items()}
        except Exception:
            pass
        return {}

    @property
    def WEBHOOK_SIGNING_SECRET(self) -> str:
        return self.webhook_signing_secret

    @property
    def WEBHOOK_TIMEOUT_SECONDS(self) -> float:
        return self.webhook_timeout_seconds

    @property
    def WEBHOOK_MAX_RETRIES(self) -> int:
        return self.webhook_max_retries


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


def validate_pipeline_settings(settings_obj: Settings) -> None:
    """
    Validates pipeline and webhook configuration settings at startup.
    Ensures webhook JSON is well-formed, and in production enforces HTTPS.
    Never logs or echoes secret values.
    """
    if settings_obj.component_webhooks:
        try:
            val = json.loads(settings_obj.component_webhooks)
            if not isinstance(val, dict):
                raise ValueError("COMPONENT_WEBHOOKS must be a JSON dictionary mapping component to URL.")
        except Exception as exc:
            raise ValueError(f"Invalid COMPONENT_WEBHOOKS JSON: {exc}")

        for comp, url in settings_obj.COMPONENT_WEBHOOKS.items():
            if not isinstance(url, str) or not url.strip():
                raise ValueError(f"Webhook URL for component '{comp}' must be a non-empty string.")
            if settings_obj.app_env == "production" and not url.lower().startswith("https://"):
                raise RuntimeError(
                    f"Insecure webhook URL for component '{comp}'. In production, webhook URLs must start with 'https://'."
                )

