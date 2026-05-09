"""
Pulse Database Queries — Reusable SQLAlchemy queries.
"""

import secrets
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from sqlalchemy import select, distinct

from pulse.db.database import get_session
from pulse.db.models import Transaction, UserProfile


# ---------------------------------------------------------------------------
# Transaction Queries
# ---------------------------------------------------------------------------
async def get_recent_transactions(thread_id: str, days: int = 7, limit: int = None) -> List[Transaction]:
    """
    Fetch transactions for a user from the last `days` days.
    """
    cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)
    async with get_session() as session:
        query = (
            select(Transaction)
            .where(Transaction.thread_id == thread_id)
            .where(Transaction.timestamp >= cutoff_date)
            .order_by(Transaction.timestamp.desc())
        )
        if limit:
            query = query.limit(limit)
        result = await session.execute(query)
        return list(result.scalars().all())


async def get_all_user_ids() -> List[str]:
    """
    Retrieve all unique thread_ids from the transactions table.
    Legacy fallback — prefer get_opted_in_profiles() for scheduling.
    """
    async with get_session() as session:
        query = select(distinct(Transaction.thread_id))
        result = await session.execute(query)
        return [str(row[0]) for row in result.all()]


# ---------------------------------------------------------------------------
# UserProfile Queries (Phase 6)
# ---------------------------------------------------------------------------
async def get_or_create_profile(
    thread_id: str,
    username: Optional[str] = None,
    full_name: Optional[str] = None
) -> UserProfile:
    """
    Fetch an existing UserProfile or create a new one on first /start.
    Only updates display info if new values are provided (not None).
    """
    async with get_session() as session:
        result = await session.execute(
            select(UserProfile).where(UserProfile.thread_id == thread_id)
        )
        profile = result.scalar_one_or_none()

        if profile is None:
            profile = UserProfile(
                thread_id=thread_id,
                username=username,
                full_name=full_name,
            )
            session.add(profile)
        else:
            # Only update if we actually received new data
            if username is not None:
                profile.username = username
            if full_name is not None:
                profile.full_name = full_name

        await session.commit()
        await session.refresh(profile)
        return profile


async def get_profile_by_id(thread_id: str) -> Optional[UserProfile]:
    """
    Pure lookup query that never modifies data. 
    Safe for use in settings toggles.
    """
    async with get_session() as session:
        result = await session.execute(
            select(UserProfile).where(UserProfile.thread_id == thread_id)
        )
        return result.scalar_one_or_none()


async def update_profile_settings(
    thread_id: str,
    wants_briefings: Optional[bool] = None,
    briefing_interval: Optional[int] = None,
    currency: Optional[str] = None,
) -> Optional[UserProfile]:
    """
    Update one or more user preference fields.
    Only updates fields that are explicitly passed (not None).
    """
    async with get_session() as session:
        result = await session.execute(
            select(UserProfile).where(UserProfile.thread_id == thread_id)
        )
        profile = result.scalar_one_or_none()
        if not profile:
            return None

        if wants_briefings is not None:
            profile.wants_briefings = wants_briefings
        if briefing_interval is not None:
            profile.briefing_interval = briefing_interval
        if currency is not None:
            profile.currency = currency

        await session.commit()
        await session.refresh(profile)
        return profile


async def mark_briefing_sent(thread_id: str) -> None:
    """
    Record that a briefing was just sent to a user.
    Called immediately after a successful send to update the schedule.
    """
    async with get_session() as session:
        result = await session.execute(
            select(UserProfile).where(UserProfile.thread_id == thread_id)
        )
        profile = result.scalar_one_or_none()
        if profile:
            profile.last_briefing_at = datetime.now(timezone.utc)
            await session.commit()


async def get_opted_in_profiles() -> List[UserProfile]:
    """
    Return all UserProfiles where wants_briefings is True.
    Used by the Smart Briefing Scheduler.
    """
    async with get_session() as session:
        result = await session.execute(
            select(UserProfile).where(UserProfile.wants_briefings == True)  # noqa: E712
        )
        return list(result.scalars().all())


async def generate_dashboard_token(thread_id: str) -> str:
    """
    Generate a cryptographically secure 6-digit OTP for dashboard login.
    Stores it in the UserProfile with a 10-minute expiry.
    Returns the token string to be sent to the user.
    """
    token = str(secrets.randbelow(900000) + 100000)  # always 6 digits: 100000–999999
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=10)

    async with get_session() as session:
        result = await session.execute(
            select(UserProfile).where(UserProfile.thread_id == thread_id)
        )
        profile = result.scalar_one_or_none()
        if not profile:
            return None

        profile.auth_token = token
        profile.token_expires_at = expires_at
        await session.commit()

    return token


async def verify_dashboard_token(thread_id: str, token: str) -> bool:
    """
    Verify a user-submitted OTP against the stored token.
    Returns True only if the token matches and has not expired.
    Clears the token after a successful verification (single-use).
    """
    async with get_session() as session:
        result = await session.execute(
            select(UserProfile).where(UserProfile.thread_id == thread_id)
        )
        profile = result.scalar_one_or_none()

        if not profile or not profile.auth_token or not profile.token_expires_at:
            return False

        now = datetime.now(timezone.utc)
        is_valid = (
            profile.auth_token == token
            and profile.token_expires_at > now
        )

        if is_valid:
            # Consume the token immediately — single use
            profile.auth_token = None
            profile.token_expires_at = None
            await session.commit()

        return is_valid
