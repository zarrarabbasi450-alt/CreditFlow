from functools import lru_cache
from typing import Annotated

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=("../.env", ".env"), extra="ignore", case_sensitive=False)
    app_name: str = "creditflow-social-publishing-service"
    app_env: str = "development"
    app_host: str = "0.0.0.0"  # noqa: S104
    app_port: int = 8109
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/creditflow"
    database_schema: str = "social"
    rabbitmq_url: str = "amqp://guest:guest@localhost:5672/"
    jwt_public_key: str = ""
    jwt_public_key_path: str = ""
    jwt_issuer: str = "creditflow-auth"
    jwt_audience: str = "creditflow-api"
    linkedin_client_id: str = ""
    linkedin_client_secret: str = ""
    linkedin_redirect_uri: str = "http://localhost:8080/api/v1/publishing/linkedin/callback"
    linkedin_scopes: Annotated[list[str], NoDecode] = ["openid", "profile", "email", "w_member_social"]
    linkedin_api_version: str = "202606"
    linkedin_api_mode: str = "ugc"
    linkedin_dev_mode: bool = True
    frontend_url: str = "http://localhost:3000"
    social_token_encryption_key: str = ""
    content_service_url: str = "http://localhost:8007"
    internal_service_token: str = ""
    publish_max_attempts: int = 5
    token_refresh_interval_seconds: int = 3600
    log_level: str = "INFO"
    trusted_hosts: Annotated[list[str], NoDecode] = ["localhost", "127.0.0.1", "testserver"]
    version: str = "0.1.0"

    @field_validator("trusted_hosts", "linkedin_scopes", mode="before")
    @classmethod
    def split_csv(cls, value: object) -> object:
        return (
            [part.strip() for part in value.split(",") if part.strip()] if isinstance(value, str) else value
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
