from fastapi import Header, HTTPException, Depends
from app.config import settings
from app.utils.security import decode_access_token
from app.db.repositories import UserRepository


def get_current_user(authorization: str = Header(None)) -> dict:
    """Validate JWT token and return active user profile. Supports local auth bypass."""
    if settings.DISABLE_DASHBOARD_AUTH:
        # Bypass: Return default admin user (ID = 1) for local debugging
        admin = UserRepository.get_by_id(1)
        if admin:
            return admin
        raise HTTPException(status_code=401, detail="Bypass failed: Default admin not found")

    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Token de autorizacao ausente ou malformatado")
    
    token = authorization.split(" ")[1]
    payload = decode_access_token(token)
    if not payload or "user_id" not in payload:
        raise HTTPException(status_code=401, detail="Token invalido ou expirado")
        
    user_id = payload["user_id"]
    user = UserRepository.get_by_id(user_id)
    if not user:
        raise HTTPException(status_code=401, detail="Usuario nao encontrado")
    if not user.get("is_active", 1):
        raise HTTPException(status_code=401, detail="Usuario inativo")
        
    return user


def get_current_admin(current_user: dict = Depends(get_current_user)) -> dict:
    """Verify that current authenticated user is an administrator."""
    if not current_user.get("is_admin", 0):
        raise HTTPException(status_code=403, detail="Acesso restrito a administradores")
    return current_user


def verify_token(authorization: str = Header(None)) -> bool:
    """Legacy/Simple token verification helper that matches JWT validity."""
    try:
        get_current_user(authorization)
        return True
    except HTTPException as e:
        raise e

