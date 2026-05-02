"""
Pulse — Main Entry Point.

Starts the Telegram bot and connects it to the LangGraph pipeline.

Usage:
    python main.py
"""

from __future__ import annotations

import logging
import sys

from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters

from pulse.bot.handlers import (
    error_handler,
    help_handler,
    message_handler,
    start_handler,
)
from pulse.config import settings


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
# Application Bootstrap
# ---------------------------------------------------------------------------
def main() -> None:
    """Build and run the Telegram bot application."""
    _setup_logging()
    logger = logging.getLogger(__name__)

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
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))

    # Register error handler
    app.add_error_handler(error_handler)

    # Start polling
    logger.info("Bot is running. Press Ctrl+C to stop.")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
