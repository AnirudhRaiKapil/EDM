from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.modules.auth.models import User
from app.modules.source import service
from app.modules.source.schemas import SourceCreate, SourceRead
from app.permissions import require_project_access, require_source_access

router = APIRouter(tags=["source"])


@router.post("/projects/{project_id}/sources", response_model=SourceRead, status_code=201)
def create_source(
    project_id: str,
    payload: SourceCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_project_access(db, current_user.id, project_id)
    return service.create_source(
        db, current_user.id, project_id, payload.name, payload.connector_type, payload.ingestion_mode
    )


@router.get("/projects/{project_id}/sources", response_model=list[SourceRead])
def list_sources(
    project_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_project_access(db, current_user.id, project_id)
    return service.list_sources(db, project_id)


@router.get("/sources/{source_id}", response_model=SourceRead)
def get_source(
    source_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_source_access(db, current_user.id, source_id)
    return service.get_source(db, source_id)
