"""
Pulse Analytics Engine — Data aggregation and trend analysis.

This module provides the logic for summarizing financial data, 
identifying trends, and preparing data for the visual dashboard.
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any

from sqlalchemy import select, func
from pulse.db.database import get_session
from pulse.db.models import Transaction

logger = logging.getLogger(__name__)

async def get_spending_by_category(user_id: str, days: int = 30) -> List[Dict[str, Any]]:
    """
    Returns a summary of spending grouped by category for a given timeframe.
    """
    since_date = datetime.utcnow() - timedelta(days=days)
    
    async with get_session() as session:
        query = (
            select(Transaction.category, func.sum(Transaction.amount).label("total"))
            .where(Transaction.thread_id == user_id)
            .where(Transaction.timestamp >= since_date)
            .group_by(Transaction.category)
            .order_by(func.sum(Transaction.amount).desc())
        )
        
        result = await session.execute(query)
        data = [{"category": row[0], "amount": float(row[1])} for row in result.all()]
        return data

async def get_daily_spending_trends(user_id: str, days: int = 30) -> List[Dict[str, Any]]:
    """
    Returns daily spending totals over time.
    """
    since_date = datetime.utcnow() - timedelta(days=days)
    
    async with get_session() as session:
        # PostgreSQL/SQLite compatible date truncation
        # Note: func.date works for both in this context
        date_label = func.date(Transaction.timestamp).label("date")
        
        query = (
            select(date_label, func.sum(Transaction.amount).label("total"))
            .where(Transaction.thread_id == user_id)
            .where(Transaction.timestamp >= since_date)
            .group_by(date_label)
            .order_by(date_label)
        )
        
        result = await session.execute(query)
        data = [{"date": str(row[0]), "amount": float(row[1])} for row in result.all()]
        return data

async def get_kpi_metrics(user_id: str) -> Dict[str, Any]:
    """
    Calculates key performance indicators for the current month.
    """
    now = datetime.utcnow()
    first_of_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    
    async with get_session() as session:
        # Total this month
        total_query = select(func.sum(Transaction.amount)).where(
            Transaction.thread_id == user_id,
            Transaction.timestamp >= first_of_month
        )
        total_result = await session.execute(total_query)
        total_month = float(total_result.scalar() or 0.0)
        
        # Transaction count
        count_query = select(func.count(Transaction.id)).where(
            Transaction.thread_id == user_id,
            Transaction.timestamp >= first_of_month
        )
        count_result = await session.execute(count_query)
        tx_count = int(count_result.scalar() or 0)
        
        # Top category
        cat_query = (
            select(Transaction.category)
            .where(Transaction.thread_id == user_id, Transaction.timestamp >= first_of_month)
            .group_by(Transaction.category)
            .order_by(func.sum(Transaction.amount).desc())
            .limit(1)
        )
        cat_result = await session.execute(cat_query)
        top_cat = cat_result.scalar() or "N/A"
        
        return {
            "total_spent_month": total_month,
            "transaction_count": tx_count,
            "top_category": top_cat,
            "days_in_month": (now - first_of_month).days + 1
        }
