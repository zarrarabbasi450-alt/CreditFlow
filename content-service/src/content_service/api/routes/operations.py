from fastapi import APIRouter, Request

router = APIRouter(tags=["operations"])


@router.get("/health", operation_id="content_health")
async def health() -> dict[str, str]:
    return {"status": "healthy"}


@router.get("/ready", operation_id="content_ready")
async def ready(request: Request) -> dict[str, str]:
    database_ready = await request.app.state.database.ping()
    events_ready = await request.app.state.events.ping()
    return {"status": "ready" if database_ready and events_ready else "degraded"}


@router.get("/version", operation_id="content_version")
async def version(request: Request) -> dict[str, str]:
    return {"service": "content-service", "version": str(request.app.state.settings.version)}
