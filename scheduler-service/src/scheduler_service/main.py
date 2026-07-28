from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import ORJSONResponse
from starlette.middleware.cors import CORSMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware

from scheduler_service.api.routes.operations import router as operations_router
from scheduler_service.api.routes.scheduler import router as scheduler_router
from scheduler_service.core.config import get_settings
from scheduler_service.core.errors import SchedulerError, scheduler_error_handler
from scheduler_service.core.logging import configure_logging
from scheduler_service.database import Database, DatabaseProtocol
from scheduler_service.middleware import RequestContextMiddleware
from scheduler_service.services.identity import IdentityServiceProtocol, JWTIdentityService
from scheduler_service.services.rabbitmq import EventBusProtocol, RabbitMQService
from scheduler_service.services.redis_lock import LockProtocol, RedisLockService
from scheduler_service.services.scheduler import SchedulerService


async def scheduler_exception_handler(request: Request, exc: Exception) -> ORJSONResponse:
    if isinstance(exc, SchedulerError):
        return await scheduler_error_handler(request, exc)
    return ORJSONResponse(
        {
            "success": False,
            "error": {"code": "INTERNAL_ERROR", "message": "Unexpected scheduler service error"},
            "meta": {"requestId": getattr(request.state, "request_id", None)},
        },
        status_code=500,
    )


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    configure_logging(settings.log_level)
    database = getattr(app.state, "database", None) or Database(settings.database_url)
    events = getattr(app.state, "events", None) or RabbitMQService(settings.rabbitmq_url)
    locks = getattr(app.state, "locks", None) or RedisLockService(settings.redis_url)
    scheduler = getattr(app.state, "scheduler", None) or SchedulerService(
        database.sessions, events, locks, settings.schedule_lock_ttl_seconds
    )
    identity_service = getattr(app.state, "identity_service", None) or JWTIdentityService(settings)
    app.state.settings = getattr(app.state, "settings", settings)
    app.state.database = database
    app.state.events = events
    app.state.locks = locks
    app.state.scheduler = scheduler
    app.state.identity_service = identity_service
    await events.start(scheduler.consume)
    try:
        yield
    finally:
        await events.close()
        await locks.close()
        await database.close()


def create_app(
    database: DatabaseProtocol | None = None,
    events: EventBusProtocol | None = None,
    locks: LockProtocol | None = None,
    identity_service: IdentityServiceProtocol | None = None,
) -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="CreditFlow Scheduler Service", version=settings.version, lifespan=lifespan)
    app.state.settings = settings
    if database is not None:
        app.state.database = database
    if events is not None:
        app.state.events = events
    if locks is not None:
        app.state.locks = locks
    if identity_service is not None:
        app.state.identity_service = identity_service
    app.add_middleware(RequestContextMiddleware)
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.trusted_hosts)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_exception_handler(SchedulerError, scheduler_exception_handler)
    app.include_router(operations_router)
    app.include_router(scheduler_router)
    return app


app = create_app()
