from sqlalchemy import select
from sqlalchemy.orm import Session

from app.events import publish
from app.modules.alerting.models import Alert
from app.modules.core.exceptions import NotFoundError, ValidationFailedError
from app.modules.notification.service import dispatch_alert

SEVERITIES = ["info", "warning", "critical"]
STATUSES = ["open", "acknowledged", "resolved"]


def create_alert(
    db: Session,
    project_id: str,
    source_entity_type: str,
    source_entity_id: str,
    severity: str,
    message: str,
) -> Alert:
    alert = Alert(
        project_id=project_id,
        source_entity_type=source_entity_type,
        source_entity_id=source_entity_id,
        severity=severity,
        message=message,
    )
    db.add(alert)
    db.commit()
    db.refresh(alert)
    publish(
        "alert.created",
        {"id": alert.id, "projectId": project_id, "severity": severity, "message": message},
    )
    dispatch_alert(db, alert)
    return alert


def list_alerts(db: Session, project_id: str, status: str | None = None) -> list[Alert]:
    stmt = select(Alert).where(Alert.project_id == project_id).order_by(Alert.created_at.desc())
    if status:
        stmt = stmt.where(Alert.status == status)
    return list(db.execute(stmt).scalars())


def get_alert(db: Session, alert_id: str) -> Alert:
    alert = db.get(Alert, alert_id)
    if alert is None:
        raise NotFoundError(f"alert '{alert_id}' not found")
    return alert


def update_status(db: Session, alert: Alert, status: str) -> Alert:
    if status not in STATUSES:
        raise ValidationFailedError(f"status must be one of {STATUSES}")
    alert.status = status
    db.add(alert)
    db.commit()
    db.refresh(alert)
    return alert
