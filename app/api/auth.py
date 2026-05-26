"""
Authentication — Bot Busca Vagas API
Handles CPF validation, login, and token management.
"""

import secrets

from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel

router = APIRouter()

_active_tokens: set[str] = set()


class LoginPayload(BaseModel):
    cpf: str
    password: str


def validate_cpf(cpf: str) -> bool:
    """Validate a Brazilian CPF number."""
    cpf = ''.join(filter(str.isdigit, cpf))
    if len(cpf) != 11 or len(set(cpf)) == 1:
        return False
    for i in range(9, 11):
        value = sum((int(cpf[num]) * ((i+1) - num) for num in range(0, i)))
        digit = ((value * 10) % 11) % 10
        if digit != int(cpf[i]):
            return False
    return True


@router.post("/api/login")
def login(payload: LoginPayload):
    if not validate_cpf(payload.cpf):
        raise HTTPException(status_code=400, detail="CPF Invalido")

    from app.api.routes.config import _parse_env_file
    env = _parse_env_file()
    correct_password = env.get("DASHBOARD_PASSWORD", "admin123")

    if payload.password != correct_password:
        raise HTTPException(status_code=401, detail="Senha incorreta")

    token = secrets.token_hex(32)
    _active_tokens.add(token)

    return {"status": "ok", "token": token, "message": "Login realizado com sucesso"}
