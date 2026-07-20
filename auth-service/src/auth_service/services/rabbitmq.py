import json
from datetime import UTC, datetime
from typing import Any, Protocol
from uuid import uuid4

import aio_pika
from aio_pika.abc import AbstractRobustConnection


class EventPublisherProtocol(Protocol):
    async def ping(self) -> bool: ...
    async def close(self) -> None: ...
    async def publish(self, routing_key: str, payload: dict[str, Any]) -> None: ...


class RabbitMQPublisher:
    def __init__(self, url: str) -> None:
        self.url = url
        self.connection: AbstractRobustConnection | None = None

    async def _connection(self) -> AbstractRobustConnection:
        if self.connection is None or self.connection.is_closed:
            self.connection = await aio_pika.connect_robust(self.url)
        return self.connection

    async def ping(self) -> bool:
        await self._connection()
        return True

    async def close(self) -> None:
        if self.connection is not None:
            await self.connection.close()

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


class InMemoryEventPublisher:
    def __init__(self) -> None:
        self.events: list[tuple[str, dict[str, Any]]] = []

    async def ping(self) -> bool:
        return True

    async def close(self) -> None:
        return None

    async def publish(self, routing_key: str, payload: dict[str, Any]) -> None:
        self.events.append((routing_key, payload))
