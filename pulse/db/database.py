"""
Pulse Database Engine — Async SQLAlchemy 2.0 setup.

Provides:
    - `engine`: Async engine connected to the configured SQLite database.
    - `async_session_factory`: Session factory for creating async sessions.
    - `Base`: Declarative base class for all ORM models.
    - `init_db()`: Creates all tables on first run.
    - `get_session()`: Async context manager for session lifecycle.

Usage:
    from pulse.db.database import get_session, init_db

    async def example():
        await init_db()
        async with get_session() as session:
            # ... use session ...
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from pulse.config import settings


# ---------------------------------------------------------------------------
# Declarative Base
# ---------------------------------------------------------------------------
class Base(DeclarativeBase):
    """Base class for all ORM models."""
    pass


# ---------------------------------------------------------------------------
# Engine — single instance, shared across the application
# ---------------------------------------------------------------------------
engine: AsyncEngine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,                   # Set True for SQL debugging
    future=True,
    # Supabase/PgBouncer requirement: disable prepared statements
    connect_args={
        "statement_cache_size": 0,
        "prepared_statement_cache_size": 0,
    }
)


# ---------------------------------------------------------------------------
# Session Factory
# ---------------------------------------------------------------------------
async_session_factory: async_sessionmaker[AsyncSession] = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,       # Critical for async — avoids MissingGreenlet
)


# ---------------------------------------------------------------------------
# Database Initialization
# ---------------------------------------------------------------------------
async def init_db() -> None:
    """
    Create all tables defined by ORM models.

    Safe to call multiple times — uses CREATE TABLE IF NOT EXISTS.
    Import models BEFORE calling this to ensure they're registered with Base.
    """
    # Import models so they register with Base.metadata
    import pulse.db.models  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


# ---------------------------------------------------------------------------
# Session Context Manager
# ---------------------------------------------------------------------------
@asynccontextmanager
async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Provide a transactional scope around a series of operations.

    Usage:
        async with get_session() as session:
            result = await session.execute(select(Transaction))
    """
    session = async_session_factory()
    try:
        yield session
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()
