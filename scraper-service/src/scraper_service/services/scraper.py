import html
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import urlparse
from uuid import UUID

import httpx

from scraper_service.core.errors import ScraperError
from scraper_service.database import ScraperRepositoryProtocol
from scraper_service.models import ScrapedDocument, ScraperJob
from scraper_service.schemas.events import EventEnvelope
from scraper_service.schemas.scraper import (
    ProductMetric,
    ProductView,
    ScrapedDocumentRead,
    ScraperCollection,
    ScraperJobCreate,
    ScraperJobRead,
)
from scraper_service.services.crawler import CrawlerProtocol
from scraper_service.services.identity import Identity
from scraper_service.services.rabbitmq import EventBusProtocol
from scraper_service.services.rate_limiter import DomainRateLimiter
from scraper_service.services.robots import RobotsCheckerProtocol
from scraper_service.services.serp import SerpClientProtocol


class ScraperService:
    def __init__(
        self,
        repository: ScraperRepositoryProtocol,
        events: EventBusProtocol,
        crawler: CrawlerProtocol,
        serp: SerpClientProtocol,
        robots: RobotsCheckerProtocol,
        rate_limiter: DomainRateLimiter,
        max_pages_per_job: int,
        publish_max_attempts: int,
    ) -> None:
        self.repository = repository
        self.events = events
        self.crawler = crawler
        self.serp = serp
        self.robots = robots
        self.rate_limiter = rate_limiter
        self.max_pages_per_job = max_pages_per_job
        self.publish_max_attempts = publish_max_attempts
        self._http = httpx.AsyncClient(timeout=10)

    async def collection(self, identity: Identity) -> ScraperCollection:
        jobs = await self._list(identity)
        queued = sum(1 for job in jobs if job.status in {"queued", "running"})
        completed = sum(1 for job in jobs if job.status == "completed")
        failed = sum(1 for job in jobs if job.status == "failed")
        view = ProductView(
            title="Scraper",
            eyebrow="Research automation",
            description="Pull competitor pages and search trends into raw documents for content generation.",
            action="New scrape job",
            metrics=[
                ProductMetric(label="Active jobs", value=str(queued), change="Queued or running"),
                ProductMetric(label="Completed", value=str(completed), change="Documents ready"),
                ProductMetric(label="Failed", value=str(failed), change="Needs attention"),
            ],
            rows=[
                {
                    "title": job.name,
                    "detail": f"{job.job_type} · {job.target[:60]}",
                    "status": job.status.title(),
                }
                for job in jobs[:5]
            ],
        )
        return ScraperCollection(view=view, items=[self._job_read(job) for job in jobs])

    async def create(self, payload: ScraperJobCreate, identity: Identity) -> ScraperJobRead:
        if not identity.can_manage_jobs:
            raise ScraperError(403, "FORBIDDEN", "Owner or Admin role is required to create scrape jobs")
        if payload.job_type == "url":
            self._validate_url(payload.target)
        job = ScraperJob(
            account_id=identity.account_id,
            created_by=identity.user_id,
            job_type=payload.job_type,
            target=payload.target,
            name=payload.name,
            max_pages=min(payload.max_pages, self.max_pages_per_job),
            recurring=payload.recurring,
            interval_hours=payload.interval_hours,
        )
        await self.repository.insert_job(job)
        await self._dispatch(job.id)
        refreshed = await self.repository.get_job(job.id)
        assert refreshed is not None  # just persisted above
        return self._job_read(refreshed)

    async def get(self, job_id: UUID, identity: Identity) -> ScraperJobRead:
        job = await self._scoped(job_id, identity)
        return self._job_read(job)

    async def cancel(self, job_id: UUID, identity: Identity) -> ScraperJobRead:
        if not identity.can_manage_jobs:
            raise ScraperError(403, "FORBIDDEN", "Owner or Admin role is required to cancel scrape jobs")
        job = await self._scoped(job_id, identity)
        if job.status != "queued":
            raise ScraperError(409, "INVALID_STATUS", "Only queued jobs can be cancelled")
        job.status = "cancelled"
        job.updated_at = _utcnow()
        await self.repository.replace_job(job)
        return self._job_read(job)

    async def list_documents(self, job_id: UUID, identity: Identity) -> list[ScrapedDocumentRead]:
        await self._scoped(job_id, identity)
        documents = await self.repository.list_documents(job_id)
        return [ScrapedDocumentRead.model_validate(document.model_dump()) for document in documents]

    async def get_document(self, document_id: UUID, identity: Identity) -> ScrapedDocumentRead:
        document = await self.repository.get_document(document_id)
        if document is None:
            raise ScraperError(404, "DOCUMENT_NOT_FOUND", "Scraped document was not found")
        if not identity.is_superadmin and document.account_id != identity.account_id:
            raise ScraperError(403, "ACCOUNT_SCOPE_REQUIRED", "Document belongs to another account")
        return ScrapedDocumentRead.model_validate(document.model_dump())

    async def consume(self, event: dict[str, Any]) -> None:
        if event.get("event_type") != "scrape.requested":
            return
        raw_event_id = event.get("event_id") or event.get("id")
        event_id = UUID(str(raw_event_id)) if raw_event_id else None
        if event_id is not None and await self.repository.has_processed_event(event_id):
            return
        payload = dict(event.get("payload") or {})
        job_id = UUID(str(payload["job_id"]))
        await self._execute(job_id)
        if event_id is not None:
            await self.repository.mark_event_processed(event_id, "scrape.requested")

    async def scan_due_recurring_jobs(self) -> int:
        due = await self.repository.due_recurring_jobs(_utcnow())
        for job in due:
            job.status = "queued"
            job.next_run_at = None
            job.updated_at = _utcnow()
            await self.repository.replace_job(job)
        for job in due:
            await self._dispatch(job.id)
        return len(due)

    async def _dispatch(self, job_id: UUID) -> None:
        await self.events.publish(
            EventEnvelope(event_type="scrape.requested", payload={"job_id": str(job_id)})
        )

    async def _execute(self, job_id: UUID) -> None:
        job = await self.repository.get_job(job_id)
        if job is None or job.status != "queued":
            return
        job.status = "running"
        job.attempts += 1
        job.updated_at = _utcnow()
        await self.repository.replace_job(job)

        try:
            if job.job_type == "url":
                documents = await self._run_url_job(job)
            elif job.job_type == "serp":
                documents = await self._run_serp_job(job)
            else:
                documents = await self._run_research_job(job)
            job.pages_processed = len(documents)
            job.status = "completed"
            job.failure_reason = None
            document_ids = [document.id for document in documents]
        except ScraperError as exc:
            job.status = "failed"
            job.failure_reason = exc.message
            document_ids = []
        except Exception as exc:  # noqa: BLE001 - never let a scrape crash the consumer loop
            job.status = "failed"
            job.failure_reason = str(exc)[:500]
            document_ids = []
        job.last_run_at = _utcnow()
        job.updated_at = _utcnow()
        if job.recurring and job.interval_hours:
            job.next_run_at = _utcnow() + timedelta(hours=job.interval_hours)
        await self.repository.replace_job(job)
        await self._emit(job, document_ids)

    async def _run_url_job(self, job: ScraperJob) -> list[ScrapedDocument]:
        domain = urlparse(job.target).netloc
        visited: set[str] = set()
        queue = [job.target]
        documents: list[ScrapedDocument] = []
        while queue and len(documents) < job.max_pages:
            url = queue.pop(0)
            if url in visited:
                continue
            visited.add(url)
            if not await self.robots.allowed(url, self._http):
                if url == job.target:
                    raise ScraperError(403, "ROBOTS_DISALLOWED", f"robots.txt disallows fetching {url}")
                continue
            await self.rate_limiter.wait(domain)
            page = await self.crawler.fetch(url)
            document = ScrapedDocument(
                job_id=job.id,
                account_id=job.account_id,
                job_type="url",
                source=page.url,
                title=page.title,
                text=page.text,
                data={"status_code": page.status_code, "links": page.links[:50]},
            )
            await self.repository.insert_document(document)
            documents.append(document)
            queue.extend(link for link in page.links if link not in visited)
        job.answer = self._build_answer(job.target, documents)
        return documents

    async def _run_serp_job(self, job: ScraperJob) -> list[ScrapedDocument]:
        result = await self.serp.search(job.target)
        summary = " | ".join(
            f"{item.get('title', '')}: {item.get('snippet', '')}" for item in result.organic_results[:10]
        )
        document = ScrapedDocument(
            job_id=job.id,
            account_id=job.account_id,
            job_type="serp",
            source=job.target,
            title=result.title,
            text=summary,
            data={
                "organic_results": result.organic_results,
                "related_searches": result.related_searches,
            },
        )
        await self.repository.insert_document(document)
        return [document]

    async def _run_research_job(self, job: ScraperJob) -> list[ScrapedDocument]:
        """Answer a free-text question by finding sources via SerpApi, scraping each, and
        synthesizing a Markdown digest of what was gathered (job.answer)."""
        result = await self.serp.search(job.target)
        candidates = [item for item in result.organic_results if item.get("link")][: job.max_pages]
        if not candidates:
            raise ScraperError(502, "NO_SOURCES_FOUND", f"No search results found for '{job.target}'")

        documents: list[ScrapedDocument] = []
        for item in candidates:
            url = str(item["link"])
            title = str(item.get("title") or url)
            snippet = str(item.get("snippet") or "")
            domain = urlparse(url).netloc
            excerpt = snippet
            try:
                if await self.robots.allowed(url, self._http):
                    await self.rate_limiter.wait(domain)
                    page = await self.crawler.fetch(url)
                    excerpt = page.text[:1200] or snippet
                    document = ScrapedDocument(
                        job_id=job.id,
                        account_id=job.account_id,
                        job_type="research",
                        source=url,
                        title=page.title or title,
                        text=excerpt,
                        data={"status_code": page.status_code, "serp_snippet": snippet},
                    )
                else:
                    document = ScrapedDocument(
                        job_id=job.id,
                        account_id=job.account_id,
                        job_type="research",
                        source=url,
                        title=title,
                        text=snippet,
                        data={"serp_snippet": snippet, "note": "robots.txt disallowed a full fetch"},
                    )
            except (ScraperError, httpx.HTTPError) as exc:
                document = ScrapedDocument(
                    job_id=job.id,
                    account_id=job.account_id,
                    job_type="research",
                    source=url,
                    title=title,
                    text=snippet,
                    data={"serp_snippet": snippet, "fetch_error": str(exc)[:300]},
                )
            await self.repository.insert_document(document)
            documents.append(document)
        job.answer = self._build_answer(job.target, documents)
        return documents

    @staticmethod
    def _build_answer(query: str, documents: list[ScrapedDocument]) -> str | None:
        """Synthesize a Markdown digest of scraped documents into a single answer.

        Scraped text originates from arbitrary third-party pages, and this answer
        gets rendered straight to HTML for the UI, so every piece of scraped text
        is HTML-escaped before being embedded in the Markdown source — otherwise a
        page containing literal "<script>"-like text could execute as live markup.
        """
        if not documents:
            return None
        sections = [
            f"## {html.escape(document.title or document.source)}\n\n"
            f"Source: <{document.source}>\n\n"
            f"{html.escape(document.text.strip())}\n"
            for document in documents
        ]
        return (
            f"# {html.escape(query)}\n\n"
            f"Gathered from {len(documents)} source(s):\n\n" + "\n".join(sections)
        )

    async def _emit(self, job: ScraperJob, document_ids: list[UUID]) -> None:
        event_type = "scrape.completed" if job.status == "completed" else "scrape.failed"
        await self.events.publish(
            EventEnvelope(
                event_type=event_type,
                payload={
                    "job_id": str(job.id),
                    "account_id": str(job.account_id),
                    "job_type": job.job_type,
                    "status": job.status,
                    "document_ids": [str(document_id) for document_id in document_ids],
                    "reason": job.failure_reason,
                },
            )
        )

    async def _list(self, identity: Identity) -> list[ScraperJob]:
        account_id = None if identity.is_superadmin else identity.account_id
        return await self.repository.list_jobs(account_id, limit=100)

    async def _scoped(self, job_id: UUID, identity: Identity) -> ScraperJob:
        job = await self.repository.get_job(job_id)
        if job is None:
            raise ScraperError(404, "JOB_NOT_FOUND", "Scrape job was not found")
        if not identity.is_superadmin and job.account_id != identity.account_id:
            raise ScraperError(403, "ACCOUNT_SCOPE_REQUIRED", "Scrape job belongs to another account")
        return job

    @staticmethod
    def _validate_url(target: str) -> None:
        parsed = urlparse(target)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ScraperError(422, "INVALID_TARGET", "target must be a valid http(s) URL for job_type=url")

    @staticmethod
    def _job_read(job: ScraperJob) -> ScraperJobRead:
        return ScraperJobRead.model_validate(job.model_dump())

    async def close(self) -> None:
        await self._http.aclose()


def _utcnow() -> datetime:
    return datetime.now(UTC)
