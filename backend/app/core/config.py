"""Application configuration loaded from environment / .env."""

from __future__ import annotations

import json
from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "EntryX"
    log_level: str = "INFO"

    # Database
    database_url: str = "sqlite:///./entryx.db"

    # Security
    secret_key: str = "dev-only-change-me-please-use-64-char-key-in-prod"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 30
    encryption_key: str = ""

    # CORS
    cors_origins: list[str] = ["http://localhost:5173"]

    # AI provider (local-first)
    ai_provider: str = "ollama"
    ai_ollama_url: str = "http://localhost:11434"
    ai_default_model: str = "qwen2.5:1.5b"

    # Paper broker
    paper_initial_balance: float = 100_000.0
    paper_leverage: float = 100.0

    # Rate limiting
    auth_rate_limit_per_minute: int = 10

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _parse_origins(cls, v: object) -> object:
        if isinstance(v, str):
            return json.loads(v)
        return v

    @property
    def is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")

    @property
    def database_connect_args(self) -> dict:
        return {"check_same_thread": False} if self.is_sqlite else {}


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    _validate_settings(settings)
    return settings


def _validate_settings(settings: Settings) -> None:
    """Validate critical settings at startup to prevent runtime surprises."""
    import logging

    logger = logging.getLogger("entryx.config")
    if settings.secret_key == "dev-only-change-me-please-use-64-char-key-in-prod":
        logger.warning(
            "SECRET_KEY is using the default dev value — set a real secret in production"
        )
    if not settings.encryption_key:
        logger.warning("ENCRYPTION_KEY is empty — broker credential encryption is disabled")
    if settings.database_url.startswith("sqlite"):
        logger.info("Using SQLite database — suitable for development only")
