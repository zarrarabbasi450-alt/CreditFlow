from fastapi import APIRouter, Request, status
from fastapi.responses import ORJSONResponse

from api_gateway import __version__

router = APIRouter()


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "healthy"}


@router.get("/version")
async def version() -> dict[str, str]:
    return {"service": "api-gateway", "version": __version__}


@router.get("/ready")
async def ready(request: Request) -> ORJSONResponse:
    checks: dict[str, str] = {}
    for name, check in (
        ("redis", request.app.state.redis.ping),
        ("rabbitmq", request.app.state.rabbitmq.ping),
    ):
        try:
            checks[name] = "healthy" if await check() else "unhealthy"
        except Exception:
            checks[name] = "unhealthy"
    healthy = all(value == "healthy" for value in checks.values())
    return ORJSONResponse(
        {"status": "ready" if healthy else "not_ready", "checks": checks},
        status_code=status.HTTP_200_OK if healthy else status.HTTP_503_SERVICE_UNAVAILABLE,
    )
