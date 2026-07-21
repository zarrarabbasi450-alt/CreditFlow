from collections import defaultdict
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from usage_service.core.config import Settings
from usage_service.core.errors import UsageError
from usage_service.models import UsageLedger
from usage_service.schemas.events import EventEnvelope, GenerationCompleted
from usage_service.schemas.usage import DailyUsage, ModelUsage, UsageSummary
from usage_service.services.rabbitmq import EventBusProtocol
from usage_service.services.redis import RedisProtocol


def monthly_period(now: datetime | None = None) -> tuple[datetime, datetime]:
    current = now or datetime.now(UTC)
    start = datetime(current.year, current.month, 1, tzinfo=UTC)
    end = (
        datetime(current.year + 1, 1, 1, tzinfo=UTC)
        if current.month == 12
        else datetime(current.year, current.month + 1, 1, tzinfo=UTC)
    )
    return start, end


class UsageService:
    def __init__(
        self,
        sessions: async_sessionmaker[AsyncSession],
        redis: RedisProtocol,
        events: EventBusProtocol,
        settings: Settings,
    ) -> None:
        self.sessions = sessions
        self.redis = redis
        self.events = events
        self.settings = settings

    def quota_key(self, account_id: UUID, start: datetime) -> str:
        return f"usage:tokens:{account_id}:{start:%Y-%m}"

    @staticmethod
    def ttl(end: datetime) -> int:
        return max(60, int((end - datetime.now(UTC)).total_seconds()) + 86400)

    async def check_quota(self, account_id: UUID, estimated_tokens: int) -> tuple[bool, int, str]:
        start, end = monthly_period()
        allowed, current = await self.redis.reserve(
            self.quota_key(account_id, start),
            estimated_tokens,
            self.settings.default_monthly_token_quota,
            self.ttl(end),
        )
        return allowed, current, start.strftime("%Y-%m")

    async def consume(self, envelope: dict[str, Any]) -> None:
        event_type = str(envelope.get("event_type") or envelope.get("type") or "")
        if event_type != "ai.generation_completed":
            raise UsageError(400, "UNSUPPORTED_EVENT", "Usage Service cannot process this event")
        raw = dict(envelope.get("payload") or envelope.get("data") or {})
        raw.setdefault("event_id", envelope.get("event_id") or envelope.get("id"))
        if envelope.get("occurred_at") is not None:
            raw.setdefault("occurred_at", envelope["occurred_at"])
        try:
            event = GenerationCompleted.model_validate(raw)
        except ValidationError as exc:
            raise UsageError(400, "INVALID_USAGE_EVENT", "Generation usage event is invalid") from exc
        start, end = monthly_period(event.occurred_at)
        previous = 0
        try:
            async with self.sessions() as session, session.begin():
                if await session.scalar(select(UsageLedger.id).where(UsageLedger.event_id == event.event_id)):
                    return
                previous = int(
                    await session.scalar(
                        select(func.coalesce(func.sum(UsageLedger.total_tokens), 0)).where(
                            UsageLedger.account_id == event.account_id,
                            UsageLedger.created_at >= start,
                            UsageLedger.created_at < end,
                        )
                    )
                    or 0
                )
                session.add(
                    UsageLedger(
                        event_id=event.event_id,
                        generation_id=event.generation_id,
                        account_id=event.account_id,
                        user_id=event.user_id,
                        model=event.model,
                        prompt_tokens=event.prompt_tokens,
                        completion_tokens=event.completion_tokens,
                        total_tokens=event.total_tokens,
                        cost_microusd=event.cost_microusd,
                        created_at=event.occurred_at,
                    )
                )
        except IntegrityError:
            return
        total = previous + event.total_tokens
        await self.redis.set_counter(self.quota_key(event.account_id, start), total, self.ttl(end))
        await self._emit_thresholds(
            event, previous, total, start, end, str(envelope.get("correlation_id") or event.event_id)
        )

    async def _emit_thresholds(
        self,
        event: GenerationCompleted,
        previous: int,
        total: int,
        start: datetime,
        end: datetime,
        correlation_id: str,
    ) -> None:
        quota = self.settings.default_monthly_token_quota
        for percentage in (80, 100):
            threshold = quota * percentage // 100
            marker = f"usage:threshold:{event.account_id}:{start:%Y-%m}:{percentage}"
            if previous < threshold <= total and await self.redis.mark_threshold(marker, self.ttl(end)):
                await self.events.publish(
                    EventEnvelope(
                        event_type="usage.threshold_reached",
                        correlation_id=correlation_id,
                        payload={
                            "account_id": str(event.account_id),
                            "threshold_percentage": percentage,
                            "tokens_used": total,
                            "quota_tokens": quota,
                            "period": start.strftime("%Y-%m"),
                        },
                    )
                )

    async def ledger(self, account_id: UUID, limit: int = 100) -> list[UsageLedger]:
        async with self.sessions() as session:
            return list(
                (
                    await session.scalars(
                        select(UsageLedger)
                        .where(UsageLedger.account_id == account_id)
                        .order_by(UsageLedger.created_at.desc())
                        .limit(limit)
                    )
                ).all()
            )

    async def summary(self, account_id: UUID, now: datetime | None = None) -> UsageSummary:
        start, end = monthly_period(now)
        async with self.sessions() as session:
            entries = list(
                (
                    await session.scalars(
                        select(UsageLedger)
                        .where(
                            UsageLedger.account_id == account_id,
                            UsageLedger.created_at >= start,
                            UsageLedger.created_at < end,
                        )
                        .order_by(UsageLedger.created_at)
                    )
                ).all()
            )
        models: dict[str, list[int]] = defaultdict(lambda: [0, 0, 0])
        days: dict[str, list[int]] = defaultdict(lambda: [0, 0, 0])
        for entry in entries:
            models[entry.model][0] += entry.total_tokens
            models[entry.model][1] += entry.cost_microusd
            models[entry.model][2] += 1
            day = entry.created_at.date().isoformat()
            days[day][0] += entry.total_tokens
            days[day][1] += entry.cost_microusd
            days[day][2] += 1
        tokens = sum(entry.total_tokens for entry in entries)
        cost = sum(entry.cost_microusd for entry in entries)
        quota = self.settings.default_monthly_token_quota
        return UsageSummary(
            account_id=account_id,
            period_start=start,
            period_end=end,
            tokens_used=tokens,
            cost_microusd=cost,
            quota_tokens=quota,
            remaining_tokens=max(0, quota - tokens),
            quota_percentage=round(tokens / quota * 100, 2) if quota else 100,
            generations=len(entries),
            by_model=[
                ModelUsage(model=model, tokens=value[0], cost_microusd=value[1], generations=value[2])
                for model, value in sorted(models.items())
            ],
            daily=[
                DailyUsage(day=day, tokens=value[0], cost_microusd=value[1], generations=value[2])
                for day, value in sorted(days.items())
            ],
        )
