from functools import lru_cache
from typing import Annotated

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=("../.env", ".env"), extra="ignore", case_sensitive=False)
    app_name: str = "creditflow-ai-generation-service"
    app_host: str = "0.0.0.0"  # noqa: S104
    app_port: int = 8006
    app_env: str = "development"
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/creditflow"
    database_schema: str = "ai_generation"
    redis_url: str = "redis://localhost:6379/4"
    rabbitmq_url: str = "amqp://guest:guest@localhost:5672/"
    jwt_public_key: str = ""
    jwt_public_key_path: str = ""
    jwt_issuer: str = "creditflow-auth"
    jwt_audience: str = "creditflow-api"
    openrouter_api_key: str = ""
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_site_url: str = "http://localhost:3000"
    openrouter_app_name: str = "CreditFlow"
    usage_service_url: str = "http://localhost:8005"
    fast_model: str = "openai/gpt-4o-mini"
    quality_model: str = "openai/gpt-4o"
    fallback_models: Annotated[list[str], NoDecode] = ["openai/gpt-4o-mini"]
    fast_model_cost_microusd_per_1k: int = 150
    quality_model_cost_microusd_per_1k: int = 3000
    estimated_prompt_tokens: int = 400
    estimated_completion_tokens: int = 800
    pollinations_base_url: str = "https://image.pollinations.ai/prompt"
    log_level: str = "INFO"
    trusted_hosts: Annotated[list[str], NoDecode] = ["localhost", "127.0.0.1", "testserver"]
    version: str = "0.1.0"

    @field_validator("trusted_hosts", mode="before")
    @classmethod
    def split_csv(cls, value: object) -> object:
        return [part.strip() for part in value.split(",")] if isinstance(value, str) else value

    @field_validator("fallback_models", mode="before")
    @classmethod
    def split_fallback_models(cls, value: object) -> object:
        return (
            [part.strip() for part in value.split(",") if part.strip()] if isinstance(value, str) else value
        )

    @property
    def allowed_models(self) -> dict[str, str]:
        return {"fast": self.fast_model, "quality": self.quality_model}

    def model_cost(self, model: str) -> int:
        if model == self.quality_model:
            return self.quality_model_cost_microusd_per_1k
        return self.fast_model_cost_microusd_per_1k

    def model_candidates(self, primary_model: str) -> list[str]:
        candidates = [primary_model, *self.fallback_models]
        return list(dict.fromkeys(candidates))


@lru_cache
def get_settings() -> Settings:
    return Settings()
