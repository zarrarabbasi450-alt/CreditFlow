from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, UploadFile

from content_service.api.dependencies import get_content_service, get_identity, get_storage
from content_service.schemas.content import ContentCollection, ContentCreate, ContentRead, ContentUpdate
from content_service.services.content import ContentService
from content_service.services.identity import Identity
from content_service.services.storage import LocalStorage

router = APIRouter(prefix="/api/v1/content", tags=["content"])


@router.get("", response_model=ContentCollection, operation_id="list_content")
async def list_content(
    identity: Annotated[Identity, Depends(get_identity)],
    service: Annotated[ContentService, Depends(get_content_service)],
) -> ContentCollection:
    return await service.collection(identity)


@router.post("", response_model=ContentRead, status_code=201, operation_id="create_content")
async def create_content(
    payload: ContentCreate,
    identity: Annotated[Identity, Depends(get_identity)],
    service: Annotated[ContentService, Depends(get_content_service)],
) -> ContentRead:
    return await service.create(payload, identity)


@router.get("/{content_id}", response_model=ContentRead, operation_id="get_content")
async def get_content(
    content_id: UUID,
    identity: Annotated[Identity, Depends(get_identity)],
    service: Annotated[ContentService, Depends(get_content_service)],
) -> ContentRead:
    return await service.get(content_id, identity)


@router.patch("/{content_id}", response_model=ContentRead, operation_id="update_content")
async def update_content(
    content_id: UUID,
    payload: ContentUpdate,
    identity: Annotated[Identity, Depends(get_identity)],
    service: Annotated[ContentService, Depends(get_content_service)],
) -> ContentRead:
    return await service.update(content_id, payload, identity)


@router.delete("/{content_id}", operation_id="delete_content")
async def delete_content(
    content_id: UUID,
    identity: Annotated[Identity, Depends(get_identity)],
    service: Annotated[ContentService, Depends(get_content_service)],
) -> dict[str, str]:
    return await service.delete(content_id, identity)


@router.post("/{content_id}/approve", response_model=ContentRead, operation_id="approve_content")
async def approve_content(
    content_id: UUID,
    identity: Annotated[Identity, Depends(get_identity)],
    service: Annotated[ContentService, Depends(get_content_service)],
) -> ContentRead:
    return await service.approve(content_id, identity)


@router.post("/{content_id}/publish", response_model=ContentRead, operation_id="publish_content")
async def publish_content(
    content_id: UUID,
    identity: Annotated[Identity, Depends(get_identity)],
    service: Annotated[ContentService, Depends(get_content_service)],
) -> ContentRead:
    return await service.publish(content_id, identity)


@router.post("/{content_id}/image", response_model=ContentRead, operation_id="upload_content_image")
async def upload_content_image(
    content_id: UUID,
    identity: Annotated[Identity, Depends(get_identity)],
    service: Annotated[ContentService, Depends(get_content_service)],
    storage: Annotated[LocalStorage, Depends(get_storage)],
    file: Annotated[UploadFile, File()],
) -> ContentRead:
    image_url, asset_ref = await storage.save(file)
    return await service.attach_image(content_id, image_url, asset_ref, identity)
