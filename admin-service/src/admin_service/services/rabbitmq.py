import json
from collections.abc import Awaitable, Callable
from typing import Any, Protocol

import aio_pika
from aio_pika import ExchangeType
from aio_pika.abc import AbstractIncomingMessage, AbstractRobustConnection

EventHandler = Callable[[dict[str, Any]], Awaitable[None]]


class EventBusProtocol(Protocol):
    async def start(self, handler: EventHandler) -> None: ...
    async def ping(self) -> bool: ...
    async def close(self) -> None: ...


class RabbitMQService:
    """Consumes ALL platform events for the audit trail — binds `#` on the shared
    topic exchange, so every routing key delivered regardless of type. admin-service
    publishes nothing of its own, per the Admin/Ops service spec."""

    def __init__(self, url: str) -> None:
        self.url = url
        self.connection: AbstractRobustConnection | None = None

    async def _connect(self) -> AbstractRobustConnection:
        if self.connection is None or self.connection.is_closed:
            self.connection = await aio_pika.connect_robust(self.url)
        return self.connection

    async def start(self, handler: EventHandler) -> None:
        channel = await (await self._connect()).channel()
        await channel.set_qos(prefetch_count=20)
        shared = await channel.declare_exchange("creditflow.events", ExchangeType.TOPIC, durable=True)
        dlx = await channel.declare_exchange("admin_events.dlx", ExchangeType.TOPIC, durable=True)
        queue = await channel.declare_queue(
            "admin-service.events",
            durable=True,
            arguments={
                "x-queue-type": "quorum",
                "x-delivery-limit": 5,
                "x-dead-letter-exchange": "admin_events.dlx",
            },
        )
        dead_letter_queue = await channel.declare_queue("admin-service.events.dead-letter", durable=True)
        await queue.bind(shared, "#")
        await dead_letter_queue.bind(dlx, "#")

        async def consume(message: AbstractIncomingMessage) -> None:
            async with message.process(requeue=True):
                envelope = json.loads(message.body)
                event_id = envelope.get("event_id") or envelope.get("id")
                event_type = str(envelope.get("event_type") or envelope.get("type") or "")
                payload = dict(envelope.get("payload") or envelope.get("data") or {})
                correlation_id = envelope.get("correlation_id") or envelope.get("correlationId")
                if not event_type:
                    return
                await handler({
                    "event_id": event_id,
                    "event_type": event_type,
                    "payload": payload,
                    "correlation_id": correlation_id,
                })

        await queue.consume(consume)

    async def ping(self) -> bool:
        return not (await self._connect()).is_closed

    async def close(self) -> None:
        if self.connection is not None:
            await self.connection.close()


class InMemoryEventBus:
    def __init__(self) -> None:
        self.handler: EventHandler | None = None

    async def start(self, handler: EventHandler) -> None:
        self.handler = handler

    async def ping(self) -> bool:
        return True

    async def close(self) -> None:
        return None

    async def deliver(
        self,
        event_type: str,
        payload: dict[str, Any],
        *,
        event_id: str | None = None,
        correlation_id: str | None = None,
    ) -> None:
        if self.handler is None:
            raise RuntimeError("Consumer is not started")
        await self.handler({
            "event_id": event_id,
            "event_type": event_type,
            "payload": payload,
            "correlation_id": correlation_id,
        })
