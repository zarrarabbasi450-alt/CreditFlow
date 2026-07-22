from typing import Protocol

import httpx

from ai_generation_service.core.config import Settings
from ai_generation_service.core.errors import AIServiceError


class UsageClientProtocol(Protocol):
    async def check_quota(self, token: str, estimated_tokens: int) -> bool: ...
    async def close(self) -> None: ...


class UsageClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.client = httpx.AsyncClient(timeout=10)

    async def check_quota(self, token: str, estimated_tokens: int) -> bool:
        try:
            response = await self.client.post(
                f"{self.settings.usage_service_url}/api/v1/usage/quota/check",
                headers={"Authorization": f"Bearer {token}"},
                json={"estimated_tokens": estimated_tokens},
            )
            response.raise_for_status()
            return bool(response.json()["allowed"])
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code in {401, 403}:
                raise AIServiceError(
                    exc.response.status_code, "USAGE_AUTH_FAILED", "Usage quota check was rejected"
                ) from exc
            raise AIServiceError(
                402, "QUOTA_EXCEEDED", "Usage quota is not available for this generation"
            ) from exc
        except (httpx.HTTPError, KeyError) as exc:
            raise AIServiceError(
                503, "USAGE_SERVICE_UNAVAILABLE", "Usage Service quota check failed"
            ) from exc

    async def close(self) -> None:
        await self.client.aclose()


class InMemoryUsageClient:
    def __init__(self, allowed: bool = True) -> None:
        self.allowed = allowed

    async def check_quota(self, token: str, estimated_tokens: int) -> bool:
        del token, estimated_tokens
        return self.allowed

    async def close(self) -> None:
        return None
