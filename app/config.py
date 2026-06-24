"""
Centralized Configuration — Bot Busca Vagas
Loads settings from config.env once and exposes them as a singleton.
All modules should import `settings` from here instead of calling os.getenv() directly.
"""

import os

from dotenv import load_dotenv
from app.utils.security import decrypt_secret

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Load environment variables from config.env (once)
load_dotenv(os.path.join(BASE_DIR, "config.env"))


class Settings:
    """Application-wide settings loaded from environment variables."""

    # ── Paths ──────────────────────────────────────────────────────
    BASE_DIR: str = BASE_DIR
    DATA_DIR: str = os.path.join(BASE_DIR, "data")
    CURRICULOS_DIR: str = os.path.join(BASE_DIR, "data", "curriculos")
    WEB_DIR: str = os.path.join(BASE_DIR, "web")
    CONFIG_FILE: str = os.path.join(BASE_DIR, "config.env")
    METRICS_FILE: str = os.path.join(BASE_DIR, "data", "metrics.json")
    LOG_FILE: str = os.path.join(BASE_DIR, "data", "bot.log")
    HUNTER_LOG_FILE: str = os.path.join(BASE_DIR, "data", "hunter.log")

    # ── API Keys ───────────────────────────────────────────────────
    GEMINI_API_KEY: str = decrypt_secret(os.getenv("GEMINI_API_KEY", ""))
    GROQ_API_KEY: str = decrypt_secret(os.getenv("GROQ_API_KEY", ""))
    HUNTER_IO_API_KEY: str = decrypt_secret(os.getenv("HUNTER_IO_API_KEY", ""))
    APOLLO_IO_API_KEY: str = decrypt_secret(os.getenv("APOLLO_IO_API_KEY", ""))
    ADZUNA_APP_ID: str = decrypt_secret(os.getenv("ADZUNA_APP_ID", ""))
    ADZUNA_APP_KEY: str = decrypt_secret(os.getenv("ADZUNA_APP_KEY", ""))
    RAPIDAPI_KEY: str = decrypt_secret(os.getenv("RAPIDAPI_KEY", ""))

    # ── Email ─────────────────────────────────────────────────────
    EMAIL_ADDRESS: str = os.getenv("EMAIL_ADDRESS", "")
    EMAIL_APP_PASSWORD: str = decrypt_secret(os.getenv("EMAIL_APP_PASSWORD", ""))
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
    JOB_CATEGORIES: str = os.getenv("JOB_CATEGORIES", "desenvolvedor de software, analista de dados, suporte de TI, help desk, desenvolvedor python, desenvolvedor web, analista de sistemas")
    PRESENCIAL_CITIES_RAW: str = os.getenv("PRESENCIAL_CITIES", "Recife, Jaboatão dos Guararapes, Olinda")

    # ── Dashboard ──────────────────────────────────────────────────
    DASHBOARD_PASSWORD: str = os.getenv("DASHBOARD_PASSWORD", "admin123")
    DASHBOARD_PASSWORD_HASH: str = os.getenv("DASHBOARD_PASSWORD_HASH", "")
    DISABLE_DASHBOARD_AUTH: bool = os.getenv("DISABLE_DASHBOARD_AUTH", "true").lower() == "true"
    PERSONALIZE_ONLY_EMAILS: bool = os.getenv("PERSONALIZE_ONLY_EMAILS", "true").lower() == "true"
    ENABLE_EMAIL_SENDING: bool = os.getenv("ENABLE_EMAIL_SENDING", "true").lower() == "true"

    # ── Gemini Model ───────────────────────────────────────────────
    GEMINI_MODEL: str = "gemini-2.5-flash"

    # ── Localidade ─────────────────────────────────────────────────
    # Vagas presenciais aceitas apenas nestas cidades
    @property
    def PRESENCIAL_CITIES(self) -> list:
        return [c.strip() for c in self.PRESENCIAL_CITIES_RAW.split(",") if c.strip()]

    # Aceitar vagas sem localidade definida (ex: "Brasil", em branco)
    ACCEPT_UNDEFINED_LOCATION: bool = True

    # ── Email Inteligente ──────────────────────────────────────────
    # Enviar email SOMENTE para pequenas empresas que pediram candidatura por email
    EMAIL_ONLY_SMALL_COMPANIES: bool = True
    # Fontes de vagas que NÃO devem receber email (usam plataformas ATS)
    EMAIL_BLOCKED_SOURCES: list = [
        "LinkedIn", "Gupy", "Indeed", "Glassdoor", "Catho",
        "Infojobs", "vagas.com", "GeekHunter", "Remotar",
        "Trampos", "Programathor", "RemoteOK", "WeWorkRemotely", "Wellfound",
    ]

    # ── ATS (Applicant Tracking System) ───────────────────────────
    # Injetar palavras-chave extraídas da vaga no currículo gerado
    ATS_KEYWORD_INJECTION: bool = True
    # Personalizar objetivo profissional com nome da empresa e cargo
    ATS_PERSONALIZE_OBJECTIVE: bool = True

    # ── Candidatura Automática ─────────────────────────────────────
    # Abrir URL da vaga no navegador para candidatura manual assistida
    ENABLE_AUTO_OPEN: bool = True
    # Log de candidaturas realizadas
    APPLICATIONS_LOG_FILE: str = os.path.join(
        os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data"),
        "applications.json"
    )


# Global singleton — import this everywhere
settings = Settings()

# Ensure data directory exists
os.makedirs(settings.DATA_DIR, exist_ok=True)
