import asyncio
import logging
from contextlib import suppress
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from billing_service.models import OutboxEvent
from billing_service.schemas.events import EventEnvelope
from billing_service.services.rabbitmq import EventBusProtocol

logger = logging.getLogger("billing_service.outbox")


class OutboxPublisher:
    def __init__(
        self, sessions: async_sessionmaker[AsyncSession], bus: EventBusProtocol, interval: float
    ) -> None:
        self.sessions, self.bus, self.interval = sessions, bus, interval
        self._stopping = asyncio.Event()

    async def run(self) -> None:
        failures = 0
        while not self._stopping.is_set():
            try:
                await self.publish_batch()
                failures = 0
            except Exception:
                failures += 1
                logger.exception("outbox_publish_failed", extra={"attempt": failures})
            delay = min(self.interval * (2 ** min(failures, 5)), 30.0)
            with suppress(TimeoutError):
                await asyncio.wait_for(self._stopping.wait(), timeout=delay)

    async def publish_batch(self) -> int:
        async with self.sessions() as session, session.begin():
            result = await session.scalars(
                select(OutboxEvent)
                .where(OutboxEvent.published_at.is_(None))
                .order_by(OutboxEvent.created_at)
                .limit(100)
                .with_for_update(skip_locked=True)
            )
            events = list(result.all())
            for stored in events:
                await self.bus.publish(
                    EventEnvelope(
                        event_id=stored.id,
                        event_type=stored.event_type,
                        correlation_id=stored.correlation_id,
                        payload=stored.payload,
                    )
                )
                stored.published_at = datetime.now(UTC)
                stored.attempts += 1
            return len(events)

    def stop(self) -> None:
        self._stopping.set()
