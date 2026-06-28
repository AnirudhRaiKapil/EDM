import hashlib
import hmac
import os
from datetime import datetime, timedelta, timezone

import jwt

from app.config import settings

# OWASP (2023) recommended minimum for PBKDF2-HMAC-SHA256. The count is embedded in
# every stored hash (see hash_password) specifically so a future increase here doesn't
# invalidate already-stored hashes the way a bare constant would -- old hashes keep
# verifying against the iteration count they were actually created with.
_PBKDF2_ITERATIONS = 600_000

# A fixed, valid-shaped hash with no real password behind it, used by verify_password's
# caller to keep a "user not found" lookup and a "wrong password" lookup the same number
# of PBKDF2 rounds -- otherwise the two cases are distinguishable by response timing
# alone (an attacker can enumerate valid emails just by measuring latency).
DUMMY_HASH = f"600000${os.urandom(16).hex()}${os.urandom(32).hex()}"


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, _PBKDF2_ITERATIONS)
    return f"{_PBKDF2_ITERATIONS}${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored_hash: str) -> bool:
    iterations_str, salt_hex, digest_hex = stored_hash.split("$")
    salt = bytes.fromhex(salt_hex)
    expected = bytes.fromhex(digest_hex)
    actual = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, int(iterations_str))
    return hmac.compare_digest(expected, actual)


def create_access_token(subject: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expire_minutes)
    payload = {"sub": subject, "exp": expire}
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")


def decode_access_token(token: str) -> str:
    payload = jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
    return payload["sub"]
