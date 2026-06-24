import os
import base64
from cryptography.fernet import Fernet
from app.config import settings

# Caminho para o arquivo da chave
KEY_FILE = os.path.join(settings.DATA_DIR, "secret.key")

def get_or_create_key() -> bytes:
    """Retorna a chave existente ou gera uma nova e a salva no local adequado."""
    os.makedirs(settings.DATA_DIR, exist_ok=True)
    if os.path.exists(KEY_FILE):
        with open(KEY_FILE, "rb") as f:
            key = f.read().strip()
            if key:
                return key
    
    # Gerar nova chave
    key = Fernet.generate_key()
    with open(KEY_FILE, "wb") as f:
        f.write(key)
    return key

def encrypt_val(val: str) -> str:
    """Criptografa um valor de texto usando Fernet."""
    if not val:
        return ""
    try:
        key = get_or_create_key()
        f = Fernet(key)
        encrypted = f.encrypt(val.encode("utf-8"))
        # Retorna o prefixo ENC# para sabermos que o campo está criptografado no arquivo env
        return f"ENC#{encrypted.decode('utf-8')}"
    except Exception:
        return val

def decrypt_val(val: str) -> str:
    """Descriptografa um valor de texto criptografado com o prefixo ENC#."""
    if not val:
        return ""
    if not val.startswith("ENC#"):
        return val
    try:
        encrypted_part = val[4:]
        key = get_or_create_key()
        f = Fernet(key)
        decrypted = f.decrypt(encrypted_part.encode("utf-8"))
        return decrypted.decode("utf-8")
    except Exception:
        # Se falhar por algum motivo (ex: chave alterada), retorna vazio ou o próprio valor para não quebrar
        return ""
