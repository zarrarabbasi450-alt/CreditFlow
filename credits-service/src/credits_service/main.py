from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import ORJSONResponse
from starlette.middleware.trustedhost import TrustedHostMiddleware

from credits_service.api.routes import credits, operations
from credits_service.core.config import get_settings
from credits_service.core.errors import CreditsError, credits_error_handler
from credits_service.core.logging import configure_logging
from credits_service.database import Database, DatabaseProtocol
from credits_service.middleware import RequestContextMiddleware
from credits_service.services.billing import BillingClient, BillingProtocol
from credits_service.services.credits import CreditsService
from credits_service.services.identity import IdentityServiceProtocol, JWTIdentityService
from credits_service.services.rabbitmq import EventBusProtocol, RabbitMQService


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    await app.state.events.start(app.state.credits.consume)
    yield
    await app.state.events.close()
    await app.state.database.close()


def create_app(
    database: DatabaseProtocol | None = None,
    events: EventBusProtocol | None = None,
    identity: IdentityServiceProtocol | None = None,
    billing: BillingProtocol | None = None,
) -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)
    app = FastAPI(
        title="CreditFlow Credits & Marketplace Service",
        version=settings.version,
        default_response_class=ORJSONResponse,
        lifespan=lifespan,
    )
    app.state.settings = settings
    app.state.database = database or Database(settings.database_url)
    app.state.events = events or RabbitMQService(settings.rabbitmq_url)
    app.state.identity = identity or JWTIdentityService(settings)
    app.state.billing = billing or BillingClient(settings.billing_service_url)
    app.state.credits = CreditsService(app.state.database.sessions, app.state.events, settings)
    app.add_exception_handler(CreditsError, credits_error_handler)
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.trusted_hosts)
    app.add_middleware(RequestContextMiddleware)
    app.include_router(operations.router)
    app.include_router(credits.router)
    return app


app = create_app()
