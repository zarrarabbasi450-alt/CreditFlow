from fastapi import APIRouter, Request

from ai_generation_service.schemas.operations import HealthResponse, ReadyResponse, VersionResponse

router = APIRouter(tags=["operations"])


@router.get("/health", response_model=HealthResponse, operation_id="health")
async def health() -> HealthResponse:
    return HealthResponse(status="ok")


@router.get("/ready", response_model=ReadyResponse, operation_id="ready")
async def ready(request: Request) -> ReadyResponse:
    checks = {
        "database": await request.app.state.database.ping(),
        "redis": await request.app.state.redis.ping(),
        "rabbitmq": await request.app.state.events.ping(),
    }
    return ReadyResponse(status="ok" if all(checks.values()) else "degraded", checks=checks)


@router.get("/version", response_model=VersionResponse, operation_id="version")
async def version(request: Request) -> VersionResponse:
    return VersionResponse(service="ai-generation-service", version=str(request.app.state.settings.version))
