from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from switchboard.api.chat import router as chat_router
from switchboard.api.health import router as health_router
from switchboard.api.keys import router as keys_router
from switchboard.cache.redis import build_redis
from switchboard.core.config import Settings, get_settings
from switchboard.core.logging import configure_logging
from switchboard.core.resources import Resources
from switchboard.db.session import build_engine, build_sessionmaker
from switchboard.limits.bucket import TokenBucket
from switchboard.providers.base import Provider
from switchboard.providers.failover import FailoverProvider
from switchboard.providers.openai import OpenAIProvider
from switchboard.providers.resilient import ResilientProvider
from switchboard.resilience.breaker import CircuitBreaker
from switchboard.providers.hedged import HedgedProvider
from switchboard.observability.middleware import MetricsMiddleware, TraceIdMiddleware
from switchboard.observability.tracing_setup import configure_tracing
from switchboard.routing.cascade import CascadeProvider


def _build_resilient(base_url: str, api_key: str, settings: Settings) -> ResilientProvider:
    return ResilientProvider(
        OpenAIProvider(base_url=base_url, api_key=api_key, timeout_s=settings.provider_timeout_s),
        breaker=CircuitBreaker(
            failure_threshold=settings.provider_failure_threshold,
            recovery_timeout=settings.provider_recovery_timeout,
        ),
        max_attempts=settings.provider_max_retries,
    )


def _build_provider(settings: Settings) -> Provider:
    primary = _build_resilient(settings.openai_base_url, settings.openai_api_key, settings)
    if settings.backup_openai_base_url and settings.backup_openai_api_key:
        backup = _build_resilient(
            settings.backup_openai_base_url, settings.backup_openai_api_key, settings
        )
        if settings.enable_hedging:
            return HedgedProvider(primary, backup, hedge_delay=settings.hedge_delay_s)
        return FailoverProvider([primary, backup])
    return primary


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    configure_logging(settings.log_level)
    engine = build_engine(settings)
    redis = build_redis(settings)
    provider = _build_provider(settings)
    cascade_provider = CascadeProvider(
        provider,
        cheap_model=settings.cascade_cheap_model,
        expensive_model=settings.cascade_expensive_model,
    )
    app.state.resources = Resources(
        settings=settings,
        engine=engine,
        sessionmaker=build_sessionmaker(engine),
        redis=redis,
        provider=provider,
        cascade_provider=cascade_provider,
        rate_limiter=TokenBucket(redis),
    )
    try:
        yield
    finally:
        await app.state.resources.close()
        app.state.resources = None


app = FastAPI(title="Switchboard", lifespan=lifespan)
app.include_router(health_router)
app.include_router(chat_router)
app.include_router(keys_router)
configure_tracing(app)
#order matters here for these two middleware
app.add_middleware(MetricsMiddleware)
app.add_middleware(TraceIdMiddleware)