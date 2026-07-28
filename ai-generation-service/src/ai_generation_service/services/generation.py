import asyncio
import logging
from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ai_generation_service.core.config import Settings
from ai_generation_service.core.errors import AIServiceError
from ai_generation_service.models import GenerationJob, ImageGenerationJob, PromptHistory
from ai_generation_service.schemas.events import (
    EventEnvelope,
    GenerationCompletedPayload,
    GenerationFailedPayload,
)
from ai_generation_service.schemas.generation import GenerationRequest, GenerationStartResponse, ImageResponse
from ai_generation_service.services.credits import CreditsClientProtocol
from ai_generation_service.services.identity import Identity
from ai_generation_service.services.images import ImageProviderProtocol
from ai_generation_service.services.openrouter import AIProviderProtocol
from ai_generation_service.services.rabbitmq import EventBusProtocol
from ai_generation_service.services.redis import RedisProtocol
from ai_generation_service.services.usage import UsageClientProtocol

logger = logging.getLogger(__name__)


class GenerationService:
    def __init__(
        self,
        sessions: async_sessionmaker[AsyncSession],
        redis: RedisProtocol,
        events: EventBusProtocol,
        usage: UsageClientProtocol,
        credits: CreditsClientProtocol,
        ai: AIProviderProtocol,
        images: ImageProviderProtocol,
        settings: Settings,
    ) -> None:
        self.sessions = sessions
        self.redis = redis
        self.events = events
        self.usage = usage
        self.credits = credits
        self.ai = ai
        self.images = images
        self.settings = settings

    def resolve_model(self, choice: str) -> str:
        try:
            return self.settings.allowed_models[choice]
        except KeyError as exc:
            raise AIServiceError(422, "UNSUPPORTED_MODEL", "Selected model is not available") from exc

    def estimate_tokens(self, payload: GenerationRequest) -> int:
        return payload.estimated_tokens or max(
            1,
            len(payload.prompt.split()) * 2
            + self.settings.estimated_prompt_tokens
            + self.settings.estimated_completion_tokens,
        )

    def channel(self, job_id: UUID) -> str:
        return f"ai:generation:{job_id}"

    def stream_channel(self, account_id: UUID, job_id: UUID) -> str:
        return f"ai:stream:{account_id}:{job_id}"

    async def start(
        self, actor: Identity, bearer_token: str, payload: GenerationRequest, correlation_id: str
    ) -> GenerationStartResponse:
        model = self.resolve_model(payload.model)
        allowed = await self.usage.check_quota(bearer_token, self.estimate_tokens(payload))
        if not allowed:
            raise AIServiceError(402, "QUOTA_EXCEEDED", "Usage quota is not available for this generation")
        job_id = uuid4()
        image_url = None
        async with self.sessions() as session, session.begin():
            session.add(
                GenerationJob(
                    id=job_id,
                    account_id=actor.account_id,
                    user_id=actor.user_id,
                    model=model,
                    status="queued",
                    prompt=payload.prompt,
                )
            )
            if payload.generate_image:
                image_url = self.images.image_url(payload.prompt)
                session.add(
                    ImageGenerationJob(
                        account_id=actor.account_id,
                        user_id=actor.user_id,
                        prompt=payload.prompt,
                        image_url=image_url,
                    )
                )
        task = asyncio.create_task(self.run_job(job_id, correlation_id, bearer_token))
        task.add_done_callback(self._log_background_error)
        return GenerationStartResponse(
            job_id=job_id, channel=self.channel(job_id), model=model, status="queued", image_url=image_url
        )

    @staticmethod
    def _log_background_error(task: asyncio.Task[None]) -> None:
        try:
            task.result()
        except Exception:
            logger.exception("generation_background_task_failed")

    async def run_job(self, job_id: UUID, correlation_id: str, bearer_token: str) -> None:
        async with self.sessions() as session, session.begin():
            job = await session.get(GenerationJob, job_id)
            if job is None:
                raise AIServiceError(404, "GENERATION_NOT_FOUND", "Generation job was not found")
            prompt = job.prompt
            model = job.model
            account_id = job.account_id
            user_id = job.user_id
        final_error: Exception | None = None
        for active_model in self.settings.model_candidates(model):
            output: list[str] = []
            await self._mark_streaming(job_id, active_model)
            try:
                async for token in self.ai.stream_completion(active_model, prompt):
                    if await self.redis.is_cancelled(str(job_id)):
                        await self._mark_cancelled(job_id)
                        await self.redis.publish_token(
                            self.channel(job_id), {"type": "cancelled", "job_id": str(job_id)}
                        )
                        await self.redis.publish_token(
                            self.stream_channel(account_id, job_id),
                            {"event": "failed", "data": {"job_id": str(job_id), "reason": "cancelled"}},
                        )
                        return
                    output.append(token)
                    await self.redis.publish_token(
                        self.channel(job_id), {"type": "token", "job_id": str(job_id), "value": token}
                    )
                    await self.redis.publish_token(
                        self.stream_channel(account_id, job_id),
                        {"event": "token", "data": {"job_id": str(job_id), "value": token}},
                    )
                await self._complete(
                    job_id,
                    account_id,
                    user_id,
                    active_model,
                    prompt,
                    "".join(output),
                    correlation_id,
                    bearer_token,
                )
                await self.redis.publish_token(
                    self.channel(job_id), {"type": "complete", "job_id": str(job_id)}
                )
                await self.redis.publish_token(
                    self.stream_channel(account_id, job_id),
                    {"event": "completed", "data": {"job_id": str(job_id)}},
                )
                return
            except Exception as exc:
                final_error = exc
                if output:
                    break
                next_models = self.settings.model_candidates(model)
                if active_model != next_models[-1]:
                    await self.redis.publish_token(
                        self.channel(job_id),
                        {
                            "type": "token",
                            "job_id": str(job_id),
                            "value": (
                                "\n\nSelected model was unavailable. Retrying with fallback model...\n\n"
                            ),
                        },
                    )
                    continue
                break
        reason = str(final_error) if final_error is not None else "Generation failed"
        await self._fail(job_id, account_id, user_id, model, reason, correlation_id)
        await self.redis.publish_token(
            self.channel(job_id), {"type": "failed", "job_id": str(job_id), "reason": reason}
        )
        await self.redis.publish_token(
            self.stream_channel(account_id, job_id),
            {"event": "failed", "data": {"job_id": str(job_id), "reason": reason}},
        )
        if isinstance(final_error, AIServiceError):
            raise final_error
        raise AIServiceError(502, "GENERATION_FAILED", "AI generation failed", {"reason": reason})

    async def _mark_streaming(self, job_id: UUID, model: str) -> None:
        async with self.sessions() as session, session.begin():
            job = await session.get(GenerationJob, job_id)
            if job is not None:
                job.status = "streaming"
                job.model = model
                job.started_at = datetime.now(UTC)

    async def _complete(
        self,
        job_id: UUID,
        account_id: UUID,
        user_id: UUID,
        model: str,
        prompt: str,
        response: str,
        correlation_id: str,
        bearer_token: str,
    ) -> None:
        prompt_tokens = max(1, len(prompt.split()) * 2)
        completion_tokens = max(1, len(response.split()) * 2)
        total_tokens = prompt_tokens + completion_tokens
        cost = total_tokens * self.settings.model_cost(model) // 1000
        image_url: str | None = None
        async with self.sessions() as session, session.begin():
            job = await session.get(GenerationJob, job_id)
            if job is None:
                raise AIServiceError(404, "GENERATION_NOT_FOUND", "Generation job was not found")
            image_url = await session.scalar(
                select(ImageGenerationJob.image_url)
                .where(ImageGenerationJob.account_id == account_id)
                .where(ImageGenerationJob.user_id == user_id)
                .where(ImageGenerationJob.prompt == prompt)
                .order_by(ImageGenerationJob.created_at.desc())
                .limit(1)
            )
            job.status = "completed"
            job.response = response
            job.prompt_tokens = prompt_tokens
            job.completion_tokens = completion_tokens
            job.total_tokens = total_tokens
            job.cost_microusd = cost
            job.completed_at = datetime.now(UTC)
            session.add(
                PromptHistory(
                    job_id=job_id,
                    account_id=account_id,
                    user_id=user_id,
                    model=model,
                    prompt=prompt,
                    response=response,
                    total_tokens=total_tokens,
                    cost_microusd=cost,
                )
            )
        payload = GenerationCompletedPayload(
            generation_id=job_id,
            account_id=account_id,
            user_id=user_id,
            model=model,
            generation_type="post",
            prompt=prompt,
            response=response,
            image_url=image_url,
            image_asset_ref=image_url,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            cost_microusd=cost,
        )
        await self.events.publish(
            EventEnvelope(
                event_type="ai.generation_completed",
                correlation_id=correlation_id,
                payload=payload.model_dump(mode="json"),
            )
        )
        credits_charged = max(1, total_tokens // 1000)
        await self.credits.consume(
            bearer_token, credits_charged, job_id, f"AI generation ({model})"
        )

    async def _fail(
        self, job_id: UUID, account_id: UUID, user_id: UUID, model: str, reason: str, correlation_id: str
    ) -> None:
        async with self.sessions() as session, session.begin():
            job = await session.get(GenerationJob, job_id)
            if job is not None:
                job.status = "failed"
                job.error_reason = reason
                job.completed_at = datetime.now(UTC)
        payload = GenerationFailedPayload(
            generation_id=job_id, account_id=account_id, user_id=user_id, model=model, reason=reason
        )
        await self.events.publish(
            EventEnvelope(
                event_type="ai.generation_failed",
                correlation_id=correlation_id,
                payload=payload.model_dump(mode="json"),
            )
        )

    async def _mark_cancelled(self, job_id: UUID) -> None:
        async with self.sessions() as session, session.begin():
            job = await session.get(GenerationJob, job_id)
            if job is not None:
                job.status = "cancelled"
                job.completed_at = datetime.now(UTC)

    async def cancel(self, job_id: UUID) -> None:
        await self.redis.cancel(str(job_id))

    async def history(self, actor: Identity, limit: int) -> list[PromptHistory]:
        async with self.sessions() as session:
            return list(
                (
                    await session.scalars(
                        select(PromptHistory)
                        .where(PromptHistory.account_id == actor.account_id)
                        .order_by(PromptHistory.created_at.desc())
                        .limit(limit)
                    )
                ).all()
            )

    async def delete_history_entry(self, actor: Identity, entry_id: UUID, correlation_id: str) -> None:
        async with self.sessions() as session, session.begin():
            entry = await session.get(PromptHistory, entry_id)
            if entry is None:
                raise AIServiceError(404, "PROMPT_HISTORY_NOT_FOUND", "Prompt history entry was not found")
            if entry.account_id != actor.account_id and not actor.is_superadmin:
                raise AIServiceError(403, "ACCOUNT_ACCESS_DENIED", "Entry belongs to another account")
            generation_id = entry.job_id
            account_id = entry.account_id
            await session.delete(entry)
        # Deleting the audit entry also removes the content-library draft (and any
        # schedule for it) that was auto-created from this same generation —
        # content-service and scheduler-service react to this event in turn.
        await self.events.publish(
            EventEnvelope(
                event_type="ai.generation_deleted",
                correlation_id=correlation_id,
                payload={"generation_id": str(generation_id), "account_id": str(account_id)},
            )
        )

    async def get_job(self, actor: Identity, job_id: UUID) -> GenerationJob:
        async with self.sessions() as session:
            job = await session.get(GenerationJob, job_id)
            if job is None:
                raise AIServiceError(404, "GENERATION_NOT_FOUND", "Generation job was not found")
            if job.account_id != actor.account_id and not actor.is_superadmin:
                raise AIServiceError(403, "ACCOUNT_ACCESS_DENIED", "Generation belongs to another account")
            return job

    async def generate_image(self, actor: Identity, prompt: str) -> ImageResponse:
        image_url = self.images.image_url(prompt)
        async with self.sessions() as session, session.begin():
            image = ImageGenerationJob(
                account_id=actor.account_id,
                user_id=actor.user_id,
                prompt=prompt,
                image_url=image_url,
            )
            session.add(image)
        return ImageResponse(id=image.id, image_url=image_url, status=image.status)
