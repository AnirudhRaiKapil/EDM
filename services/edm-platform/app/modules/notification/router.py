from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.modules.auth.models import User
from app.modules.notification import service
from app.modules.notification.schemas import NotificationChannelCreate, NotificationChannelRead
from app.permissions import require_notification_channel_access, require_project_access

router = APIRouter(tags=["notification"])


@router.post(
    "/projects/{project_id}/notification-channels",
    response_model=NotificationChannelRead,
    status_code=201,
)
def create_channel(
    project_id: str,
    payload: NotificationChannelCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_project_access(db, current_user.id, project_id)
    return service.create_channel(db, current_user.id, project_id, payload.type, payload.config)


@router.get(
    "/projects/{project_id}/notification-channels", response_model=list[NotificationChannelRead]
)
def list_channels(
    project_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_project_access(db, current_user.id, project_id)
    return service.list_channels(db, project_id)


@router.delete("/notification-channels/{channel_id}", status_code=204)
def delete_channel(
    channel_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_notification_channel_access(db, current_user.id, channel_id)
    channel = service.get_channel(db, channel_id)
    service.delete_channel(db, channel)
