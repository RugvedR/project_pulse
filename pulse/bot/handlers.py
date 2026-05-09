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
from pulse.db.queries import (
    get_or_create_profile, 
    get_profile_by_id,
    update_profile_settings, 
    generate_dashboard_token
)
from pulse.graph import get_graph
from pulse.nodes.coach import run_coach
from pulse.config import settings

logger = logging.getLogger(__name__)

# Track whether DB has been initialized
_db_initialized = False


# ---------------------------------------------------------------------------
# /start Command Handler
# ---------------------------------------------------------------------------
async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle /start: register or update the user's profile, then welcome them.
    """
    user = update.effective_user
    user_id = str(user.id)

    # Ensure DB is initialized
    global _db_initialized
    if not _db_initialized:
        await init_db()
        _db_initialized = True

    # Upsert the user profile
    profile = await get_or_create_profile(
        thread_id=user_id,
        username=user.username,
        full_name=user.full_name,
    )

    is_new = profile.joined_at is not None
    if is_new:
        welcome = (
            f"👋 Welcome to *Pulse*, {user.first_name}!\n\n"
            "I'm your AI-powered expense tracker. Just tell me about "
            "your expenses in plain language and I'll handle the rest.\n\n"
            "*Examples:*\n"
            "  • _Spent 450 at the badminton court_\n"
            "  • _Paid 120 for auto rickshaw_\n"
            "  • _Coffee at Starbucks for 350_\n"
            "  • _2000 groceries at DMart_\n\n"
            "I'll parse the amount, vendor, and category — then save it.\n\n"
            "Use /settings to configure your preferences.\n"
            "Use /help for the full command list."
        )
    else:
        welcome = f"👋 Welcome back, {user.first_name}! Ready to track your expenses."

    await update.message.reply_text(welcome, parse_mode="Markdown")


# ---------------------------------------------------------------------------
# /help Command Handler
# ---------------------------------------------------------------------------
async def help_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    help_text = (
        "*Pulse Commands*\n\n"
        "/start       — Welcome & registration\n"
        "/help        — Show this help\n"
        "/briefing    — Generate an on-demand spending report\n"
        "/settings    — Configure your preferences\n"
        "/dashboard   — Get a secure login code for the web dashboard\n\n"
        "*Tracking Expenses:*\n"
        "Just send a message describing your expense. I'll extract "
        "the details and save them automatically.\n\n"
        "*Supported Categories:*\n"
        "Food, Transport, Entertainment, Shopping, Bills, "
        "Health, Education, Sport, Groceries, Subscriptions, "
        "Travel, Gifts, Personal, Other"
    )
    await update.message.reply_text(help_text, parse_mode="Markdown")


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
        try:
            await status_message.delete()
            await update.message.reply_text(briefing, parse_mode="Markdown")
        except Exception as parse_err:
            logger.warning("Markdown parsing failed, falling back to plain text: %s", parse_err)
            await update.message.reply_text(briefing)
    except Exception as e:
        logger.error("Error generating briefing: %s", e, exc_info=True)
        await status_message.edit_text("Sorry, I ran into an issue while generating your briefing.")


# ---------------------------------------------------------------------------
# /dashboard Command Handler
# ---------------------------------------------------------------------------
async def dashboard_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle /dashboard: generate a short-lived OTP and send it to the user.
    The OTP is used to authenticate on the Streamlit dashboard without a password.
    """
    user_id = str(update.effective_user.id)

    token = await generate_dashboard_token(user_id)
    if not token:
        await update.message.reply_text(
            "⚠️ You need to register first. Please send /start."
        )
        return

    msg = (
        "📊 *Pulse Analytics Dashboard*\n\n"
        "Open the dashboard and log in with:\n"
        f"🆔 *Your ID:* `{user_id}`\n"
        f"🔑 *Access Code:* `{token}`\n\n"
        "⏳ _This code expires in 10 minutes and can only be used once._\n\n"
        f"🔗 [Open Dashboard]({settings.DASHBOARD_URL}?user_id={user_id}&token={token})"
    )
    await update.message.reply_text(msg, parse_mode="Markdown")


# ---------------------------------------------------------------------------
# /settings Command Handler
# ---------------------------------------------------------------------------
async def settings_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Show an interactive settings menu via Inline Keyboard.
    """
    user_id = str(update.effective_user.id)

    # Fetch the current profile to show live state
    profile = await get_or_create_profile(
        thread_id=user_id,
        username=update.effective_user.username,
        full_name=update.effective_user.full_name,
    )

    briefing_status = "✅ On" if profile.wants_briefings else "❌ Off"
    interval_label = f"{profile.briefing_interval} days"
    currency_label = profile.currency

    keyboard = [
        [
            InlineKeyboardButton(
                f"📬 Briefings: {briefing_status}",
                callback_data="settings_toggle_briefings"
            )
        ],
        [
            InlineKeyboardButton("⏱ Every 3 days", callback_data="settings_interval_3"),
            InlineKeyboardButton("⏱ Every 7 days", callback_data="settings_interval_7"),
            InlineKeyboardButton("⏱ Every 14 days", callback_data="settings_interval_14"),
        ],
        [
            InlineKeyboardButton("💰 Currency: INR", callback_data="settings_currency_INR"),
            InlineKeyboardButton("💰 Currency: USD", callback_data="settings_currency_USD"),
            InlineKeyboardButton("💰 Currency: EUR", callback_data="settings_currency_EUR"),
        ],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    settings_text = (
        "⚙️ *Pulse Settings*\n\n"
        f"📬 Briefings: {briefing_status}\n"
        f"⏱ Frequency: {interval_label}\n"
        f"💰 Currency: {currency_label}\n\n"
        "Tap a button below to change a setting:"
    )
    await update.message.reply_text(
        settings_text, reply_markup=reply_markup, parse_mode="Markdown"
    )


async def settings_callback_handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """
    Process button presses from the /settings inline keyboard.
    """
    query = update.callback_query
    await query.answer()

    user_id = str(update.effective_user.id)
    action = query.data

    if action == "settings_toggle_briefings":
        profile = await get_profile_by_id(thread_id=user_id)
        if not profile:
            await query.edit_message_text("⚠️ Profile not found. Please send /start first.")
            return
            
        new_state = not profile.wants_briefings
        await update_profile_settings(thread_id=user_id, wants_briefings=new_state)
        state_label = "✅ enabled" if new_state else "❌ disabled"
        await query.edit_message_text(f"📬 Weekly briefings are now *{state_label}*.", parse_mode="Markdown")

    elif action.startswith("settings_interval_"):
        days = int(action.split("_")[-1])
        await update_profile_settings(thread_id=user_id, briefing_interval=days)
        await query.edit_message_text(f"⏱ Briefing frequency set to every *{days} days*.", parse_mode="Markdown")

    elif action.startswith("settings_currency_"):
        currency = action.split("_")[-1]
        await update_profile_settings(thread_id=user_id, currency=currency)
        await query.edit_message_text(f"💰 Currency updated to *{currency}*.", parse_mode="Markdown")


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

        # Send a typing action and an initial status message
        await update.message.chat.send_action(action="typing")
        status_message = await update.message.reply_text("✨ Pulse is processing...")

        # Process the graph using streaming
        async for chunk in graph.astream(initial_state, config=config, stream_mode="updates"):
            for node_name, node_state in chunk.items():
                # Update status based on node transitions
                if node_name == "scribe":
                    parsed = node_state.get("parsed_transaction")
                    if parsed and getattr(parsed, "needs_research", False):
                        await status_message.edit_text(f"🔍 Researching unfamiliar vendor: '{parsed.vendor}'...")
                    else:
                        await status_message.edit_text("✅ Expense parsed. Checking rules...")
                
                elif node_name == "investigator":
                    await status_message.edit_text("🕵️ Investigation complete. Finalizing categorization...")
                
                elif node_name == "vault":
                    # We will delete the status message before the final success message
                    pass

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
        response = graph_state.values.get("response_to_user", "✅ Transaction saved!")
        await query.message.reply_text(response)
        
    elif action == "hitl_reject":
        await query.edit_message_text("❌ Transaction rejected. It was not saved.")
        # We don't resume the graph, just let it die.

# ---------------------------------------------------------------------------
# Error Handler
# ---------------------------------------------------------------------------
async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.error("Telegram error: %s", context.error, exc_info=context.error)
