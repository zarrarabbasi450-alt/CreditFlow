from fastapi import APIRouter, Request
from fastapi.responses import ORJSONResponse

router = APIRouter(tags=["operations"])


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "healthy"}


@router.get("/ready")
async def ready(request: Request) -> ORJSONResponse:
    database, rabbitmq = await request.app.state.database.ping(), await request.app.state.rabbitmq.ping()
    status = 200 if database and rabbitmq else 503
    return ORJSONResponse(
        {
            "status": "ready" if status == 200 else "not_ready",
            "checks": {"database": database, "rabbitmq": rabbitmq},
        },
        status_code=status,
    )


@router.get("/version")
async def version(request: Request) -> dict[str, str]:
    return {"version": str(request.app.state.settings.version)}
