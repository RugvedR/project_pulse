"""
Pulse — Main Entry Point.

Starts the Telegram bot and connects it to the LangGraph pipeline.

Usage:
    python main.py
"""

from __future__ import annotations

import logging
import sys

from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes

from pulse.bot.handlers import (
    error_handler,
    help_handler,
    message_handler,
    start_handler,
    button_callback_handler,
    briefing_handler,
)
from pulse.config import settings

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Logging Configuration
# ---------------------------------------------------------------------------
def _setup_logging() -> None:
    """Configure structured logging for the application."""
    logging.basicConfig(
        format="%(asctime)s | %(name)-25s | %(levelname)-7s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        level=logging.INFO,
        stream=sys.stdout,
    )
    # Reduce noise from third-party libraries
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("telegram").setLevel(logging.WARNING)
    logging.getLogger("google").setLevel(logging.WARNING)


# ---------------------------------------------------------------------------
# Background Jobs
# ---------------------------------------------------------------------------
async def weekly_briefing_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Job that runs automatically every 7 days.
    Iterates over all users in the database and sends them a personalized 
    spending briefing using the Coach node.
    """
    logger.info("Weekly briefing job triggered.")
    from pulse.db.queries import get_all_user_ids
    from pulse.nodes.coach import run_coach
    
    try:
        user_ids = await get_all_user_ids()
        if not user_ids:
            logger.info("No users found in database for briefings.")
            return

        logger.info("Sending weekly briefings to %d users.", len(user_ids))
        
        for user_id in user_ids:
            try:
                # Run the coach pipeline for this user
                briefing = await run_coach(user_id, days=7)
                
                # Send the briefing to the user's Telegram chat
                await context.bot.send_message(
                    chat_id=int(user_id), 
                    text=briefing, 
                    parse_mode="Markdown"
                )
                logger.info("Briefing sent successfully to user %s", user_id)
            except Exception as e:
                logger.error("Failed to send briefing to user %s: %s", user_id, e)
                
    except Exception as e:
        logger.error("Error in weekly_briefing_job: %s", e)


# ---------------------------------------------------------------------------
# Application Bootstrap
# ---------------------------------------------------------------------------
def main() -> None:
    """Build and run the Telegram bot application."""
    _setup_logging()

    # Validate required config
    if not settings.TELEGRAM_BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN is not set. Check your .env file.")
        sys.exit(1)

    if not settings.GEMINI_API_KEY:
        logger.error("GEMINI_API_KEY is not set. Check your .env file.")
        sys.exit(1)

    logger.info("Starting Pulse Expense Orchestrator...")
    logger.info("  LLM Model: %s", settings.LLM_MODEL_NAME)
    logger.info("  Database:  %s", settings.DATABASE_URL)
    logger.info("  HITL Threshold: %s INR", settings.LARGE_EXPENSE_THRESHOLD)

    # Build the Telegram application
    app = ApplicationBuilder().token(settings.TELEGRAM_BOT_TOKEN).build()

    # Register handlers (order matters — commands first, then catch-all)
    app.add_handler(CommandHandler("start", start_handler))
    app.add_handler(CommandHandler("help", help_handler))
    app.add_handler(CommandHandler("briefing", briefing_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))
    app.add_handler(CallbackQueryHandler(button_callback_handler))

    # Schedule the weekly coach job (runs every 7 days)
    if app.job_queue:
        app.job_queue.run_repeating(weekly_briefing_job, interval=7 * 24 * 60 * 60, first=10)

    # Register error handler
    app.add_error_handler(error_handler)

    # Start polling
    logger.info("Bot is running. Press Ctrl+C to stop.")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
