"""
Config & Upload Routes — /api/config, /api/upload-resume
Manages application settings and resume file uploads.
"""

import os
import re

from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from pydantic import BaseModel

from app.config import settings
from app.api.dependencies import verify_token

router = APIRouter()


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
    dashboard_password: str = "admin123"
    personalize_only_emails: bool = True


def _parse_env_file() -> dict:
    """Read config.env into a dict."""
    config = {}
    if not os.path.exists(settings.CONFIG_FILE):
        return config
    with open(settings.CONFIG_FILE, "r", encoding="utf-8", errors="replace") as f:
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
    if os.path.exists(settings.CONFIG_FILE):
        with open(settings.CONFIG_FILE, "r", encoding="utf-8") as f:
            lines = f.readlines()

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

    for key, value in config.items():
        if key not in written_keys:
            new_lines.append(f"{key}={value}\n")

    with open(settings.CONFIG_FILE, "w", encoding="utf-8") as f:
        f.writelines(new_lines)


@router.get("/api/config", dependencies=[Depends(verify_token)])
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
        "dashboard_password": raw.get("DASHBOARD_PASSWORD", "admin123"),
        "personalize_only_emails": raw.get("PERSONALIZE_ONLY_EMAILS", "true").lower() == "true",
    }


@router.post("/api/config", dependencies=[Depends(verify_token)])
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
        "PERSONALIZE_ONLY_EMAILS": str(payload.personalize_only_emails).lower(),
    }
    if hasattr(payload, 'dashboard_password') and payload.dashboard_password:
        env_map["DASHBOARD_PASSWORD"] = payload.dashboard_password

    _write_env_file(env_map)
    return {"status": "ok", "message": "Configuracoes salvas com sucesso!"}


@router.post("/api/upload-resume", dependencies=[Depends(verify_token)])
async def upload_resume(file: UploadFile = File(...)):
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(400, "Apenas arquivos PDF sao aceitos.")

    basename = os.path.basename(file.filename)
    safe_name = re.sub(r"[^\w.\-]", "_", basename)
    dest = os.path.join(settings.BASE_DIR, safe_name)

    with open(dest, "wb") as f:
        content = await file.read()
        f.write(content)

    env = _parse_env_file()
    env["RESUME_PDF"] = safe_name
    _write_env_file(env)

    return {"status": "ok", "filename": safe_name, "message": f"Curriculo '{safe_name}' salvo com sucesso!"}
