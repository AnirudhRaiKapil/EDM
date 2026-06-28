from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.modules.auth.models import User
from app.modules.pipeline import service
from app.modules.pipeline.schemas import PipelineCreate, PipelineRead
from app.permissions import require_pipeline_access, require_project_access

router = APIRouter(tags=["pipeline"])


@router.post("/projects/{project_id}/pipelines", response_model=PipelineRead, status_code=201)
def create_pipeline(
    project_id: str,
    payload: PipelineCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_project_access(db, current_user.id, project_id)
    return service.create_pipeline(
        db,
        current_user.id,
        project_id,
        payload.source_id,
        payload.name,
        payload.output_dataset_name,
        payload.output_layer,
        payload.transformations,
    )


@router.get("/projects/{project_id}/pipelines", response_model=list[PipelineRead])
def list_pipelines(
    project_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_project_access(db, current_user.id, project_id)
    return service.list_pipelines(db, project_id)


@router.get("/pipelines/{pipeline_id}", response_model=PipelineRead)
def get_pipeline(
    pipeline_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_pipeline_access(db, current_user.id, pipeline_id)
    return service.get_pipeline(db, pipeline_id)
