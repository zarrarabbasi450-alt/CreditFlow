import asyncio
from time import perf_counter

from fastapi import APIRouter, Request

from api_gateway.schemas.responses import (
    AdminActivity,
    AdminMetric,
    AdminOverviewResponse,
    AdminView,
    ServiceHealth,
)
from api_gateway.services.proxy import ProxyService

router = APIRouter(prefix="/api/v1/admin", tags=["administration"])
SERVICES = ("auth", "users", "billing", "credits", "usage")


async def probe(proxy: ProxyService, service: str) -> ServiceHealth:
    started = perf_counter()
    healthy = await proxy.service_healthy(service)
    elapsed = round((perf_counter() - started) * 1000)
    if healthy:
        return ServiceHealth(
            service=service.replace("users", "tenant").title(),
            status="Healthy",
            uptime=100,
            latencyP95Ms=elapsed,
            detail="Service is reachable",
        )
    return ServiceHealth(
        service=service.replace("users", "tenant").title(),
        status="Down",
        uptime=0,
        latencyP95Ms=elapsed,
        detail="Service is unavailable",
    )


@router.get("/overview", response_model=AdminOverviewResponse, operation_id="admin_overview")
async def overview(request: Request) -> AdminOverviewResponse:
    proxy: ProxyService = request.app.state.proxy
    health = list(await asyncio.gather(*(probe(proxy, service) for service in SERVICES)))
    healthy = sum(item.status == "Healthy" for item in health)
    rows = [AdminActivity(title=item.service, detail=item.detail, status=item.status) for item in health]
    return AdminOverviewResponse(
        view=AdminView(
            metrics=[
                AdminMetric(label="Services healthy", value=f"{healthy}/{len(health)}", change="Live"),
                AdminMetric(label="Services down", value=str(len(health) - healthy), change="Live"),
            ],
            rows=rows,
        ),
        health=health,
    )
