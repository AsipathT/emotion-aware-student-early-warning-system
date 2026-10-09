import asyncio
import os
import pytest
from typing import AsyncGenerator
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text

# Assuming lms_postgres is accessible
TEST_DB_URL = "postgresql+asyncpg://lms_user:changeme_strong_password@db:5432/lms_test"
SYNC_TEST_DB_URL = "postgresql://lms_user:changeme_strong_password@db:5432/lms_test"

os.environ["DATABASE_URL"] = TEST_DB_URL
import pytest_asyncio
from app.main import app
from app.core.db import Base

@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"

def setup_db_sync():
    async def _setup():
        sys_engine = create_async_engine("postgresql+asyncpg://lms_user:changeme_strong_password@db:5432/postgres", isolation_level="AUTOCOMMIT")
        async with sys_engine.connect() as conn:
            await conn.execute(text("DROP DATABASE IF EXISTS lms_test (FORCE);"))
            await conn.execute(text("CREATE DATABASE lms_test;"))
        await sys_engine.dispose()
        
        engine = create_async_engine(TEST_DB_URL)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        await engine.dispose()
    asyncio.run(_setup())

def teardown_db_sync():
    async def _teardown():
        sys_engine = create_async_engine("postgresql+asyncpg://lms_user:changeme_strong_password@db:5432/postgres", isolation_level="AUTOCOMMIT")
        async with sys_engine.connect() as conn:
            await conn.execute(text("DROP DATABASE IF EXISTS lms_test (FORCE);"))
        await sys_engine.dispose()
    asyncio.run(_teardown())

@pytest_asyncio.fixture(scope="function", autouse=True)
def setup_test_database():
    setup_db_sync()
    yield
    teardown_db_sync()
@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    engine = create_async_engine(TEST_DB_URL)
    SessionLocal = sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    async with SessionLocal() as session:
        yield session
    await engine.dispose()

@pytest_asyncio.fixture
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    async def override_get_db():
        yield db_session
        
    from app.core.db import get_db
    app.dependency_overrides[get_db] = override_get_db
    
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
        
    app.dependency_overrides.clear()
