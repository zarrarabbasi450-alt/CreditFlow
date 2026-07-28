from collections.abc import Awaitable, Callable
from typing import Protocol, cast

from redis.asyncio import Redis


class LockProtocol(Protocol):
    async def acquire(self, key: str, ttl_seconds: int) -> bool: ...
    async def ping(self) -> bool: ...
    async def close(self) -> None: ...


class RedisLockService:
    def __init__(self, url: str) -> None:
        self.client: Redis = Redis.from_url(url, decode_responses=True)

    async def acquire(self, key: str, ttl_seconds: int) -> bool:
        return bool(await self.client.set(key, "1", ex=ttl_seconds, nx=True))

    async def ping(self) -> bool:
        return bool(await self.client.ping())

    async def close(self) -> None:
        close = cast(Callable[[], Awaitable[None]], self.client.aclose)
        await close()


class InMemoryLockService:
    def __init__(self) -> None:
        self.keys: set[str] = set()

    async def acquire(self, key: str, ttl_seconds: int) -> bool:
        del ttl_seconds
        if key in self.keys:
            return False
        self.keys.add(key)
        return True

    async def ping(self) -> bool:
        return True

    async def close(self) -> None:
        return None
