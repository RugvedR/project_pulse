"""
Pulse MCP Server — Model Context Protocol integration.

This module exposes Pulse's core features (database access, web search)
as standard MCP tools. This allows any MCP-compatible AI client
(like Claude Desktop or custom agents) to seamlessly use Pulse.

Usage:
    python -m pulse.mcp_server
"""

import asyncio
import logging
from typing import List, Dict, Any, Optional

from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel

from pulse.db.crud import create_transaction
from pulse.db.database import get_session
from pulse.db.queries import get_recent_transactions
from pulse.tools.search import get_search_provider, SearchQueryInput
from pulse.config import settings

logger = logging.getLogger(__name__)

# Initialize FastMCP Server
mcp = FastMCP("Pulse-MCP", dependencies=["langchain-google-genai", "duckduckgo-search", "sqlalchemy", "aiosqlite"])

@mcp.tool()
async def add_transaction(
    thread_id: str,
    amount: float,
    vendor: str,
    category: str,
    source_text: str,
    currency: str = "INR",
    notes: str = ""
) -> str:
    """
    Save a new financial transaction to the user's database.

    Args:
        thread_id: The unique identifier for the user.
        amount: The monetary amount of the transaction.
        vendor: The merchant or service provider name.
        category: The expense category (e.g., Food, Transport).
        source_text: A description or the original text input.
        currency: The currency code (default INR).
        notes: Optional extra context.
    """
    logger.info("MCP Tool [add_transaction] called for thread=%s", thread_id)
    try:
        async with get_session() as session:
            txn = await create_transaction(
                session=session,
                thread_id=thread_id,
                amount=amount,
                vendor=vendor,
                category=category,
                source_text=source_text,
                currency=currency,
                notes=notes if notes else None,
            )
            # Explicitly commit since the transaction context manager usually does it on successful exit,
            # but we want to ensure it's saved. get_session() yields an AsyncSession.
            await session.commit()
            return f"Transaction {txn.id} successfully saved."
    except Exception as e:
        logger.error("MCP Tool [add_transaction] error: %s", e)
        return f"Error saving transaction: {str(e)}"

@mcp.tool()
async def get_transactions(thread_id: str, days: int = 7) -> str:
    """
    Retrieve the user's recent financial transactions.

    Args:
        thread_id: The unique identifier for the user.
        days: Number of days to look back (default 7).
    """
    logger.info("MCP Tool [get_transactions] called for thread=%s", thread_id)
    try:
        transactions = await get_recent_transactions(thread_id, days)
        if not transactions:
            return f"No transactions found in the last {days} days."
            
        result = [f"Transactions for the last {days} days:"]
        for t in transactions:
            date_str = t.timestamp.strftime("%Y-%m-%d %H:%M")
            result.append(f"[{date_str}] {t.currency} {t.amount} at {t.vendor} ({t.category})")
            if t.notes:
                result.append(f"  Notes: {t.notes}")
                
        return "\n".join(result)
    except Exception as e:
        logger.error("MCP Tool [get_transactions] error: %s", e)
        return f"Error retrieving transactions: {str(e)}"

@mcp.tool()
async def search_web(query: str, max_results: int = 3) -> str:
    """
    Search the internet for information, especially useful for identifying unknown vendors.

    Args:
        query: The search query string.
        max_results: Maximum number of results to return (default 3).
    """
    logger.info("MCP Tool [search_web] called with query: %s", query)
    try:
        provider = get_search_provider(settings.SEARCH_PROVIDER)
        search_input = SearchQueryInput(query=query, max_results=max_results)
        results = await provider.search(search_input)
        
        if not results:
            return "No results found."
            
        output = []
        for r in results:
            output.append(f"Title: {r['title']}\nLink: {r['link']}\nSnippet: {r['snippet']}\n")
            
        return "\n".join(output)
    except Exception as e:
        logger.error("MCP Tool [search_web] error: %s", e)
        return f"Error searching the web: {str(e)}"

if __name__ == "__main__":
    # Run the MCP server over standard input/output
    logging.basicConfig(level=logging.INFO)
    logger.info("Starting Pulse MCP Server on stdio...")
    mcp.run(transport='stdio')
