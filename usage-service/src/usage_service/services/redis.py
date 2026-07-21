from collections.abc import Awaitable, Callable
from typing import Any, Protocol, cast

from redis.asyncio import Redis

RESERVE_SCRIPT = """
local current = tonumber(redis.call('GET', KEYS[1]) or '0')
local requested = tonumber(ARGV[1])
local quota = tonumber(ARGV[2])
local ttl = tonumber(ARGV[3])
if current + requested > quota then
  return {0, current}
end
local updated = redis.call('INCRBY', KEYS[1], requested)
redis.call('EXPIRE', KEYS[1], ttl)
return {1, updated}
"""


class RedisProtocol(Protocol):
    async def reserve(self, key: str, amount: int, quota: int, ttl: int) -> tuple[bool, int]: ...
    async def set_counter(self, key: str, value: int, ttl: int) -> None: ...
    async def mark_threshold(self, key: str, ttl: int) -> bool: ...
    async def ping(self) -> bool: ...
    async def close(self) -> None: ...


class RedisService:
    def __init__(self, url: str) -> None:
        self.client: Redis = Redis.from_url(url, decode_responses=True)

    async def reserve(self, key: str, amount: int, quota: int, ttl: int) -> tuple[bool, int]:
        raw = await cast(
            Awaitable[Any],
            self.client.eval(RESERVE_SCRIPT, 1, key, str(amount), str(quota), str(ttl)),
        )
        result = cast(list[int], raw)
        return bool(result[0]), int(result[1])

    async def set_counter(self, key: str, value: int, ttl: int) -> None:
        await self.client.set(key, value, ex=ttl)

    async def mark_threshold(self, key: str, ttl: int) -> bool:
        return bool(await self.client.set(key, "1", ex=ttl, nx=True))

    async def ping(self) -> bool:
        return bool(await self.client.ping())

    async def close(self) -> None:
        close = cast(Callable[[], Awaitable[None]], self.client.aclose)
        await close()


class InMemoryRedisService:
    def __init__(self) -> None:
        self.counters: dict[str, int] = {}
        self.thresholds: set[str] = set()

    async def reserve(self, key: str, amount: int, quota: int, ttl: int) -> tuple[bool, int]:
        del ttl
        current = self.counters.get(key, 0)
        if current + amount > quota:
            return False, current
        self.counters[key] = current + amount
        return True, self.counters[key]

    async def set_counter(self, key: str, value: int, ttl: int) -> None:
        del ttl
        self.counters[key] = value

    async def mark_threshold(self, key: str, ttl: int) -> bool:
        del ttl
        if key in self.thresholds:
            return False
        self.thresholds.add(key)
        return True

    async def ping(self) -> bool:
        return True

    async def close(self) -> None:
        return None
