import json
from collections.abc import Awaitable, Callable
from typing import Any, Protocol

import aio_pika
from aio_pika import DeliveryMode, ExchangeType, Message
from aio_pika.abc import AbstractIncomingMessage, AbstractRobustConnection

from scheduler_service.schemas.events import EventEnvelope

EventHandler = Callable[[dict[str, Any]], Awaitable[None]]


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
        await channel.set_qos(prefetch_count=20)
        content_exchange = await channel.declare_exchange("content_events", ExchangeType.TOPIC, durable=True)
        shared_exchange = await channel.declare_exchange(
            "creditflow.events", ExchangeType.TOPIC, durable=True
        )
        dlx = await channel.declare_exchange("scheduler_events.dlx", ExchangeType.TOPIC, durable=True)
        queue = await channel.declare_queue(
            "scheduler-service.content-events",
            durable=True,
            arguments={
                "x-queue-type": "quorum",
                "x-delivery-limit": 5,
                "x-dead-letter-exchange": "scheduler_events.dlx",
            },
        )
        dead_letter_queue = await channel.declare_queue(
            "scheduler-service.content-events.dead-letter", durable=True
        )
        await queue.bind(content_exchange, "content.created")
        await queue.bind(shared_exchange, "content.created")
        await queue.bind(content_exchange, "content.deleted")
        await queue.bind(shared_exchange, "content.deleted")
        await dead_letter_queue.bind(dlx, "#")

        async def consume(message: AbstractIncomingMessage) -> None:
            async with message.process(requeue=True):
                await handler(dict(json.loads(message.body)))

        await queue.consume(consume)

    async def publish(self, event: EventEnvelope) -> None:
        channel = await (await self._connect()).channel(publisher_confirms=True, on_return_raises=True)
        scheduler_exchange = await channel.declare_exchange(
            "scheduler_events", ExchangeType.TOPIC, durable=True
        )
        shared_exchange = await channel.declare_exchange(
            "creditflow.events", ExchangeType.TOPIC, durable=True
        )
        message = Message(
            event.model_dump_json().encode(),
            delivery_mode=DeliveryMode.PERSISTENT,
            content_type="application/json",
            message_id=str(event.event_id),
            correlation_id=event.correlation_id,
            type=event.event_type,
        )
        await scheduler_exchange.publish(message, routing_key=event.event_type, mandatory=False)
        await shared_exchange.publish(message, routing_key=event.event_type, mandatory=False)
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

    async def deliver(self, event: dict[str, Any]) -> None:
        if self.handler is None:
            raise RuntimeError("Consumer is not started")
        await self.handler(event)
