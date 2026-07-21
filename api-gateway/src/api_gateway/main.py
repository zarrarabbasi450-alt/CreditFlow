from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import ORJSONResponse
from starlette.middleware.trustedhost import TrustedHostMiddleware

from api_gateway.api.routes import admin, dashboard, operations, proxy, sse, webhooks
from api_gateway.core.config import get_settings
from api_gateway.core.errors import (
    GatewayError,
    gateway_error_handler,
    unexpected_error_handler,
    validation_error_handler,
)
from api_gateway.core.logging import configure_logging
from api_gateway.middleware.auth_rate_limit import AuthRateLimitMiddleware
from api_gateway.middleware.request_context import RequestContextMiddleware
from api_gateway.services.proxy import ProxyService
from api_gateway.services.rabbitmq import RabbitPublisher
from api_gateway.services.rate_limiter import RateLimiter
from api_gateway.services.redis import InMemoryRedisService, RedisService
from api_gateway.services.sse import SSEService

configure_logging()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = app.state.settings
    redis = InMemoryRedisService() if settings.allow_in_memory_redis else RedisService(settings.redis_url)
    rabbit = RabbitPublisher(settings.rabbitmq_url)
    client = httpx.AsyncClient(
        timeout=httpx.Timeout(settings.downstream_timeout_seconds), follow_redirects=False
    )
    app.state.redis = redis
    app.state.rabbitmq = rabbit
    app.state.rate_limiter = RateLimiter(redis)
    app.state.proxy = ProxyService(client, settings.service_urls)
    app.state.sse = SSEService(redis, settings.sse_heartbeat_seconds)
    yield
    await client.aclose()
    await redis.close()
    await rabbit.close()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="CreditFlow API Gateway",
        version=settings.version,
        default_response_class=ORJSONResponse,
        lifespan=lifespan,
    )
    app.state.settings = settings
    app.add_exception_handler(GatewayError, gateway_error_handler)
    app.add_exception_handler(RequestValidationError, validation_error_handler)
    app.add_exception_handler(Exception, unexpected_error_handler)
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.trusted_hosts)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["Authorization", "Content-Type", "X-Request-ID", "X-Correlation-ID"],
    )
    app.add_middleware(AuthRateLimitMiddleware, settings=settings)
    app.add_middleware(RequestContextMiddleware)
    app.include_router(operations.router)
    app.include_router(webhooks.router)
    app.include_router(dashboard.router)
    app.include_router(admin.router)
    app.include_router(sse.router)
    app.include_router(proxy.router)
    return app


app = create_app()
