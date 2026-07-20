import json
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Any, Protocol
from uuid import uuid4

import aio_pika
from aio_pika.abc import AbstractChannel, AbstractIncomingMessage, AbstractRobustConnection

EventHandler = Callable[[dict[str, Any]], Awaitable[None]]


class EventPublisherProtocol(Protocol):
    async def publish(self, routing_key: str, payload: dict[str, Any]) -> None: ...


class EventBusProtocol(EventPublisherProtocol, Protocol):
    async def start(self, handler: EventHandler) -> None: ...

    async def close(self) -> None: ...


class RabbitMQService:
    def __init__(self, url: str) -> None:
        self.url = url
        self.connection: AbstractRobustConnection | None = None
        self.consumer_channel: AbstractChannel | None = None

    async def _connection(self) -> AbstractRobustConnection:
        if self.connection is None or self.connection.is_closed:
            self.connection = await aio_pika.connect_robust(self.url)
        return self.connection

    async def publish(self, routing_key: str, payload: dict[str, Any]) -> None:
        connection = await self._connection()
        async with connection.channel() as channel:
            exchange = await channel.declare_exchange(
                "creditflow.events", aio_pika.ExchangeType.TOPIC, durable=True
            )
            envelope = {
                "id": str(uuid4()),
                "type": routing_key,
                "occurred_at": datetime.now(UTC).isoformat(),
                "data": payload,
            }
            await exchange.publish(
                aio_pika.Message(
                    json.dumps(envelope).encode(),
                    content_type="application/json",
                    delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
                ),
                routing_key=routing_key,
            )

    async def start(self, handler: EventHandler) -> None:
        connection = await self._connection()
        self.consumer_channel = await connection.channel()
        await self.consumer_channel.set_qos(prefetch_count=10)
        exchange = await self.consumer_channel.declare_exchange(
            "creditflow.events", aio_pika.ExchangeType.TOPIC, durable=True
        )
        queue = await self.consumer_channel.declare_queue("tenant-service.user-registered", durable=True)
        await queue.bind(exchange, routing_key="user.registered")

        async def consume(message: AbstractIncomingMessage) -> None:
            async with message.process(requeue=True):
                envelope = json.loads(message.body)
                data = envelope.get("data")
                if not isinstance(data, dict):
                    raise ValueError("Event data must be an object")
                await handler(data)

        await queue.consume(consume)

    async def close(self) -> None:
        if self.consumer_channel is not None:
            await self.consumer_channel.close()
        if self.connection is not None:
            await self.connection.close()


class InMemoryEventBus:
    def __init__(self) -> None:
        self.events: list[tuple[str, dict[str, Any]]] = []
        self.handler: EventHandler | None = None

    async def publish(self, routing_key: str, payload: dict[str, Any]) -> None:
        self.events.append((routing_key, payload))

    async def start(self, handler: EventHandler) -> None:
        self.handler = handler

    async def close(self) -> None:
        return None

    async def deliver(self, payload: dict[str, Any]) -> None:
        if self.handler is None:
            raise RuntimeError("Consumer is not started")
        await self.handler(payload)
