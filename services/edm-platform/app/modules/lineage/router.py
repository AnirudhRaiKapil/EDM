from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.modules.auth.models import User
from app.modules.catalog.service import get_dataset
from app.modules.lineage import service
from app.modules.lineage.schemas import LineageGraphRead
from app.modules.pipeline.service import get_pipeline
from app.modules.source.service import get_source
from app.permissions import require_project_access

router = APIRouter(tags=["lineage"])


def _graph(db: Session, entity_type: str, entity_id: str) -> LineageGraphRead:
    return LineageGraphRead(
        entity_type=entity_type,
        entity_id=entity_id,
        upstream=service.get_upstream(db, entity_type, entity_id),
        downstream=service.get_downstream(db, entity_type, entity_id),
    )


@router.get("/lineage/datasets/{dataset_id}", response_model=LineageGraphRead)
def dataset_lineage(
    dataset_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    dataset = get_dataset(db, dataset_id)
    require_project_access(db, current_user.id, dataset.project_id)
    return _graph(db, "dataset", dataset_id)


@router.get("/lineage/sources/{source_id}", response_model=LineageGraphRead)
def source_lineage(
    source_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    source = get_source(db, source_id)
    require_project_access(db, current_user.id, source.project_id)
    return _graph(db, "source", source_id)


@router.get("/lineage/pipelines/{pipeline_id}", response_model=LineageGraphRead)
def pipeline_lineage(
    pipeline_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    pipeline = get_pipeline(db, pipeline_id)
    require_project_access(db, current_user.id, pipeline.project_id)
    return _graph(db, "pipeline", pipeline_id)
