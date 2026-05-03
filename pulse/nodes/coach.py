"""
Coach Node — Proactive financial insights and anomaly detection.

This node acts independently of the main transaction flow. It is triggered
manually (e.g. via /briefing) or via a cron scheduler. It queries the user's
historical data and provides an LLM-generated briefing.
"""

import logging
from typing import Optional

from langchain_core.messages import SystemMessage, HumanMessage
from langchain_google_genai import ChatGoogleGenerativeAI

from pulse.config import settings
from pulse.db.queries import get_recent_transactions

logger = logging.getLogger(__name__)

# LLM singleton for Coach
_llm = None

def _get_llm() -> ChatGoogleGenerativeAI:
    global _llm
    if _llm is None:
        _llm = ChatGoogleGenerativeAI(
            model=settings.LLM_MODEL_NAME,
            google_api_key=settings.GEMINI_API_KEY,
            temperature=0.4, # slightly higher temp for more conversational insights
            max_retries=1,
        )
    return _llm


_COACH_SYSTEM_PROMPT = """You are Pulse, an elite AI financial coach. Your job is to review a user's recent spending and provide a highly readable, proactive briefing.

You will receive a list of transactions from the last N days.

Your briefing must be written in Markdown and follow this structure:
1. **Summary:** A 1-2 sentence overview of their spending (Total spent, biggest category).
2. **Category Breakdown:** A bulleted list of top spending categories.
3. **Anomalies / Callouts:** Point out anything unusual (e.g., a very large transaction, multiple identical small transactions, or heavy spending in non-essentials). If none, omit this section.
4. **Coach's Tip:** One actionable, friendly piece of financial advice based ONLY on their specific data.

Keep the tone professional but encouraging. Do not hallucinate transactions. Use the currency specified in the data.
"""

async def run_coach(thread_id: str, days: int = 7) -> str:
    """
    Execute the Coach pipeline.
    
    Args:
        thread_id: The Telegram user ID.
        days: Number of days to look back for the briefing.
        
    Returns:
        A Markdown-formatted briefing string from the LLM.
    """
    logger.info("Coach node running for thread_id=%s, days=%d", thread_id, days)
    
    # 1. Fetch data
    transactions = await get_recent_transactions(thread_id, days)
    
    if not transactions:
        return f"I looked at your records for the last {days} days, but you don't have any transactions logged yet. Let's start tracking!"
        
    # 2. Format data for the LLM
    data_context = f"Here are the user's transactions for the last {days} days:\n\n"
    total_spent = 0.0
    for t in transactions:
        total_spent += t.amount
        date_str = t.timestamp.strftime("%Y-%m-%d")
        data_context += f"- {date_str}: {t.currency} {t.amount:.2f} at {t.vendor} (Category: {t.category})\n"
        
    data_context += f"\nTotal Spent: {transactions[0].currency} {total_spent:.2f}"
    
    # 3. Ask the LLM
    try:
        messages = [
            SystemMessage(content=_COACH_SYSTEM_PROMPT),
            HumanMessage(content=data_context)
        ]
        
        response = await _get_llm().ainvoke(messages)
        return response.content.strip()
    except Exception as e:
        logger.error("Coach node error: %s", e, exc_info=True)
        return "I'm having trouble analyzing your data right now. Please try again later."
