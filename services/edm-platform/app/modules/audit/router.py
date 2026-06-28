from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.modules.audit import service
from app.modules.audit.schemas import AuditEventRead
from app.modules.auth.models import User
from app.modules.auth.service import require_workspace_role

router = APIRouter(tags=["audit"])


@router.get("/workspaces/{workspace_id}/audit-events", response_model=list[AuditEventRead])
def list_workspace_audit_events(
    workspace_id: str,
    limit: int = service.DEFAULT_LIST_LIMIT,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Owner-only: this log can reveal who has access to what and when credentials
    # were rotated, which is exactly the kind of thing a plain member shouldn't see
    # about their own workspace.
    require_workspace_role(db, current_user.id, workspace_id, allowed=["owner"])
    return service.list_workspace_events(db, workspace_id, limit)


@router.get("/users/me/audit-events", response_model=list[AuditEventRead])
def list_my_audit_events(
    limit: int = service.DEFAULT_LIST_LIMIT,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return service.list_my_events(db, current_user.id, current_user.email, limit)
