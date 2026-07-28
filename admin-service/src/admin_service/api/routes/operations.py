from typing import Any

from fastapi import APIRouter, Request

router = APIRouter(tags=["operations"])


@router.get("/health", operation_id="health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/ready", operation_id="ready")
async def ready(request: Request) -> dict[str, str]:
    database = getattr(request.app.state, "database", None)
    events = getattr(request.app.state, "events", None)
    if database is not None:
        await database.ping()
    if events is not None:
        await events.ping()
    return {"status": "ready"}


@router.get("/version", operation_id="version")
async def version(request: Request) -> dict[str, Any]:
    settings = request.app.state.settings
    return {"service": "admin-service", "version": settings.version}
