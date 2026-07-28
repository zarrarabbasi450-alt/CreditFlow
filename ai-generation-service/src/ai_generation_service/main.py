from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import ORJSONResponse
from starlette.middleware.trustedhost import TrustedHostMiddleware

from ai_generation_service.api.routes import generation, operations
from ai_generation_service.core.config import get_settings
from ai_generation_service.core.errors import AIServiceError, ai_error_handler
from ai_generation_service.core.logging import configure_logging
from ai_generation_service.database import Database, DatabaseProtocol
from ai_generation_service.middleware import RequestContextMiddleware
from ai_generation_service.services.credits import CreditsClient, CreditsClientProtocol
from ai_generation_service.services.generation import GenerationService
from ai_generation_service.services.identity import IdentityServiceProtocol, JWTIdentityService
from ai_generation_service.services.images import ImageProviderProtocol, PollinationsImageProvider
from ai_generation_service.services.openrouter import AIProviderProtocol, OpenRouterProvider
from ai_generation_service.services.rabbitmq import EventBusProtocol, RabbitMQService
from ai_generation_service.services.redis import RedisProtocol, RedisService
from ai_generation_service.services.usage import UsageClient, UsageClientProtocol


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    yield
    await app.state.ai.close()
    await app.state.usage.close()
    await app.state.credits.close()
    await app.state.events.close()
    await app.state.redis.close()
    await app.state.database.close()


def create_app(
    database: DatabaseProtocol | None = None,
    redis: RedisProtocol | None = None,
    events: EventBusProtocol | None = None,
    usage: UsageClientProtocol | None = None,
    credits: CreditsClientProtocol | None = None,
    ai: AIProviderProtocol | None = None,
    images: ImageProviderProtocol | None = None,
    identity: IdentityServiceProtocol | None = None,
) -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)
    app = FastAPI(
        title="CreditFlow AI Generation Service",
        version=settings.version,
        default_response_class=ORJSONResponse,
        lifespan=lifespan,
    )
    app.state.settings = settings
    app.state.database = database or Database(settings.database_url)
    app.state.redis = redis or RedisService(settings.redis_url)
    app.state.events = events or RabbitMQService(settings.rabbitmq_url)
    app.state.usage = usage or UsageClient(settings)
    app.state.credits = credits or CreditsClient(settings)
    app.state.ai = ai or OpenRouterProvider(settings)
    app.state.images = images or PollinationsImageProvider(settings)
    app.state.identity = identity or JWTIdentityService(settings)
    app.state.generations = GenerationService(
        app.state.database.sessions,
        app.state.redis,
        app.state.events,
        app.state.usage,
        app.state.credits,
        app.state.ai,
        app.state.images,
        settings,
    )
    app.add_exception_handler(AIServiceError, ai_error_handler)
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.trusted_hosts)
    app.add_middleware(RequestContextMiddleware)
    app.include_router(operations.router)
    app.include_router(generation.router)
    app.include_router(generation.internal_router)
    return app


app = create_app()
