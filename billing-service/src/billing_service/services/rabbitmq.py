import json
from collections.abc import Awaitable, Callable
from typing import Any, Protocol

import aio_pika
from aio_pika import DeliveryMode, ExchangeType, Message
from aio_pika.abc import AbstractIncomingMessage, AbstractRobustConnection

from billing_service.schemas.events import EventEnvelope

EventHandler = Callable[[dict[str, Any]], Awaitable[None]]
AccountHandler = Callable[[dict[str, Any], str], Awaitable[None]]


class EventBusProtocol(Protocol):
    async def start(self, account_handler: AccountHandler, webhook_handler: EventHandler) -> None: ...
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

    async def start(self, account_handler: AccountHandler, webhook_handler: EventHandler) -> None:
        connection = await self._connect()
        channel = await connection.channel()
        await channel.set_qos(prefetch_count=20)
        exchange = await channel.declare_exchange("creditflow.events", ExchangeType.TOPIC, durable=True)
        dlx = await channel.declare_exchange("creditflow.events.dlx", ExchangeType.TOPIC, durable=True)
        queue = await channel.declare_queue(
            "billing-service.events",
            durable=True,
            arguments={
                "x-queue-type": "quorum",
                "x-delivery-limit": 5,
                "x-dead-letter-exchange": "creditflow.events.dlx",
            },
        )
        dead_letter_queue = await channel.declare_queue("billing-service.events.dead-letter", durable=True)
        await queue.bind(exchange, "account.created")
        await queue.bind(exchange, "billing.#")
        await dead_letter_queue.bind(dlx, "#")

        async def consume(message: AbstractIncomingMessage) -> None:
            async with message.process(requeue=True):
                envelope = json.loads(message.body)
                event_type = str(envelope.get("event_type") or envelope.get("type") or "")
                if event_type == "account.created":
                    payload = envelope.get("payload") or envelope.get("data") or {}
                    await account_handler(
                        dict(payload),
                        str(envelope.get("correlation_id") or envelope.get("correlationId") or ""),
                    )
                else:
                    await webhook_handler(envelope)

        await queue.consume(consume)

    async def publish(self, event: EventEnvelope) -> None:
        connection = await self._connect()
        channel = await connection.channel(publisher_confirms=True, on_return_raises=True)
        exchange = await channel.declare_exchange("billing_events", ExchangeType.TOPIC, durable=True)
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
            mandatory=False,
        )
        await channel.close()

    async def ping(self) -> bool:
        return not (await self._connect()).is_closed

    async def close(self) -> None:
        if self.connection is not None:
            await self.connection.close()
