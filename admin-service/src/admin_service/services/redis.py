import json
from collections.abc import Awaitable
from typing import Protocol, cast
from uuid import UUID

from redis.asyncio import Redis

from admin_service.schemas.admin import SessionItem


class SessionDirectoryProtocol(Protocol):
    async def ping(self) -> bool: ...
    async def close(self) -> None: ...
    async def list_sessions(self, account_id: UUID | None) -> list[SessionItem]: ...
    async def get_session(self, jti: str) -> SessionItem | None: ...
    async def revoke_session(self, jti: str) -> bool: ...


class RedisSessionDirectory:
    """Reads auth-service's session keys directly out of the same Redis instance.

    auth-service stores `auth:session:{jti}` -> JSON {user_id, account_id,
    account_role, platform_role} with a TTL, and a per-user `auth:user_sessions:
    {user_id}` set of jtis. There is no per-account index, so listing sessions for
    an account requires scanning the `auth:session:*` keyspace and filtering —
    acceptable for an admin/ops tool, not a hot path.
    """

    def __init__(self, url: str) -> None:
        self.client: Redis = Redis.from_url(url, decode_responses=True)

    async def ping(self) -> bool:
        return bool(await self.client.ping())

    async def close(self) -> None:
        await cast(Awaitable[None], self.client.aclose())

    async def _scan_sessions(self) -> list[tuple[str, dict[str, str]]]:
        results: list[tuple[str, dict[str, str]]] = []
        async for key in self.client.scan_iter(match="auth:session:*"):
            raw = await self.client.get(key)
            if not raw:
                continue
            try:
                value = json.loads(raw)
            except ValueError:
                continue
            results.append((key.removeprefix("auth:session:"), value))
        return results

    async def list_sessions(self, account_id: UUID | None) -> list[SessionItem]:
        items = []
        for jti, value in await self._scan_sessions():
            if account_id is not None and value.get("account_id") != str(account_id):
                continue
            items.append(
                SessionItem(
                    jti=jti,
                    user_id=UUID(str(value["user_id"])),
                    account_id=UUID(str(value["account_id"])),
                    account_role=str(value.get("account_role") or ""),
                    platform_role=value.get("platform_role"),
                )
            )
        return items

    async def get_session(self, jti: str) -> SessionItem | None:
        raw = await self.client.get(f"auth:session:{jti}")
        if not raw:
            return None
        value = json.loads(raw)
        return SessionItem(
            jti=jti,
            user_id=UUID(str(value["user_id"])),
            account_id=UUID(str(value["account_id"])),
            account_role=str(value.get("account_role") or ""),
            platform_role=value.get("platform_role"),
        )

    async def revoke_session(self, jti: str) -> bool:
        session = await self.get_session(jti)
        if session is None:
            return False
        await self.client.delete(f"auth:session:{jti}")
        await cast(
            Awaitable[int], self.client.srem(f"auth:user_sessions:{session.user_id}", jti)
        )
        return True


class InMemorySessionDirectory:
    def __init__(self) -> None:
        self.sessions: dict[str, SessionItem] = {}

    async def ping(self) -> bool:
        return True

    async def close(self) -> None:
        return None

    async def list_sessions(self, account_id: UUID | None) -> list[SessionItem]:
        return [
            session
            for session in self.sessions.values()
            if account_id is None or session.account_id == account_id
        ]

    async def get_session(self, jti: str) -> SessionItem | None:
        return self.sessions.get(jti)

    async def revoke_session(self, jti: str) -> bool:
        return self.sessions.pop(jti, None) is not None
