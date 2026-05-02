"""
Pulse CRUD Operations — Async database access layer.

All functions accept `thread_id` as a required parameter to enforce
multi-user isolation. No function ever operates across users.

Usage:
    from pulse.db.crud import create_transaction, get_transactions
    from pulse.db.database import get_session

    async with get_session() as session:
        txn = await create_transaction(session, thread_id="123", ...)
        all_txns = await get_transactions(session, thread_id="123")
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from pulse.db.models import Transaction


# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------
async def create_transaction(
    session: AsyncSession,
    *,
    thread_id: str,
    amount: float,
    vendor: str,
    category: str,
    source_text: str,
    currency: str = "INR",
    is_unusual: bool = False,
    notes: Optional[str] = None,
) -> Transaction:
    """
    Insert a new transaction into the database.

    Args:
        session:     Active async session (managed by get_session context).
        thread_id:   Telegram user ID — per-user isolation.
        amount:      Transaction amount.
        vendor:      Vendor/merchant name.
        category:    Expense category.
        source_text: Original user input text (for auditability).
        currency:    Currency code (default: "INR").
        is_unusual:  Whether the expense was flagged as unusual.
        notes:       Optional user note.

    Returns:
        The created Transaction ORM instance with populated `id`.
    """
    txn = Transaction(
        thread_id=thread_id,
        amount=amount,
        currency=currency,
        vendor=vendor,
        category=category,
        source_text=source_text,
        is_unusual=is_unusual,
        notes=notes,
    )
    session.add(txn)
    await session.flush()  # Populates txn.id without committing
    return txn


# ---------------------------------------------------------------------------
# Read — By Thread
# ---------------------------------------------------------------------------
async def get_transactions(
    session: AsyncSession,
    *,
    thread_id: str,
    limit: int = 50,
) -> List[Transaction]:
    """
    Retrieve transactions for a user, most recent first.

    Args:
        session:   Active async session.
        thread_id: Telegram user ID.
        limit:     Max number of records to return.

    Returns:
        List of Transaction objects ordered by timestamp descending.
    """
    stmt = (
        select(Transaction)
        .where(Transaction.thread_id == thread_id)
        .order_by(Transaction.timestamp.desc())
        .limit(limit)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


# ---------------------------------------------------------------------------
# Read — By ID (with thread_id guard)
# ---------------------------------------------------------------------------
async def get_transaction_by_id(
    session: AsyncSession,
    *,
    thread_id: str,
    transaction_id: int,
) -> Optional[Transaction]:
    """
    Retrieve a single transaction by ID, scoped to a user.

    Args:
        session:        Active async session.
        thread_id:      Telegram user ID (prevents cross-user access).
        transaction_id: The transaction's primary key.

    Returns:
        Transaction if found, None otherwise.
    """
    stmt = select(Transaction).where(
        Transaction.id == transaction_id,
        Transaction.thread_id == thread_id,
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


# ---------------------------------------------------------------------------
# Read — By Date Range
# ---------------------------------------------------------------------------
async def get_transactions_in_range(
    session: AsyncSession,
    *,
    thread_id: str,
    start: datetime,
    end: datetime,
) -> List[Transaction]:
    """
    Retrieve transactions within a date range for a user.

    Used by the Coach node for weekly/monthly analysis.

    Args:
        session:   Active async session.
        thread_id: Telegram user ID.
        start:     Start of range (inclusive, UTC).
        end:       End of range (inclusive, UTC).

    Returns:
        List of Transaction objects within the range.
    """
    # Ensure timestamps are UTC-aware
    if start.tzinfo is None:
        start = start.replace(tzinfo=timezone.utc)
    if end.tzinfo is None:
        end = end.replace(tzinfo=timezone.utc)

    stmt = (
        select(Transaction)
        .where(
            Transaction.thread_id == thread_id,
            Transaction.timestamp >= start,
            Transaction.timestamp <= end,
        )
        .order_by(Transaction.timestamp.asc())
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


# ---------------------------------------------------------------------------
# Update
# ---------------------------------------------------------------------------
async def update_transaction(
    session: AsyncSession,
    *,
    thread_id: str,
    transaction_id: int,
    **fields,
) -> Optional[Transaction]:
    """
    Update specific fields on a transaction.

    Only fields passed as keyword arguments are updated.
    Silently ignores unknown field names.

    Args:
        session:        Active async session.
        thread_id:      Telegram user ID.
        transaction_id: The transaction's primary key.
        **fields:       Column names and their new values.

    Returns:
        Updated Transaction if found, None otherwise.
    """
    txn = await get_transaction_by_id(
        session, thread_id=thread_id, transaction_id=transaction_id
    )
    if txn is None:
        return None

    valid_columns = {c.key for c in Transaction.__table__.columns}
    for key, value in fields.items():
        if key in valid_columns and key not in ("id", "thread_id"):
            setattr(txn, key, value)

    await session.flush()
    return txn
