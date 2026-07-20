import time
from dataclasses import dataclass

from api_gateway.services.redis_protocol import RedisProtocol

SCRIPT = """
local key = KEYS[1]
local now = tonumber(ARGV[1])
local window = tonumber(ARGV[2])
local limit = tonumber(ARGV[3])
local member = ARGV[4]
redis.call('ZREMRANGEBYSCORE', key, 0, now-window)
local count = redis.call('ZCARD', key)
if count >= limit then
  local oldest = redis.call('ZRANGE', key, 0, 0, 'WITHSCORES')
  return {0, count, math.ceil((tonumber(oldest[2])+window-now)/1000)}
end
redis.call('ZADD', key, now, member)
redis.call('PEXPIRE', key, window)
return {1, count+1, 0}
"""


@dataclass(frozen=True)
class RateLimitResult:
    allowed: bool
    limit: int
    remaining: int
    retry_after: int


class RateLimiter:
    def __init__(self, redis: RedisProtocol) -> None:
        self.redis = redis

    async def check(self, key: str, limit: int, window_seconds: int, request_id: str) -> RateLimitResult:
        now = int(time.time() * 1000)
        result = await self.redis.eval(
            SCRIPT, [f"rate:{key}"], [now, window_seconds * 1000, limit, f"{now}:{request_id}"]
        )
        allowed, count, retry = (int(value) for value in result)
        return RateLimitResult(bool(allowed), limit, max(0, limit - count), retry)
