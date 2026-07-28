from typing import Any

from fastapi import APIRouter, Request

router = APIRouter()


@router.get("/health", operation_id="health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/ready", operation_id="ready")
async def ready(request: Request) -> dict[str, Any]:
    database_ok = await request.app.state.database.ping()
    events_ok = await request.app.state.events.ping()
    redis_ok = await request.app.state.locks.ping()
    return {"status": "ready" if database_ok and events_ok and redis_ok else "degraded"}


@router.get("/version", operation_id="version")
async def version(request: Request) -> dict[str, str]:
    return {"service": "scheduler-service", "version": request.app.state.settings.version}
