from functools import lru_cache
from typing import Annotated

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=("../.env", ".env"), extra="ignore", case_sensitive=False)
    app_env: str = "development"
    app_port: int = 8003
    database_url: str = "postgresql+asyncpg://postgres:CHANGE_ME@localhost:5432/creditflow"
    database_schema: str = "billing"
    rabbitmq_url: str = "amqp://guest:guest@localhost:5672/"
    jwt_public_key_path: str = ""
    jwt_public_key: str = ""
    jwt_issuer: str = "creditflow-auth"
    jwt_audience: str = "creditflow-api"
    stripe_secret_key: str = ""
    stripe_pro_price_id: str = ""
    stripe_team_price_id: str = ""
    stripe_enterprise_price_id: str = ""
    stripe_checkout_success_url: str = "http://localhost:3000/billing?checkout=success"
    stripe_checkout_cancel_url: str = "http://localhost:3000/billing?checkout=cancelled"
    stripe_portal_return_url: str = "http://localhost:3000/billing"
    dunning_grace_days: int = 7
    outbox_poll_seconds: float = 1.0
    trusted_hosts: Annotated[list[str], NoDecode] = ["localhost", "127.0.0.1", "testserver"]
    version: str = "0.1.0"

    @field_validator("trusted_hosts", mode="before")
    @classmethod
    def split_csv(cls, value: object) -> object:
        return [part.strip() for part in value.split(",")] if isinstance(value, str) else value

    @property
    def price_ids(self) -> dict[str, str]:
        return {
            "pro": self.stripe_pro_price_id,
            "team": self.stripe_team_price_id,
            "enterprise": self.stripe_enterprise_price_id,
        }


@lru_cache
def get_settings() -> Settings:
    return Settings()
