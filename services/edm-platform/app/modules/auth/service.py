from sqlalchemy import select
from sqlalchemy.orm import Session

from app.events import publish
from app.modules.auth.models import User
from app.modules.auth.security import create_access_token, hash_password, verify_password
from app.modules.core.exceptions import ConflictError, UnauthorizedError


def register_user(db: Session, email: str, display_name: str, password: str) -> User:
    existing = db.execute(select(User).where(User.email == email)).scalar_one_or_none()
    if existing:
        raise ConflictError(f"user with email {email} already exists")

    user = User(email=email, display_name=display_name, password_hash=hash_password(password))
    db.add(user)
    db.commit()
    db.refresh(user)
    publish("user.created", {"id": user.id, "email": user.email})
    return user


def authenticate_user(db: Session, email: str, password: str) -> User:
    user = db.execute(select(User).where(User.email == email)).scalar_one_or_none()
    if not user or not verify_password(password, user.password_hash):
        raise UnauthorizedError("invalid email or password")
    return user


def issue_token(user: User) -> str:
    return create_access_token(subject=user.id)


def get_user_by_id(db: Session, user_id: str) -> User | None:
    return db.get(User, user_id)
