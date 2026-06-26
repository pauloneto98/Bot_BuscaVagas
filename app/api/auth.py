import datetime
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

from app.utils.security import hash_password, verify_password, create_access_token
from app.db.repositories import UserRepository, UserConfigRepository
from app.api.dependencies import get_current_user, get_current_admin

router = APIRouter()


class LoginPayload(BaseModel):
    email: str
    password: str


class CreateUserPayload(BaseModel):
    email: str
    password: str
    name: str
    is_admin: bool = False


@router.post("/api/login")
def login(payload: LoginPayload):
    """Authenticate email and password, return JWT token."""
    email = payload.email.strip().lower()
    user = UserRepository.get_by_email(email)
    
    if not user:
        raise HTTPException(status_code=401, detail="Email ou senha incorretos")
        
    if not user.get("is_active", 1):
        raise HTTPException(status_code=403, detail="Esta conta foi desativada")
        
    if not verify_password(payload.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Email ou senha incorretos")
        
    # Update last login timestamp
    UserRepository.update_last_login(user["id"])
    
    # Generate JWT Token (valid for 24h by default)
    token = create_access_token(
        data={"user_id": user["id"], "email": user["email"]},
        expires_delta=datetime.timedelta(hours=24)
    )
    
    return {
        "status": "ok",
        "token": token,
        "user": {
            "id": user["id"],
            "email": user["email"],
            "name": user["name"],
            "is_admin": bool(user["is_admin"])
        },
        "message": "Login realizado com sucesso"
    }


@router.post("/api/admin/create-user")
def create_user(payload: CreateUserPayload, admin: dict = Depends(get_current_admin)):
    """Create a new user and initialize empty settings. Protected: Admin Only."""
    email = payload.email.strip().lower()
    
    # Check if user already exists
    if UserRepository.get_by_email(email):
        raise HTTPException(status_code=400, detail="Este email ja esta cadastrado")
        
    # Create user
    password_hash = hash_password(payload.password)
    user_id = UserRepository.create({
        "email": email,
        "password_hash": password_hash,
        "name": payload.name.strip(),
        "is_admin": payload.is_admin,
        "is_active": True
    })
    
    if not user_id:
        raise HTTPException(status_code=500, detail="Erro ao criar usuario")
        
    # Initialize default user config
    UserConfigRepository.save(user_id, {
        "candidate_name": payload.name.strip(),
        "resume_filename": "",
        "email_address": email,
        "email_app_password": "",
        "email_cc": "",
        "job_categories": [],
        "presencial_cities": [],
        "search_presencial": True,
        "search_portugal": True,
        "max_jobs_per_category": 5
    })
    
    return {
        "status": "ok",
        "message": f"Usuario {payload.name} criado com sucesso",
        "user_id": user_id
    }


@router.get("/api/me")
def get_me(current_user: dict = Depends(get_current_user)):
    """Retrieve details of current authenticated user."""
    return {
        "id": current_user["id"],
        "email": current_user["email"],
        "name": current_user["name"],
        "is_admin": bool(current_user["is_admin"])
    }


@router.get("/api/admin/users")
def get_users_list(admin: dict = Depends(get_current_admin)):
    """List all users for admin dashboard. Protected: Admin Only."""
    users = UserRepository.get_all()
    # Normalize is_admin and is_active to bool
    for u in users:
        u["is_admin"] = bool(u["is_admin"])
        u["is_active"] = bool(u["is_active"])
    return {"status": "ok", "users": users}


@router.post("/api/admin/users/{target_user_id}/toggle")
def toggle_user_status(target_user_id: int, admin: dict = Depends(get_current_admin)):
    """Toggle a user's is_active status. Protected: Admin Only."""
    # Prevent self-deactivation
    if target_user_id == admin["id"]:
        raise HTTPException(status_code=400, detail="Você não pode desativar sua própria conta")
        
    user = UserRepository.get_by_id(target_user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")
        
    new_status = not bool(user["is_active"])
    UserRepository.update_status(target_user_id, new_status)
    
    status_str = "ativado" if new_status else "desativado"
    return {"status": "ok", "message": f"Usuário {user['name']} foi {status_str} com sucesso", "is_active": new_status}


