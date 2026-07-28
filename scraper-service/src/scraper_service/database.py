from datetime import UTC, datetime
from typing import Any, Protocol
from uuid import UUID

from motor.motor_asyncio import AsyncIOMotorClient
from pymongo.errors import DuplicateKeyError

from scraper_service.models import ScrapedDocument, ScraperJob


class ScraperRepositoryProtocol(Protocol):
    async def insert_job(self, job: ScraperJob) -> None: ...
    async def get_job(self, job_id: UUID) -> ScraperJob | None: ...
    async def list_jobs(self, account_id: UUID | None, limit: int = 100) -> list[ScraperJob]: ...
    async def replace_job(self, job: ScraperJob) -> None: ...
    async def due_recurring_jobs(self, now: datetime) -> list[ScraperJob]: ...
    async def insert_document(self, document: ScrapedDocument) -> None: ...
    async def get_document(self, document_id: UUID) -> ScrapedDocument | None: ...
    async def list_documents(self, job_id: UUID) -> list[ScrapedDocument]: ...
    async def has_processed_event(self, event_id: UUID) -> bool: ...
    async def mark_event_processed(self, event_id: UUID, event_type: str) -> None: ...
    async def ping(self) -> bool: ...
    async def close(self) -> None: ...


def _job_to_doc(job: ScraperJob) -> dict[str, Any]:
    payload = job.model_dump(mode="json")
    payload["_id"] = payload.pop("id")
    return payload


def _doc_to_job(payload: dict[str, Any]) -> ScraperJob:
    payload = dict(payload)
    payload["id"] = payload.pop("_id")
    return ScraperJob.model_validate(payload)


def _document_to_doc(document: ScrapedDocument) -> dict[str, Any]:
    payload = document.model_dump(mode="json")
    payload["_id"] = payload.pop("id")
    return payload


def _doc_to_document(payload: dict[str, Any]) -> ScrapedDocument:
    payload = dict(payload)
    payload["id"] = payload.pop("_id")
    return ScrapedDocument.model_validate(payload)


class MongoScraperRepository:
    def __init__(self, url: str, database_name: str) -> None:
        self.client: AsyncIOMotorClient[Any] = AsyncIOMotorClient(url)
        self.database = self.client[database_name]
        self.jobs = self.database["scraper_jobs"]
        self.documents = self.database["scraped_documents"]
        self.processed_events = self.database["processed_events"]

    async def insert_job(self, job: ScraperJob) -> None:
        await self.jobs.insert_one(_job_to_doc(job))

    async def get_job(self, job_id: UUID) -> ScraperJob | None:
        payload = await self.jobs.find_one({"_id": str(job_id)})
        return _doc_to_job(payload) if payload else None

    async def list_jobs(self, account_id: UUID | None, limit: int = 100) -> list[ScraperJob]:
        query: dict[str, Any] = {"account_id": str(account_id)} if account_id else {}
        cursor = self.jobs.find(query).sort("created_at", -1).limit(limit)
        return [_doc_to_job(payload) async for payload in cursor]

    async def replace_job(self, job: ScraperJob) -> None:
        await self.jobs.replace_one({"_id": str(job.id)}, _job_to_doc(job))

    async def due_recurring_jobs(self, now: datetime) -> list[ScraperJob]:
        query = {
            "recurring": True,
            "status": {"$in": ["completed", "failed"]},
            "next_run_at": {"$lte": now.isoformat()},
        }
        cursor = self.jobs.find(query)
        return [_doc_to_job(payload) async for payload in cursor]

    async def insert_document(self, document: ScrapedDocument) -> None:
        await self.documents.insert_one(_document_to_doc(document))

    async def get_document(self, document_id: UUID) -> ScrapedDocument | None:
        payload = await self.documents.find_one({"_id": str(document_id)})
        return _doc_to_document(payload) if payload else None

    async def list_documents(self, job_id: UUID) -> list[ScrapedDocument]:
        cursor = self.documents.find({"job_id": str(job_id)}).sort("fetched_at", -1)
        return [_doc_to_document(payload) async for payload in cursor]

    async def has_processed_event(self, event_id: UUID) -> bool:
        return await self.processed_events.find_one({"_id": str(event_id)}) is not None

    async def mark_event_processed(self, event_id: UUID, event_type: str) -> None:
        # _id is Mongo's own unique index — a duplicate insert (redelivered event_id)
        # fails cleanly instead of silently double-recording.
        try:
            await self.processed_events.insert_one({
                "_id": str(event_id),
                "event_type": event_type,
                "processed_at": datetime.now(UTC).isoformat(),
            })
        except DuplicateKeyError:
            pass

    async def ping(self) -> bool:
        await self.database.command("ping")
        return True

    async def close(self) -> None:
        self.client.close()
