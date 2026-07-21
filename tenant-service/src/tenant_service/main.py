from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import ORJSONResponse
from starlette.middleware.trustedhost import TrustedHostMiddleware

from tenant_service.api.routes import accounts, invites, operations
from tenant_service.core.config import get_settings
from tenant_service.core.errors import TenantError, tenant_error_handler
from tenant_service.core.logging import configure_logging
from tenant_service.database import Database, DatabaseProtocol
from tenant_service.services.accounts import AccountService
from tenant_service.services.identity import IdentityServiceProtocol, JWTIdentityService
from tenant_service.services.rabbitmq import EventBusProtocol, RabbitMQService


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    await app.state.rabbitmq.start(app.state.accounts.handle_event)
    yield
    await app.state.rabbitmq.close()
    await app.state.database.close()


def create_app(
    database: DatabaseProtocol | None = None,
    rabbitmq: EventBusProtocol | None = None,
    identity: IdentityServiceProtocol | None = None,
) -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)
    app = FastAPI(
        title="CreditFlow Tenant Service",
        version=settings.version,
        default_response_class=ORJSONResponse,
        lifespan=lifespan,
    )
    app.state.settings = settings
    app.state.database = database or Database(settings.database_url)
    app.state.rabbitmq = rabbitmq or RabbitMQService(settings.rabbitmq_url)
    app.state.identity = identity or JWTIdentityService(settings)
    app.state.accounts = AccountService(app.state.database.sessions, app.state.rabbitmq)
    app.add_exception_handler(TenantError, tenant_error_handler)
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.trusted_hosts)
    app.include_router(operations.router)
    app.include_router(accounts.router)
    app.include_router(invites.router)
    return app


app = create_app()
