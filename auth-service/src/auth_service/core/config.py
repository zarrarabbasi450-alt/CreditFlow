from functools import lru_cache
from typing import Annotated

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=("../.env", ".env"), extra="ignore", case_sensitive=False)

    app_name: str = "creditflow-auth-service"
    app_host: str = "0.0.0.0"  # noqa: S104 - container listener is intentionally public
    app_port: int = 8001
    app_env: str = "development"
    database_url: str = "postgresql+asyncpg://postgres:CHANGE_ME@localhost:5432/creditflow"
    database_schema: str = "auth"
    redis_url: str = "redis://localhost:6379/0"
    rabbitmq_url: str = "amqp://guest:guest@localhost:5672/"
    log_level: str = "INFO"
    trusted_hosts: Annotated[list[str], NoDecode] = ["localhost", "127.0.0.1", "testserver"]
    jwt_private_key_path: str = ""
    jwt_public_key_path: str = ""
    jwt_issuer: str = "creditflow-auth"
    jwt_audience: str = "creditflow-api"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 30
    email_verification_expire_hours: int = 24
    password_reset_expire_minutes: int = 30
    login_attempt_limit: int = 5
    login_attempt_window_seconds: int = 900
    bootstrap_superadmin_email: str = ""
    tenant_service_url: str = "http://localhost:8002"
    internal_service_token: str = ""
    version: str = "0.1.0"

    @field_validator("trusted_hosts", mode="before")
    @classmethod
    def split_csv(cls, value: object) -> object:
        return [part.strip() for part in value.split(",")] if isinstance(value, str) else value


@lru_cache
def get_settings() -> Settings:
    return Settings()
