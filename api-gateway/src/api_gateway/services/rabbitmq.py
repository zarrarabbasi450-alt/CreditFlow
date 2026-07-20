import aio_pika
from aio_pika import DeliveryMode, ExchangeType, Message
from aio_pika.abc import AbstractRobustConnection

from api_gateway.schemas.events import EventEnvelope


class RabbitPublisher:
    def __init__(self, url: str) -> None:
        self.url = url
        self.connection: AbstractRobustConnection | None = None

    async def connect(self) -> None:
        if self.connection is None or self.connection.is_closed:
            self.connection = await aio_pika.connect_robust(self.url)

    async def ping(self) -> bool:
        await self.connect()
        return self.connection is not None and not self.connection.is_closed

    async def publish(self, event: EventEnvelope) -> None:
        await self.connect()
        assert self.connection is not None
        channel = await self.connection.channel(publisher_confirms=True, on_return_raises=True)
        exchange = await channel.declare_exchange("creditflow.events", ExchangeType.TOPIC, durable=True)
        message = Message(
            event.model_dump_json().encode(),
            content_type="application/json",
            delivery_mode=DeliveryMode.PERSISTENT,
            message_id=str(event.event_id),
            correlation_id=event.correlation_id,
            type=event.event_type,
        )
        await exchange.publish(message, routing_key=event.event_type, mandatory=True)
        await channel.close()

    async def close(self) -> None:
        if self.connection is not None:
            await self.connection.close()
