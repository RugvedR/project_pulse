"""
Pulse Graph — LangGraph StateGraph assembly and compilation.

This module wires together the LangGraph nodes, defines edges,
and compiles the graph with a persistent checkpointer.

Phase 1: Linear graph — Scribe → Vault
Phase 2: Will add Router, Investigator, and conditional edges.

Usage:
    from pulse.graph import get_graph

    graph = get_graph()
    result = await graph.ainvoke(
        {"raw_input": "Spent 450 at badminton", "thread_id": "user123"},
        config={"configurable": {"thread_id": "user123"}},
    )
"""

from __future__ import annotations

import logging
from typing import Optional

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, StateGraph

from pulse.config import settings
from pulse.nodes.scribe import scribe_node
from pulse.nodes.investigator import investigator_node
from pulse.nodes.vault import vault_node
from pulse.state import AgentState
import pulse.schemas.transaction # Register for checkpoint serialization

logger = logging.getLogger(__name__)


import aiosqlite
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

_checkpointer: Optional[AsyncSqliteSaver] = None
_sqlite_conn: Optional[aiosqlite.Connection] = None

async def get_checkpointer() -> AsyncSqliteSaver:
    """
    Get or create the LangGraph checkpointer asynchronously.

    Currently uses AsyncSqliteSaver for local development.
    To upgrade to Postgres/Redis in Phase 4, change this function only.

    Returns:
        An AsyncSqliteSaver instance connected to the configured checkpoint DB.
    """
    global _checkpointer, _sqlite_conn
    if _checkpointer is None:
        _sqlite_conn = await aiosqlite.connect(settings.CHECKPOINT_DB_PATH, check_same_thread=False)
        
        # Monkey-patch is_alive to satisfy LangGraph's AsyncSqliteSaver setup check
        if not hasattr(_sqlite_conn, "is_alive"):
            _sqlite_conn.is_alive = lambda: True
            
        _checkpointer = AsyncSqliteSaver(_sqlite_conn)
        await _checkpointer.setup()
    return _checkpointer


# ---------------------------------------------------------------------------
# Graph Builder
# ---------------------------------------------------------------------------
def _route_after_scribe(state: dict) -> str:
    """Route based on Scribe's output."""
    parsed = state.get("parsed_transaction")
    if not parsed:
        logger.info("Routing from Scribe -> END (no parsed transaction)")
        return END
        
    if parsed.needs_research:
        logger.info(f"Routing from Scribe -> investigator (needs_research=True)")
        return "investigator"
        
    if parsed.amount >= settings.LARGE_EXPENSE_THRESHOLD:
        logger.info(f"Routing from Scribe -> hitl_node (amount {parsed.amount} >= {settings.LARGE_EXPENSE_THRESHOLD})")
        return "hitl_node"
        
    logger.info(f"Routing from Scribe -> vault (amount {parsed.amount} < {settings.LARGE_EXPENSE_THRESHOLD})")
    return "vault"

def _route_after_investigator(state: dict) -> str:
    """Route after research."""
    parsed = state.get("parsed_transaction")
    if parsed and parsed.amount >= settings.LARGE_EXPENSE_THRESHOLD:
        logger.info(f"Routing from Investigator -> hitl_node (amount {parsed.amount} >= {settings.LARGE_EXPENSE_THRESHOLD})")
        return "hitl_node"
    logger.info("Routing from Investigator -> vault")
    return "vault"

async def hitl_node(state: dict) -> dict:
    """
    Dummy node for Human-in-the-Loop.
    We pause the graph *before* this node runs.
    When resumed, it passes through to Vault.
    """
    return {"needs_hitl": True}

def build_graph() -> StateGraph:
    """Construct the Phase 2 LangGraph."""
    graph = StateGraph(AgentState)

    # Add nodes
    graph.add_node("scribe", scribe_node)
    graph.add_node("investigator", investigator_node)
    graph.add_node("hitl_node", hitl_node)
    graph.add_node("vault", vault_node)

    # Define edges
    graph.set_entry_point("scribe")
    
    # After scribe, conditional route
    graph.add_conditional_edges(
        "scribe", 
        _route_after_scribe, 
        {"investigator": "investigator", "hitl_node": "hitl_node", "vault": "vault", END: END}
    )
    
    # After investigator, check if large expense
    graph.add_conditional_edges(
        "investigator",
        _route_after_investigator,
        {"hitl_node": "hitl_node", "vault": "vault"}
    )
    
    # HITL goes to Vault
    graph.add_edge("hitl_node", "vault")
    graph.add_edge("vault", END)

    return graph


# ---------------------------------------------------------------------------
# Compiled Graph — ready to invoke
# ---------------------------------------------------------------------------
_compiled_graph = None


async def get_graph():
    """
    Get the compiled, checkpointed LangGraph.

    The graph is compiled once and cached for reuse.

    Returns:
        Compiled graph ready for `ainvoke()` or `astream()`.
    """
    global _compiled_graph
    if _compiled_graph is None:
        checkpointer = await get_checkpointer()
        builder = build_graph()
        _compiled_graph = builder.compile(checkpointer=checkpointer, interrupt_before=["hitl_node"])
        logger.info("LangGraph compiled with AsyncSqliteSaver and HITL interrupts")
    return _compiled_graph
