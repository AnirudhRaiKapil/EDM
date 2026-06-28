from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.modules.auth.models import User
from app.modules.job import service
from app.modules.job.schemas import JobRead
from app.permissions import require_job_access, require_pipeline_access

router = APIRouter(tags=["job"])


@router.post("/pipelines/{pipeline_id}/jobs", response_model=JobRead, status_code=201)
def trigger_job(
    pipeline_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_pipeline_access(db, current_user.id, pipeline_id)
    return service.run_pipeline(db, current_user.id, pipeline_id, trigger="manual")


@router.get("/pipelines/{pipeline_id}/jobs", response_model=list[JobRead])
def list_jobs(
    pipeline_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_pipeline_access(db, current_user.id, pipeline_id)
    return service.list_jobs(db, pipeline_id)


@router.get("/jobs/{job_id}", response_model=JobRead)
def get_job(
    job_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_job_access(db, current_user.id, job_id)
    return service.get_job(db, job_id)
