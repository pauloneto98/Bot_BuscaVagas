"""
Web Server — Bot de Candidatura Automática
FastAPI backend que serve a interface web e expõe endpoints de controle.
Arquitetura modular pronta para escalar para SaaS no futuro.
"""

import json
import os
import re
import subprocess
import sys
import threading
from datetime import datetime

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

# ── Paths ──────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
WEB_DIR = os.path.join(BASE_DIR, "web")
CONFIG_FILE = os.path.join(BASE_DIR, "config.env")
HISTORY_FILE = os.path.join(DATA_DIR, "history.json")
METRICS_FILE = os.path.join(DATA_DIR, "metrics.json")
LOG_FILE = os.path.join(DATA_DIR, "bot.log")

os.makedirs(DATA_DIR, exist_ok=True)

# ── App ────────────────────────────────────────────────────────────
app = FastAPI(title="Bot Busca Vagas", version="3.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Bot process state ─────────────────────────────────────────────
_bot_process: subprocess.Popen | None = None
_bot_lock = threading.Lock()


# ═══════════════════════════════════════════════════════════════════
#  MODELS
# ═══════════════════════════════════════════════════════════════════

class ConfigPayload(BaseModel):
    gemini_api_key: str = ""
    email_address: str = ""
    email_app_password: str = ""
    email_cc: str = ""
    candidate_name: str = ""
    resume_pdf: str = ""
    max_jobs_per_category: int = 10
    search_presencial: bool = True
    search_portugal: bool = True
    request_delay_min: float = 2
    request_delay_max: float = 5


class BotStartPayload(BaseModel):
    mode: str = "full"  # full | teste | manual


# ═══════════════════════════════════════════════════════════════════
#  CONFIG ENDPOINTS
# ═══════════════════════════════════════════════════════════════════

def _parse_env_file() -> dict:
    """Read config.env into a dict."""
    config = {}
    if not os.path.exists(CONFIG_FILE):
        return config
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, _, value = line.partition("=")
                config[key.strip()] = value.strip()
    return config


def _write_env_file(config: dict):
    """Write config dict back to config.env preserving comments."""
    lines = []
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            lines = f.readlines()

    # Build a set of keys we've written
    written_keys = set()
    new_lines = []

    for line in lines:
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and "=" in stripped:
            key = stripped.split("=", 1)[0].strip()
            if key in config:
                new_lines.append(f"{key}={config[key]}\n")
                written_keys.add(key)
            else:
                new_lines.append(line)
        else:
            new_lines.append(line)

    # Append any new keys not yet in the file
    for key, value in config.items():
        if key not in written_keys:
            new_lines.append(f"{key}={value}\n")

    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        f.writelines(new_lines)


@app.get("/api/config")
def get_config():
    raw = _parse_env_file()
    return {
        "gemini_api_key": raw.get("GEMINI_API_KEY", ""),
        "email_address": raw.get("EMAIL_ADDRESS", ""),
        "email_app_password": raw.get("EMAIL_APP_PASSWORD", ""),
        "email_cc": raw.get("EMAIL_CC", ""),
        "candidate_name": raw.get("CANDIDATE_NAME", ""),
        "resume_pdf": raw.get("RESUME_PDF", ""),
        "max_jobs_per_category": int(raw.get("MAX_JOBS_PER_CATEGORY", "10")),
        "search_presencial": raw.get("SEARCH_PRESENCIAL", "true").lower() == "true",
        "search_portugal": raw.get("SEARCH_PORTUGAL", "true").lower() == "true",
        "request_delay_min": float(raw.get("REQUEST_DELAY_MIN", "2")),
        "request_delay_max": float(raw.get("REQUEST_DELAY_MAX", "5")),
    }


@app.post("/api/config")
def save_config(payload: ConfigPayload):
    env_map = {
        "GEMINI_API_KEY": payload.gemini_api_key,
        "EMAIL_ADDRESS": payload.email_address,
        "EMAIL_APP_PASSWORD": payload.email_app_password,
        "EMAIL_CC": payload.email_cc,
        "CANDIDATE_NAME": payload.candidate_name,
        "RESUME_PDF": payload.resume_pdf,
        "MAX_JOBS_PER_CATEGORY": str(payload.max_jobs_per_category),
        "SEARCH_PRESENCIAL": str(payload.search_presencial).lower(),
        "SEARCH_PORTUGAL": str(payload.search_portugal).lower(),
        "REQUEST_DELAY_MIN": str(payload.request_delay_min),
        "REQUEST_DELAY_MAX": str(payload.request_delay_max),
    }
    _write_env_file(env_map)
    return {"status": "ok", "message": "Configurações salvas com sucesso!"}


# ═══════════════════════════════════════════════════════════════════
#  RESUME UPLOAD
# ═══════════════════════════════════════════════════════════════════

@app.post("/api/upload-resume")
async def upload_resume(file: UploadFile = File(...)):
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(400, "Apenas arquivos PDF são aceitos.")

    # Sanitize filename
    safe_name = re.sub(r"[^\w.\-]", "_", file.filename)
    dest = os.path.join(BASE_DIR, safe_name)

    with open(dest, "wb") as f:
        content = await file.read()
        f.write(content)

    # Update config.env to point to new resume
    env = _parse_env_file()
    env["RESUME_PDF"] = safe_name
    _write_env_file(env)

    return {
        "status": "ok",
        "filename": safe_name,
        "message": f"Currículo '{safe_name}' salvo com sucesso!",
    }


# ═══════════════════════════════════════════════════════════════════
#  STATS / DASHBOARD
# ═══════════════════════════════════════════════════════════════════

@app.get("/api/stats")
def get_stats():
    # Load history
    history = {"candidaturas": []}
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                history = json.load(f)
        except Exception:
            pass

    candidaturas = history.get("candidaturas", [])
    total = len(candidaturas)
    enviados = sum(1 for c in candidaturas if c.get("email_enviado"))
    hoje = datetime.now().strftime("%Y-%m-%d")
    hoje_count = sum(
        1 for c in candidaturas
        if c.get("data", "").startswith(hoje)
    )

    # Per-day counts for chart (last 30 days)
    from collections import Counter
    day_counts = Counter()
    for c in candidaturas:
        d = c.get("data", "")[:10]
        if d:
            day_counts[d] += 1

    # Sort by date
    sorted_days = sorted(day_counts.items())[-30:]

    # Top companies
    emp_counts: dict[str, int] = {}
    for c in candidaturas:
        emp = c.get("empresa", "Desconhecida")
        emp_counts[emp] = emp_counts.get(emp, 0) + 1
    top_empresas = sorted(
        emp_counts.items(), key=lambda x: -x[1]
    )[:10]

    # Source breakdown
    source_counts: dict[str, int] = {}
    for c in candidaturas:
        note = c.get("notas", "")
        if "JSON" in note or "manual" in note.lower():
            src = "Manual"
        elif "teste" in note.lower():
            src = "Teste"
        else:
            src = "Automático"
        source_counts[src] = source_counts.get(src, 0) + 1

    # Metrics
    metrics = {"rate_limit_hits": 0, "gemini_calls": 0, "fallbacks_used": 0}
    if os.path.exists(METRICS_FILE):
        try:
            with open(METRICS_FILE, "r", encoding="utf-8") as f:
                metrics = json.load(f)
        except Exception:
            pass

    return {
        "total": total,
        "emails_enviados": enviados,
        "sem_email": total - enviados,
        "hoje": hoje_count,
        "chart_days": {
            "labels": [d[0] for d in sorted_days],
            "values": [d[1] for d in sorted_days],
        },
        "top_empresas": {
            "labels": [e[0] for e in top_empresas],
            "values": [e[1] for e in top_empresas],
        },
        "sources": source_counts,
        "metrics": metrics,
    }


@app.get("/api/jobs")
def get_recent_jobs():
    """Return recent application history."""
    history = {"candidaturas": []}
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                history = json.load(f)
        except Exception:
            pass

    recent = list(reversed(history.get("candidaturas", [])))[:50]
    return {"jobs": recent}


# ═══════════════════════════════════════════════════════════════════
#  BOT CONTROL
# ═══════════════════════════════════════════════════════════════════

@app.post("/api/start")
def start_bot(payload: BotStartPayload):
    global _bot_process
    with _bot_lock:
        if _bot_process and _bot_process.poll() is None:
            return {
                "status": "running",
                "message": "O bot já está em execução!",
            }

        # Clear log file
        with open(LOG_FILE, "w", encoding="utf-8") as f:
            f.write("")

        # Build command
        cmd = [sys.executable, os.path.join(BASE_DIR, "main.py")]
        if payload.mode == "teste":
            cmd.append("--teste")
        elif payload.mode == "manual":
            cmd.append("--manual")

        _bot_process = subprocess.Popen(
            cmd,
            stdout=open(LOG_FILE, "a", encoding="utf-8"),
            stderr=subprocess.STDOUT,
            cwd=BASE_DIR,
            env={**os.environ, "PYTHONUNBUFFERED": "1"},
        )

        return {
            "status": "started",
            "pid": _bot_process.pid,
            "message": "Bot iniciado com sucesso!",
        }


@app.post("/api/stop")
def stop_bot():
    global _bot_process
    with _bot_lock:
        if _bot_process and _bot_process.poll() is None:
            _bot_process.terminate()
            _bot_process = None
            return {"status": "stopped", "message": "Bot parado."}
        return {"status": "idle", "message": "O bot não está rodando."}


@app.get("/api/bot-status")
def bot_status():
    global _bot_process
    with _bot_lock:
        if _bot_process is None:
            return {"running": False}
        if _bot_process.poll() is None:
            return {"running": True, "pid": _bot_process.pid}
        else:
            code = _bot_process.returncode
            _bot_process = None
            return {"running": False, "last_exit_code": code}


@app.get("/api/logs")
def get_logs():
    """Return bot log contents for the live terminal."""
    if not os.path.exists(LOG_FILE):
        return {"log": ""}
    try:
        with open(LOG_FILE, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
        # Return last 500 lines max
        lines = content.split("\n")
        if len(lines) > 500:
            lines = lines[-500:]
        return {"log": "\n".join(lines)}
    except Exception:
        return {"log": ""}


# ═══════════════════════════════════════════════════════════════════
#  STATIC FILES & SPA
# ═══════════════════════════════════════════════════════════════════

# Serve the web directory for static assets
app.mount("/static", StaticFiles(directory=WEB_DIR), name="static")


@app.get("/")
def serve_index():
    return FileResponse(os.path.join(WEB_DIR, "index.html"))


if __name__ == "__main__":
    import uvicorn
    print("\n>>> Bot Busca Vagas - Dashboard Web")
    print("    Abra no navegador: http://localhost:8000\n")
    uvicorn.run(app, host="0.0.0.0", port=8000)
