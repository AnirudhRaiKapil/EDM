import json
import os
from pathlib import Path

DEFAULT_API_URL = "http://localhost:8000/api/v1"
CONFIG_DIR = Path(os.environ.get("EDM_CLI_HOME", Path.home() / ".edm"))
CREDENTIALS_PATH = CONFIG_DIR / "credentials.json"


def get_api_url() -> str:
    return os.environ.get("EDM_API_URL", DEFAULT_API_URL)


def save_token(token: str, email: str) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CREDENTIALS_PATH.write_text(json.dumps({"token": token, "email": email}))
    CREDENTIALS_PATH.chmod(0o600)


def load_token() -> str | None:
    if not CREDENTIALS_PATH.is_file():
        return None
    return json.loads(CREDENTIALS_PATH.read_text()).get("token")


def load_email() -> str | None:
    if not CREDENTIALS_PATH.is_file():
        return None
    return json.loads(CREDENTIALS_PATH.read_text()).get("email")


def clear_token() -> None:
    if CREDENTIALS_PATH.is_file():
        CREDENTIALS_PATH.unlink()
