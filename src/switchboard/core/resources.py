from dataclasses import dataclass

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from switchboard.core.config import Settings
from switchboard.limits.bucket import TokenBucket
from switchboard.providers.base import Provider


@dataclass(slots=True)
class Resources:
    settings: Settings
    engine: AsyncEngine
    sessionmaker: async_sessionmaker[AsyncSession]
    redis: Redis
    provider: Provider
    rate_limiter: TokenBucket
    cascade_provider: Provider

    async def close(self) -> None:
        await self.redis.aclose()
        await self.engine.dispose()
        await self.provider.aclose()