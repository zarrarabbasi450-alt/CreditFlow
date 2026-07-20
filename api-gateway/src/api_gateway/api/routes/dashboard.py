import asyncio
from typing import Any

from fastapi import APIRouter, Request

from api_gateway.schemas.responses import DashboardResponse
from api_gateway.services.proxy import ProxyService

router = APIRouter(prefix="/api/v1/dashboard", tags=["dashboard"])
TARGETS = {
    "tenant": ("users", "/api/v1/accounts/my"),
    "credits": ("credits", "/api/v1/credits/summary"),
    "usage": ("usage", "/api/v1/usage/summary"),
    "content": ("content", "/api/v1/content/summary"),
    "scheduler": ("scheduler", "/api/v1/scheduler/summary"),
    "notifications": ("notifications", "/api/v1/notifications/summary"),
}


@router.get("/overview", response_model=DashboardResponse)
async def overview(request: Request) -> DashboardResponse:
    proxy: ProxyService = request.app.state.proxy
    results = await asyncio.gather(
        *(proxy.request_json(service, path, request) for service, path in TARGETS.values()),
        return_exceptions=True,
    )
    data: dict[str, Any] = {}
    degraded: list[str] = []
    for name, result in zip(TARGETS, results, strict=True):
        if isinstance(result, BaseException):
            degraded.append(name)
        else:
            data[name] = result
    return DashboardResponse(
        data=data,
        degraded_services=degraded,
        request_id=request.state.request_id,
        correlation_id=request.state.correlation_id,
    )
