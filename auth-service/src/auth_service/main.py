from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.responses import ORJSONResponse
from starlette.middleware.trustedhost import TrustedHostMiddleware

from auth_service.api.routes import auth, operations
from auth_service.core.config import get_settings
from auth_service.core.errors import AuthError, auth_error_handler, validation_error_handler
from auth_service.core.logging import configure_logging
from auth_service.database import Database, DatabaseProtocol
from auth_service.middleware.request_context import RequestContextMiddleware
from auth_service.services.auth import AuthService
from auth_service.services.email_verification import EmailVerificationService
from auth_service.services.jwt import JWTService
from auth_service.services.password_reset import PasswordResetService
from auth_service.services.rabbitmq import EventPublisherProtocol, RabbitMQPublisher
from auth_service.services.redis import RedisProtocol, RedisService


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    yield
    await app.state.redis.close()
    await app.state.publisher.close()
    await app.state.database.close()


def create_app(
    database: DatabaseProtocol | None = None,
    redis: RedisProtocol | None = None,
    publisher: EventPublisherProtocol | None = None,
) -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)
    app = FastAPI(
        title="CreditFlow Auth Service",
        version=settings.version,
        default_response_class=ORJSONResponse,
        lifespan=lifespan,
    )
    app.state.settings = settings
    app.state.database = database or Database(settings.database_url)
    app.state.redis = redis or RedisService(settings.redis_url)
    app.state.publisher = publisher or RabbitMQPublisher(settings.rabbitmq_url)
    app.state.email_verification = EmailVerificationService(
        app.state.database.sessions,
        app.state.publisher,
        settings.email_verification_expire_hours,
    )
    app.state.password_reset = PasswordResetService(
        app.state.database.sessions,
        app.state.redis,
        app.state.publisher,
        settings.password_reset_expire_minutes,
    )
    app.state.authentication = AuthService(
        app.state.database.sessions,
        JWTService(settings),
        app.state.redis,
        app.state.email_verification,
        settings.login_attempt_limit,
        settings.login_attempt_window_seconds,
        settings.bootstrap_superadmin_email,
        settings.tenant_service_url,
    )
    app.add_exception_handler(AuthError, auth_error_handler)
    app.add_exception_handler(RequestValidationError, validation_error_handler)
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.trusted_hosts)
    app.add_middleware(RequestContextMiddleware)
    app.include_router(operations.router)
    app.include_router(auth.router)
    return app


app = create_app()
