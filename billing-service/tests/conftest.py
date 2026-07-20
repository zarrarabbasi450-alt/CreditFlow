from collections.abc import AsyncIterator
from typing import Any
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from billing_service.main import create_app
from billing_service.models import Base, Subscription
from billing_service.services.identity import Identity

ACCOUNT_ID = uuid4()


class IdentityStub:
    def __init__(self, role: str = "Owner") -> None:
        self.role = role

    def verify(self, token: str) -> Identity:
        del token
        return Identity(uuid4(), ACCOUNT_ID, self.role)


class StripeStub:
    def create_customer(self, account_id: str, name: str) -> str:
        return f"cus_{account_id[:8]}"

    def create_checkout(self, customer: str, price: str, seats: int, account_id: str) -> str:
        return "https://checkout.stripe.test/session"

    def create_portal(self, customer: str) -> str:
        return "https://billing.stripe.test/portal"

    def update_subscription(
        self, subscription_id: str, item_id: str, price: str, seats: int, proration: str
    ) -> dict[str, Any]:
        return {"id": subscription_id}

    def cancel_subscription(self, subscription_id: str) -> dict[str, Any]:
        return {"id": subscription_id}

    def create_refund(self, payment_intent: str, amount: int | None, reason: str) -> dict[str, Any]:
        return {"id": "re_test", "amount": amount or 1000, "currency": "usd", "status": "succeeded"}


class BusStub:
    events: list[Any]

    def __init__(self) -> None:
        self.events = []

    async def start(self, account_handler: Any, webhook_handler: Any) -> None:
        pass

    async def publish(self, event: Any) -> None:
        self.events.append(event)

    async def ping(self) -> bool:
        return True

    async def close(self) -> None:
        pass


class DatabaseStub:
    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self.sessions = sessions

    async def ping(self) -> bool:
        return True

    async def close(self) -> None:
        pass


@pytest.fixture
async def client() -> AsyncIterator[AsyncClient]:
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        execution_options={"schema_translate_map": {"billing": None}},
    )
    async with engine.begin() as connection:
        await connection.run_sync(lambda conn: Base.metadata.create_all(conn, checkfirst=True))
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    async with sessions() as session, session.begin():
        session.add(Subscription(account_id=ACCOUNT_ID, stripe_customer_id="cus_test"))
    app = create_app(DatabaseStub(sessions), BusStub(), IdentityStub(), StripeStub())
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as value:
        yield value
    await engine.dispose()


@pytest.fixture
def auth() -> dict[str, str]:
    return {"Authorization": "Bearer test"}
