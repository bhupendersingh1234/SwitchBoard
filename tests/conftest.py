import pytest
from httpx import ASGITransport, AsyncClient

from switchboard.core.config import get_settings
from switchboard.db.session import build_engine, build_sessionmaker
from switchboard.main import app
from switchboard.cache.redis import build_redis
from switchboard.core.config import get_settings


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.fixture
async def live_client():
    transport = ASGITransport(app=app)
    async with (
        app.router.lifespan_context(app),
        AsyncClient(transport=transport, base_url="http://test") as c,
    ):
        yield c


@pytest.fixture
async def db_session():
    engine = build_engine(get_settings())
    sessionmaker = build_sessionmaker(engine)
    async with sessionmaker() as session:
        yield session
        await session.rollback()
    await engine.dispose()


@pytest.fixture
async def redis():
    r = build_redis(get_settings())
    yield r
    await r.flushdb()
    await r.aclose()