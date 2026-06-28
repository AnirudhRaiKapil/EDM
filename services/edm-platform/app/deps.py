from fastapi import Depends, Header
from sqlalchemy.orm import Session

from app.database import get_db
from app.modules.auth.models import User
from app.modules.auth.security import decode_access_token
from app.modules.auth.service import get_user_by_id
from app.modules.core.exceptions import UnauthorizedError


def get_current_user(
    authorization: str = Header(default=""),
    db: Session = Depends(get_db),
) -> User:
    if not authorization.startswith("Bearer "):
        raise UnauthorizedError("missing bearer token")
    token = authorization.removeprefix("Bearer ").strip()
    try:
        user_id = decode_access_token(token)
    except Exception as exc:
        raise UnauthorizedError("invalid or expired token") from exc

    user = get_user_by_id(db, user_id)
    if user is None:
        raise UnauthorizedError("user no longer exists")
    return user
