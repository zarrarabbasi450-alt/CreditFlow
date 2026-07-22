from functools import lru_cache
from typing import Annotated

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=("../.env", ".env"), extra="ignore", case_sensitive=False)
    app_env: str = "development"
    api_gateway_host: str = "0.0.0.0"  # noqa: S104 - container listener is intentionally public
    api_gateway_port: int = 8080
    cors_origins: Annotated[list[str], NoDecode] = ["http://localhost:3000"]
    trusted_hosts: Annotated[list[str], NoDecode] = ["localhost", "127.0.0.1", "testserver"]
    jwt_public_key: str = ""
    jwt_public_key_path: str = ""
    jwt_issuer: str = "creditflow-auth"
    jwt_audience: str = "creditflow-api"
    redis_url: str = "redis://localhost:6379/0"
    rabbitmq_url: str = "amqp://guest:guest@localhost:5672/"
    allow_in_memory_redis: bool = False
    stripe_webhook_secret: str = ""
    linkedin_webhook_secret: str = ""
    openrouter_webhook_secret: str = ""
    auth_service_url: str = "http://localhost:8001"
    user_tenant_service_url: str = "http://localhost:8002"
    billing_service_url: str = "http://localhost:8003"
    credits_marketplace_service_url: str = "http://localhost:8004"
    usage_metering_service_url: str = "http://localhost:8005"
    ai_generation_service_url: str = "http://localhost:8006"
    content_service_url: str = "http://localhost:8007"
    scheduler_service_url: str = "http://localhost:8108"
    social_publishing_service_url: str = "http://localhost:8109"
    scraper_service_url: str = "http://localhost:8110"
    notification_service_url: str = "http://localhost:8111"
    admin_ops_service_url: str = "http://localhost:8112"
    public_rate_limit: int = 60
    account_rate_limit: int = 300
    rate_limit_window_seconds: int = 60
    webhook_rate_limit: int = 120
    downstream_timeout_seconds: float = 10.0
    webhook_max_body_bytes: int = 1_048_576
    sse_heartbeat_seconds: float = 15.0
    version: str = "1.0.0"

    @field_validator("cors_origins", "trusted_hosts", mode="before")
    @classmethod
    def split_csv(cls, value: object) -> object:
        return [part.strip() for part in value.split(",")] if isinstance(value, str) else value

    @property
    def service_urls(self) -> dict[str, str]:
        return {
            "auth": self.auth_service_url,
            "users": self.user_tenant_service_url,
            "billing": self.billing_service_url,
            "credits": self.credits_marketplace_service_url,
            "usage": self.usage_metering_service_url,
            "ai": self.ai_generation_service_url,
            "content": self.content_service_url,
            "scheduler": self.scheduler_service_url,
            "publishing": self.social_publishing_service_url,
            "scraper": self.scraper_service_url,
            "notifications": self.notification_service_url,
            "admin": self.admin_ops_service_url,
        }


@lru_cache
def get_settings() -> Settings:
    return Settings()
