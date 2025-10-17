"""Application settings loaded from environment variables."""

import os
import sys
from functools import lru_cache
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from loguru import logger
from pydantic import BaseModel, Field, ValidationError, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


BASE_DIR = Path(__file__).resolve().parent.parent
ENV_CANDIDATES = [BASE_DIR / ".env", BASE_DIR.parent / ".env"]


def _load_env_file() -> None:
    """Load the optional .env file when present."""
    for env_path in ENV_CANDIDATES:
        if env_path.exists():
            load_dotenv(env_path, override=False)


_load_env_file()


class DatabaseSettings(BaseModel):
    """Configuration for the primary PostgreSQL database."""

    url: str = "postgresql+psycopg2://postgres:postgres@db:5432/postgres"
    echo: bool = False


class RedisSettings(BaseModel):
    """Configuration for Redis cache/message broker."""

    url: str = "redis://redis:6379/0"
    health_check_interval: int = 30


class Settings(BaseSettings):
    """Top-level API configuration."""

    model_config = SettingsConfigDict(env_prefix="", env_file=None, extra="ignore")

    environment: str = Field("development", alias="APP_ENV")
    api_host: str = Field("0.0.0.0", alias="API_HOST")
    api_port: int = Field(8000, alias="API_PORT")
    log_level: str = Field("INFO", alias="APP_LOG_LEVEL")
    api_key: Optional[str] = Field(None, alias="APP_API_KEY")
    secret_key: str = Field("change_me", alias="SECRET_KEY")
    encryption_key: Optional[str] = Field(None, alias="ENCRYPTION_KEY")
    admin_api_key: Optional[str] = Field(None, alias="ADMIN_API_KEY")

    database: DatabaseSettings = DatabaseSettings()
    database_url: Optional[str] = Field(None, alias="APP_DATABASE__URL")
    redis: RedisSettings = RedisSettings()

    openai_api_key: Optional[str] = Field(None, alias="OPENAI_API_KEY")
    resend_api_key: Optional[str] = Field(None, alias="RESEND_API_KEY")
    resend_from_email: Optional[str] = Field(None, alias="RESEND_FROM_EMAIL")
    expo_access_token: Optional[str] = Field(None, alias="EXPO_ACCESS_TOKEN")
    expo_push_url: str = Field("https://exp.host/--/api/v2/push/send", alias="EXPO_PUSH_URL")
    google_client_id: Optional[str] = Field(None, alias="GOOGLE_CLIENT_ID")
    google_client_secret: Optional[str] = Field(None, alias="GOOGLE_CLIENT_SECRET")
    google_redirect_uri: Optional[str] = Field(
        "http://localhost:8000/oauth/google/callback",
        alias="GOOGLE_REDIRECT_URI",
    )
    stripe_secret_key: Optional[str] = Field(None, alias="STRIPE_API_KEY")
    stripe_price_pro: Optional[str] = Field(None, alias="STRIPE_PRICE_PRO")
    stripe_webhook_secret: Optional[str] = Field(None, alias="STRIPE_WEBHOOK_SECRET")

    postgres_host: Optional[str] = Field(None, alias="POSTGRES_HOST")
    postgres_port: Optional[int] = Field(None, alias="POSTGRES_PORT")
    postgres_db: Optional[str] = Field(None, alias="POSTGRES_DB")
    postgres_user: Optional[str] = Field(None, alias="POSTGRES_USER")
    postgres_password: Optional[str] = Field(None, alias="POSTGRES_PASSWORD")

    redis_url_override: Optional[str] = Field(None, alias="REDIS_URL")
    celery_beat_enabled: bool = Field(True, alias="CELERY_BEAT")

    @model_validator(mode="after")
    def _apply_overrides(self) -> "Settings":
        env_database_url = self.database_url or os.environ.get("APP_DATABASE__URL")
        if env_database_url:
            self.database = DatabaseSettings(
                url=env_database_url,
                echo=self.database.echo,
            )
            # When DSN is provided, ignore individual overrides below.
            self.postgres_host = None
            self.postgres_port = None
            self.postgres_db = None
            self.postgres_user = None
            self.postgres_password = None

        if any(
            value is not None
            for value in (
                self.postgres_host,
                self.postgres_port,
                self.postgres_db,
                self.postgres_user,
                self.postgres_password,
            )
        ):
            host = self.postgres_host or "db"
            port = self.postgres_port or 5432
            db_name = self.postgres_db or "postgres"
            user = self.postgres_user or "postgres"
            password = self.postgres_password or "postgres"
            self.database = DatabaseSettings(
                url=f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{db_name}",
                echo=self.database.echo,
            )

        if self.redis_url_override:
            self.redis = RedisSettings(
                url=self.redis_url_override,
                health_check_interval=self.redis.health_check_interval,
            )

        return self


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached Settings instance."""

    try:
        settings_obj = Settings()
    except ValidationError as exc:
        logger.error(
            "configuration_validation_failed",
            error="validation_error",
            details=exc.errors(),
        )
        sys.exit(1)

    missing = _collect_missing_env(settings_obj)
    if missing:
        logger.error(
            "configuration_validation_failed",
            error="missing_environment",
            missing_envs=missing,
        )
        sys.exit(1)

    if settings_obj.secret_key == "change_me":
        logger.error(
            "configuration_validation_failed",
            error="insecure_secret_key",
            message="SECRET_KEY must be set to a non-default value.",
        )
        sys.exit(1)

    return settings_obj


def _collect_missing_env(settings_obj: Settings) -> list[str]:
    missing: list[str] = []

    db_env_present = bool(
        os.environ.get("APP_DATABASE__URL")
        or os.environ.get("DATABASE_URL")
        or all(
            os.environ.get(name)
            for name in ("POSTGRES_HOST", "POSTGRES_DB", "POSTGRES_USER", "POSTGRES_PASSWORD")
        )
    )
    if not db_env_present or not settings_obj.database.url:
        missing.append("APP_DATABASE__URL or POSTGRES_*")

    redis_env_present = bool(os.environ.get("APP_REDIS__URL") or os.environ.get("REDIS_URL"))
    if not redis_env_present or not settings_obj.redis.url:
        missing.append("APP_REDIS__URL or REDIS_URL")

    if not os.environ.get("OPENAI_API_KEY"):
        missing.append("OPENAI_API_KEY")

    if not os.environ.get("ENCRYPTION_KEY"):
        missing.append("ENCRYPTION_KEY")

    if not os.environ.get("TZ"):
        missing.append("TZ")

    if settings_obj.admin_api_key and os.environ.get("ADMIN_API_KEY") != settings_obj.admin_api_key:
        missing.append("ADMIN_API_KEY")

    return missing


settings = get_settings()

