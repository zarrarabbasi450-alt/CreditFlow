from functools import lru_cache
from typing import Annotated

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=("../.env", ".env"), extra="ignore", case_sensitive=False)
    app_name: str = "creditflow-notification-service"
    app_env: str = "development"
    app_host: str = "0.0.0.0"  # noqa: S104
    app_port: int = 8111
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/creditflow"
    database_schema: str = "notifications"
    rabbitmq_url: str = "amqp://guest:guest@localhost:5672/"
    jwt_public_key: str = ""
    jwt_public_key_path: str = ""
    jwt_issuer: str = "creditflow-auth"
    jwt_audience: str = "creditflow-api"
    internal_service_token: str = ""
    auth_service_url: str = "http://localhost:8001"
    tenant_service_url: str = "http://localhost:8002"
    frontend_url: str = "http://localhost:3000"
    email_provider: str = "resend"
    resend_api_key: str = ""
    email_from: str = "CreditFlow <onboarding@resend.dev>"
    google_client_id: str = ""
    google_client_secret: str = ""
    google_refresh_token: str = ""
    gmail_sender_email: str = ""
    slack_webhook_url: str = ""
    request_timeout_seconds: float = 15.0
    log_level: str = "INFO"
    trusted_hosts: Annotated[list[str], NoDecode] = ["localhost", "127.0.0.1", "testserver"]
    version: str = "0.1.0"

    @field_validator("trusted_hosts", mode="before")
    @classmethod
    def split_csv(cls, value: object) -> object:
        return (
            [part.strip() for part in value.split(",") if part.strip()] if isinstance(value, str) else value
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
