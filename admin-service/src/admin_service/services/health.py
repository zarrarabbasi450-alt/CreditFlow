import asyncio
import time
from typing import Protocol

import httpx

from admin_service.schemas.admin import ServiceHealthItem


class HealthCheckerProtocol(Protocol):
    async def check_all(self) -> list[ServiceHealthItem]: ...
    async def close(self) -> None: ...


class HealthChecker:
    """Pings each known service's `/health` endpoint to build the operational
    overview. Point-in-time only — `uptime` reflects this single check, not a
    tracked historical percentage, since admin-service keeps no health history."""

    def __init__(self, targets: dict[str, str], timeout_seconds: float) -> None:
        self.targets = targets
        self.client = httpx.AsyncClient(timeout=timeout_seconds)

    async def _check_one(self, service: str, base_url: str) -> ServiceHealthItem:
        started = time.monotonic()
        try:
            response = await self.client.get(f"{base_url.rstrip('/')}/health")
            latency_ms = int((time.monotonic() - started) * 1000)
            if response.status_code == 200:
                return ServiceHealthItem(
                    service=service, status="Healthy", uptime=100.0, latencyP95Ms=latency_ms, detail="OK"
                )
            return ServiceHealthItem(
                service=service,
                status="Degraded",
                uptime=0.0,
                latencyP95Ms=latency_ms,
                detail=f"HTTP {response.status_code}",
            )
        except httpx.HTTPError as exc:
            latency_ms = int((time.monotonic() - started) * 1000)
            return ServiceHealthItem(
                service=service, status="Down", uptime=0.0, latencyP95Ms=latency_ms, detail=str(exc)
            )

    async def check_all(self) -> list[ServiceHealthItem]:
        return list(
            await asyncio.gather(
                *(self._check_one(service, url) for service, url in self.targets.items())
            )
        )

    async def close(self) -> None:
        await self.client.aclose()
