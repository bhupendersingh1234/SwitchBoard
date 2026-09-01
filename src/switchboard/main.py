from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from switchboard.api.chat import router as chat_router
from switchboard.api.health import router as health_router
from switchboard.cache.redis import build_redis
from switchboard.core.config import get_settings
from switchboard.core.logging import configure_logging
from switchboard.core.resources import Resources
from switchboard.db.session import build_engine, build_sessionmaker
from switchboard.providers.openai import OpenAIProvider


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    configure_logging(settings.log_level)
    engine = build_engine(settings)
    app.state.resources = Resources(
        settings=settings,
        engine=engine,
        sessionmaker=build_sessionmaker(engine),
        redis=build_redis(settings),
        provider=OpenAIProvider(
            base_url=settings.openai_base_url,
            api_key=settings.openai_api_key,
            timeout_s=settings.provider_timeout_s,
        ),
    )
    try:
        yield
    finally:
        await app.state.resources.close()
        app.state.resources = None


app = FastAPI(title="Switchboard", lifespan=lifespan)
app.include_router(health_router)
app.include_router(chat_router)