from sqlalchemy import select
from sqlalchemy.orm import Session

from app.events import publish
from app.modules.auth.service import assign_workspace_role, list_user_workspace_ids
from app.modules.core.exceptions import ConflictError, NotFoundError
from app.modules.workspace.models import Project, Workspace


def create_workspace(db: Session, owner_id: str, name: str, description: str) -> Workspace:
    existing = db.execute(select(Workspace).where(Workspace.name == name)).scalar_one_or_none()
    if existing:
        raise ConflictError(f"workspace '{name}' already exists")

    workspace = Workspace(name=name, description=description, owner_id=owner_id)
    db.add(workspace)
    db.commit()
    db.refresh(workspace)
    assign_workspace_role(db, owner_id, workspace.id, "owner")
    publish("workspace.created", {"id": workspace.id, "name": workspace.name})
    return workspace


def list_workspaces(db: Session, user_id: str) -> list[Workspace]:
    workspace_ids = list_user_workspace_ids(db, user_id)
    if not workspace_ids:
        return []
    return list(
        db.execute(select(Workspace).where(Workspace.id.in_(workspace_ids))).scalars()
    )


def get_workspace(db: Session, workspace_id: str) -> Workspace:
    workspace = db.get(Workspace, workspace_id)
    if workspace is None:
        raise NotFoundError(f"workspace '{workspace_id}' not found")
    return workspace


def create_project(
    db: Session, owner_id: str, workspace_id: str, name: str, environment: str
) -> Project:
    get_workspace(db, workspace_id)  # 404s if missing
    project = Project(
        workspace_id=workspace_id, name=name, environment=environment, owner_id=owner_id
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    publish("project.created", {"id": project.id, "workspaceId": workspace_id, "name": name})
    return project


def list_projects(db: Session, workspace_id: str) -> list[Project]:
    return list(
        db.execute(select(Project).where(Project.workspace_id == workspace_id)).scalars()
    )


def get_project(db: Session, project_id: str) -> Project:
    project = db.get(Project, project_id)
    if project is None:
        raise NotFoundError(f"project '{project_id}' not found")
    return project


def get_workspace_id_for_project(db: Session, project_id: str) -> str:
    return get_project(db, project_id).workspace_id
