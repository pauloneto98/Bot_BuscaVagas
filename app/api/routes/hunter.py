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
from app.api.dependencies import get_current_user
from app.db.repositories import LeadRepository
from app.utils.paths import get_user_log_file

router = APIRouter()

# Track hunter processes by user_id
_hunter_processes: dict[int, subprocess.Popen] = {}
_hunter_lock = threading.Lock()


@router.post("/api/hunter/start")
def start_hunter(current_user: dict = Depends(get_current_user)):
    global _hunter_processes
    user_id = current_user["id"]
    with _hunter_lock:
        proc = _hunter_processes.get(user_id)
        if proc and proc.poll() is None:
            return {"status": "running", "message": "O Email Hunter ja esta em execucao!"}

        log_file = get_user_log_file(user_id, "hunter.log")
        with open(log_file, "w", encoding="utf-8") as f:
            f.write("")

        cmd = [sys.executable, "-m", "app.core.hunter"]
        # Pass user_id as env variable to child process
        child_env = {
            **os.environ,
            "PYTHONUNBUFFERED": "1",
            "PYTHONIOENCODING": "utf-8",
            "CURRENT_USER_ID": str(user_id)
        }
        
        _hunter_processes[user_id] = subprocess.Popen(
            cmd,
            stdout=open(log_file, "a", encoding="utf-8"),
            stderr=subprocess.STDOUT,
            cwd=settings.BASE_DIR,
            env=child_env,
        )
        return {"status": "started", "pid": _hunter_processes[user_id].pid, "message": "Email Hunter iniciado!"}


@router.post("/api/hunter/stop")
def stop_hunter(current_user: dict = Depends(get_current_user)):
    global _hunter_processes
    user_id = current_user["id"]
    with _hunter_lock:
        proc = _hunter_processes.get(user_id)
        if proc and proc.poll() is None:
            proc.terminate()
            _hunter_processes[user_id] = None
            return {"status": "stopped", "message": "Email Hunter parado."}
        return {"status": "idle", "message": "O Hunter nao esta rodando."}


@router.get("/api/hunter/status")
def hunter_status(current_user: dict = Depends(get_current_user)):
    global _hunter_processes
    user_id = current_user["id"]
    with _hunter_lock:
        proc = _hunter_processes.get(user_id)
        if proc is None:
            return {"running": False}
        if proc.poll() is None:
            return {"running": True, "pid": proc.pid}
        else:
            code = proc.returncode
            _hunter_processes[user_id] = None
            return {"running": False, "last_exit_code": code}


@router.get("/api/hunter/logs")
def get_hunter_logs(current_user: dict = Depends(get_current_user)):
    user_id = current_user["id"]
    log_file = get_user_log_file(user_id, "hunter.log")
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


@router.get("/api/hunter/leads")
def get_hunter_leads(current_user: dict = Depends(get_current_user)):
    user_id = current_user["id"]
    leads = LeadRepository.get_all(user_id)
    return {"leads": leads}


class LeadPayload(BaseModel):
    empresa: str
    email: str
    site: str = ""
    cargo_da_vaga: str = ""
    fonte: str = "Manual"
    status: str = "pending"


@router.post("/api/leads")
def create_lead(payload: LeadPayload, current_user: dict = Depends(get_current_user)):
    user_id = current_user["id"]
    lead_data = {
        "empresa": payload.empresa,
        "email": payload.email,
        "site": payload.site,
        "cargo_da_vaga": payload.cargo_da_vaga,
        "fonte": payload.fonte,
        "data": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "status": payload.status
    }
    success = LeadRepository.insert(lead_data, user_id)
    if success:
        return {"status": "success", "message": "Lead inserido com sucesso!"}
    return {"status": "error", "message": "Erro ao inserir lead. E-mail duplicado?"}


@router.put("/api/leads/{lead_id}")
def update_lead(lead_id: int, payload: LeadPayload, current_user: dict = Depends(get_current_user)):
    user_id = current_user["id"]
    lead_data = {
        "empresa": payload.empresa,
        "email": payload.email,
        "site": payload.site,
        "cargo_da_vaga": payload.cargo_da_vaga,
        "fonte": payload.fonte,
        "status": payload.status
    }
    LeadRepository.update_lead(lead_id, lead_data, user_id)
    return {"status": "success", "message": "Lead atualizado com sucesso!"}


@router.delete("/api/leads/{lead_id}")
def delete_lead(lead_id: int, current_user: dict = Depends(get_current_user)):
    user_id = current_user["id"]
    LeadRepository.delete_lead(lead_id, user_id)
    return {"status": "success", "message": "Lead removido com sucesso!"}


@router.post("/api/leads/apply")
def start_leads_application(current_user: dict = Depends(get_current_user)):
    """Legado: redireciona para execução unificada."""
    from app.api.routes.bot import start_bot, BotStartPayload
    return start_bot(BotStartPayload(mode="full", hunt_leads_first=False), current_user=current_user)


