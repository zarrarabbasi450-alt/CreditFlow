from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import ORJSONResponse
from starlette.middleware.cors import CORSMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware

from notification_service.api.routes.notifications import router as notifications_router
from notification_service.api.routes.operations import router as operations_router
from notification_service.core.config import Settings, get_settings
from notification_service.core.errors import NotificationError, notification_error_handler
from notification_service.core.logging import configure_logging
from notification_service.database import Database, DatabaseProtocol
from notification_service.middleware import RequestContextMiddleware
from notification_service.services.directory import DirectoryClient, DirectoryClientProtocol
from notification_service.services.email import EmailClientProtocol, GmailOAuthEmailClient, ResendEmailClient
from notification_service.services.identity import IdentityServiceProtocol, JWTIdentityService
from notification_service.services.notifications import NotificationService
from notification_service.services.rabbitmq import EventBusProtocol, RabbitMQService
from notification_service.services.slack import SlackClientProtocol, SlackWebhookClient


def _build_email_client(settings: Settings) -> EmailClientProtocol:
    if settings.email_provider == "gmail":
        return GmailOAuthEmailClient(
            settings.google_client_id,
            settings.google_client_secret,
            settings.google_refresh_token,
            settings.gmail_sender_email,
            settings.request_timeout_seconds,
        )
    return ResendEmailClient(settings.resend_api_key, settings.email_from, settings.request_timeout_seconds)


async def exception_handler(request: Request, exc: Exception) -> ORJSONResponse:
    if isinstance(exc, NotificationError):
        return await notification_error_handler(request, exc)
    return ORJSONResponse(
        {"success": False, "error": {"code": "INTERNAL_ERROR", "message": "Unexpected notification error"}},
        status_code=500,
    )


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    configure_logging(settings.log_level)
    database = getattr(app.state, "database", None) or Database(settings.database_url)
    events = getattr(app.state, "events", None) or RabbitMQService(settings.rabbitmq_url)
    email = getattr(app.state, "email", None) or _build_email_client(settings)
    slack = getattr(app.state, "slack", None) or SlackWebhookClient(
        settings.slack_webhook_url, settings.request_timeout_seconds
    )
    directory = getattr(app.state, "directory", None) or DirectoryClient(
        settings.auth_service_url,
        settings.tenant_service_url,
        settings.internal_service_token,
        settings.request_timeout_seconds,
    )
    notifications = getattr(app.state, "notifications", None) or NotificationService(
        database.sessions, events, email, slack, directory, settings.frontend_url
    )
    app.state.settings = settings
    app.state.database = database
    app.state.events = events
    app.state.email = email
    app.state.slack = slack
    app.state.directory = directory
    app.state.notifications = notifications
    app.state.identity_service = getattr(app.state, "identity_service", None) or JWTIdentityService(settings)
    await events.start(notifications.consume)
    try:
        yield
    finally:
        await events.close()
        await email.close()
        await slack.close()
        await directory.close()
        await database.close()


def create_app(
    database: DatabaseProtocol | None = None,
    events: EventBusProtocol | None = None,
    email: EmailClientProtocol | None = None,
    slack: SlackClientProtocol | None = None,
    directory: DirectoryClientProtocol | None = None,
    identity_service: IdentityServiceProtocol | None = None,
) -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="CreditFlow Notification Service", version=settings.version, lifespan=lifespan)
    app.state.settings = settings
    if database is not None:
        app.state.database = database
    if events is not None:
        app.state.events = events
    if email is not None:
        app.state.email = email
    if slack is not None:
        app.state.slack = slack
    if directory is not None:
        app.state.directory = directory
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
    app.add_exception_handler(NotificationError, exception_handler)
    app.include_router(operations_router)
    app.include_router(notifications_router)
    return app


app = create_app()
