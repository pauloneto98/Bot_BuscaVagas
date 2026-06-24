"""
Security helpers for the Bot Busca Vagas application.
Includes secret encryption, password hashing, and CPF validation.
"""

import hashlib
import os
import secrets
from cryptography.fernet import Fernet, InvalidToken


def _get_fernet() -> Fernet | None:
    encryption_key = os.getenv("ENCRYPTION_KEY", "").strip()
    if not encryption_key:
        from app.utils.crypto import get_or_create_key
        try:
            return Fernet(get_or_create_key())
        except Exception:
            return None

    try:
        return Fernet(encryption_key.encode("utf-8") if isinstance(encryption_key, str) else encryption_key)
    except Exception:
        return None


def encrypt_secret(value: str) -> str:
    if not value:
        return ""
    fernet = _get_fernet()
    if not fernet:
        return value
    token = fernet.encrypt(value.encode("utf-8"))
    return f"ENC({token.decode('utf-8')})"


def decrypt_secret(value: str) -> str:
    if not isinstance(value, str):
        return ""
    if not value.startswith("ENC(") or not value.endswith(")"):
        return value

    fernet = _get_fernet()
    if not fernet:
        return value

    try:
        cipher_text = value[4:-1].encode("utf-8")
        return fernet.decrypt(cipher_text).decode("utf-8")
    except InvalidToken:
        return value


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        200000,
    )
    return f"pbkdf2_sha256${salt}${digest.hex()}"


def verify_password(password: str, stored_hash: str) -> bool:
    if not stored_hash:
        return False
    if stored_hash.startswith("pbkdf2_sha256$"):
        try:
            _, salt, digest_hex = stored_hash.split("$", 2)
        except ValueError:
            return False
        digest = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt.encode("utf-8"),
            200000,
        )
        return secrets.compare_digest(digest.hex(), digest_hex)
    return secrets.compare_digest(password, stored_hash)


def validate_cpf(cpf: str) -> bool:
    cpf = ''.join(filter(str.isdigit, cpf))
    if len(cpf) != 11 or len(set(cpf)) == 1:
        return False
    for i in range(9, 11):
        value = sum((int(cpf[num]) * ((i + 1) - num) for num in range(0, i)))
        digit = ((value * 10) % 11) % 10
        if digit != int(cpf[i]):
            return False
    return True
