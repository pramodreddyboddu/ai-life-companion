"""Application settings loaded from environment variables."""

from functools import lru_cache
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from pydantic import BaseModel, Field, model_validator
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

    database: DatabaseSettings = DatabaseSettings()
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

    return Settings()


settings = get_settings()

