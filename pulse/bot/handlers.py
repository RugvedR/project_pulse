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

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from pulse.db.database import init_db
from pulse.graph import get_graph
from pulse.nodes.coach import run_coach

logger = logging.getLogger(__name__)

# Track whether DB has been initialized
_db_initialized = False


# ---------------------------------------------------------------------------
# /start Command Handler
# ---------------------------------------------------------------------------
async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
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
# /briefing Command Handler
# ---------------------------------------------------------------------------
async def briefing_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle the /briefing command to generate a proactive financial summary.
    Usage: /briefing [days] (defaults to 7)
    """
    user_id = str(update.effective_user.id)
    
    # Parse days argument if provided
    days = 7
    if context.args:
        try:
            days = int(context.args[0])
            if days <= 0 or days > 365:
                raise ValueError()
        except ValueError:
            await update.message.reply_text("Please provide a valid number of days (1-365). Example: /briefing 30")
            return
            
    # Show typing indicator
    await update.message.chat.send_action(action="typing")
    status_message = await update.message.reply_text(f"📊 Analyzing your spending from the last {days} days...")
    
    # Run the Coach Node
    try:
        briefing = await run_coach(user_id, days)
        await status_message.delete()
        await update.message.reply_text(briefing, parse_mode="Markdown")
    except Exception as e:
        logger.error("Error generating briefing: %s", e, exc_info=True)
        await status_message.edit_text("Sorry, I ran into an issue while generating your briefing.")


# ---------------------------------------------------------------------------
# Message Handler — main expense processing pipeline
# ---------------------------------------------------------------------------
async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.message.text:
        return

    user_message = update.message.text.strip()
    user_id = str(update.effective_user.id)

    logger.info("Message from user %s: %s", user_id, user_message[:100])

    global _db_initialized
    if not _db_initialized:
        await init_db()
        _db_initialized = True
        logger.info("Database initialized on first message")

    try:
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

        config = {"configurable": {"thread_id": user_id}}
        graph = await get_graph()

        # Send a typing action to show it's thinking
        await update.message.chat.send_action(action="typing")
        
        status_message = None

        # Process the graph using streaming
        async for chunk in graph.astream(initial_state, config=config, stream_mode="updates"):
            for node_name, node_state in chunk.items():
                # If Scribe finished and needs research, tell the user!
                if node_name == "scribe":
                    parsed = node_state.get("parsed_transaction")
                    if parsed and getattr(parsed, "needs_research", False):
                        status_message = await update.message.reply_text(f"🔍 Researching unfamiliar vendor: '{parsed.vendor}'...")

        # After streaming finishes, check if it was paused or completed
        graph_state = await graph.aget_state(config)
        
        if graph_state.next and "hitl_node" in graph_state.next:
            # We hit the interrupt! Request human approval.
            parsed = graph_state.values.get("parsed_transaction")
            
            keyboard = [
                [
                    InlineKeyboardButton("✅ Approve", callback_data="hitl_approve"),
                    InlineKeyboardButton("❌ Reject", callback_data="hitl_reject"),
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            msg = (
                f"⚠️ **Large Expense Alert**\n\n"
                f"Amount: {parsed.currency} {parsed.amount}\n"
                f"Vendor: {parsed.vendor}\n"
                f"Category: {parsed.category}\n\n"
                f"Do you want to save this transaction?"
            )
            
            if status_message:
                await status_message.delete()
                
            await update.message.reply_text(msg, reply_markup=reply_markup, parse_mode="Markdown")
            return

        # Not paused, finished completely
        if status_message:
            await status_message.delete()

        response_text = graph_state.values.get("response_to_user", "")
        if response_text:
            await update.message.reply_text(response_text)
        else:
            await update.message.reply_text("Something went wrong - I didn't generate a response. Please try again.")

    except Exception as e:
        logger.error("Error processing message: %s", e, exc_info=True)
        await update.message.reply_text("Sorry, something went wrong. Please try again in a moment.")


# ---------------------------------------------------------------------------
# Button Callback Handler (for HITL)
# ---------------------------------------------------------------------------
async def button_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle Inline Keyboard button clicks."""
    query = update.callback_query
    await query.answer()
    
    user_id = str(update.effective_user.id)
    config = {"configurable": {"thread_id": user_id}}
    graph = await get_graph()
    
    action = query.data
    
    if action == "hitl_approve":
        await query.edit_message_text("✅ Approved! Saving transaction...")
        
        # Update the state to indicate approval and resume
        await graph.aupdate_state(config, {"hitl_approved": True})
        
        # Resume the graph
        async for chunk in graph.astream(None, config=config, stream_mode="updates"):
            pass
            
        graph_state = await graph.aget_state(config)
        response_text = graph_state.values.get("response_to_user", "Saved successfully.")
        await query.message.reply_text(response_text)
        
    elif action == "hitl_reject":
        await query.edit_message_text("❌ Transaction rejected. It was not saved.")
        # We don't resume the graph, just let it die.

# ---------------------------------------------------------------------------
# Error Handler
# ---------------------------------------------------------------------------
async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.error("Telegram error: %s", context.error, exc_info=context.error)
