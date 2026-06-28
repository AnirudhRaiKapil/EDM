from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.audit.models import AuditEvent

DEFAULT_LIST_LIMIT = 100
MAX_LIST_LIMIT = 500


def record_event(
    db: Session,
    action: str,
    actor_user_id: str | None = None,
    subject_email: str | None = None,
    workspace_id: str | None = None,
    entity_type: str | None = None,
    entity_id: str | None = None,
    metadata: dict | None = None,
) -> AuditEvent:
    """Writes one audit row. Never raises on behalf of the caller's main operation --
    callers append this after their own work succeeds (or, for login failures, instead
    of raising immediately), so a recording bug here is never an excuse to fail an
    unrelated request. There is deliberately no update/delete: this module has no
    function that does either."""
    event = AuditEvent(
        action=action,
        actor_user_id=actor_user_id,
        subject_email=subject_email,
        workspace_id=workspace_id,
        entity_type=entity_type,
        entity_id=entity_id,
        event_metadata=metadata or {},
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


def list_workspace_events(db: Session, workspace_id: str, limit: int = DEFAULT_LIST_LIMIT) -> list[AuditEvent]:
    limit = min(limit, MAX_LIST_LIMIT)
    return list(
        db.execute(
            select(AuditEvent)
            .where(AuditEvent.workspace_id == workspace_id)
            .order_by(AuditEvent.created_at.desc())
            .limit(limit)
        ).scalars()
    )


def list_my_events(db: Session, user_id: str, email: str, limit: int = DEFAULT_LIST_LIMIT) -> list[AuditEvent]:
    limit = min(limit, MAX_LIST_LIMIT)
    return list(
        db.execute(
            select(AuditEvent)
            .where((AuditEvent.actor_user_id == user_id) | (AuditEvent.subject_email == email))
            .order_by(AuditEvent.created_at.desc())
            .limit(limit)
        ).scalars()
    )
