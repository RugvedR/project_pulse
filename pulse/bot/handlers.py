"""
Pulse Telegram Handlers — Bridge between Telegram and the LangGraph.

Each handler receives a Telegram Update, prepares the AgentState,
invokes the compiled graph, and sends the response back to the user.

Design:
    - `thread_id` = Telegram user_id (multi-user isolation)
    - Graph config uses the same thread_id for checkpointer persistence
    - All handlers are async (PTB v20+ requirement)
"""

from __future__ import annotations

import logging
from typing import Any

from telegram import Update
from telegram.ext import ContextTypes

from pulse.db.database import init_db
from pulse.graph import get_graph

logger = logging.getLogger(__name__)

# Track whether DB has been initialized
_db_initialized = False


# ---------------------------------------------------------------------------
# /start Command Handler
# ---------------------------------------------------------------------------
async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle the /start command.

    Sends a welcome message explaining what Pulse does and how to use it.
    """
    welcome = (
        "Welcome to Pulse!\n\n"
        "I'm your AI-powered expense tracker. Just tell me about "
        "your expenses in natural language, and I'll handle the rest.\n\n"
        "Examples:\n"
        "  - Spent 450 at the badminton court\n"
        "  - Paid 120 for auto rickshaw\n"
        "  - Coffee at Starbucks for 350\n"
        "  - 2000 groceries at DMart\n\n"
        "I'll parse the amount, vendor, and category, "
        "then save it to your expense tracker.\n\n"
        "Type /help for more commands."
    )
    await update.message.reply_text(welcome)


# ---------------------------------------------------------------------------
# /help Command Handler
# ---------------------------------------------------------------------------
async def help_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /help command with usage instructions."""
    help_text = (
        "Pulse Commands:\n\n"
        "/start  - Welcome message\n"
        "/help   - Show this help\n\n"
        "Usage:\n"
        "Just send me a message describing your expense. "
        "I'll extract the details and save them.\n\n"
        "Supported categories:\n"
        "Food, Transport, Entertainment, Shopping, Bills, "
        "Health, Education, Sport, Groceries, Subscriptions, "
        "Travel, Gifts, Personal, Other"
    )
    await update.message.reply_text(help_text)


# ---------------------------------------------------------------------------
# Message Handler — main expense processing pipeline
# ---------------------------------------------------------------------------
async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle incoming text messages by invoking the LangGraph.

    Flow:
        1. Extract user message and thread_id
        2. Ensure DB tables exist (first-run init)
        3. Prepare initial state for the graph
        4. Invoke the graph with thread_id config
        5. Send the response back to Telegram
    """
    # Guard against empty messages
    if not update.message or not update.message.text:
        return

    user_message = update.message.text.strip()
    user_id = str(update.effective_user.id)

    logger.info("Message from user %s: %s", user_id, user_message[:100])

    # Lazy DB init on first message
    global _db_initialized
    if not _db_initialized:
        await init_db()
        _db_initialized = True
        logger.info("Database initialized on first message")

    try:
        # Prepare the initial state
        initial_state: dict[str, Any] = {
            "raw_input": user_message,
            "thread_id": user_id,
            "parsed_transaction": None,
            "vendor_known": True,
            "needs_hitl": False,
            "hitl_approved": None,
            "vendor_info": None,
            "db_result": "",
            "error_message": None,
            "response_to_user": "",
            "retry_count": 0,
            "messages": [],
        }

        # Config for checkpointer persistence
        config = {"configurable": {"thread_id": user_id}}

        # Invoke the graph
        graph = await get_graph()
        result = await graph.ainvoke(initial_state, config=config)

        # Send the response to the user
        response_text = result.get("response_to_user", "")
        if response_text:
            await update.message.reply_text(response_text)
        else:
            await update.message.reply_text(
                "Something went wrong - I didn't generate a response. Please try again."
            )

    except Exception as e:
        logger.error("Error processing message: %s", e, exc_info=True)
        await update.message.reply_text(
            "Sorry, something went wrong. Please try again in a moment."
        )


# ---------------------------------------------------------------------------
# Error Handler
# ---------------------------------------------------------------------------
async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Log errors from the Telegram bot."""
    logger.error("Telegram error: %s", context.error, exc_info=context.error)
