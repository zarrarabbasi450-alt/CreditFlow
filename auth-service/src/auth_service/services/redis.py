import json
import time
from collections.abc import Awaitable
from typing import Protocol, cast
from uuid import UUID

from redis.asyncio import Redis


class RedisProtocol(Protocol):
    async def ping(self) -> bool: ...
    async def close(self) -> None: ...
    async def store_session(
        self,
        jti: str,
        user_id: UUID,
        account_id: UUID,
        account_role: str,
        platform_role: str | None,
        ttl: int,
    ) -> None: ...
    async def session_active(self, jti: str) -> bool: ...
    async def revoke_session(self, jti: str, user_id: UUID) -> None: ...
    async def revoke_user_sessions(self, user_id: UUID) -> None: ...
    async def login_allowed(self, email: str, ip: str, limit: int) -> bool: ...
    async def record_login_failure(self, email: str, ip: str, window: int) -> None: ...
    async def clear_login_failures(self, email: str, ip: str) -> None: ...


class RedisService:
    def __init__(self, url: str) -> None:
        self.client: Redis = Redis.from_url(url, decode_responses=True)

    async def ping(self) -> bool:
        return bool(await self.client.ping())

    async def close(self) -> None:
        await cast(Awaitable[None], self.client.aclose())

    async def store_session(
        self,
        jti: str,
        user_id: UUID,
        account_id: UUID,
        account_role: str,
        platform_role: str | None,
        ttl: int,
    ) -> None:
        session_key = f"auth:session:{jti}"
        user_key = f"auth:user_sessions:{user_id}"
        value = json.dumps({
            "user_id": str(user_id),
            "account_id": str(account_id),
            "account_role": account_role,
            "platform_role": platform_role,
        })
        async with self.client.pipeline(transaction=True) as pipe:
            pipe.set(session_key, value, ex=max(ttl, 1))
            pipe.sadd(user_key, jti)
            pipe.expire(user_key, max(ttl, 1))
            await pipe.execute()

    async def session_active(self, jti: str) -> bool:
        return bool(await self.client.exists(f"auth:session:{jti}"))

    async def revoke_session(self, jti: str, user_id: UUID) -> None:
        await self.client.delete(f"auth:session:{jti}")
        await self.client.srem(f"auth:user_sessions:{user_id}", jti)

    async def revoke_user_sessions(self, user_id: UUID) -> None:
        user_key = f"auth:user_sessions:{user_id}"
        members = await cast(Awaitable[set[str]], self.client.smembers(user_key))
        if members:
            await self.client.delete(*(f"auth:session:{jti}" for jti in members))
        await self.client.delete(user_key)

    async def login_allowed(self, email: str, ip: str, limit: int) -> bool:
        email_count, ip_count = await self.client.mget(f"auth:login:email:{email}", f"auth:login:ip:{ip}")
        return int(email_count or 0) < limit and int(ip_count or 0) < limit

    async def record_login_failure(self, email: str, ip: str, window: int) -> None:
        for key in (f"auth:login:email:{email}", f"auth:login:ip:{ip}"):
            count = await self.client.incr(key)
            if count == 1:
                await self.client.expire(key, window)

    async def clear_login_failures(self, email: str, ip: str) -> None:
        await self.client.delete(f"auth:login:email:{email}", f"auth:login:ip:{ip}")


class InMemoryRedisService:
    def __init__(self) -> None:
        self.sessions: dict[str, tuple[UUID, float, str, str | None]] = {}
        self.failures: dict[str, tuple[int, float]] = {}

    async def ping(self) -> bool:
        return True

    async def close(self) -> None:
        return None

    async def store_session(
        self,
        jti: str,
        user_id: UUID,
        account_id: UUID,
        account_role: str,
        platform_role: str | None,
        ttl: int,
    ) -> None:
        del account_id
        self.sessions[jti] = (user_id, time.monotonic() + ttl, account_role, platform_role)

    async def session_active(self, jti: str) -> bool:
        value = self.sessions.get(jti)
        return value is not None and value[1] > time.monotonic()

    async def revoke_session(self, jti: str, user_id: UUID) -> None:
        del user_id
        self.sessions.pop(jti, None)

    async def revoke_user_sessions(self, user_id: UUID) -> None:
        self.sessions = {key: value for key, value in self.sessions.items() if value[0] != user_id}

    async def login_allowed(self, email: str, ip: str, limit: int) -> bool:
        now = time.monotonic()
        return all(self.failures.get(key, (0, now))[0] < limit for key in (f"e:{email}", f"i:{ip}"))

    async def record_login_failure(self, email: str, ip: str, window: int) -> None:
        now = time.monotonic()
        for key in (f"e:{email}", f"i:{ip}"):
            count, expires = self.failures.get(key, (0, now + window))
            if expires <= now:
                count, expires = 0, now + window
            self.failures[key] = (count + 1, expires)

    async def clear_login_failures(self, email: str, ip: str) -> None:
        self.failures.pop(f"e:{email}", None)
        self.failures.pop(f"i:{ip}", None)
