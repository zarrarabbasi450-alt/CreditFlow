import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI, Request
from fastapi.responses import ORJSONResponse
from starlette.middleware.cors import CORSMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware

from social_publishing_service.api.routes.operations import router as operations_router
from social_publishing_service.api.routes.publishing import router as publishing_router
from social_publishing_service.core.config import get_settings
from social_publishing_service.core.errors import SocialPublishingError, social_error_handler
from social_publishing_service.core.logging import configure_logging
from social_publishing_service.database import Database, DatabaseProtocol
from social_publishing_service.middleware import RequestContextMiddleware
from social_publishing_service.services.content_client import ContentClient, ContentClientProtocol
from social_publishing_service.services.crypto import TokenCipher
from social_publishing_service.services.identity import IdentityServiceProtocol, JWTIdentityService
from social_publishing_service.services.linkedin import LinkedInClient, LinkedInClientProtocol
from social_publishing_service.services.publishing import SocialPublishingService
from social_publishing_service.services.rabbitmq import EventBusProtocol, RabbitMQService


async def token_refresh_loop(publishing: SocialPublishingService, interval_seconds: int) -> None:
    while True:
        await asyncio.sleep(interval_seconds)
        await publishing.refresh_expiring_tokens()


async def exception_handler(request: Request, exc: Exception) -> ORJSONResponse:
    if isinstance(exc, SocialPublishingError):
        return await social_error_handler(request, exc)
    return ORJSONResponse(
        {
            "success": False,
            "error": {"code": "INTERNAL_ERROR", "message": "Unexpected social publishing error"},
        },
        status_code=500,
    )


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    configure_logging(settings.log_level)
    database = getattr(app.state, "database", None) or Database(settings.database_url)
    events = getattr(app.state, "events", None) or RabbitMQService(settings.rabbitmq_url)
    linkedin = getattr(app.state, "linkedin", None) or LinkedInClient(settings)
    content = getattr(app.state, "content_client", None) or ContentClient(
        settings.content_service_url, settings.internal_service_token
    )
    cipher = getattr(app.state, "cipher", None)
    if cipher is None and settings.social_token_encryption_key:
        cipher = TokenCipher(settings.social_token_encryption_key)
    publishing = getattr(app.state, "publishing", None) or SocialPublishingService(
        database.sessions, events, linkedin, content, cipher, settings
    )
    app.state.settings = settings
    app.state.database = database
    app.state.events = events
    app.state.linkedin = linkedin
    app.state.content_client = content
    app.state.cipher = cipher
    app.state.publishing = publishing
    app.state.identity_service = getattr(app.state, "identity_service", None) or JWTIdentityService(settings)
    await events.start(publishing.consume)
    refresh_task = asyncio.create_task(
        token_refresh_loop(publishing, settings.token_refresh_interval_seconds),
        name="linkedin-token-refresh",
    )
    try:
        yield
    finally:
        refresh_task.cancel()
        with suppress(asyncio.CancelledError):
            await refresh_task
        await events.close()
        await linkedin.close()
        await content.close()
        await database.close()


def create_app(
    database: DatabaseProtocol | None = None,
    events: EventBusProtocol | None = None,
    linkedin: LinkedInClientProtocol | None = None,
    content: ContentClientProtocol | None = None,
    identity_service: IdentityServiceProtocol | None = None,
    cipher: TokenCipher | None = None,
) -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="CreditFlow Social Publishing Service", version=settings.version, lifespan=lifespan)
    app.state.settings = settings
    if database is not None:
        app.state.database = database
    if events is not None:
        app.state.events = events
    if linkedin is not None:
        app.state.linkedin = linkedin
    if content is not None:
        app.state.content_client = content
    if identity_service is not None:
        app.state.identity_service = identity_service
    if cipher is not None:
        app.state.cipher = cipher
    app.add_middleware(RequestContextMiddleware)
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.trusted_hosts)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_exception_handler(SocialPublishingError, exception_handler)
    app.include_router(operations_router)
    app.include_router(publishing_router)
    return app


app = create_app()
