import json
from collections.abc import Awaitable, Callable
from typing import Any, Protocol

import aio_pika
from aio_pika import DeliveryMode, ExchangeType, Message
from aio_pika.abc import AbstractIncomingMessage, AbstractRobustConnection

from credits_service.schemas.events import EventEnvelope

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
        exchange = await channel.declare_exchange("billing_events", ExchangeType.TOPIC, durable=True)
        dlx = await channel.declare_exchange("billing_events.dlx", ExchangeType.TOPIC, durable=True)
        queue = await channel.declare_queue(
            "credits-service.billing-events",
            durable=True,
            arguments={
                "x-queue-type": "quorum",
                "x-delivery-limit": 5,
                "x-dead-letter-exchange": "billing_events.dlx",
            },
        )
        dead_letter_queue = await channel.declare_queue(
            "credits-service.billing-events.dead-letter", durable=True
        )
        await queue.bind(exchange, "invoice.paid")
        await queue.bind(exchange, "refund.issued")
        await queue.bind(exchange, "credits.purchased")
        await dead_letter_queue.bind(dlx, "#")

        async def consume(message: AbstractIncomingMessage) -> None:
            async with message.process(requeue=True):
                await handler(dict(json.loads(message.body)))

        await queue.consume(consume)

    async def publish(self, event: EventEnvelope) -> None:
        channel = await (await self._connect()).channel(publisher_confirms=True, on_return_raises=True)
        exchange = await channel.declare_exchange("credits_events", ExchangeType.TOPIC, durable=True)
        await exchange.publish(
            Message(
                event.model_dump_json().encode(),
                delivery_mode=DeliveryMode.PERSISTENT,
                content_type="application/json",
                message_id=str(event.event_id),
                correlation_id=event.correlation_id,
                type=event.event_type,
            ),
            routing_key=event.event_type,
            # Consumers are deployed independently. Publishing must remain
            # successful while Usage/Notification queues are not online yet.
            mandatory=False,
        )
        await channel.close()

    async def ping(self) -> bool:
        return not (await self._connect()).is_closed

    async def close(self) -> None:
        if self.connection is not None:
            await self.connection.close()
