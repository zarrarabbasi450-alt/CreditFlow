from typing import Protocol
from uuid import UUID

import httpx


class DirectoryClientProtocol(Protocol):
    async def get_user_email(self, user_id: UUID) -> str | None: ...
    async def get_account_owner_email(self, account_id: UUID) -> str | None: ...
    async def close(self) -> None: ...


class DirectoryClient:
    """Resolves who to email for events that don't carry an email address directly
    (only a user_id or account_id). Calls the trusted internal endpoints on
    auth-service and tenant-service, guarded by the shared internal service token —
    the same trust boundary already used for other cross-service reads."""

    def __init__(
        self,
        auth_service_url: str,
        tenant_service_url: str,
        internal_service_token: str,
        timeout_seconds: float,
    ) -> None:
        self.auth_service_url = auth_service_url.rstrip("/")
        self.tenant_service_url = tenant_service_url.rstrip("/")
        self.headers = {"Authorization": f"Bearer {internal_service_token}"}
        self.client = httpx.AsyncClient(timeout=timeout_seconds)

    async def get_user_email(self, user_id: UUID) -> str | None:
        response = await self.client.get(
            f"{self.auth_service_url}/api/v1/auth/internal/users/{user_id}", headers=self.headers
        )
        if response.status_code >= 400:
            return None
        return str(response.json().get("email")) or None

    async def get_account_owner_email(self, account_id: UUID) -> str | None:
        response = await self.client.get(
            f"{self.tenant_service_url}/api/v1/accounts/internal/{account_id}/owner", headers=self.headers
        )
        if response.status_code >= 400:
            return None
        owner_user_id = response.json().get("user_id")
        if not owner_user_id:
            return None
        return await self.get_user_email(UUID(str(owner_user_id)))

    async def close(self) -> None:
        await self.client.aclose()
