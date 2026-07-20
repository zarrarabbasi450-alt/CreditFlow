from fastapi import APIRouter, Request
from fastapi.responses import ORJSONResponse

router = APIRouter(tags=["operations"])


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "healthy"}


@router.get("/ready")
async def ready(request: Request) -> ORJSONResponse:
    database = await request.app.state.database.ping()
    rabbitmq = await request.app.state.events.ping()
    healthy = database and rabbitmq
    return ORJSONResponse(
        status_code=200 if healthy else 503,
        content={
            "status": "ready" if healthy else "not_ready",
            "checks": {"postgresql": database, "rabbitmq": rabbitmq},
        },
    )


@router.get("/version")
async def version(request: Request) -> dict[str, str]:
    return {"service": "credits-service", "version": request.app.state.settings.version}
