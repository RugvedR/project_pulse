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
from telegram.request import HTTPXRequest
import threading
import http.server
import socketserver

def run_health_check():
    """
    Tiny web server to satisfy cloud hosting 'port' requirements.
    This keeps the bot alive on providers like Hugging Face or Render.
    """
    port = 7860
    handler = http.server.SimpleHTTPRequestHandler
    with socketserver.TCPServer(("", port), handler) as httpd:
        logger.info(f"Health check server running on port {port}")
        httpd.serve_forever()

from pulse.bot.handlers import (
    error_handler,
    help_handler,
    message_handler,
    start_handler,
    button_callback_handler,
    briefing_handler,
    dashboard_handler,
    settings_handler,
    settings_callback_handler,
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
async def smart_briefing_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Smart Briefing Scheduler — runs once daily.

    Instead of a fixed global timer, this job queries the database to find
    users who are individually "due" for a briefing based on their personal
    interval preference and the last time they received one.

    This is self-healing: if the bot was offline, it catches up immediately
    on restart without skipping any user.
    """
    from datetime import datetime, timezone
    from pulse.db.queries import get_opted_in_profiles, mark_briefing_sent
    from pulse.nodes.coach import run_coach

    logger.info("Smart briefing scheduler running — checking user schedules.")
    now = datetime.now(timezone.utc)

    try:
        profiles = await get_opted_in_profiles()
        if not profiles:
            logger.info("No opted-in users found.")
            return

        due_count = 0
        for profile in profiles:
            # Determine if this user is due for a briefing
            if profile.last_briefing_at is None:
                # Never received one — send on first run
                is_due = True
            else:
                days_since = (now - profile.last_briefing_at).total_seconds() / 86400
                is_due = days_since >= profile.briefing_interval

            if not is_due:
                continue

            due_count += 1
            user_id = profile.thread_id
            try:
                briefing = await run_coach(user_id, days=profile.briefing_interval)
                try:
                    await context.bot.send_message(
                        chat_id=int(user_id),
                        text=briefing,
                        parse_mode="Markdown"
                    )
                except Exception:
                    # Fallback to plain text if Markdown parsing fails
                    await context.bot.send_message(chat_id=int(user_id), text=briefing)

                await mark_briefing_sent(user_id)
                logger.info("Briefing sent to user %s (interval: %d days).", user_id, profile.briefing_interval)

            except Exception as e:
                logger.error("Failed to send briefing to user %s: %s", user_id, e)

        logger.info("Briefing check complete. %d user(s) received briefings.", due_count)

    except Exception as e:
        logger.error("Error in smart_briefing_job: %s", e)


# ---------------------------------------------------------------------------
# Application Bootstrap
# ---------------------------------------------------------------------------
async def post_init(application: ApplicationBuilder) -> None:
    """
    This runs once the bot's event loop is active but before it starts 
    processing updates. Ideal for database initialization.
    """
    from pulse.db.database import init_db
    logger.info("Initializing database via post_init...")
    await init_db()
    logger.info("Database initialized successfully.")

def main() -> None:
    """Build and run the Telegram bot application."""
    _setup_logging()
    
    # Start health check server in background (for cloud hosting uptime)
    threading.Thread(target=run_health_check, daemon=True).start()
    
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

    # Build the Telegram application with a longer timeout for cloud stability
    request = HTTPXRequest(connect_timeout=30.0, read_timeout=30.0)
    app = (
        ApplicationBuilder()
        .token(settings.TELEGRAM_BOT_TOKEN)
        .post_init(post_init)
        .request(request)
        .build()
    )

    # Register handlers (order matters — specific callbacks before catch-all)
    app.add_handler(CommandHandler("start", start_handler))
    app.add_handler(CommandHandler("help", help_handler))
    app.add_handler(CommandHandler("briefing", briefing_handler))
    app.add_handler(CommandHandler("dashboard", dashboard_handler))
    app.add_handler(CommandHandler("settings", settings_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))
    
    # Route settings callbacks and HITL callbacks to their respective handlers
    app.add_handler(CallbackQueryHandler(settings_callback_handler, pattern="^settings_"))
    app.add_handler(CallbackQueryHandler(button_callback_handler, pattern="^hitl_"))

    # Smart Briefing Scheduler — runs daily, checks per-user intervals
    if app.job_queue:
        app.job_queue.run_repeating(
            smart_briefing_job,
            interval=24 * 60 * 60,  # Check once a day
            first=30,               # First check 30 seconds after startup
        )
        logger.info("Smart briefing scheduler registered (daily check).")

    # Register error handler
    app.add_error_handler(error_handler)

    # Start polling
    logger.info("Bot is running. Press Ctrl+C to stop.")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
