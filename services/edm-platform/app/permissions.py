from sqlalchemy.orm import Session

from app.modules.auth import service as auth_service
from app.modules.auth.service import WORKSPACE_ROLES
from app.modules.job import service as job_service
from app.modules.notebook import service as notebook_service
from app.modules.notification import service as notification_service
from app.modules.pipeline import service as pipeline_service
from app.modules.source import service as source_service
from app.modules.workspace import service as workspace_service


def require_project_access(
    db: Session, user_id: str, project_id: str, allowed: list[str] = WORKSPACE_ROLES
) -> str:
    workspace_id = workspace_service.get_workspace_id_for_project(db, project_id)
    return auth_service.require_workspace_role(db, user_id, workspace_id, allowed)


def require_source_access(
    db: Session, user_id: str, source_id: str, allowed: list[str] = WORKSPACE_ROLES
) -> str:
    source = source_service.get_source(db, source_id)
    return require_project_access(db, user_id, source.project_id, allowed)


def require_pipeline_access(
    db: Session, user_id: str, pipeline_id: str, allowed: list[str] = WORKSPACE_ROLES
) -> str:
    pipeline = pipeline_service.get_pipeline(db, pipeline_id)
    return require_project_access(db, user_id, pipeline.project_id, allowed)


def require_job_access(
    db: Session, user_id: str, job_id: str, allowed: list[str] = WORKSPACE_ROLES
) -> str:
    job = job_service.get_job(db, job_id)
    return require_pipeline_access(db, user_id, job.pipeline_id, allowed)


def require_notebook_access(
    db: Session, user_id: str, notebook_id: str, allowed: list[str] = WORKSPACE_ROLES
) -> str:
    notebook = notebook_service.get_notebook(db, notebook_id)
    return require_project_access(db, user_id, notebook.project_id, allowed)


def require_notification_channel_access(
    db: Session, user_id: str, channel_id: str, allowed: list[str] = WORKSPACE_ROLES
) -> str:
    channel = notification_service.get_channel(db, channel_id)
    return require_project_access(db, user_id, channel.project_id, allowed)
