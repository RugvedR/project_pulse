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
from pulse.nodes.vault import vault_node
from pulse.state import AgentState

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
def _should_save(state: dict) -> str:
    """
    Routing function after Scribe.

    If the Scribe successfully parsed a transaction, proceed to Vault.
    Otherwise, go to END (the error message is already in response_to_user).
    """
    if state.get("parsed_transaction") is not None:
        return "vault"
    return END


def build_graph() -> StateGraph:
    """
    Construct the Phase 1 LangGraph.

    Graph structure:
        START → scribe → (parsed?) → vault → END
                             ↓
                            END (parse error)
    """
    graph = StateGraph(AgentState)

    # Add nodes
    graph.add_node("scribe", scribe_node)
    graph.add_node("vault", vault_node)

    # Define edges
    graph.set_entry_point("scribe")
    graph.add_conditional_edges("scribe", _should_save, {"vault": "vault", END: END})
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
        _compiled_graph = builder.compile(checkpointer=checkpointer)
        logger.info("LangGraph compiled with AsyncSqliteSaver checkpointer")
    return _compiled_graph
