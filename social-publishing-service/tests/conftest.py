from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import UUID

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from social_publishing_service.core.config import Settings
from social_publishing_service.main import create_app
from social_publishing_service.models import Base
from social_publishing_service.services.content_client import ContentClientProtocol, ContentSnapshot
from social_publishing_service.services.identity import Identity
from social_publishing_service.services.linkedin import (
    LinkedInClientProtocol,
    LinkedInProfile,
    LinkedInPublishResult,
    LinkedInTokens,
)
from social_publishing_service.services.publishing import SocialPublishingService
from social_publishing_service.services.rabbitmq import InMemoryEventBus


class TestIdentityService:
    def verify(self, token: str) -> Identity:
        del token
        return Identity(
            user_id=UUID("11111111-1111-1111-1111-111111111111"),
            account_id=UUID("22222222-2222-2222-2222-222222222222"),
            account_role="Owner",
        )


class TestDatabase:
    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self.sessions = sessions

    async def ping(self) -> bool:
        return True

    async def close(self) -> None:
        return None


class FakeContentClient(ContentClientProtocol):
    async def get_content(self, content_id: UUID, bearer_token: str | None = None) -> ContentSnapshot:
        del bearer_token
        return ContentSnapshot(
            id=content_id,
            account_id=UUID("22222222-2222-2222-2222-222222222222"),
            title="Launch post",
            body="Scheduled LinkedIn post",
            status="approved",
            image_url="https://example.com/image.png",
            image_asset_ref="local:image.png",
        )

    async def close(self) -> None:
        return None


class FakeLinkedInClient(LinkedInClientProtocol):
    def authorization_url(self, state: str) -> str:
        return f"https://linkedin.test/oauth?state={state}"

    async def exchange_code(self, code: str) -> LinkedInTokens:
        del code
        return LinkedInTokens(
            "access",
            "refresh",
            datetime.now(UTC) + timedelta(minutes=30),
            datetime.now(UTC) + timedelta(days=60),
            "openid profile email w_member_social",
        )

    async def profile(self, access_token: str) -> LinkedInProfile:
        del access_token
        return LinkedInProfile("urn:li:person:test", "Test Member", "test@example.com")

    async def refresh(self, refresh_token: str) -> LinkedInTokens:
        del refresh_token
        return LinkedInTokens(
            "access2",
            "refresh2",
            datetime.now(UTC) + timedelta(hours=2),
            datetime.now(UTC) + timedelta(days=60),
            "openid profile email w_member_social",
        )

    async def publish(
        self, access_token: str, author_urn: str, caption: str, image_url: str | None
    ) -> LinkedInPublishResult:
        del access_token, author_urn, caption, image_url
        return LinkedInPublishResult("linkedin-post-id", "https://linkedin.example/post", "urn:li:image:test")

    async def close(self) -> None:
        return None


@pytest_asyncio.fixture
async def app(tmp_path: Path) -> AsyncIterator[Any]:
    engine = create_async_engine(
        f"sqlite+aiosqlite:///{tmp_path / 'social.db'}",
        execution_options={"schema_translate_map": {"social": None}},
    )
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    database = TestDatabase(sessions)
    events = InMemoryEventBus()
    application = create_app(
        database=database,
        events=events,
        linkedin=FakeLinkedInClient(),
        content=FakeContentClient(),
        identity_service=TestIdentityService(),
    )
    application.state.database = database
    application.state.events = events
    application.state.settings = Settings(linkedin_dev_mode=True, social_token_encryption_key="")
    application.state.publishing = SocialPublishingService(
        sessions,
        events,
        FakeLinkedInClient(),
        FakeContentClient(),
        None,
        application.state.settings,
    )
    await events.start(application.state.publishing.consume)
    yield application
    await engine.dispose()


@pytest_asyncio.fixture
async def client(app: Any) -> AsyncIterator[AsyncClient]:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as ac:
        yield ac


@pytest.fixture
def auth_headers() -> dict[str, str]:
    return {"Authorization": "Bearer test"}
