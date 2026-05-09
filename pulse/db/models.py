"""
Pulse ORM Models — SQLAlchemy 2.0 declarative models.

All models use:
    - `Mapped` / `mapped_column` for type-safe column definitions.
    - `thread_id` indexing for multi-user isolation.
    - UTC timestamps for consistency.

Tables:
    - UserProfile: Registered users, preferences, and auth tokens (Phase 6).
    - Transaction:  Individual expense/income records.
    - Budget:       Monthly budget limits per category.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import Boolean, DateTime, Float, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from pulse.db.database import Base


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _utcnow() -> datetime:
    """Return timezone-aware UTC now."""
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# UserProfile Model (Phase 6 — Multi-Tenant Identity & Preferences)
# ---------------------------------------------------------------------------
class UserProfile(Base):
    """
    A registered Pulse user.

    Created automatically when a user sends /start for the first time.
    Stores personal preferences, scheduling state, and a short-lived
    OTP token used to authenticate dashboard sessions.

    Attributes:
        thread_id:          Telegram user ID — the primary identity key.
        username:           Telegram @handle (updated on each /start).
        full_name:          Display name from Telegram.
        currency:           Preferred currency code (e.g., "INR", "USD").
        wants_briefings:    Whether the user has opted in to scheduled reports.
        briefing_interval:  Days between each briefing (3, 7, or 14).
        last_briefing_at:   UTC timestamp of the last successful briefing sent.
        auth_token:         6-digit OTP for dashboard login (plain, short-lived).
        token_expires_at:   UTC expiry time for the current auth_token.
        joined_at:          UTC timestamp of first /start registration.
    """

    __tablename__ = "user_profiles"

    thread_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    username: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    full_name: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    currency: Mapped[str] = mapped_column(String(8), nullable=False, default="INR")
    wants_briefings: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    briefing_interval: Mapped[int] = mapped_column(Integer, nullable=False, default=7)
    last_briefing_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )
    auth_token: Mapped[Optional[str]] = mapped_column(String(6), nullable=True, default=None)
    token_expires_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )
    joined_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )

    def __repr__(self) -> str:
        return (
            f"<UserProfile(thread_id={self.thread_id!r}, "
            f"username={self.username!r}, currency={self.currency!r}, "
            f"wants_briefings={self.wants_briefings})>"
        )


# ---------------------------------------------------------------------------
# Transaction Model
# ---------------------------------------------------------------------------
class Transaction(Base):
    """
    A single financial transaction recorded by the user.

    Attributes:
        id:             Auto-incrementing primary key.
        thread_id:      Telegram user_id — isolates data per user.
        amount:         Transaction amount in base currency (INR).
        currency:       Currency code (default: INR, ready for multi-currency).
        vendor:         Cleaned vendor/merchant name.
        category:       Expense category (e.g., "Food", "Transport", "Sport").
        timestamp:      UTC timestamp of when the transaction was recorded.
        source_text:    Original raw user input — full auditability trail.
        is_unusual:     Flagged by the Router node if expense seems unusual.
        notes:          Optional user-provided note.
    """

    __tablename__ = "transactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    thread_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    amount: Mapped[float] = mapped_column(Float, nullable=False)
    currency: Mapped[str] = mapped_column(String(8), nullable=False, default="INR")
    vendor: Mapped[str] = mapped_column(String(255), nullable=False)
    category: Mapped[str] = mapped_column(String(64), nullable=False)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
    )
    source_text: Mapped[str] = mapped_column(Text, nullable=False)
    is_unusual: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True, default=None)

    # Composite index for common query patterns
    __table_args__ = (
        Index("ix_transactions_thread_category", "thread_id", "category"),
        Index("ix_transactions_thread_timestamp", "thread_id", "timestamp"),
    )

    def __repr__(self) -> str:
        return (
            f"<Transaction(id={self.id}, thread_id={self.thread_id!r}, "
            f"amount={self.amount}, vendor={self.vendor!r}, "
            f"category={self.category!r})>"
        )


# ---------------------------------------------------------------------------
# Budget Model (Phase 3 — schema defined early for forward compatibility)
# ---------------------------------------------------------------------------
class Budget(Base):
    """
    Monthly budget limit for a specific category.

    Used by the Coach node to detect overspending.
    """

    __tablename__ = "budgets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    thread_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    category: Mapped[str] = mapped_column(String(64), nullable=False)
    monthly_limit: Mapped[float] = mapped_column(Float, nullable=False)
    month: Mapped[str] = mapped_column(String(7), nullable=False)  # "2026-05"

    __table_args__ = (
        Index("ix_budgets_thread_month", "thread_id", "month"),
    )

    def __repr__(self) -> str:
        return (
            f"<Budget(id={self.id}, thread_id={self.thread_id!r}, "
            f"category={self.category!r}, limit={self.monthly_limit})>"
        )
