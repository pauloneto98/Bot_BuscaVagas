# Bot Busca Vagas

**Automated Job Application Pipeline** — An intelligent bot that scrapes job listings, adapts resumes using AI (Gemini/Groq), and sends personalized applications via email and browser automation.

[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![SQLite](https://img.shields.io/badge/SQLite-3-003B57?logo=sqlite&logoColor=white)](https://sqlite.org)
[![Gemini](https://img.shields.io/badge/Google_Gemini-AI-4285F4?logo=google&logoColor=white)](https://ai.google.dev)

---

## Features

- **AI-Powered Resume Adaptation** — Uses Google Gemini (with Groq/Llama 3 fallback) to tailor resumes for each job posting
- **Multi-Source Job Scraping** — Aggregates listings from LinkedIn, Gupy, Indeed, Glassdoor, Remote OK, and 10+ other platforms
- **Email Lead Hunter** — Autonomous web crawler that discovers HR emails using DuckDuckGo, Hunter.io, and Apollo.io APIs
- **Browser Automation** — Playwright-based form filling for direct portal applications (LinkedIn Easy Apply, etc.)
- **Web Dashboard** — Real-time control panel with live logs, statistics charts, and configuration management
- **24/7 Autonomous Mode** — Continuous operation with intelligent pacing to avoid rate limits
- **Duplicate Prevention** — SQLite-backed O(1) lookups ensure no duplicate applications

## Architecture

```
bot_curriculo/
├── app/                    # Application package
│   ├── config.py           # Centralized settings (singleton)
│   ├── core/               # Business logic modules
│   │   ├── analyzer.py     # AI job analysis (Gemini + Groq fallback)
│   │   ├── scraper.py      # Multi-platform job scraping
│   │   ├── resume.py       # PDF/DOCX resume generation
│   │   ├── mailer.py       # SMTP email sender
│   │   ├── researcher.py   # Company email discovery
│   │   ├── browser.py      # Playwright automation
│   │   ├── hunter.py       # Lead prospecting engine
│   │   └── validator.py    # Configuration validation
│   ├── db/                 # Data access layer
│   │   ├── connection.py   # SQLite connection & schema
│   │   └── repositories.py # Application & Lead repositories
│   ├── api/                # Web layer (FastAPI)
│   │   ├── server.py       # App factory & middleware
│   │   ├── auth.py         # CPF validation & JWT tokens
│   │   ├── dependencies.py # Route guards
│   │   └── routes/         # Endpoint modules
│   │       ├── bot.py      # Bot control (start/stop/logs)
│   │       ├── hunter.py   # Lead hunter control
│   │       ├── auto.py     # 24/7 scheduler control
│   │       ├── stats.py    # Dashboard analytics
│   │       └── config.py   # Settings management
│   └── services/           # Orchestration layer
│       ├── logger.py       # Application logging & metrics
│       └── scheduler.py    # Continuous operation loop
├── web/                    # Frontend (HTML/JS/CSS)
├── data/                   # Runtime data (DB, logs, cache)
├── main.py                 # CLI entry point
└── web_server.py           # Dashboard entry point
```

## Tech Stack

| Layer | Technologies |
|-------|-------------|
| **AI/NLP** | Google Gemini 1.5 Flash, Groq (Llama 3.3 70B) |
| **Backend** | Python 3.11+, FastAPI, Uvicorn |
| **Database** | SQLite with optimized indexes |
| **Scraping** | Requests, BeautifulSoup4, DuckDuckGo Search |
| **Automation** | Playwright (Chromium) |
| **Email** | SMTP (Gmail App Passwords) |
| **APIs** | Hunter.io, Apollo.io |
| **Frontend** | Vanilla JS, Chart.js |
| **Documents** | python-docx, ReportLab (PDF) |

## Quick Start

```bash
# 1. Clone the repository
git clone https://github.com/pauloneto98/Bot_BuscaVagas.git
cd Bot_BuscaVagas

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure environment
cp config.env.example config.env
# Edit config.env with your API keys and email credentials

# 4a. Run via CLI (single execution)
python main.py

# 4b. Run via Web Dashboard
python web_server.py
# Open http://localhost:8000
```

## Usage Modes

| Mode | Command | Description |
|------|---------|-------------|
| **Full Auto** | `python main.py` | Scrape + analyze + apply |
| **Test** | `python main.py --teste` | Single mock job, no email sent |
| **Manual** | `python main.py --manual` | Apply to pending DB leads |
| **Validate** | `python main.py --validar` | Check all API keys and configs |
| **Dashboard** | `python web_server.py` | Web UI with full control |

## Configuration

All settings are managed via `config.env`:

```env
# AI
GEMINI_API_KEY=your_key_here
GROQ_API_KEY=your_key_here

# Email (Gmail)
EMAIL_ADDRESS=your@gmail.com
EMAIL_APP_PASSWORD=your_app_password

# Candidate
CANDIDATE_NAME=Your Full Name
RESUME_PDF=YourResume.pdf

# Search
MAX_JOBS_PER_CATEGORY=10
SEARCH_PRESENCIAL=true
SEARCH_PORTUGAL=true
```

## Pipeline Flow

```
Job Sources ──► Scraper ──► AI Analyzer ──► Resume Adapter ──► Email/Browser
     │              │            │                │                  │
  LinkedIn       Filter       Gemini          PDF/DOCX            SMTP
  Gupy         Duplicates     Groq            Generation         Gmail
  Indeed         (SQLite)    (fallback)                        Playwright
  Remote OK
  10+ more
```

---

## Licenca / License

This project is for educational and portfolio purposes.

---

*Built with Python, FastAPI, and Google Gemini AI.*
