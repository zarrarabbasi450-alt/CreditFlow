from fastapi import APIRouter, Request, status
from fastapi.responses import ORJSONResponse

from auth_service import __version__
from auth_service.database import Database
from auth_service.schemas.responses import HealthResponse, ReadinessResponse

router = APIRouter()


@router.get("/health", operation_id="health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(status="healthy")


@router.get("/version", operation_id="version")
async def version() -> dict[str, str]:
    return {"service": "auth-service", "version": __version__}


@router.get("/ready", operation_id="ready", response_model=ReadinessResponse)
async def ready(request: Request) -> ORJSONResponse:
    database: Database = request.app.state.database
    try:
        healthy = await database.ping()
    except Exception:
        healthy = False
    return ORJSONResponse(
        {
            "status": "ready" if healthy else "not_ready",
            "checks": {"postgresql": "healthy" if healthy else "unhealthy"},
        },
        status_code=status.HTTP_200_OK if healthy else status.HTTP_503_SERVICE_UNAVAILABLE,
    )
