import json
from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Any, Protocol, cast

from redis.asyncio import Redis


class RedisProtocol(Protocol):
    async def publish_token(self, channel: str, event: dict[str, Any]) -> None: ...
    async def cancel(self, job_id: str) -> None: ...
    async def is_cancelled(self, job_id: str) -> bool: ...
    async def stream(self, channel: str) -> AsyncIterator[dict[str, Any]]: ...
    async def ping(self) -> bool: ...
    async def close(self) -> None: ...


class RedisService:
    def __init__(self, url: str) -> None:
        self.client: Redis = Redis.from_url(url, decode_responses=True)

    async def publish_token(self, channel: str, event: dict[str, Any]) -> None:
        await self.client.publish(channel, json.dumps(event))

    async def cancel(self, job_id: str) -> None:
        await self.client.set(f"ai:cancel:{job_id}", "1", ex=3600)

    async def is_cancelled(self, job_id: str) -> bool:
        return bool(await self.client.exists(f"ai:cancel:{job_id}"))

    async def stream(self, channel: str) -> AsyncIterator[dict[str, Any]]:
        pubsub = self.client.pubsub()
        await pubsub.subscribe(channel)
        try:
            async for message in pubsub.listen():
                if message["type"] != "message":
                    continue
                payload = cast(dict[str, Any], json.loads(str(message["data"])))
                yield payload
                if payload.get("type") in {"complete", "failed", "cancelled"}:
                    break
        finally:
            close = cast(Callable[[], Awaitable[None]], pubsub.aclose)
            await close()

    async def ping(self) -> bool:
        return bool(await self.client.ping())

    async def close(self) -> None:
        close = cast(Callable[[], Awaitable[None]], self.client.aclose)
        await close()


class InMemoryRedisService:
    def __init__(self) -> None:
        self.messages: dict[str, list[dict[str, Any]]] = {}
        self.cancelled: set[str] = set()

    async def publish_token(self, channel: str, event: dict[str, Any]) -> None:
        self.messages.setdefault(channel, []).append(event)

    async def cancel(self, job_id: str) -> None:
        self.cancelled.add(job_id)

    async def is_cancelled(self, job_id: str) -> bool:
        return job_id in self.cancelled

    async def stream(self, channel: str) -> AsyncIterator[dict[str, Any]]:
        for message in self.messages.get(channel, []):
            yield message

    async def ping(self) -> bool:
        return True

    async def close(self) -> None:
        return None
