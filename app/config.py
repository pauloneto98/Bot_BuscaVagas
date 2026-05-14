"""
Centralized Configuration — Bot Busca Vagas
Loads settings from config.env once and exposes them as a singleton.
All modules should import `settings` from here instead of calling os.getenv() directly.
"""

import os

from dotenv import load_dotenv

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Load environment variables from config.env (once)
load_dotenv(os.path.join(BASE_DIR, "config.env"))


class Settings:
    """Application-wide settings loaded from environment variables."""

    # ── Paths ──────────────────────────────────────────────────────
    BASE_DIR: str = BASE_DIR
    DATA_DIR: str = os.path.join(BASE_DIR, "data")
    WEB_DIR: str = os.path.join(BASE_DIR, "web")
    CONFIG_FILE: str = os.path.join(BASE_DIR, "config.env")
    METRICS_FILE: str = os.path.join(BASE_DIR, "data", "metrics.json")
    LOG_FILE: str = os.path.join(BASE_DIR, "data", "bot.log")
    HUNTER_LOG_FILE: str = os.path.join(BASE_DIR, "data", "hunter.log")

    # ── API Keys ───────────────────────────────────────────────────
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
    HUNTER_IO_API_KEY: str = os.getenv("HUNTER_IO_API_KEY", "")
    APOLLO_IO_API_KEY: str = os.getenv("APOLLO_IO_API_KEY", "")

    # ── Email ──────────────────────────────────────────────────────
    EMAIL_ADDRESS: str = os.getenv("EMAIL_ADDRESS", "")
    EMAIL_APP_PASSWORD: str = os.getenv("EMAIL_APP_PASSWORD", "")
    EMAIL_CC: str = os.getenv("EMAIL_CC", "")

    # ── Candidate ──────────────────────────────────────────────────
    CANDIDATE_NAME: str = os.getenv("CANDIDATE_NAME", "Paulo Antonio do Nascimento Neto")
    RESUME_PDF: str = os.getenv("RESUME_PDF", "Curriculo-PauloNeto.pdf")

    # ── Search ─────────────────────────────────────────────────────
    MAX_JOBS_PER_CATEGORY: int = int(os.getenv("MAX_JOBS_PER_CATEGORY", "10"))
    SEARCH_PRESENCIAL: bool = os.getenv("SEARCH_PRESENCIAL", "true").lower() == "true"
    SEARCH_PORTUGAL: bool = os.getenv("SEARCH_PORTUGAL", "true").lower() == "true"
    REQUEST_DELAY_MIN: float = float(os.getenv("REQUEST_DELAY_MIN", "2"))
    REQUEST_DELAY_MAX: float = float(os.getenv("REQUEST_DELAY_MAX", "5"))

    # ── Dashboard ──────────────────────────────────────────────────
    DASHBOARD_PASSWORD: str = os.getenv("DASHBOARD_PASSWORD", "admin123")
    PERSONALIZE_ONLY_EMAILS: bool = os.getenv("PERSONALIZE_ONLY_EMAILS", "true").lower() == "true"

    # ── Gemini Model ───────────────────────────────────────────────
    GEMINI_MODEL: str = "gemini-1.5-flash"


# Global singleton — import this everywhere
settings = Settings()

# Ensure data directory exists
os.makedirs(settings.DATA_DIR, exist_ok=True)
