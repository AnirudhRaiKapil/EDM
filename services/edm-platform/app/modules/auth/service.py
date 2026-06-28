from sqlalchemy import select
from sqlalchemy.orm import Session

from app.events import publish
from app.modules.auth.models import RoleAssignment, User
from app.modules.auth.security import create_access_token, hash_password, verify_password
from app.modules.core.exceptions import ConflictError, ForbiddenError, NotFoundError, UnauthorizedError

WORKSPACE_ROLES = ["owner", "member"]


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


def get_user_by_email(db: Session, email: str) -> User | None:
    return db.execute(select(User).where(User.email == email)).scalar_one_or_none()


def assign_workspace_role(db: Session, user_id: str, workspace_id: str, role_name: str) -> RoleAssignment:
    existing = db.execute(
        select(RoleAssignment).where(
            RoleAssignment.user_id == user_id,
            RoleAssignment.scope == "workspace",
            RoleAssignment.scope_id == workspace_id,
        )
    ).scalar_one_or_none()
    if existing:
        existing.role_name = role_name
        db.add(existing)
        db.commit()
        db.refresh(existing)
        return existing

    assignment = RoleAssignment(
        user_id=user_id, role_name=role_name, scope="workspace", scope_id=workspace_id
    )
    db.add(assignment)
    db.commit()
    db.refresh(assignment)
    return assignment


def get_workspace_role(db: Session, user_id: str, workspace_id: str) -> str | None:
    assignment = db.execute(
        select(RoleAssignment).where(
            RoleAssignment.user_id == user_id,
            RoleAssignment.scope == "workspace",
            RoleAssignment.scope_id == workspace_id,
        )
    ).scalar_one_or_none()
    return assignment.role_name if assignment else None


def list_user_workspace_ids(db: Session, user_id: str) -> list[str]:
    assignments = db.execute(
        select(RoleAssignment).where(
            RoleAssignment.user_id == user_id, RoleAssignment.scope == "workspace"
        )
    ).scalars()
    return [a.scope_id for a in assignments]


def list_workspace_members(db: Session, workspace_id: str) -> list[RoleAssignment]:
    return list(
        db.execute(
            select(RoleAssignment).where(
                RoleAssignment.scope == "workspace", RoleAssignment.scope_id == workspace_id
            )
        ).scalars()
    )


def require_workspace_role(
    db: Session, user_id: str, workspace_id: str, allowed: list[str] = WORKSPACE_ROLES
) -> str:
    role_name = get_workspace_role(db, user_id, workspace_id)
    if role_name is None:
        raise NotFoundError(f"workspace '{workspace_id}' not found")
    if role_name not in allowed:
        raise ForbiddenError(f"role '{role_name}' cannot perform this action; requires one of {allowed}")
    return role_name
