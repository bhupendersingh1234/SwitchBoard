from dataclasses import dataclass

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from switchboard.core.config import Settings


@dataclass(slots=True)
class Resources:
    settings: Settings
    engine: AsyncEngine
    sessionmaker: async_sessionmaker[AsyncSession]
    redis: Redis

    async def close(self) -> None:
        await self.redis.aclose()
        await self.engine.dispose()