from sqlalchemy import select
from sqlalchemy.orm import Session

from app.events import publish
from app.modules.audit import service as audit_service
from app.modules.auth.models import RoleAssignment, User
from app.modules.auth.security import DUMMY_HASH, create_access_token, hash_password, verify_password
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
    audit_service.record_event(db, "user.registered", actor_user_id=user.id, subject_email=email)
    return user


def authenticate_user(db: Session, email: str, password: str) -> User:
    user = db.execute(select(User).where(User.email == email)).scalar_one_or_none()
    # Always run a PBKDF2 verification, even when there's no user to check against --
    # otherwise a "no such user" response returns measurably faster than a "wrong
    # password" one (no hashing work done), letting an attacker enumerate valid emails
    # by timing alone. DUMMY_HASH is never a real password's hash; this call always
    # returns False, it just costs the same as a real check.
    password_hash = user.password_hash if user else DUMMY_HASH
    password_ok = verify_password(password, password_hash)
    if not user or not password_ok:
        # actor_user_id is set when the account exists (wrong password) and left null
        # when it doesn't (no such user) -- both cases still record subject_email, so
        # "who has been trying to log into my account" is answerable either way via
        # GET /users/me/audit-events.
        audit_service.record_event(
            db, "user.login_failed", actor_user_id=user.id if user else None, subject_email=email
        )
        raise UnauthorizedError("invalid email or password")
    audit_service.record_event(db, "user.login_succeeded", actor_user_id=user.id, subject_email=email)
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
        assignment = existing
    else:
        assignment = RoleAssignment(
            user_id=user_id, role_name=role_name, scope="workspace", scope_id=workspace_id
        )
        db.add(assignment)
        db.commit()
        db.refresh(assignment)

    audit_service.record_event(
        db,
        "role.assigned",
        workspace_id=workspace_id,
        entity_type="user",
        entity_id=user_id,
        metadata={"role": role_name},
    )
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
