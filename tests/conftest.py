import pytest
from httpx import ASGITransport, AsyncClient

from switchboard.core.config import get_settings
from switchboard.db.session import build_engine, build_sessionmaker
from switchboard.main import app


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