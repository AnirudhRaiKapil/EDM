from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.modules.core.models import TimestampMixin, UUIDPrimaryKeyMixin


class User(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "auth_users"

    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")


class RoleAssignment(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """02-domain-model.md: binds (User, Role, scope, scopeId). MVP only needs
    workspace-scoped 'owner'/'member' roles; finer-grained roles are V2 (edm-governance)."""

    __tablename__ = "auth_role_assignments"

    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("auth_users.id"), nullable=False)
    role_name: Mapped[str] = mapped_column(String(50), nullable=False)
    scope: Mapped[str] = mapped_column(String(20), nullable=False, default="workspace")
    scope_id: Mapped[str] = mapped_column(String(36), nullable=False)
