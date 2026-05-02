"""
Pulse Agent State — The single source of truth for the LangGraph.

This TypedDict defines every piece of data that flows between nodes.
Each node reads from and writes to this state. The graph framework
manages state persistence via the checkpointer.

Design principles:
    - Every field has a clear owner (which node writes it).
    - `thread_id` is always present — multi-user from Day 1.
    - `messages` uses `add_messages` reducer for LLM conversation history.
"""

from __future__ import annotations

from typing import Annotated, List, Optional

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages

from pulse.schemas.transaction import TransactionInput


class AgentState(dict):
    """
    State schema for the Pulse LangGraph.

    Fields are grouped by which node primarily writes them.
    All nodes can read any field.

    Attributes:
        thread_id:           Telegram user_id — persistence & isolation key.
        raw_input:           Original message text from the user.

        parsed_transaction:  Structured output from the Scribe node.

        vendor_known:        Whether the Router recognized the vendor.
        needs_hitl:          Whether the expense requires human approval.
        hitl_approved:       User's HITL decision (None = pending).

        vendor_info:         Web search result from the Investigator node.

        db_result:           Outcome of the Vault node DB write.
        error_message:       Error detail for self-correction.
        response_to_user:    Final message to send back via Telegram.

        retry_count:         Number of Scribe→Vault retries attempted.
        messages:            LLM conversation history (append-only via add_messages).
    """

    # ── Core Input (set by bot handler) ───────────────────────────────────
    thread_id: str
    raw_input: str

    # ── Scribe Output ─────────────────────────────────────────────────────
    parsed_transaction: Optional[TransactionInput]

    # ── Router Signals ────────────────────────────────────────────────────
    vendor_known: bool
    needs_hitl: bool
    hitl_approved: Optional[bool]

    # ── Investigator Output ───────────────────────────────────────────────
    vendor_info: Optional[str]

    # ── Vault Output ──────────────────────────────────────────────────────
    db_result: str
    error_message: Optional[str]
    response_to_user: str

    # ── Loop Control ──────────────────────────────────────────────────────
    retry_count: int
    messages: Annotated[List[BaseMessage], add_messages]
