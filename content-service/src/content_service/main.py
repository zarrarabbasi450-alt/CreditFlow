from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.staticfiles import StaticFiles

from content_service.api.routes.content import router as content_router
from content_service.api.routes.operations import router as operations_router
from content_service.core.config import get_settings
from content_service.core.errors import ContentError, content_error_handler
from content_service.core.logging import configure_logging
from content_service.database import Database, DatabaseProtocol
from content_service.middleware import RequestContextMiddleware
from content_service.services.content import ContentService
from content_service.services.identity import IdentityServiceProtocol, JWTIdentityService
from content_service.services.rabbitmq import EventBusProtocol, RabbitMQService
from content_service.services.storage import LocalStorage


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    configure_logging(settings.log_level)
    database = getattr(app.state, "database", None) or Database(settings.database_url)
    events = getattr(app.state, "events", None) or RabbitMQService(settings.rabbitmq_url)
    storage = getattr(app.state, "storage", None) or LocalStorage(
        settings.upload_dir, settings.public_upload_base_url
    )
    content = getattr(app.state, "content", None) or ContentService(database.sessions, events)
    identity_service = getattr(app.state, "identity_service", None) or JWTIdentityService(settings)
    app.state.settings = getattr(app.state, "settings", settings)
    app.state.database = database
    app.state.events = events
    app.state.storage = storage
    app.state.content = content
    app.state.identity_service = identity_service
    await events.start(content.consume)
    try:
        yield
    finally:
        await events.close()
        await database.close()


def create_app(
    database: DatabaseProtocol | None = None,
    events: EventBusProtocol | None = None,
    storage: LocalStorage | None = None,
    identity_service: IdentityServiceProtocol | None = None,
) -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="CreditFlow Content Service", version=settings.version, lifespan=lifespan)
    if database is not None:
        app.state.database = database
    if events is not None:
        app.state.events = events
    if storage is not None:
        app.state.storage = storage
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
    app.add_exception_handler(ContentError, content_error_handler)
    app.mount("/uploads", StaticFiles(directory=settings.upload_dir), name="uploads")
    app.include_router(operations_router)
    app.include_router(content_router)
    return app


app = create_app()
