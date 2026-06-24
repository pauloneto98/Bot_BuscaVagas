"""
Authentication — Bot Busca Vagas API
Handles CPF validation, login, and token management.
"""

import secrets

from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel

from app.utils.security import validate_cpf, verify_password

router = APIRouter()

_active_tokens: set[str] = set()


class LoginPayload(BaseModel):
    cpf: str
    password: str


@router.post("/api/login")
def login(payload: LoginPayload):
    if not validate_cpf(payload.cpf):
        raise HTTPException(status_code=400, detail="CPF Invalido")

    from app.api.routes.config import _parse_env_file
    from app.utils.security import decrypt_secret
    env = _parse_env_file()
    correct_password = decrypt_secret(env.get("DASHBOARD_PASSWORD", "admin123"))

    if payload.password != correct_password:
        raise HTTPException(status_code=401, detail="Senha incorreta")

    token = secrets.token_hex(32)
    _active_tokens.add(token)

    return {"status": "ok", "token": token, "message": "Login realizado com sucesso"}
