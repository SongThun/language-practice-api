import uuid
from collections.abc import AsyncGenerator

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.base import Base
from app.db.session import get_db
from app.dependencies import get_current_user
from app.main import app

# Import all models so tables are registered
from app.models import *  # noqa: F401, F403

# Use SQLite for tests -- no PostgreSQL required
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

test_engine = create_async_engine(TEST_DATABASE_URL, echo=False)
test_session_factory = async_sessionmaker(
    test_engine, class_=AsyncSession, expire_on_commit=False
)

TEST_USER_ID = uuid.UUID("12345678-1234-1234-1234-123456789abc")


@pytest_asyncio.fixture(scope="session")
async def setup_database():
    """Create all tables at the start of the test session, drop at the end."""
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await test_engine.dispose()


@pytest_asyncio.fixture
async def db_session(setup_database) -> AsyncGenerator[AsyncSession, None]:
    """Provide a database session that rolls back after each test.

    Uses a nested transaction (SAVEPOINT) so that the outer connection
    can be reused across tests while each test's changes are rolled back.
    """
    async with test_engine.connect() as conn:
        trans = await conn.begin()
        session = AsyncSession(bind=conn, expire_on_commit=False)

        # Make session.begin() use SAVEPOINTs instead of real transactions
        # so our outer transaction stays intact
        @event.listens_for(session.sync_session, "after_transaction_end")
        def restart_savepoint(s, transaction):
            if transaction.nested and not transaction._parent.nested:
                s.begin_nested()

        yield session

        await session.close()
        await trans.rollback()


@pytest_asyncio.fixture
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """Provide an async HTTP client with auth and DB overrides."""

    async def _override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    async def _override_get_current_user() -> uuid.UUID:
        return TEST_USER_ID

    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_current_user] = _override_get_current_user

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac

    app.dependency_overrides.clear()
