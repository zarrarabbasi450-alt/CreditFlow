from collections.abc import AsyncIterator
from typing import Any
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from credits_service.main import create_app
from credits_service.models import Base, CreditLedger, LedgerType
from credits_service.services.identity import Identity

ACCOUNT_ID = uuid4()
SELLER_ID = uuid4()


class IdentityStub:
    def verify(self, token: str) -> Identity:
        account = SELLER_ID if token.endswith("seller") else ACCOUNT_ID
        return Identity(uuid4(), account, "Owner")


class BillingStub:
    async def create_escrow(
        self, token: str, listing_id: UUID, seller_account_id: UUID, amount: int
    ) -> tuple[str, str | None, str]:
        return "pi_test", "secret", "requires_confirmation"

    async def capture_escrow(self, token: str, payment_intent_id: str) -> str:
        return "succeeded"


class BusStub:
    def __init__(self) -> None:
        self.events: list[Any] = []

    async def start(self, handler: Any) -> None:
        self.handler = handler

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
        execution_options={"schema_translate_map": {"credits": None}},
    )
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    async with sessions() as session, session.begin():
        session.add(
            CreditLedger(
                account_id=SELLER_ID,
                entry_type=LedgerType.GRANT,
                amount=5000,
                description="seed",
                reference_type="test",
                reference_id="seed",
            )
        )
    app = create_app(DatabaseStub(sessions), BusStub(), IdentityStub(), BillingStub())
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as value:
        yield value
    await engine.dispose()


@pytest.fixture
def auth() -> dict[str, str]:
    return {"Authorization": "Bearer buyer"}


@pytest.fixture
def seller_auth() -> dict[str, str]:
    return {"Authorization": "Bearer seller"}
