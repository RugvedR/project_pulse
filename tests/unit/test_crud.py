"""
Unit tests for pulse.db.crud — Database CRUD operations.

Tests run against an in-memory SQLite database to avoid polluting
the real database. Each test gets a fresh database.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import AsyncGenerator

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from pulse.db.database import Base
from pulse.db.models import Transaction  # noqa: F401 — register model
from pulse.db.crud import (
    create_transaction,
    get_transaction_by_id,
    get_transactions,
    get_transactions_in_range,
    update_transaction,
)


# ---------------------------------------------------------------------------
# Fixtures — fresh in-memory DB for each test
# ---------------------------------------------------------------------------
@pytest_asyncio.fixture
async def session() -> AsyncGenerator[AsyncSession, None]:
    """Create a fresh in-memory SQLite database and yield a session."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(
        bind=engine, class_=AsyncSession, expire_on_commit=False
    )

    async with session_factory() as session:
        yield session

    await engine.dispose()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------
class TestCreateTransaction:
    """Tests for create_transaction."""

    @pytest.mark.asyncio
    async def test_creates_transaction_with_all_fields(self, session: AsyncSession):
        txn = await create_transaction(
            session,
            thread_id="user_1",
            amount=450.0,
            vendor="Badminton Court",
            category="Sport",
            source_text="Spent 450 at the badminton court",
        )

        assert txn.id is not None
        assert txn.thread_id == "user_1"
        assert txn.amount == 450.0
        assert txn.currency == "INR"
        assert txn.vendor == "Badminton Court"
        assert txn.category == "Sport"
        assert txn.source_text == "Spent 450 at the badminton court"
        assert txn.is_unusual is False
        assert txn.notes is None
        assert txn.timestamp is not None

    @pytest.mark.asyncio
    async def test_creates_with_custom_currency_and_notes(self, session: AsyncSession):
        txn = await create_transaction(
            session,
            thread_id="user_2",
            amount=10.0,
            vendor="Starbucks",
            category="Food",
            source_text="Coffee 10 USD",
            currency="USD",
            notes="Iced latte",
        )

        assert txn.currency == "USD"
        assert txn.notes == "Iced latte"

    @pytest.mark.asyncio
    async def test_creates_unusual_transaction(self, session: AsyncSession):
        txn = await create_transaction(
            session,
            thread_id="user_1",
            amount=50000.0,
            vendor="Apple Store",
            category="Shopping",
            source_text="Bought a MacBook for 50000",
            is_unusual=True,
        )

        assert txn.is_unusual is True


class TestGetTransactions:
    """Tests for get_transactions (multi-user isolation)."""

    @pytest.mark.asyncio
    async def test_returns_only_users_transactions(self, session: AsyncSession):
        # Create transactions for two users
        await create_transaction(
            session, thread_id="user_A", amount=100,
            vendor="V1", category="Food", source_text="t1",
        )
        await create_transaction(
            session, thread_id="user_B", amount=200,
            vendor="V2", category="Transport", source_text="t2",
        )
        await create_transaction(
            session, thread_id="user_A", amount=300,
            vendor="V3", category="Bills", source_text="t3",
        )

        user_a_txns = await get_transactions(session, thread_id="user_A")
        user_b_txns = await get_transactions(session, thread_id="user_B")

        assert len(user_a_txns) == 2
        assert len(user_b_txns) == 1
        assert all(t.thread_id == "user_A" for t in user_a_txns)
        assert user_b_txns[0].thread_id == "user_B"

    @pytest.mark.asyncio
    async def test_returns_most_recent_first(self, session: AsyncSession):
        await create_transaction(
            session, thread_id="user_1", amount=100,
            vendor="First", category="Food", source_text="t1",
        )
        await create_transaction(
            session, thread_id="user_1", amount=200,
            vendor="Second", category="Food", source_text="t2",
        )

        txns = await get_transactions(session, thread_id="user_1")
        assert txns[0].vendor == "Second"  # Most recent first
        assert txns[1].vendor == "First"

    @pytest.mark.asyncio
    async def test_respects_limit(self, session: AsyncSession):
        for i in range(5):
            await create_transaction(
                session, thread_id="user_1", amount=float(i),
                vendor=f"V{i}", category="Food", source_text=f"t{i}",
            )

        txns = await get_transactions(session, thread_id="user_1", limit=3)
        assert len(txns) == 3

    @pytest.mark.asyncio
    async def test_empty_for_unknown_user(self, session: AsyncSession):
        txns = await get_transactions(session, thread_id="nobody")
        assert len(txns) == 0


class TestGetTransactionById:
    """Tests for get_transaction_by_id (with thread_id guard)."""

    @pytest.mark.asyncio
    async def test_finds_own_transaction(self, session: AsyncSession):
        created = await create_transaction(
            session, thread_id="user_1", amount=100,
            vendor="Test", category="Food", source_text="t1",
        )

        found = await get_transaction_by_id(
            session, thread_id="user_1", transaction_id=created.id
        )

        assert found is not None
        assert found.id == created.id

    @pytest.mark.asyncio
    async def test_cannot_access_other_users_transaction(self, session: AsyncSession):
        created = await create_transaction(
            session, thread_id="user_1", amount=100,
            vendor="Test", category="Food", source_text="t1",
        )

        found = await get_transaction_by_id(
            session, thread_id="user_2", transaction_id=created.id
        )

        assert found is None  # Cross-user access blocked


class TestUpdateTransaction:
    """Tests for update_transaction."""

    @pytest.mark.asyncio
    async def test_updates_amount(self, session: AsyncSession):
        created = await create_transaction(
            session, thread_id="user_1", amount=100,
            vendor="Test", category="Food", source_text="t1",
        )

        updated = await update_transaction(
            session, thread_id="user_1", transaction_id=created.id,
            amount=500.0,
        )

        assert updated is not None
        assert updated.amount == 500.0

    @pytest.mark.asyncio
    async def test_cannot_update_thread_id(self, session: AsyncSession):
        created = await create_transaction(
            session, thread_id="user_1", amount=100,
            vendor="Test", category="Food", source_text="t1",
        )

        updated = await update_transaction(
            session, thread_id="user_1", transaction_id=created.id,
            thread_id_new="hacker",  # Should be ignored
        )

        assert updated is not None
        assert updated.thread_id == "user_1"

    @pytest.mark.asyncio
    async def test_returns_none_for_wrong_user(self, session: AsyncSession):
        created = await create_transaction(
            session, thread_id="user_1", amount=100,
            vendor="Test", category="Food", source_text="t1",
        )

        result = await update_transaction(
            session, thread_id="user_2", transaction_id=created.id,
            amount=999,
        )

        assert result is None
