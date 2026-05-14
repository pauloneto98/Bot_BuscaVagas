"""
Email Hunter Routes — /api/hunter/*
Manages the email lead hunter subprocess.
"""

import os
import subprocess
import sys
import threading

from fastapi import APIRouter, Depends

from app.config import settings
from app.api.dependencies import verify_token
from app.db.repositories import LeadRepository

router = APIRouter()

_hunter_process: subprocess.Popen | None = None
_hunter_lock = threading.Lock()


@router.post("/api/hunter/start", dependencies=[Depends(verify_token)])
def start_hunter():
    global _hunter_process
    with _hunter_lock:
        if _hunter_process and _hunter_process.poll() is None:
            return {"status": "running", "message": "O Email Hunter ja esta em execucao!"}

        log_file = settings.HUNTER_LOG_FILE
        with open(log_file, "w", encoding="utf-8") as f:
            f.write("")

        cmd = [sys.executable, "-m", "app.core.hunter"]
        _hunter_process = subprocess.Popen(
            cmd,
            stdout=open(log_file, "a", encoding="utf-8"),
            stderr=subprocess.STDOUT,
            cwd=settings.BASE_DIR,
            env={**os.environ, "PYTHONUNBUFFERED": "1", "PYTHONIOENCODING": "utf-8"},
        )
        return {"status": "started", "pid": _hunter_process.pid, "message": "Email Hunter iniciado!"}


@router.post("/api/hunter/stop", dependencies=[Depends(verify_token)])
def stop_hunter():
    global _hunter_process
    with _hunter_lock:
        if _hunter_process and _hunter_process.poll() is None:
            _hunter_process.terminate()
            _hunter_process = None
            return {"status": "stopped", "message": "Email Hunter parado."}
        return {"status": "idle", "message": "O Hunter nao esta rodando."}


@router.get("/api/hunter/status", dependencies=[Depends(verify_token)])
def hunter_status():
    global _hunter_process
    with _hunter_lock:
        if _hunter_process is None:
            return {"running": False}
        if _hunter_process.poll() is None:
            return {"running": True, "pid": _hunter_process.pid}
        else:
            code = _hunter_process.returncode
            _hunter_process = None
            return {"running": False, "last_exit_code": code}


@router.get("/api/hunter/logs", dependencies=[Depends(verify_token)])
def get_hunter_logs():
    log_file = settings.HUNTER_LOG_FILE
    if not os.path.exists(log_file):
        return {"log": ""}
    try:
        with open(log_file, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
        lines = content.split("\n")
        if len(lines) > 500:
            lines = lines[-500:]
        return {"log": "\n".join(lines)}
    except Exception:
        return {"log": ""}


@router.get("/api/hunter/leads", dependencies=[Depends(verify_token)])
def get_hunter_leads():
    leads = LeadRepository.get_all()
    return {"leads": leads}


@router.post("/api/leads/apply", dependencies=[Depends(verify_token)])
def start_leads_application():
    from app.api.routes.bot import _bot_process, _bot_lock
    import app.api.routes.bot as bot_mod

    with _bot_lock:
        if _bot_process and _bot_process.poll() is None:
            return {"status": "running", "message": "O bot ja esta em execucao! Aguarde ele finalizar."}

        log_file = settings.LOG_FILE
        with open(log_file, "w", encoding="utf-8") as f:
            f.write("Iniciando candidatura para os leads pendentes do banco...\n")

        cmd = [sys.executable, os.path.join(settings.BASE_DIR, "main.py"), "--manual"]
        bot_mod._bot_process = subprocess.Popen(
            cmd,
            stdout=open(log_file, "a", encoding="utf-8"),
            stderr=subprocess.STDOUT,
            cwd=settings.BASE_DIR,
            env={**os.environ, "PYTHONUNBUFFERED": "1"},
        )

        return {"status": "started", "pid": bot_mod._bot_process.pid, "message": "Disparo de e-mails para os leads iniciado!"}
