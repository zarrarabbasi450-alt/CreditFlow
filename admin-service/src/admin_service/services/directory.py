from typing import Protocol, cast
from uuid import UUID

import httpx

from admin_service.schemas.admin import AccountSummary


class DirectoryClientProtocol(Protocol):
    async def get_account_summary(self, account_id: UUID) -> AccountSummary: ...
    async def close(self) -> None: ...


class DirectoryClient:
    """Read-only aggregation across tenant-service, credits-service, and usage-service.

    Each call is independent and best-effort: if one dependency is unreachable or
    the account isn't known there, that slice of the summary is left as None rather
    than failing the whole aggregation — this is an ops visibility tool, not a
    write path, so partial data beats no data.
    """

    def __init__(
        self,
        tenant_service_url: str,
        credits_service_url: str,
        usage_service_url: str,
        internal_service_token: str,
        timeout_seconds: float,
    ) -> None:
        self.tenant_service_url = tenant_service_url.rstrip("/")
        self.credits_service_url = credits_service_url.rstrip("/")
        self.usage_service_url = usage_service_url.rstrip("/")
        self.headers = {"Authorization": f"Bearer {internal_service_token}"}
        self.client = httpx.AsyncClient(timeout=timeout_seconds)

    async def get_account_summary(self, account_id: UUID) -> AccountSummary:
        plan_tier: str | None = None
        seat_count: int | None = None
        member_count: int | None = None
        credit_balance: int | None = None
        usage_tokens: int | None = None
        usage_quota_tokens: int | None = None

        tenant_response = await self._get(
            f"{self.tenant_service_url}/api/v1/accounts/internal/{account_id}/summary"
        )
        if tenant_response is not None:
            plan_tier = cast(str | None, tenant_response.get("plan_tier"))
            seat_count = cast(int | None, tenant_response.get("seat_count"))
            member_count = cast(int | None, tenant_response.get("member_count"))

        credits_response = await self._get(
            f"{self.credits_service_url}/api/v1/credits/internal/{account_id}/balance"
        )
        if credits_response is not None:
            credit_balance = cast(int | None, credits_response.get("balance"))

        usage_response = await self._get(
            f"{self.usage_service_url}/api/v1/usage/summary", params={"account_id": str(account_id)}
        )
        if usage_response is not None:
            usage_tokens = cast(int | None, usage_response.get("tokens_used"))
            usage_quota_tokens = cast(int | None, usage_response.get("quota_tokens"))

        return AccountSummary(
            account_id=account_id,
            plan_tier=plan_tier,
            seat_count=seat_count,
            member_count=member_count,
            credit_balance=credit_balance,
            usage_tokens=usage_tokens,
            usage_quota_tokens=usage_quota_tokens,
        )

    async def _get(self, url: str, params: dict[str, str] | None = None) -> dict[str, object] | None:
        try:
            response = await self.client.get(url, headers=self.headers, params=params)
        except httpx.HTTPError:
            return None
        if response.status_code >= 400:
            return None
        result: dict[str, object] = response.json()
        return result

    async def close(self) -> None:
        await self.client.aclose()
