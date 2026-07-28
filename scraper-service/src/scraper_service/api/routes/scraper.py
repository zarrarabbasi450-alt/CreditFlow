from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends

from scraper_service.api.dependencies import get_identity, get_scraper_service
from scraper_service.schemas.scraper import (
    ScrapedDocumentRead,
    ScraperCollection,
    ScraperJobCreate,
    ScraperJobRead,
)
from scraper_service.services.identity import Identity
from scraper_service.services.scraper import ScraperService

router = APIRouter(prefix="/api/v1/scraper", tags=["scraper"])


@router.get("/jobs", response_model=ScraperCollection, operation_id="list_scraper_jobs")
async def list_jobs(
    identity: Annotated[Identity, Depends(get_identity)],
    service: Annotated[ScraperService, Depends(get_scraper_service)],
) -> ScraperCollection:
    return await service.collection(identity)


@router.post("/jobs", response_model=ScraperJobRead, status_code=201, operation_id="create_scraper_job")
async def create_job(
    payload: ScraperJobCreate,
    identity: Annotated[Identity, Depends(get_identity)],
    service: Annotated[ScraperService, Depends(get_scraper_service)],
) -> ScraperJobRead:
    return await service.create(payload, identity)


@router.get("/jobs/{job_id}", response_model=ScraperJobRead, operation_id="get_scraper_job")
async def get_job(
    job_id: UUID,
    identity: Annotated[Identity, Depends(get_identity)],
    service: Annotated[ScraperService, Depends(get_scraper_service)],
) -> ScraperJobRead:
    return await service.get(job_id, identity)


@router.post("/jobs/{job_id}/cancel", response_model=ScraperJobRead, operation_id="cancel_scraper_job")
async def cancel_job(
    job_id: UUID,
    identity: Annotated[Identity, Depends(get_identity)],
    service: Annotated[ScraperService, Depends(get_scraper_service)],
) -> ScraperJobRead:
    return await service.cancel(job_id, identity)


@router.get(
    "/jobs/{job_id}/documents",
    response_model=list[ScrapedDocumentRead],
    operation_id="list_scraper_job_documents",
)
async def list_job_documents(
    job_id: UUID,
    identity: Annotated[Identity, Depends(get_identity)],
    service: Annotated[ScraperService, Depends(get_scraper_service)],
) -> list[ScrapedDocumentRead]:
    return await service.list_documents(job_id, identity)


@router.get(
    "/documents/{document_id}", response_model=ScrapedDocumentRead, operation_id="get_scraper_document"
)
async def get_document(
    document_id: UUID,
    identity: Annotated[Identity, Depends(get_identity)],
    service: Annotated[ScraperService, Depends(get_scraper_service)],
) -> ScrapedDocumentRead:
    return await service.get_document(document_id, identity)
