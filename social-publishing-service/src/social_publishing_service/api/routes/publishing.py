from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import RedirectResponse

from social_publishing_service.api.dependencies import get_credentials, get_identity, get_publishing_service
from social_publishing_service.core.errors import SocialPublishingError
from social_publishing_service.schemas.publishing import (
    ConnectResponse,
    DevLinkedInConnectionRequest,
    ManualLinkedInPostRequest,
    PublishContentRequest,
    PublishingCollection,
    PublishJobRead,
    SocialConnectionRead,
)
from social_publishing_service.services.identity import Identity
from social_publishing_service.services.publishing import SocialPublishingService

router = APIRouter(prefix="/api/v1/publishing", tags=["publishing"])


@router.get("", response_model=PublishingCollection, operation_id="get_publishing")
async def get_publishing(
    identity: Annotated[Identity, Depends(get_identity)],
    service: Annotated[SocialPublishingService, Depends(get_publishing_service)],
) -> PublishingCollection:
    return await service.collection(identity)


@router.post("/linkedin/connect", response_model=ConnectResponse, operation_id="connect_linkedin")
async def connect_linkedin(
    identity: Annotated[Identity, Depends(get_identity)],
    service: Annotated[SocialPublishingService, Depends(get_publishing_service)],
) -> ConnectResponse:
    return await service.connect(identity)


@router.post(
    "/linkedin/dev-connect", response_model=SocialConnectionRead, operation_id="connect_linkedin_dev"
)
async def connect_linkedin_dev(
    payload: DevLinkedInConnectionRequest,
    identity: Annotated[Identity, Depends(get_identity)],
    service: Annotated[SocialPublishingService, Depends(get_publishing_service)],
) -> SocialConnectionRead:
    return await service.connect_dev(identity, payload)


@router.get("/linkedin/callback", operation_id="linkedin_callback", response_model=None)
async def linkedin_callback(
    service: Annotated[SocialPublishingService, Depends(get_publishing_service)],
    state: Annotated[str, Query(min_length=8)],
    code: Annotated[str | None, Query(min_length=1)] = None,
    error: str | None = None,
    error_description: str | None = None,
    response: Literal["redirect", "json"] = "redirect",
) -> SocialConnectionRead | RedirectResponse:
    if error:
        await service.callback_failed(state, error, error_description)
        if response == "json":
            raise SocialPublishingError(
                400,
                "LINKEDIN_OAUTH_FAILED",
                error_description or error,
                {"provider_error": error},
            )
        return RedirectResponse(service.callback_result_url("error", error_description or error))
    if code is None:
        raise SocialPublishingError(422, "OAUTH_CODE_REQUIRED", "LinkedIn did not return an OAuth code")
    result = await service.callback(state, code)
    if response == "json":
        return result
    return RedirectResponse(service.callback_result_url("connected", "LinkedIn profile connected"))


@router.delete("/connections/{connection_id}", operation_id="disconnect_linkedin")
async def disconnect_linkedin(
    connection_id: UUID,
    identity: Annotated[Identity, Depends(get_identity)],
    service: Annotated[SocialPublishingService, Depends(get_publishing_service)],
) -> dict[str, str]:
    return await service.disconnect(identity, connection_id)


@router.post("/linkedin/content", response_model=PublishJobRead, operation_id="publish_content_to_linkedin")
async def publish_content_to_linkedin(
    payload: PublishContentRequest,
    request: Request,
    credentials: Annotated[object, Depends(get_credentials)],
    identity: Annotated[Identity, Depends(get_identity)],
    service: Annotated[SocialPublishingService, Depends(get_publishing_service)],
) -> PublishJobRead:
    token = request.headers.get("authorization", "").removeprefix("Bearer ").strip() or None
    del credentials
    return await service.publish_content(identity, payload, token)


@router.post("/linkedin", response_model=PublishJobRead, operation_id="publish_manual_to_linkedin")
async def publish_manual_to_linkedin(
    payload: ManualLinkedInPostRequest,
    identity: Annotated[Identity, Depends(get_identity)],
    service: Annotated[SocialPublishingService, Depends(get_publishing_service)],
) -> PublishJobRead:
    return await service.publish_manual(identity, payload)


@router.post("/linkedin/refresh-tokens", operation_id="refresh_linkedin_tokens")
async def refresh_linkedin_tokens(
    identity: Annotated[Identity, Depends(get_identity)],
    service: Annotated[SocialPublishingService, Depends(get_publishing_service)],
) -> dict[str, int]:
    if not identity.can_manage_social:
        return {"refreshed": 0}
    return {"refreshed": await service.refresh_expiring_tokens()}
