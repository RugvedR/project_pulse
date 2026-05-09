"""
Pulse Configuration — Centralized application settings.

All configuration is loaded from environment variables (via .env file)
using pydantic-settings. This is the SINGLE source of truth for all
runtime configuration, including model selection, database URLs,
and feature thresholds.

Usage:
    from pulse.config import settings
    print(settings.LLM_MODEL_NAME)
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


# ---------------------------------------------------------------------------
# Path helpers — resolve relative to the project root
# ---------------------------------------------------------------------------
_PROJECT_ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    """
    Application-wide settings.

    Values are loaded in this priority order:
    1. Environment variables (highest)
    2. `.env` file in the project root
    3. Defaults defined here (lowest)
    """

    model_config = SettingsConfigDict(
        env_file=str(_PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # ── Dashboard Security ────────────────────────────────────────────────

    # ── LLM Provider ──────────────────────────────────────────────────────
    LLM_PROVIDER: str = "google"              # google | ollama
    GEMINI_API_KEY: Optional[str] = None      # Optional if using Ollama
    LLM_MODEL_NAME: str = "gemini-2.5-flash"
    OLLAMA_BASE_URL: str = "http://localhost:11434"

    # ── Universal Protocol (Phase 4) ──────────────────────────────────────
    MCP_SERVER_PORT: int = 8000

    # ── Telegram Bot ──────────────────────────────────────────────────────
    TELEGRAM_BOT_TOKEN: str

    # ── Search Provider (Phase 2) ─────────────────────────────────────────
    SEARCH_PROVIDER: str = "tavily"          # tavily | serper | duckduckgo
    TAVILY_API_KEY: Optional[str] = None
    SERPER_API_KEY: Optional[str] = None

    # ── Database ──────────────────────────────────────────────────────────
    DATABASE_URL_RAW: str = Field(default=f"sqlite+aiosqlite:///{_PROJECT_ROOT / 'data' / 'pulse.db'}", alias="DATABASE_URL")
    CHECKPOINT_DB_PATH: str = str(_PROJECT_ROOT / "data" / "checkpoints.db")
    DASHBOARD_URL: str

    @property
    def DATABASE_URL(self) -> str:
        """
        Returns the database URL. 
        If it starts with postgresql://, it replaces it with postgresql+psycopg2:// 
        for SQLAlchemy 2.0 compatibility.
        """
        url = self.DATABASE_URL_RAW
        if url.startswith("postgresql://"):
            return url.replace("postgresql://", "postgresql+asyncpg://", 1)
        return url

    # ── Feature Thresholds ────────────────────────────────────────────────
    LARGE_EXPENSE_THRESHOLD: float = 1000.0   # INR — triggers HITL review
    WEEKLY_BRIEFING_DAY: str = "monday"

    # ── Derived Helpers ───────────────────────────────────────────────────
    @property
    def project_root(self) -> Path:
        """Return the resolved project root path."""
        return _PROJECT_ROOT

    @property
    def data_dir(self) -> Path:
        """Return the data directory, creating it if necessary."""
        data = _PROJECT_ROOT / "data"
        data.mkdir(parents=True, exist_ok=True)
        return data


# ---------------------------------------------------------------------------
# Singleton — import `settings` from anywhere in the codebase
# ---------------------------------------------------------------------------
settings = Settings()
