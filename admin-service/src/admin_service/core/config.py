from functools import lru_cache
from typing import Annotated

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=("../.env", ".env"), extra="ignore", case_sensitive=False)
    app_name: str = "creditflow-admin-service"
    app_env: str = "development"
    app_host: str = "0.0.0.0"  # noqa: S104
    app_port: int = 8112
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/creditflow"
    database_schema: str = "admin"
    rabbitmq_url: str = "amqp://guest:guest@localhost:5672/"
    redis_url: str = "redis://localhost:6379/0"
    jwt_public_key: str = ""
    jwt_public_key_path: str = ""
    jwt_issuer: str = "creditflow-auth"
    jwt_audience: str = "creditflow-api"
    internal_service_token: str = ""
    auth_service_url: str = "http://localhost:8001"
    tenant_service_url: str = "http://localhost:8002"
    billing_service_url: str = "http://localhost:8003"
    credits_service_url: str = "http://localhost:8004"
    usage_service_url: str = "http://localhost:8005"
    ai_generation_service_url: str = "http://localhost:8006"
    content_service_url: str = "http://localhost:8007"
    scheduler_service_url: str = "http://localhost:8108"
    social_publishing_service_url: str = "http://localhost:8109"
    scraper_service_url: str = "http://localhost:8110"
    notification_service_url: str = "http://localhost:8111"
    request_timeout_seconds: float = 15.0
    health_check_timeout_seconds: float = 2.0
    log_level: str = "INFO"
    trusted_hosts: Annotated[list[str], NoDecode] = ["localhost", "127.0.0.1", "testserver"]
    version: str = "0.1.0"

    @field_validator("trusted_hosts", mode="before")
    @classmethod
    def split_csv(cls, value: object) -> object:
        return (
            [part.strip() for part in value.split(",") if part.strip()] if isinstance(value, str) else value
        )

    @property
    def health_targets(self) -> dict[str, str]:
        return {
            "auth-service": self.auth_service_url,
            "tenant-service": self.tenant_service_url,
            "billing-service": self.billing_service_url,
            "credits-service": self.credits_service_url,
            "usage-service": self.usage_service_url,
            "ai-generation-service": self.ai_generation_service_url,
            "content-service": self.content_service_url,
            "scheduler-service": self.scheduler_service_url,
            "social-publishing-service": self.social_publishing_service_url,
            "scraper-service": self.scraper_service_url,
            "notification-service": self.notification_service_url,
        }


@lru_cache
def get_settings() -> Settings:
    return Settings()
