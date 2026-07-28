from functools import lru_cache
from typing import Annotated, Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=("../.env", ".env"), extra="ignore", case_sensitive=False)
    app_name: str = "creditflow-scraper-service"
    app_env: str = "development"
    app_host: str = "0.0.0.0"  # noqa: S104
    app_port: int = 8110
    mongodb_url: str = "mongodb://localhost:27017"
    mongodb_database: str = "creditflow_scraper"
    rabbitmq_url: str = "amqp://guest:guest@localhost:5672/"
    jwt_public_key: str = ""
    jwt_public_key_path: str = ""
    jwt_issuer: str = "creditflow-auth"
    jwt_audience: str = "creditflow-api"
    internal_service_token: str = ""
    frontend_url: str = "http://localhost:3000"
    scraper_engine: Literal["httpx", "playwright"] = "httpx"
    scraper_user_agent: str = "CreditFlowBot/1.0 (+https://creditflow.example/bot)"
    request_timeout_seconds: float = 20.0
    robots_cache_seconds: int = 3600
    min_request_interval_seconds: float = 2.0
    max_pages_per_job: int = 10
    max_document_chars: int = 20_000
    serpapi_api_key: str = ""
    serpapi_base_url: str = "https://serpapi.com/search"
    serpapi_engine: str = "google"
    recurring_scan_interval_seconds: int = 60
    publish_max_attempts: int = 5
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
