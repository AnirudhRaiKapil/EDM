import base64
import hashlib
import json

from cryptography.fernet import Fernet, InvalidToken

from app.config import settings


def _fernet() -> Fernet:
    key_bytes = hashlib.sha256(settings.secret_encryption_key.encode()).digest()
    return Fernet(base64.urlsafe_b64encode(key_bytes))


def encrypt_credentials(credentials: dict) -> str:
    payload = json.dumps(credentials).encode()
    return _fernet().encrypt(payload).decode()


def decrypt_credentials(ciphertext: str) -> dict:
    try:
        payload = _fernet().decrypt(ciphertext.encode())
    except InvalidToken as exc:
        raise ValueError("credentials could not be decrypted (wrong key, or corrupted data)") from exc
    return json.loads(payload)
