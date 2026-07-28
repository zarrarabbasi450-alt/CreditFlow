from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import Select, and_, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from scheduler_service.core.errors import SchedulerError
from scheduler_service.models import ProcessedEvent, ScheduledPost, utcnow
from scheduler_service.schemas.events import EventEnvelope
from scheduler_service.schemas.scheduler import CalendarResponse, ScheduledPostResponse, SchedulerSummary
from scheduler_service.services.identity import Identity
from scheduler_service.services.rabbitmq import EventBusProtocol
from scheduler_service.services.redis_lock import LockProtocol


def ensure_utc(value: datetime) -> datetime:
    aware = value if value.tzinfo else value.replace(tzinfo=UTC)
    return aware.astimezone(UTC)


class SchedulerService:
    def __init__(
        self,
        sessions: async_sessionmaker[AsyncSession],
        events: EventBusProtocol,
        locks: LockProtocol,
        lock_ttl_seconds: int = 120,
    ) -> None:
        self.sessions = sessions
        self.events = events
        self.locks = locks
        self.lock_ttl_seconds = lock_ttl_seconds

    def _scope(
        self, statement: Select[tuple[ScheduledPost]], identity: Identity
    ) -> Select[tuple[ScheduledPost]]:
        if identity.is_superadmin:
            return statement
        return statement.where(ScheduledPost.account_id == identity.account_id)

    def _to_response(self, item: ScheduledPost, timezone: str) -> ScheduledPostResponse:
        zone = ZoneInfo(timezone)
        return ScheduledPostResponse(
            id=item.id,
            account_id=item.account_id,
            content_id=item.content_id,
            title=item.title,
            status=item.status,
            publish_at=item.publish_at,
            publish_at_local=item.publish_at.astimezone(zone),
            timezone=timezone,
            fired_at=item.fired_at,
            cancelled_at=item.cancelled_at,
            created_at=item.created_at,
            updated_at=item.updated_at,
        )

    async def calendar(
        self,
        identity: Identity,
        range_start: datetime,
        range_end: datetime,
        timezone: str,
    ) -> CalendarResponse:
        start_utc = ensure_utc(range_start)
        end_utc = ensure_utc(range_end)
        if end_utc <= start_utc:
            raise SchedulerError(422, "INVALID_RANGE", "range_end must be after range_start")
        statement = select(ScheduledPost).where(
            and_(ScheduledPost.publish_at >= start_utc, ScheduledPost.publish_at <= end_utc)
        )
        statement = self._scope(statement, identity).order_by(ScheduledPost.publish_at.asc())
        async with self.sessions() as session:
            items = list((await session.scalars(statement)).all())
        return CalendarResponse(
            items=[self._to_response(item, timezone) for item in items],
            timezone=timezone,
            range_start=start_utc,
            range_end=end_utc,
        )

    async def schedule(
        self,
        identity: Identity,
        content_id: UUID,
        title: str,
        publish_at: datetime,
        timezone: str,
    ) -> ScheduledPostResponse:
        if not identity.can_manage_schedule:
            raise SchedulerError(403, "FORBIDDEN", "You cannot schedule content for this account")
        publish_at_utc = ensure_utc(publish_at)
        if publish_at_utc <= utcnow():
            raise SchedulerError(422, "PAST_PUBLISH_AT", "publish_at must be in the future")
        item = ScheduledPost(
            account_id=identity.account_id,
            content_id=content_id,
            created_by=identity.user_id,
            title=title,
            publish_at=publish_at_utc,
            timezone=timezone,
        )
        async with self.sessions() as session:
            existing = await session.scalar(
                select(ScheduledPost.id).where(
                    and_(
                        ScheduledPost.account_id == identity.account_id,
                        ScheduledPost.content_id == content_id,
                        ScheduledPost.status == "scheduled",
                    )
                )
            )
            if existing is not None:
                raise SchedulerError(
                    409,
                    "CONTENT_ALREADY_SCHEDULED",
                    "This content item already has an active schedule",
                )
            session.add(item)
            try:
                await session.commit()
            except IntegrityError as exc:
                await session.rollback()
                raise SchedulerError(
                    409,
                    "CONTENT_ALREADY_SCHEDULED",
                    "This content item already has an active schedule",
                ) from exc
            await session.refresh(item)
        return self._to_response(item, timezone)

    async def get(self, identity: Identity, schedule_id: UUID, timezone: str) -> ScheduledPostResponse:
        item = await self._get_model(identity, schedule_id)
        return self._to_response(item, timezone)

    async def reschedule(
        self, identity: Identity, schedule_id: UUID, publish_at: datetime, timezone: str
    ) -> ScheduledPostResponse:
        item = await self._get_model(identity, schedule_id)
        if item.status != "scheduled":
            raise SchedulerError(409, "SCHEDULE_NOT_ACTIVE", "Only active schedules can be rescheduled")
        publish_at_utc = ensure_utc(publish_at)
        if publish_at_utc <= utcnow():
            raise SchedulerError(422, "PAST_PUBLISH_AT", "publish_at must be in the future")
        async with self.sessions() as session:
            managed = await session.get(ScheduledPost, item.id)
            if managed is None:
                raise SchedulerError(404, "SCHEDULE_NOT_FOUND", "Scheduled post was not found")
            managed.publish_at = publish_at_utc
            managed.timezone = timezone
            managed.updated_at = utcnow()
            await session.commit()
            await session.refresh(managed)
        return self._to_response(managed, timezone)

    async def cancel(self, identity: Identity, schedule_id: UUID, timezone: str) -> ScheduledPostResponse:
        item = await self._get_model(identity, schedule_id)
        if item.status != "scheduled":
            raise SchedulerError(409, "SCHEDULE_NOT_ACTIVE", "Only active schedules can be cancelled")
        async with self.sessions() as session:
            managed = await session.get(ScheduledPost, item.id)
            if managed is None:
                raise SchedulerError(404, "SCHEDULE_NOT_FOUND", "Scheduled post was not found")
            managed.status = "cancelled"
            managed.cancelled_at = utcnow()
            managed.updated_at = utcnow()
            await session.commit()
            await session.refresh(managed)
        return self._to_response(managed, timezone)

    async def summary(self, identity: Identity) -> SchedulerSummary:
        async with self.sessions() as session:
            scheduled_statement = select(func.count(ScheduledPost.id)).where(
                ScheduledPost.status == "scheduled"
            )
            due_statement = select(func.count(ScheduledPost.id)).where(
                and_(ScheduledPost.status == "scheduled", ScheduledPost.publish_at <= utcnow())
            )
            next_statement = select(func.min(ScheduledPost.publish_at)).where(
                ScheduledPost.status == "scheduled"
            )
            if not identity.is_superadmin:
                scheduled_statement = scheduled_statement.where(
                    ScheduledPost.account_id == identity.account_id
                )
                due_statement = due_statement.where(ScheduledPost.account_id == identity.account_id)
                next_statement = next_statement.where(ScheduledPost.account_id == identity.account_id)
            scheduled_count = int(await session.scalar(scheduled_statement) or 0)
            due_count = int(await session.scalar(due_statement) or 0)
            next_publish_at = await session.scalar(next_statement)
        return SchedulerSummary(
            scheduled_count=scheduled_count,
            due_count=due_count,
            next_publish_at=next_publish_at,
        )

    async def fire_due(self, limit: int = 100) -> int:
        now = utcnow()
        async with self.sessions() as session:
            due = list(
                (
                    await session.scalars(
                        select(ScheduledPost)
                        .where(and_(ScheduledPost.status == "scheduled", ScheduledPost.publish_at <= now))
                        .order_by(ScheduledPost.publish_at.asc())
                        .limit(limit)
                    )
                ).all()
            )
        fired = 0
        for item in due:
            lock_key = f"scheduler:scheduled_post:{item.id}:fire"
            if not await self.locks.acquire(lock_key, self.lock_ttl_seconds):
                continue
            async with self.sessions() as session:
                managed = await session.get(ScheduledPost, item.id)
                if managed is None or managed.status != "scheduled":
                    continue
                managed.status = "fired"
                managed.fired_at = utcnow()
                managed.updated_at = utcnow()
                await session.commit()
                await self._publish_scheduled(managed)
                fired += 1
        return fired

    async def consume(self, event: dict[str, Any]) -> None:
        raw_event_id = event.get("event_id") or event.get("id")
        event_id = UUID(str(raw_event_id)) if raw_event_id else None
        if event_id is not None:
            async with self.sessions() as session:
                if await session.scalar(
                    select(ProcessedEvent.id).where(ProcessedEvent.event_id == event_id)
                ):
                    return
        event_type = str(event.get("event_type"))
        if event_type == "content.deleted":
            await self._cancel_by_content(event)
        if event_id is not None:
            try:
                async with self.sessions() as session, session.begin():
                    session.add(ProcessedEvent(event_id=event_id, event_type=event_type))
            except IntegrityError:
                pass

    async def _cancel_by_content(self, event: dict[str, Any]) -> None:
        payload = dict(event.get("payload") or {})
        content_id_raw = payload.get("content_id")
        if not content_id_raw:
            return
        content_id = UUID(str(content_id_raw))
        async with self.sessions() as session, session.begin():
            item = await session.scalar(
                select(ScheduledPost).where(
                    ScheduledPost.content_id == content_id, ScheduledPost.status == "scheduled"
                )
            )
            if item is None:
                return
            item.status = "cancelled"
            item.cancelled_at = utcnow()
            item.updated_at = utcnow()

    async def _get_model(self, identity: Identity, schedule_id: UUID) -> ScheduledPost:
        statement = select(ScheduledPost).where(ScheduledPost.id == schedule_id)
        statement = self._scope(statement, identity)
        async with self.sessions() as session:
            item = await session.scalar(statement)
        if item is None:
            raise SchedulerError(404, "SCHEDULE_NOT_FOUND", "Scheduled post was not found")
        return item

    async def _publish_scheduled(self, item: ScheduledPost) -> None:
        event = EventEnvelope(
            event_type="content.scheduled",
            occurred_at=utcnow(),
            payload={
                "scheduled_post_id": str(item.id),
                "account_id": str(item.account_id),
                "content_id": str(item.content_id),
                "publish_at": item.publish_at.isoformat(),
                "title": item.title,
            },
        )
        await self.events.publish(event)


SchedulerFactory = Callable[[], SchedulerService]
