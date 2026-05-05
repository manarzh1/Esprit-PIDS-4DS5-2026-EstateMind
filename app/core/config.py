"""
app/core/config.py
==================
Configuration centrale Estate Mind BO6.
Lit le fichier .env via pydantic-settings.

RÈGLE ARCHITECTURALE :
  BO6 est un orchestrateur PUR.
  Il ne touche PAS PostgreSQL directement.
  Il appelle les agents BO1-BO5 via HTTP.
  PostgreSQL Supabase = traçabilité BO6 uniquement (schéma bo6_tracking).
"""

import os
from functools import lru_cache
from typing import Literal
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Application ───────────────────────────────────────────
    app_name: str = "Estate Mind"
    app_version: str = "1.0.0"
    app_env: Literal["development", "staging", "production"] = "development"
    debug: bool = True
    log_level: str = "INFO"

    # ── Server ────────────────────────────────────────────────
    host: str = "0.0.0.0"
    port: int = 8000
    allowed_origins: str = "http://localhost:3000,http://localhost:5173"

    @property
    def origins_list(self) -> list[str]:
        return [o.strip() for o in self.allowed_origins.split(",") if o.strip()]

    secret_key: str = "change-me-in-production"

    # ── Supabase ──────────────────────────────────────────────
    database_url: str = ""
    supabase_url: str = ""
    supabase_anon_key: str = ""

    @property
    def async_database_url(self) -> str:
        url = self.database_url or os.getenv("DATABASE_URL", "")
        if not url:
            raise ValueError("DATABASE_URL manquant dans .env — configurer Supabase")
        url = url.replace("postgresql://", "postgresql+asyncpg://")
        url = url.replace("postgres://", "postgresql+asyncpg://")
        return url

    @property
    def sync_database_url(self) -> str:
        url = self.database_url or os.getenv("DATABASE_URL", "")
        if not url:
            raise ValueError("DATABASE_URL manquant dans .env — configurer Supabase")
        url = url.replace("postgresql+asyncpg://", "postgresql://")
        url = url.replace("postgres://", "postgresql://")
        return url

    # ── Redis (optionnel) ─────────────────────────────────────
    redis_url: str = "redis://localhost:6379/0"
    enable_cache: bool = False

    # ── NLP ───────────────────────────────────────────────────
    enable_translation: bool = True
    enable_explainability: bool = True

    # ── PDF ───────────────────────────────────────────────────
    pdf_output_dir: str = "./reports"

    # ── Agents BO1-BO5 (BO6 appelle ces URLs via HTTP) ────────
    agent_bo1_url: str = "http://localhost:8001"
    agent_bo2_url: str = "http://localhost:8002"
    agent_bo3_url: str = "http://localhost:8003"
    agent_bo4_url: str = "http://localhost:8004"
    agent_bo5_url: str = "http://localhost:8005"
    agent_timeout: int = 20

    # ── Dashboard ─────────────────────────────────────────────
    dashboard_port: int = 8050


@lru_cache
def get_settings() -> Settings:
    """Singleton — lit .env une seule fois."""
    return Settings()
