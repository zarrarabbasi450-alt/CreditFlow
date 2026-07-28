import json
from collections.abc import Awaitable, Callable
from typing import Any, Protocol

import aio_pika
from aio_pika import DeliveryMode, ExchangeType, Message
from aio_pika.abc import AbstractIncomingMessage, AbstractRobustConnection

from notification_service.schemas.events import EventEnvelope

EventHandler = Callable[[dict[str, Any]], Awaitable[None]]

CONSUMED_ROUTING_KEYS = (
    "user.registered",
    "user.password_reset_requested",
    "invoice.paid",
    "payment.failed",
    "member.invited",
    "member.joined",
    "post.published",
    "post.failed",
    "usage.threshold_reached",
)


class EventBusProtocol(Protocol):
    async def start(self, handler: EventHandler) -> None: ...
    async def publish(self, event: EventEnvelope) -> None: ...
    async def ping(self) -> bool: ...
    async def close(self) -> None: ...


class RabbitMQService:
    def __init__(self, url: str) -> None:
        self.url = url
        self.connection: AbstractRobustConnection | None = None

    async def _connect(self) -> AbstractRobustConnection:
        if self.connection is None or self.connection.is_closed:
            self.connection = await aio_pika.connect_robust(self.url)
        return self.connection

    async def start(self, handler: EventHandler) -> None:
        channel = await (await self._connect()).channel()
        await channel.set_qos(prefetch_count=10)
        shared = await channel.declare_exchange("creditflow.events", ExchangeType.TOPIC, durable=True)
        dlx = await channel.declare_exchange("notification_events.dlx", ExchangeType.TOPIC, durable=True)
        queue = await channel.declare_queue(
            "notification-service.events",
            durable=True,
            arguments={
                "x-queue-type": "quorum",
                "x-delivery-limit": 5,
                "x-dead-letter-exchange": "notification_events.dlx",
            },
        )
        dead_letter_queue = await channel.declare_queue(
            "notification-service.events.dead-letter", durable=True
        )
        for routing_key in CONSUMED_ROUTING_KEYS:
            await queue.bind(shared, routing_key)
            await dead_letter_queue.bind(dlx, routing_key)

        async def consume(message: AbstractIncomingMessage) -> None:
            async with message.process(requeue=True):
                envelope = json.loads(message.body)
                event_type = str(envelope.get("event_type") or envelope.get("type") or "")
                payload = dict(envelope.get("payload") or envelope.get("data") or {})
                correlation_id = envelope.get("correlation_id")
                await handler({
                    "event_type": event_type,
                    "payload": payload,
                    "correlation_id": correlation_id,
                })

        await queue.consume(consume)

    async def publish(self, event: EventEnvelope) -> None:
        channel = await (await self._connect()).channel(publisher_confirms=True, on_return_raises=True)
        notifications = await channel.declare_exchange(
            "notification_events", ExchangeType.TOPIC, durable=True
        )
        shared = await channel.declare_exchange("creditflow.events", ExchangeType.TOPIC, durable=True)
        message = Message(
            event.model_dump_json().encode(),
            delivery_mode=DeliveryMode.PERSISTENT,
            content_type="application/json",
            message_id=str(event.event_id),
            correlation_id=event.correlation_id,
            type=event.event_type,
        )
        await notifications.publish(message, routing_key=event.event_type, mandatory=False)
        await shared.publish(message, routing_key=event.event_type, mandatory=False)
        await channel.close()

    async def ping(self) -> bool:
        return not (await self._connect()).is_closed

    async def close(self) -> None:
        if self.connection is not None:
            await self.connection.close()


class InMemoryEventBus:
    def __init__(self) -> None:
        self.events: list[EventEnvelope] = []
        self.handler: EventHandler | None = None

    async def start(self, handler: EventHandler) -> None:
        self.handler = handler

    async def publish(self, event: EventEnvelope) -> None:
        self.events.append(event)

    async def ping(self) -> bool:
        return True

    async def close(self) -> None:
        return None

    async def deliver(
        self,
        event_type: str,
        payload: dict[str, Any],
        correlation_id: str | None = None,
        event_id: str | None = None,
    ) -> None:
        if self.handler is None:
            raise RuntimeError("Consumer is not started")
        await self.handler({
            "event_id": event_id,
            "event_type": event_type,
            "payload": payload,
            "correlation_id": correlation_id,
        })
