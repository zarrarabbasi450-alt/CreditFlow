import asyncio
import time
from collections import defaultdict
from collections.abc import AsyncGenerator, Awaitable, Callable
from typing import Any, cast

from redis.asyncio import Redis


class RedisService:
    def __init__(self, url: str) -> None:
        self.client: Redis = Redis.from_url(url, decode_responses=True)

    async def ping(self) -> bool:
        return bool(await self.client.ping())

    async def deduplicate(self, key: str, ttl: int = 86400) -> bool:
        return bool(await self.client.set(key, "1", ex=ttl, nx=True))

    async def delete(self, key: str) -> None:
        await self.client.delete(key)

    async def exists(self, key: str) -> bool:
        return bool(await self.client.exists(key))

    async def eval(self, script: str, keys: list[str], args: list[str | int]) -> list[int]:
        redis_args = [*keys, *(str(argument) for argument in args)]
        result = await cast(Awaitable[Any], self.client.eval(script, len(keys), *redis_args))
        return cast(list[int], result)

    async def subscribe(self, channel: str) -> AsyncGenerator[dict[str, Any]]:
        pubsub = self.client.pubsub()
        await pubsub.subscribe(channel)
        try:
            async for message in pubsub.listen():
                if message["type"] == "message":
                    yield message
        finally:
            await pubsub.unsubscribe(channel)
            close_pubsub = cast(Callable[[], Awaitable[None]], pubsub.aclose)
            await close_pubsub()

    async def close(self) -> None:
        await self.client.aclose()


class InMemoryRedisService:
    def __init__(self) -> None:
        self.events: dict[str, float] = {}
        self.windows: dict[str, list[int]] = defaultdict(list)
        self.channels: dict[str, asyncio.Queue[dict[str, Any]]] = defaultdict(asyncio.Queue)

    async def ping(self) -> bool:
        return True

    async def deduplicate(self, key: str, ttl: int = 86400) -> bool:
        now = time.time()
        self.events = {item: expires for item, expires in self.events.items() if expires > now}
        if key in self.events:
            return False
        self.events[key] = now + ttl
        return True

    async def delete(self, key: str) -> None:
        self.events.pop(key, None)

    async def exists(self, key: str) -> bool:
        now = time.time()
        return self.events.get(key, 0) > now

    async def eval(self, _script: str, keys: list[str], args: list[str | int]) -> list[int]:
        now, window, limit = int(args[0]), int(args[1]), int(args[2])
        key = keys[0]
        self.windows[key] = [stamp for stamp in self.windows[key] if stamp > now - window]
        if len(self.windows[key]) >= limit:
            return [
                0,
                len(self.windows[key]),
                max(1, (self.windows[key][0] + window - now + 999) // 1000),
            ]
        self.windows[key].append(now)
        return [1, len(self.windows[key]), 0]

    async def subscribe(self, channel: str) -> AsyncGenerator[dict[str, Any]]:
        while True:
            yield await self.channels[channel].get()

    async def close(self) -> None:
        return None
