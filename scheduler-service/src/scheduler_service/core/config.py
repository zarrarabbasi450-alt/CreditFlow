from functools import lru_cache
from typing import Annotated

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=("../.env", ".env"), extra="ignore", case_sensitive=False)
    app_name: str = "creditflow-scheduler-service"
    app_host: str = "0.0.0.0"  # noqa: S104
    app_port: int = 8108
    app_env: str = "development"
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/creditflow"
    database_schema: str = "scheduler"
    redis_url: str = "redis://localhost:6379/4"
    celery_broker_url: str = "redis://localhost:6379/4"
    celery_result_backend: str = "redis://localhost:6379/4"
    rabbitmq_url: str = "amqp://guest:guest@localhost:5672/"
    jwt_public_key: str = ""
    jwt_public_key_path: str = ""
    jwt_issuer: str = "creditflow-auth"
    jwt_audience: str = "creditflow-api"
    due_scan_interval_seconds: int = 60
    schedule_lock_ttl_seconds: int = 120
    log_level: str = "INFO"
    trusted_hosts: Annotated[list[str], NoDecode] = ["localhost", "127.0.0.1", "testserver"]
    version: str = "0.1.0"

    @field_validator("trusted_hosts", mode="before")
    @classmethod
    def split_csv(cls, value: object) -> object:
        return [part.strip() for part in value.split(",")] if isinstance(value, str) else value


@lru_cache
def get_settings() -> Settings:
    return Settings()
