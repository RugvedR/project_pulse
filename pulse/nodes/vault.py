"""
Vault Node — Writes validated transactions to the database.

The Vault is the final action node in the Phase 1 graph. It takes
the validated `parsed_transaction` from state and persists it to SQLite
via the CRUD layer.

Input:  `parsed_transaction` (TransactionInput) — validated by Scribe
        `thread_id` (str) — Telegram user_id
        `raw_input` (str) — original text for `source_text` auditability
Output: `db_result` (str) — "success" or "error: <reason>"
        `response_to_user` (str) — confirmation or error message
"""

from __future__ import annotations

import logging
from typing import Any, Dict

from pulse.db.crud import create_transaction
from pulse.db.database import get_session
from pulse.schemas.transaction import TransactionInput

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Node Function
# ---------------------------------------------------------------------------
async def vault_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Persist a validated transaction to the database.

    Args:
        state: Current AgentState dict.

    Returns:
        Partial state update with:
        - db_result: "success" or "error: <reason>"
        - response_to_user: user-friendly confirmation or error message
        - retry_count: incremented on error
    """
    parsed = state.get("parsed_transaction")
    thread_id = state.get("thread_id", "")
    raw_input = state.get("raw_input", "")
    retry_count = state.get("retry_count", 0)

    # Guard: no transaction to save
    if parsed is None:
        logger.warning("Vault called with no parsed_transaction")
        return {
            "db_result": "error: no transaction data",
            "response_to_user": state.get("response_to_user", "No transaction to save."),
        }

    # Ensure parsed is a TransactionInput instance
    if isinstance(parsed, dict):
        parsed = TransactionInput(**parsed)

    try:
        async with get_session() as session:
            txn = await create_transaction(
                session,
                thread_id=thread_id,
                amount=parsed.amount,
                currency=parsed.currency,
                vendor=parsed.vendor,
                category=parsed.category,
                source_text=raw_input,
                is_unusual=state.get("needs_hitl", False),
                notes=parsed.notes,
            )

        # Build confirmation message
        confirmation = (
            f"Saved! {parsed.currency} {parsed.amount:.2f} "
            f"at {parsed.vendor} [{parsed.category}]"
        )

        logger.info(
            "Vault saved transaction id=%s for thread=%s: %s %s at %s",
            txn.id, thread_id, parsed.currency, parsed.amount, parsed.vendor,
        )

        return {
            "db_result": "success",
            "response_to_user": confirmation,
        }

    except Exception as e:
        new_retry = retry_count + 1
        logger.error(
            "Vault DB error (retry %d): %s", new_retry, e, exc_info=True,
        )

        return {
            "db_result": f"error: {str(e)}",
            "error_message": str(e),
            "response_to_user": "Sorry, I couldn't save that transaction. Please try again.",
            "retry_count": new_retry,
        }
