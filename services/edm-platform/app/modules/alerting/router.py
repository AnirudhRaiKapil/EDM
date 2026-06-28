from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.modules.alerting import service
from app.modules.alerting.schemas import AlertRead, AlertStatusUpdate
from app.modules.auth.models import User
from app.permissions import require_project_access

router = APIRouter(tags=["alerting"])


@router.get("/projects/{project_id}/alerts", response_model=list[AlertRead])
def list_alerts(
    project_id: str,
    status: str | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_project_access(db, current_user.id, project_id)
    return service.list_alerts(db, project_id, status)


@router.patch("/alerts/{alert_id}", response_model=AlertRead)
def update_alert_status(
    alert_id: str,
    payload: AlertStatusUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    alert = service.get_alert(db, alert_id)
    require_project_access(db, current_user.id, alert.project_id)
    return service.update_status(db, alert, payload.status)
