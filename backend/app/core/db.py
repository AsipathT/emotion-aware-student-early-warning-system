"""
backend/app/core/db.py

SQLAlchemy 2.0 async engine, session factory, and declarative Base.

Usage
-----
Import `AsyncSessionLocal` as a FastAPI dependency via `get_db()`.
Import `Base` in every model file so Alembic can discover all tables.

    from app.core.db import Base, get_db
"""

from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings

# ── Engine ────────────────────────────────────────────────────────────────────
# pool_pre_ping=True transparently reconnects on stale connections (e.g. after
# the DB container restarts during development).
engine = create_async_engine(
    settings.database_url,
    echo=settings.debug,          # logs all SQL when DEBUG=true
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
)

# ── Session factory ───────────────────────────────────────────────────────────
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,   # keep ORM objects usable after commit
    autocommit=False,
    autoflush=False,
)


# ── Declarative Base ──────────────────────────────────────────────────────────
class Base(DeclarativeBase):
    """
    Single shared declarative base for **all** SQLAlchemy models in this
    project.  Every model module must import this class and subclass it so
    that Alembic's autogenerate can discover the complete schema.

    Example
    -------
    from app.core.db import Base

    class User(Base):
        __tablename__ = "users"
        ...
    """
    pass


# ── FastAPI dependency ────────────────────────────────────────────────────────
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Yield an async database session and guarantee clean-up.

    Inject into route handlers with:
        db: AsyncSession = Depends(get_db)
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
