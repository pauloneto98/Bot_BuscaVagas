"""
Bot Control Routes — /api/start, /api/stop, /api/bot-status, /api/logs
Manages the main job application bot subprocess.
"""

import os
import subprocess
import sys
import threading

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.config import settings
from app.api.dependencies import verify_token

router = APIRouter()

# ── Process State ──────────────────────────────────────────────────
_bot_process: subprocess.Popen | None = None
_bot_lock = threading.Lock()


class BotStartPayload(BaseModel):
    mode: str = "full"  # full | teste | manual


@router.post("/api/start", dependencies=[Depends(verify_token)])
def start_bot(payload: BotStartPayload):
    global _bot_process
    with _bot_lock:
        if _bot_process and _bot_process.poll() is None:
            return {"status": "running", "message": "O bot ja esta em execucao!"}

        log_file = settings.LOG_FILE
        with open(log_file, "w", encoding="utf-8") as f:
            f.write("")

        cmd = [sys.executable, os.path.join(settings.BASE_DIR, "main.py")]
        if payload.mode == "teste":
            cmd.append("--teste")
        elif payload.mode == "manual":
            cmd.append("--manual")

        _bot_process = subprocess.Popen(
            cmd,
            stdout=open(log_file, "a", encoding="utf-8"),
            stderr=subprocess.STDOUT,
            cwd=settings.BASE_DIR,
            env={**os.environ, "PYTHONUNBUFFERED": "1"},
        )

        return {"status": "started", "pid": _bot_process.pid, "message": "Bot iniciado com sucesso!"}


@router.post("/api/stop", dependencies=[Depends(verify_token)])
def stop_bot():
    global _bot_process
    with _bot_lock:
        if _bot_process and _bot_process.poll() is None:
            _bot_process.terminate()
            _bot_process = None
            return {"status": "stopped", "message": "Bot parado."}
        return {"status": "idle", "message": "O bot nao esta rodando."}


@router.get("/api/bot-status", dependencies=[Depends(verify_token)])
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


@router.get("/api/logs", dependencies=[Depends(verify_token)])
def get_logs():
    """Return bot log contents for the live terminal."""
    log_file = settings.LOG_FILE
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
