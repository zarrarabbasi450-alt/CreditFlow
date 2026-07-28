import json
from collections.abc import Awaitable, Callable
from typing import Any, Protocol

import aio_pika
from aio_pika import DeliveryMode, ExchangeType, Message
from aio_pika.abc import AbstractIncomingMessage, AbstractRobustConnection

from scraper_service.schemas.events import EventEnvelope

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
        await channel.set_qos(prefetch_count=10)
        shared = await channel.declare_exchange("creditflow.events", ExchangeType.TOPIC, durable=True)
        scraper = await channel.declare_exchange("scraper_events", ExchangeType.TOPIC, durable=True)
        dlx = await channel.declare_exchange("scraper_events.dlx", ExchangeType.TOPIC, durable=True)
        queue = await channel.declare_queue(
            "scraper-service.requests",
            durable=True,
            arguments={
                "x-queue-type": "quorum",
                "x-delivery-limit": 5,
                "x-dead-letter-exchange": "scraper_events.dlx",
            },
        )
        dead_letter_queue = await channel.declare_queue("scraper-service.requests.dead-letter", durable=True)
        await dead_letter_queue.bind(dlx, "scrape.requested")
        await queue.bind(shared, "scrape.requested")
        await queue.bind(scraper, "scrape.requested")

        async def consume(message: AbstractIncomingMessage) -> None:
            async with message.process(requeue=True):
                await handler(dict(json.loads(message.body)))

        await queue.consume(consume)

    async def publish(self, event: EventEnvelope) -> None:
        channel = await (await self._connect()).channel(publisher_confirms=True, on_return_raises=True)
        scraper = await channel.declare_exchange("scraper_events", ExchangeType.TOPIC, durable=True)
        shared = await channel.declare_exchange("creditflow.events", ExchangeType.TOPIC, durable=True)
        message = Message(
            event.model_dump_json().encode(),
            delivery_mode=DeliveryMode.PERSISTENT,
            content_type="application/json",
            message_id=str(event.event_id),
            correlation_id=event.correlation_id,
            type=event.event_type,
        )
        await scraper.publish(message, routing_key=event.event_type, mandatory=False)
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
        if self.handler is not None:
            await self.handler(event.model_dump(mode="json"))

    async def ping(self) -> bool:
        return True

    async def close(self) -> None:
        return None
