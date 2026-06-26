import os
import re

from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from pydantic import BaseModel

from app.config import settings
from app.api.dependencies import get_current_user
from app.db.repositories import UserConfigRepository, UserRepository
from app.utils.security import verify_password, hash_password
from app.utils.crypto import encrypt_val, decrypt_val
from app.utils.paths import get_user_data_dir

router = APIRouter()


class ConfigPayload(BaseModel):
    gemini_api_key: str = ""
    email_address: str = ""
    email_app_password: str = ""
    email_cc: str = ""
    candidate_name: str = ""
    resume_pdf: str = ""
    max_jobs_per_category: int = 5
    search_presencial: bool = True
    search_portugal: bool = True
    request_delay_min: float = 2
    request_delay_max: float = 5
    dashboard_password: str = ""
    personalize_only_emails: bool = True
    use_base_resume_only: bool = False
    job_categories: str = ""
    presencial_cities: str = ""
    confirm_password: str = ""


@router.get("/api/config")
def get_config(current_user: dict = Depends(get_current_user)):
    """Retrieve configurations for the logged-in user from database."""
    user_id = current_user["id"]
    cfg = UserConfigRepository.get_by_user_id(user_id)
    
    if not cfg:
        # Fallback default configuration if not initialized
        cfg = {
            "candidate_name": current_user["name"],
            "resume_filename": "",
            "email_address": current_user["email"],
            "email_app_password": "",
            "email_cc": "",
            "job_categories": [],
            "presencial_cities": [],
            "search_presencial": True,
            "search_portugal": True,
            "max_jobs_per_category": 5
        }

    # Decrypt SMTP app password using Fernet helper
    email_pass_raw = decrypt_val(cfg.get("email_app_password", ""))
    masked_email_pass = f"{email_pass_raw[:4]}..." if len(email_pass_raw) > 4 else email_pass_raw

    # Convert lists to comma-separated strings for frontend compatibility
    cats = cfg.get("job_categories", [])
    cats_str = ", ".join(cats) if isinstance(cats, list) else str(cats)
    
    cities = cfg.get("presencial_cities", [])
    cities_str = ", ".join(cities) if isinstance(cities, list) else str(cities)

    return {
        "gemini_api_key": "********",  # Shared key is hidden from regular users
        "email_address": cfg.get("email_address", ""),
        "email_app_password": masked_email_pass,
        "email_cc": cfg.get("email_cc", ""),
        "candidate_name": cfg.get("candidate_name", ""),
        "resume_pdf": cfg.get("resume_filename", ""),
        "max_jobs_per_category": int(cfg.get("max_jobs_per_category", 5)),
        "search_presencial": bool(cfg.get("search_presencial", True)),
        "search_portugal": bool(cfg.get("search_portugal", True)),
        "request_delay_min": settings.REQUEST_DELAY_MIN,  # Global server delay config
        "request_delay_max": settings.REQUEST_DELAY_MAX,  # Global server delay config
        "dashboard_password": "●●●●●●●●",  # Masked password field
        "personalize_only_emails": settings.PERSONALIZE_ONLY_EMAILS,
        "use_base_resume_only": True,  # Default flow behavior
        "job_categories": cats_str,
        "presencial_cities": cities_str,
    }


@router.post("/api/config")
def save_config(payload: ConfigPayload, current_user: dict = Depends(get_current_user)):
    """Save user configurations and optionally update dashboard password."""
    user_id = current_user["id"]
    
    # Authenticate config modification with user's current password
    if not payload.confirm_password or not verify_password(payload.confirm_password, current_user["password_hash"]):
        raise HTTPException(status_code=401, detail="Senha de confirmacao incorreta ou nao informada.")

    # Retrieve existing user config to verify masked inputs
    old_cfg = UserConfigRepository.get_by_user_id(user_id) or {}
    
    # Handle SMTP password decryption verification/encryption
    new_app_pass = payload.email_app_password
    if new_app_pass.endswith("...") and old_cfg.get("email_app_password"):
        email_pass_encrypted = old_cfg["email_app_password"]
    else:
        email_pass_encrypted = encrypt_val(new_app_pass)

    # Parse comma-separated categories and cities into clean lists
    categories_list = [c.strip() for c in payload.job_categories.split(",") if c.strip()]
    cities_list = [c.strip() for c in payload.presencial_cities.split(",") if c.strip()]

    # Save to user_config
    UserConfigRepository.save(user_id, {
        "candidate_name": payload.candidate_name.strip(),
        "resume_filename": payload.resume_pdf,
        "email_address": payload.email_address.strip(),
        "email_app_password": email_pass_encrypted,
        "email_cc": payload.email_cc.strip(),
        "job_categories": categories_list,
        "presencial_cities": cities_list,
        "search_presencial": payload.search_presencial,
        "search_portugal": payload.search_portugal,
        "max_jobs_per_category": payload.max_jobs_per_category
    })

    # Support updating user's dashboard login password
    new_dash_pass = payload.dashboard_password.strip()
    if new_dash_pass and not new_dash_pass.startswith("●"):
        # Hash new password and update in users table
        new_hash = hash_password(new_dash_pass)
        UserRepository.update_password(user_id, new_hash)

    return {"status": "ok", "message": "Configuracoes salvas com sucesso!"}


@router.post("/api/upload-resume")
async def upload_resume(file: UploadFile = File(...), current_user: dict = Depends(get_current_user)):
    """Upload resume PDF and store it inside the user's isolated directory."""
    user_id = current_user["id"]
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(400, "Apenas arquivos PDF sao aceitos.")

    basename = os.path.basename(file.filename)
    safe_name = re.sub(r"[^\w.\-]", "_", basename)
    
    # Store the file inside user's isolated data folder
    user_dir = get_user_data_dir(user_id)
    dest = os.path.join(user_dir, safe_name)

    with open(dest, "wb") as f:
        content = await file.read()
        f.write(content)

    # Save filename to user's config
    cfg = UserConfigRepository.get_by_user_id(user_id) or {}
    cfg["resume_filename"] = safe_name
    UserConfigRepository.save(user_id, cfg)

    # Clear user-specific base resume parsing cache if exists
    cache_file = os.path.join(user_dir, "base_resume_parsed.json")
    if os.path.exists(cache_file):
        try:
            os.remove(cache_file)
        except OSError:
            pass

    return {"status": "ok", "filename": safe_name, "message": f"Curriculo '{safe_name}' salvo com sucesso!"}

