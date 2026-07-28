from collections.abc import AsyncIterator
from datetime import datetime
from typing import Any
from uuid import UUID

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from scraper_service.core.config import Settings
from scraper_service.main import create_app
from scraper_service.models import ScrapedDocument, ScraperJob
from scraper_service.services.crawler import CrawlerProtocol, PageFetchResult
from scraper_service.services.identity import Identity
from scraper_service.services.rabbitmq import InMemoryEventBus
from scraper_service.services.rate_limiter import DomainRateLimiter
from scraper_service.services.robots import RobotsCheckerProtocol
from scraper_service.services.scraper import ScraperService
from scraper_service.services.serp import SerpClientProtocol, SerpResult

TEST_ACCOUNT_ID = UUID("22222222-2222-2222-2222-222222222222")
TEST_USER_ID = UUID("11111111-1111-1111-1111-111111111111")


class TestIdentityService:
    def verify(self, token: str) -> Identity:
        del token
        return Identity(user_id=TEST_USER_ID, account_id=TEST_ACCOUNT_ID, account_role="Owner")


class InMemoryRepository:
    def __init__(self) -> None:
        self.jobs: dict[UUID, ScraperJob] = {}
        self.documents: dict[UUID, ScrapedDocument] = {}
        self.processed_event_ids: set[UUID] = set()

    async def insert_job(self, job: ScraperJob) -> None:
        self.jobs[job.id] = job

    async def get_job(self, job_id: UUID) -> ScraperJob | None:
        return self.jobs.get(job_id)

    async def list_jobs(self, account_id: UUID | None, limit: int = 100) -> list[ScraperJob]:
        items = [job for job in self.jobs.values() if account_id is None or job.account_id == account_id]
        return sorted(items, key=lambda job: job.created_at, reverse=True)[:limit]

    async def replace_job(self, job: ScraperJob) -> None:
        self.jobs[job.id] = job

    async def due_recurring_jobs(self, now: datetime) -> list[ScraperJob]:
        return [
            job
            for job in self.jobs.values()
            if job.recurring
            and job.status in {"completed", "failed"}
            and job.next_run_at is not None
            and job.next_run_at <= now
        ]

    async def insert_document(self, document: ScrapedDocument) -> None:
        self.documents[document.id] = document

    async def get_document(self, document_id: UUID) -> ScrapedDocument | None:
        return self.documents.get(document_id)

    async def list_documents(self, job_id: UUID) -> list[ScrapedDocument]:
        return [document for document in self.documents.values() if document.job_id == job_id]

    async def has_processed_event(self, event_id: UUID) -> bool:
        return event_id in self.processed_event_ids

    async def mark_event_processed(self, event_id: UUID, event_type: str) -> None:
        del event_type
        self.processed_event_ids.add(event_id)

    async def ping(self) -> bool:
        return True

    async def close(self) -> None:
        return None


class FakeCrawler(CrawlerProtocol):
    async def fetch(self, url: str) -> PageFetchResult:
        return PageFetchResult(
            url=url, status_code=200, title="Example title", text="Example page text", links=[]
        )

    async def close(self) -> None:
        return None


class AllowAllRobotsChecker(RobotsCheckerProtocol):
    async def allowed(self, url: str, client: Any) -> bool:
        del url, client
        return True


class FakeSerpClient(SerpClientProtocol):
    async def search(self, query: str) -> SerpResult:
        return SerpResult(
            query=query,
            title=query,
            organic_results=[
                {"title": "Competitor result", "snippet": "Trend snippet", "link": "https://example.com"}
            ],
            related_searches=[{"query": f"{query} trends"}],
            raw={"search_information": {"query_displayed": query}},
        )

    async def close(self) -> None:
        return None


@pytest_asyncio.fixture
async def app() -> AsyncIterator[Any]:
    repository = InMemoryRepository()
    events = InMemoryEventBus()
    crawler = FakeCrawler()
    serp = FakeSerpClient()
    settings = Settings(internal_service_token="internal-test-token")  # noqa: S106
    application = create_app(
        repository=repository,
        events=events,
        crawler=crawler,
        serp=serp,
        identity_service=TestIdentityService(),
    )
    application.state.settings = settings
    scraper = ScraperService(
        repository,
        events,
        crawler,
        serp,
        AllowAllRobotsChecker(),
        DomainRateLimiter(0.0),
        settings.max_pages_per_job,
        settings.publish_max_attempts,
    )
    application.state.scraper = scraper
    await events.start(scraper.consume)
    yield application
    await scraper.close()


@pytest_asyncio.fixture
async def client(app: Any) -> AsyncIterator[AsyncClient]:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as ac:
        yield ac


@pytest.fixture
def auth_headers() -> dict[str, str]:
    return {"Authorization": "Bearer test"}
