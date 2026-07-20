import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import ORJSONResponse
from starlette.middleware.trustedhost import TrustedHostMiddleware

from billing_service.api.routes import billing, operations
from billing_service.core.config import get_settings
from billing_service.core.errors import BillingError, billing_error_handler
from billing_service.core.logging import configure_logging
from billing_service.database import Database, DatabaseProtocol
from billing_service.services.billing import BillingService
from billing_service.services.identity import IdentityServiceProtocol, JWTIdentityService
from billing_service.services.outbox import OutboxPublisher
from billing_service.services.rabbitmq import EventBusProtocol, RabbitMQService
from billing_service.services.stripe import StripeProtocol, StripeService

configure_logging()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    await app.state.rabbitmq.start(
        app.state.billing.create_account_customer, app.state.billing.handle_gateway_event
    )
    outbox_task = asyncio.create_task(app.state.outbox.run())

    async def dunning() -> None:
        while True:
            await asyncio.sleep(60)
            await app.state.billing.downgrade_overdue()

    dunning_task = asyncio.create_task(dunning())
    yield
    app.state.outbox.stop()
    dunning_task.cancel()
    await asyncio.gather(outbox_task, dunning_task, return_exceptions=True)
    await app.state.rabbitmq.close()
    await app.state.database.close()


def create_app(
    database: DatabaseProtocol | None = None,
    rabbitmq: EventBusProtocol | None = None,
    identity: IdentityServiceProtocol | None = None,
    stripe_service: StripeProtocol | None = None,
) -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="CreditFlow Billing Service",
        version=settings.version,
        default_response_class=ORJSONResponse,
        lifespan=lifespan,
    )
    app.state.settings = settings
    app.state.database = database or Database(settings.database_url)
    app.state.rabbitmq = rabbitmq or RabbitMQService(settings.rabbitmq_url)
    app.state.identity = identity or JWTIdentityService(settings)
    app.state.stripe = stripe_service or StripeService(settings)
    app.state.billing = BillingService(app.state.database.sessions, app.state.stripe, settings)
    app.state.outbox = OutboxPublisher(
        app.state.database.sessions, app.state.rabbitmq, settings.outbox_poll_seconds
    )
    app.add_exception_handler(BillingError, billing_error_handler)
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.trusted_hosts)
    app.include_router(operations.router)
    app.include_router(billing.router)
    return app


app = create_app()
