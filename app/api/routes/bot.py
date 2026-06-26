"""
Bot Control Routes — /api/start, /api/stop, /api/bot-status, /api/logs
Execução unificada: opcionalmente busca leads, depois aplica candidaturas.
"""

import os
import subprocess
import sys
import threading

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.config import settings
from app.api.dependencies import get_current_user
from app.utils.paths import get_user_log_file
from app.services.job_queue import JobQueue
from app.db.connection import get_db_connection

router = APIRouter()


class BotStartPayload(BaseModel):
    mode: str = "full"  # full | teste
    hunt_leads_first: bool = False


@router.post("/api/start")
def start_bot(payload: BotStartPayload, current_user: dict = Depends(get_current_user)):
    user_id = current_user["id"]
    
    # Check if there is already a pending or running job for this user
    active_job = JobQueue.get_active_job_for_user(user_id)
    if active_job:
        return {"status": "running", "message": "Você já tem uma execução pendente ou em andamento na fila!"}

    # Determine job_type
    if payload.mode == "teste":
        job_type = "teste"
    elif payload.hunt_leads_first:
        job_type = "full_cycle"
    else:
        job_type = "apply_only"

    # Clear logs
    log_file = get_user_log_file(user_id, "bot.log")
    try:
        with open(log_file, "w", encoding="utf-8") as f:
            f.write("")
    except Exception:
        pass

    # Add to queue
    job_id = JobQueue.add_job(user_id, job_type)
    return {"status": "started", "job_id": job_id, "message": "Sua solicitação foi adicionada à fila de execução com sucesso!"}


@router.post("/api/stop")
def stop_bot(current_user: dict = Depends(get_current_user)):
    user_id = current_user["id"]
    active_job = JobQueue.get_active_job_for_user(user_id)
    if active_job:
        JobQueue.cancel_job(active_job["id"])
        return {"status": "stopped", "message": "Sua execução foi cancelada/interrompida."}
    return {"status": "idle", "message": "Nenhuma execução ativa encontrada para parar."}


@router.get("/api/bot-status")
def bot_status(current_user: dict = Depends(get_current_user)):
    user_id = current_user["id"]
    active_job = JobQueue.get_active_job_for_user(user_id)
    if active_job:
        pos = JobQueue.get_queue_position(user_id, active_job["id"])
        return {
            "running": active_job["status"] == "running",
            "status": active_job["status"],
            "queue_position": pos,
            "job_id": active_job["id"],
            "job_type": active_job["job_type"]
        }
    
    # Return last completed job info
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM job_queue WHERE user_id = ? ORDER BY id DESC LIMIT 1", (user_id,))
            row = cursor.fetchone()
        if row:
            job = dict(row)
            return {
                "running": False,
                "status": job["status"],
                "last_job_id": job["id"],
                "last_exit_code": 0 if job["status"] == "done" else 1
            }
    except Exception:
        pass

    return {"running": False, "status": "idle"}


@router.get("/api/logs")
def get_logs(current_user: dict = Depends(get_current_user)):
    user_id = current_user["id"]
    log_file = get_user_log_file(user_id, "bot.log")
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

