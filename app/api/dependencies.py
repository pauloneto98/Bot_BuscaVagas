"""
API Dependencies — Bot Busca Vagas
Shared dependencies for FastAPI route protection.
"""

from fastapi import Header, HTTPException

from app.config import settings


def verify_token(authorization: str = Header(None)):
    """Verify Bearer token from Authorization header."""
    if settings.DISABLE_DASHBOARD_AUTH:
        return True
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Unauthorized")
    token = authorization.split(" ")[1]

    from app.api.auth import _active_tokens
    if token not in _active_tokens:
        raise HTTPException(status_code=401, detail="Unauthorized")
    return True
