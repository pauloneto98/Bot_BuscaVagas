"""
Email Hunter Routes — /api/hunter/*
Manages the email lead hunter subprocess.
"""

import os
import subprocess
import sys
import threading
from datetime import datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel

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


class LeadPayload(BaseModel):
    empresa: str
    email: str
    site: str = ""
    cargo_da_vaga: str = ""
    fonte: str = "Manual"
    status: str = "pending"


@router.post("/api/leads", dependencies=[Depends(verify_token)])
def create_lead(payload: LeadPayload):
    lead_data = {
        "empresa": payload.empresa,
        "email": payload.email,
        "site": payload.site,
        "cargo_da_vaga": payload.cargo_da_vaga,
        "fonte": payload.fonte,
        "data": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "status": payload.status
    }
    success = LeadRepository.insert(lead_data)
    if success:
        return {"status": "success", "message": "Lead inserido com sucesso!"}
    return {"status": "error", "message": "Erro ao inserir lead. E-mail duplicado?"}


@router.put("/api/leads/{lead_id}", dependencies=[Depends(verify_token)])
def update_lead(lead_id: int, payload: LeadPayload):
    lead_data = {
        "empresa": payload.empresa,
        "email": payload.email,
        "site": payload.site,
        "cargo_da_vaga": payload.cargo_da_vaga,
        "fonte": payload.fonte,
        "status": payload.status
    }
    LeadRepository.update_lead(lead_id, lead_data)
    return {"status": "success", "message": "Lead atualizado com sucesso!"}


@router.delete("/api/leads/{lead_id}", dependencies=[Depends(verify_token)])
def delete_lead(lead_id: int):
    LeadRepository.delete_lead(lead_id)
    return {"status": "success", "message": "Lead removido com sucesso!"}


@router.post("/api/leads/apply", dependencies=[Depends(verify_token)])
def start_leads_application():
    """Legado: redireciona para execução unificada (leads já entram no modo full)."""
    from app.api.routes.bot import start_bot, BotStartPayload

    return start_bot(BotStartPayload(mode="full", hunt_leads_first=False))

