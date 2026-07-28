from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import ORJSONResponse
from starlette.middleware.cors import CORSMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware

from admin_service.api.routes.admin import router as admin_router
from admin_service.api.routes.operations import router as operations_router
from admin_service.core.config import get_settings
from admin_service.core.errors import AdminError, admin_error_handler
from admin_service.core.logging import configure_logging
from admin_service.database import Database, DatabaseProtocol
from admin_service.middleware import RequestContextMiddleware
from admin_service.services.admin import AdminService
from admin_service.services.directory import DirectoryClient, DirectoryClientProtocol
from admin_service.services.health import HealthChecker, HealthCheckerProtocol
from admin_service.services.identity import IdentityServiceProtocol, JWTIdentityService
from admin_service.services.rabbitmq import EventBusProtocol, RabbitMQService
from admin_service.services.redis import RedisSessionDirectory, SessionDirectoryProtocol


async def exception_handler(request: Request, exc: Exception) -> ORJSONResponse:
    if isinstance(exc, AdminError):
        return await admin_error_handler(request, exc)
    return ORJSONResponse(
        {"success": False, "error": {"code": "INTERNAL_ERROR", "message": "Unexpected admin error"}},
        status_code=500,
    )


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    configure_logging(settings.log_level)
    database = getattr(app.state, "database", None) or Database(settings.database_url)
    events = getattr(app.state, "events", None) or RabbitMQService(settings.rabbitmq_url)
    session_directory = getattr(app.state, "session_directory", None) or RedisSessionDirectory(
        settings.redis_url
    )
    directory = getattr(app.state, "directory", None) or DirectoryClient(
        settings.tenant_service_url,
        settings.credits_service_url,
        settings.usage_service_url,
        settings.internal_service_token,
        settings.request_timeout_seconds,
    )
    health = getattr(app.state, "health", None) or HealthChecker(
        settings.health_targets, settings.health_check_timeout_seconds
    )
    admin = getattr(app.state, "admin", None) or AdminService(
        database.sessions, session_directory, directory, health
    )
    app.state.settings = settings
    app.state.database = database
    app.state.events = events
    app.state.session_directory = session_directory
    app.state.directory = directory
    app.state.health = health
    app.state.admin = admin
    app.state.identity_service = getattr(app.state, "identity_service", None) or JWTIdentityService(settings)
    await events.start(admin.consume)
    try:
        yield
    finally:
        await events.close()
        await session_directory.close()
        await directory.close()
        await health.close()
        await database.close()


def create_app(
    database: DatabaseProtocol | None = None,
    events: EventBusProtocol | None = None,
    session_directory: SessionDirectoryProtocol | None = None,
    directory: DirectoryClientProtocol | None = None,
    health: HealthCheckerProtocol | None = None,
    identity_service: IdentityServiceProtocol | None = None,
) -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="CreditFlow Admin Service", version=settings.version, lifespan=lifespan)
    app.state.settings = settings
    if database is not None:
        app.state.database = database
    if events is not None:
        app.state.events = events
    if session_directory is not None:
        app.state.session_directory = session_directory
    if directory is not None:
        app.state.directory = directory
    if health is not None:
        app.state.health = health
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
    app.add_exception_handler(AdminError, exception_handler)
    app.include_router(operations_router)
    app.include_router(admin_router)
    return app


app = create_app()
