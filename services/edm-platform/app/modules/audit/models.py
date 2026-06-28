from datetime import datetime

from sqlalchemy import JSON, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.modules.core.models import UUIDPrimaryKeyMixin, utcnow


class AuditEvent(Base, UUIDPrimaryKeyMixin):
    """Immutable: written once by record_event(), never updated or deleted (no
    service function exists to do either). Deliberately not TimestampMixin -- an
    `updated_at` column would imply these rows can change, which they can't.

    actor_user_id is nullable: a failed login against an email with no matching
    account has no real actor. subject_email exists alongside actor_user_id
    specifically so "show me login activity against my own email" is answerable even
    for attempts where actor_user_id is null (see GET /users/me/audit-events)."""

    __tablename__ = "audit_events"

    actor_user_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    subject_email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    workspace_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    entity_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    entity_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    event_metadata: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
