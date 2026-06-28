from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.modules.auth import service as auth_service
from app.modules.auth.models import User
from app.modules.core.exceptions import NotFoundError, ValidationFailedError
from app.modules.workspace import service
from app.modules.workspace.schemas import (
    MemberAssign,
    MemberRead,
    ProjectCreate,
    ProjectRead,
    WorkspaceCreate,
    WorkspaceRead,
)

router = APIRouter(tags=["workspace"])


@router.post("/workspaces", response_model=WorkspaceRead, status_code=201)
def create_workspace(
    payload: WorkspaceCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return service.create_workspace(db, current_user.id, payload.name, payload.description)


@router.get("/workspaces", response_model=list[WorkspaceRead])
def list_workspaces(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return service.list_workspaces(db, current_user.id)


@router.get("/workspaces/{workspace_id}", response_model=WorkspaceRead)
def get_workspace(
    workspace_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    auth_service.require_workspace_role(db, current_user.id, workspace_id)
    return service.get_workspace(db, workspace_id)


@router.post("/workspaces/{workspace_id}/members", response_model=MemberRead, status_code=201)
def add_member(
    workspace_id: str,
    payload: MemberAssign,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    auth_service.require_workspace_role(db, current_user.id, workspace_id, allowed=["owner"])
    if payload.role not in auth_service.WORKSPACE_ROLES:
        raise ValidationFailedError(f"role must be one of {auth_service.WORKSPACE_ROLES}")

    target_user = auth_service.get_user_by_email(db, payload.email)
    if target_user is None:
        raise NotFoundError(f"no user with email '{payload.email}'")

    assignment = auth_service.assign_workspace_role(db, target_user.id, workspace_id, payload.role)
    return MemberRead(user_id=target_user.id, email=target_user.email, role_name=assignment.role_name)


@router.get("/workspaces/{workspace_id}/members", response_model=list[MemberRead])
def list_members(
    workspace_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    auth_service.require_workspace_role(db, current_user.id, workspace_id)
    members = []
    for assignment in auth_service.list_workspace_members(db, workspace_id):
        user = auth_service.get_user_by_id(db, assignment.user_id)
        members.append(MemberRead(user_id=user.id, email=user.email, role_name=assignment.role_name))
    return members


@router.post("/workspaces/{workspace_id}/projects", response_model=ProjectRead, status_code=201)
def create_project(
    workspace_id: str,
    payload: ProjectCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    auth_service.require_workspace_role(db, current_user.id, workspace_id)
    return service.create_project(
        db, current_user.id, workspace_id, payload.name, payload.environment
    )


@router.get("/workspaces/{workspace_id}/projects", response_model=list[ProjectRead])
def list_projects(
    workspace_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    auth_service.require_workspace_role(db, current_user.id, workspace_id)
    return service.list_projects(db, workspace_id)
