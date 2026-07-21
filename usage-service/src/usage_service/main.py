from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import ORJSONResponse
from starlette.middleware.trustedhost import TrustedHostMiddleware

from usage_service.api.routes import operations, usage
from usage_service.core.config import get_settings
from usage_service.core.errors import UsageError, usage_error_handler
from usage_service.core.logging import configure_logging
from usage_service.database import Database, DatabaseProtocol
from usage_service.middleware import RequestContextMiddleware
from usage_service.services.identity import IdentityServiceProtocol, JWTIdentityService
from usage_service.services.rabbitmq import EventBusProtocol, RabbitMQService
from usage_service.services.redis import RedisProtocol, RedisService
from usage_service.services.usage import UsageService


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    await app.state.events.start(app.state.usage.consume)
    yield
    await app.state.events.close()
    await app.state.redis.close()
    await app.state.database.close()


def create_app(
    database: DatabaseProtocol | None = None,
    redis: RedisProtocol | None = None,
    events: EventBusProtocol | None = None,
    identity: IdentityServiceProtocol | None = None,
) -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)
    app = FastAPI(
        title="CreditFlow Usage / Metering Service",
        version=settings.version,
        default_response_class=ORJSONResponse,
        lifespan=lifespan,
    )
    app.state.settings = settings
    app.state.database = database or Database(settings.database_url)
    app.state.redis = redis or RedisService(settings.redis_url)
    app.state.events = events or RabbitMQService(settings.rabbitmq_url)
    app.state.identity = identity or JWTIdentityService(settings)
    app.state.usage = UsageService(app.state.database.sessions, app.state.redis, app.state.events, settings)
    app.add_exception_handler(UsageError, usage_error_handler)
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.trusted_hosts)
    app.add_middleware(RequestContextMiddleware)
    app.include_router(operations.router)
    app.include_router(usage.router)
    return app


app = create_app()
