import json
from collections.abc import AsyncIterator
from typing import Annotated, cast
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, Response, status
from fastapi.responses import StreamingResponse

from ai_generation_service.api.dependencies import get_identity
from ai_generation_service.models import GenerationJob
from ai_generation_service.schemas.generation import (
    GenerationJobResponse,
    GenerationRequest,
    GenerationStartResponse,
    ImageRequest,
    ImageResponse,
    PromptHistoryResponse,
)
from ai_generation_service.services.generation import GenerationService
from ai_generation_service.services.identity import Identity

router = APIRouter(prefix="/api/v1/ai", tags=["ai"])
Actor = Annotated[Identity, Depends(get_identity)]


def service(request: Request) -> GenerationService:
    return cast(GenerationService, request.app.state.generations)


def bearer_token(request: Request) -> str:
    authorization = request.headers.get("authorization", "")
    return authorization.removeprefix("Bearer ").removeprefix("bearer ")


@router.get("/overview", operation_id="get_ai_overview")
async def overview(actor: Actor) -> dict[str, object]:
    return {
        "title": "AI Studio",
        "eyebrow": "AI GENERATION",
        "description": "Generate campaign drafts through OpenRouter with live metering and prompt history.",
        "action": "Generate content",
        "metrics": [
            {"label": "Available models", "value": "2", "change": actor.account_role},
            {"label": "Streaming", "value": "SSE", "change": "Redis fan-out"},
            {"label": "Quota check", "value": "Live", "change": "Usage Service"},
        ],
        "rows": [],
    }


@router.post("/generations", response_model=GenerationStartResponse, operation_id="start_generation")
async def start_generation(
    payload: GenerationRequest, request: Request, actor: Actor
) -> GenerationStartResponse:
    return await service(request).start(
        actor,
        bearer_token(request),
        payload,
        str(getattr(request.state, "correlation_id", getattr(request.state, "request_id", ""))),
    )


@router.get("/generations/{job_id}", response_model=GenerationJobResponse, operation_id="get_generation")
async def get_generation(job_id: UUID, request: Request, actor: Actor) -> GenerationJobResponse:
    return GenerationJobResponse.model_validate(await service(request).get_job(actor, job_id))


@router.post("/generations/{job_id}/cancel", operation_id="cancel_generation")
async def cancel_generation(job_id: UUID, request: Request, actor: Actor) -> dict[str, str]:
    await service(request).get_job(actor, job_id)
    await service(request).cancel(job_id)
    return {"status": "cancel_requested"}


@router.get("/generations/{job_id}/stream", operation_id="stream_generation")
async def stream_generation(job_id: UUID, request: Request, actor: Actor) -> StreamingResponse:
    await service(request).get_job(actor, job_id)
    channel = service(request).channel(job_id)

    async def events() -> AsyncIterator[str]:
        async for event in request.app.state.redis.stream(channel):
            yield f"data: {json.dumps(event)}\n\n"

    return StreamingResponse(events(), media_type="text/event-stream")


@router.get("/history", response_model=list[PromptHistoryResponse], operation_id="get_prompt_history")
async def history(
    request: Request,
    actor: Actor,
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
) -> list[PromptHistoryResponse]:
    return [
        PromptHistoryResponse.model_validate(item) for item in await service(request).history(actor, limit)
    ]


@router.delete(
    "/history/{entry_id}", status_code=status.HTTP_204_NO_CONTENT, operation_id="delete_prompt_history_entry"
)
async def delete_history_entry(entry_id: UUID, request: Request, actor: Actor) -> Response:
    correlation_id = str(getattr(request.state, "correlation_id", getattr(request.state, "request_id", "")))
    await service(request).delete_history_entry(actor, entry_id, correlation_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/images", response_model=ImageResponse, operation_id="generate_image")
async def generate_image(payload: ImageRequest, request: Request, actor: Actor) -> ImageResponse:
    return await service(request).generate_image(actor, payload.prompt)


internal_router = APIRouter(prefix="/internal", tags=["internal"])


@internal_router.get("/generations/{job_id}/ownership", operation_id="get_internal_generation_ownership")
async def generation_ownership(job_id: UUID, request: Request) -> dict[str, str]:
    async with request.app.state.database.sessions() as session:
        job = await session.get(GenerationJob, job_id)
        if job is None:
            return {"account_id": "", "user_id": ""}
        return {"account_id": str(job.account_id), "user_id": str(job.user_id)}
