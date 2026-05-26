# Architecture

## System Overview

```mermaid
graph TB
    subgraph "Entry Points"
        CLI["main.py (CLI)"]
        WEB["web_server.py (Dashboard)"]
    end

    subgraph "app/api/ — Web Layer"
        SERVER["server.py"]
        AUTH["auth.py"]
        DEPS["dependencies.py"]
        subgraph "routes/"
            R_BOT["bot.py"]
            R_HUNTER["hunter.py"]
            R_AUTO["auto.py"]
            R_STATS["stats.py"]
            R_CONFIG["config.py"]
        end
    end

    subgraph "app/services/ — Orchestration"
        LOGGER["logger.py"]
        SCHED["scheduler.py"]
    end

    subgraph "app/core/ — Business Logic"
        SCRAPER["scraper.py"]
        ANALYZER["analyzer.py"]
        RESUME["resume.py"]
        MAILER["mailer.py"]
        RESEARCHER["researcher.py"]
        BROWSER["browser.py"]
        HUNTER["hunter.py"]
        VALIDATOR["validator.py"]
    end

    subgraph "app/db/ — Data Layer"
        CONN["connection.py"]
        REPO["repositories.py"]
    end

    subgraph "app/ — Config"
        CONFIG["config.py (singleton)"]
    end

    CLI --> SCRAPER
    CLI --> ANALYZER
    CLI --> RESUME
    CLI --> MAILER
    CLI --> BROWSER
    CLI --> LOGGER

    WEB --> SERVER
    SERVER --> AUTH
    SERVER --> R_BOT
    SERVER --> R_HUNTER
    SERVER --> R_AUTO
    SERVER --> R_STATS
    SERVER --> R_CONFIG

    R_BOT --> DEPS
    R_HUNTER --> DEPS
    R_AUTO --> DEPS
    R_STATS --> REPO
    R_CONFIG --> CONFIG

    SCHED --> HUNTER
    SCHED --> CLI

    ANALYZER --> LOGGER
    HUNTER --> RESEARCHER
    HUNTER --> REPO
    LOGGER --> REPO

    REPO --> CONN
    CONFIG -.-> SCRAPER
    CONFIG -.-> ANALYZER
    CONFIG -.-> MAILER
    CONFIG -.-> RESEARCHER
```

## Layer Responsibilities

| Layer | Directory | Purpose |
|-------|-----------|---------|
| **Config** | `app/config.py` | Loads `config.env` once. All modules import `settings` from here instead of calling `os.getenv()` directly. |
| **Core** | `app/core/` | Pure business logic — no web framework dependencies. Each module handles one domain (scraping, analysis, email, etc.). |
| **Data** | `app/db/` | SQLite connection management and repository pattern for clean data access. |
| **Services** | `app/services/` | Cross-cutting concerns: logging, metrics tracking, and the 24/7 scheduler. |
| **API** | `app/api/` | FastAPI routers organized by feature. Each route file is self-contained with its own state management. |

## Design Decisions

1. **Repository Pattern**: All database access goes through `ApplicationRepository` and `LeadRepository` static methods, making it easy to swap SQLite for PostgreSQL in the future.

2. **Centralized Config**: A single `Settings` class eliminates 8+ scattered `load_dotenv()` calls and provides type hints for all configuration values.

3. **Subprocess Isolation**: The bot, hunter, and scheduler run as separate Python processes (via `subprocess.Popen`), preventing any crash from taking down the web dashboard.

4. **Graceful Fallbacks**: Gemini → Groq → Base Resume. The pipeline never stops due to a single API failure.
