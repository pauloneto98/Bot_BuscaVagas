import os
from app.config import settings

def get_user_data_dir(user_id: int) -> str:
    """Return the base directory for a specific user's files."""
    path = os.path.join(settings.DATA_DIR, "users", str(user_id))
    os.makedirs(path, exist_ok=True)
    return path

def get_user_log_file(user_id: int, log_name: str) -> str:
    """Return the absolute path to a specific log file for a user."""
    user_dir = get_user_data_dir(user_id)
    return os.path.join(user_dir, log_name)

def get_user_resume_dir(user_id: int) -> str:
    """Return the directory where customized resumes are generated for a user."""
    path = os.path.join(get_user_data_dir(user_id), "curriculos")
    os.makedirs(path, exist_ok=True)
    return path
