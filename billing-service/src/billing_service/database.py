from typing import Protocol

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine


class DatabaseProtocol(Protocol):
    sessions: async_sessionmaker[AsyncSession]

    async def ping(self) -> bool: ...
    async def close(self) -> None: ...


class Database:
    def __init__(self, url: str) -> None:
        self.engine: AsyncEngine = create_async_engine(url, pool_pre_ping=True)
        self.sessions = async_sessionmaker(self.engine, expire_on_commit=False)

    async def ping(self) -> bool:
        async with self.engine.connect() as connection:
            return bool((await connection.execute(text("SELECT 1"))).scalar_one() == 1)

    async def close(self) -> None:
        await self.engine.dispose()
