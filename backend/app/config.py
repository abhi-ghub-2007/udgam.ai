"""Settings, loaded once from .env (A-15).

A missing key never crashes the app and never reaches the browser by name.
It logs one clear line and the matching service degrades to its Mock.
"""
from __future__ import annotations

import logging
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

log = logging.getLogger("udgam.config")

PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env", env_file_encoding="utf-8", extra="ignore"
    )

    # --- Supabase -------------------------------------------------------
    SUPABASE_URL: str = ""
    SUPABASE_ANON_KEY: str = ""
    SUPABASE_SERVICE_ROLE_KEY: str = ""
    DATABASE_URL: str = ""

    # --- External integrations (all optional) ---------------------------
    USE_MOCK_INTEGRATIONS: bool = True
    OPENWEATHERMAP_API_KEY: str = ""
    AGMARKNET_API_KEY: str = ""
    RAZORPAY_KEY_ID: str = ""
    RAZORPAY_KEY_SECRET: str = ""
    OSRM_BASE_URL: str = "https://router.project-osrm.org"
    # Server-side only, like SUPABASE_ANON_KEY -- never baked into the bundle
    # as a VITE_* build-time var. Reaches the browser at runtime via
    # GET /api/config (A-16 pattern), which lets referrer-restriction in
    # Google Cloud Console be the actual security boundary rather than
    # secrecy of a key that has to be readable by client-side JS anyway.
    GOOGLE_MAPS_API_KEY: str = ""

    # --- App ------------------------------------------------------------
    APP_ENV: str = "development"
    CORS_ORIGINS: str = "http://localhost:5500,http://127.0.0.1:5500"

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    @property
    def supabase_configured(self) -> bool:
        return bool(self.SUPABASE_URL and self.SUPABASE_ANON_KEY)

    def integration_mode(self, key_name: str, label: str) -> str:
        """'live' if the key is present and mocks are off, else 'mock'."""
        if self.USE_MOCK_INTEGRATIONS:
            return "mock"
        if not getattr(self, key_name, ""):
            log.warning("%s not set - %s will use its mock implementation", key_name, label)
            return "mock"
        return "live"


@lru_cache
def get_settings() -> Settings:
    s = Settings()
    if not s.supabase_configured:
        log.warning(
            "Supabase is not configured. Copy .env.example to .env and fill it in. "
            "Auth-dependent endpoints will return 503 until then."
        )
    return s


settings = get_settings()
