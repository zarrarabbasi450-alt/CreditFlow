from functools import lru_cache
from typing import Annotated

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=("../.env", ".env"), extra="ignore", case_sensitive=False)

    app_name: str = "creditflow-credits-service"
    app_host: str = "0.0.0.0"  # noqa: S104
    app_port: int = 8004
    app_env: str = "development"
    database_url: str = "postgresql+asyncpg://postgres:CHANGE_ME@localhost:5432/creditflow"
    database_schema: str = "credits"
    rabbitmq_url: str = "amqp://guest:guest@localhost:5672/"
    billing_service_url: str = "http://localhost:8003"
    jwt_public_key: str = ""
    jwt_public_key_path: str = ""
    jwt_issuer: str = "creditflow-auth"
    jwt_audience: str = "creditflow-api"
    log_level: str = "INFO"
    trusted_hosts: Annotated[list[str], NoDecode] = ["localhost", "127.0.0.1", "testserver"]
    credit_grant_free: int = 0
    credit_grant_pro: int = 10_000
    credit_grant_team: int = 40_000
    credit_grant_enterprise: int = 100_000
    low_balance_threshold: int = 1_000
    version: str = "0.1.0"

    @field_validator("trusted_hosts", mode="before")
    @classmethod
    def split_csv(cls, value: object) -> object:
        return [part.strip() for part in value.split(",")] if isinstance(value, str) else value

    @property
    def plan_grants(self) -> dict[str, int]:
        return {
            "free": self.credit_grant_free,
            "pro": self.credit_grant_pro,
            "team": self.credit_grant_team,
            "enterprise": self.credit_grant_enterprise,
        }


@lru_cache
def get_settings() -> Settings:
    return Settings()
