"""
Pulse Database Queries — Reusable SQLAlchemy queries.
"""

from datetime import datetime, timedelta, timezone
from typing import List

from sqlalchemy import select

from pulse.db.database import get_session
from pulse.db.models import Transaction

async def get_recent_transactions(thread_id: str, days: int = 7) -> List[Transaction]:
    """
    Fetch all transactions for a specific user from the last `days` days.
    
    Args:
        thread_id: Telegram user ID.
        days: Number of days to look back.
        
    Returns:
        List of Transaction objects.
    """
    cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)
    
    async with get_session() as session:
        query = (
            select(Transaction)
            .where(Transaction.thread_id == thread_id)
            .where(Transaction.timestamp >= cutoff_date)
            .order_by(Transaction.timestamp.asc())
        )
        
        result = await session.execute(query)
        # result.scalars().all() returns a list of Transaction ORM objects
        return list(result.scalars().all())

async def get_all_user_ids() -> List[str]:
    """
    Retrieve all unique thread_ids (user IDs) from the database.
    Used for background broadcast jobs like weekly briefings.
    """
    async with get_session() as session:
        # Use select(Transaction.thread_id).distinct()
        from sqlalchemy import distinct
        query = select(distinct(Transaction.thread_id))
        result = await session.execute(query)
        return [str(row[0]) for row in result.all()]
