from fastapi import APIRouter, Request
from fastapi.responses import ORJSONResponse

router = APIRouter(tags=["operations"])


@router.get("/health", operation_id="health")
async def health() -> dict[str, str]:
    return {"status": "healthy"}


@router.get("/ready", operation_id="ready")
async def ready(request: Request) -> ORJSONResponse:
    database = await request.app.state.database.ping()
    redis = await request.app.state.redis.ping()
    rabbitmq = await request.app.state.events.ping()
    healthy = database and redis and rabbitmq
    return ORJSONResponse(
        status_code=200 if healthy else 503,
        content={
            "status": "ready" if healthy else "not_ready",
            "checks": {"postgresql": database, "redis": redis, "rabbitmq": rabbitmq},
        },
    )


@router.get("/version", operation_id="version")
async def version(request: Request) -> dict[str, str]:
    return {"service": "usage-service", "version": request.app.state.settings.version}
