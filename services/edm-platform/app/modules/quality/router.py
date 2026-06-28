from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.modules.auth.models import User
from app.modules.catalog.service import get_dataset
from app.modules.quality import service
from app.modules.quality.schemas import QualityRuleCreate, QualityRuleRead, QualityRunRead
from app.permissions import require_project_access

router = APIRouter(tags=["quality"])


@router.post(
    "/catalog/datasets/{dataset_id}/quality-rules", response_model=QualityRuleRead, status_code=201
)
def create_rule(
    dataset_id: str,
    payload: QualityRuleCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    dataset = get_dataset(db, dataset_id)
    require_project_access(db, current_user.id, dataset.project_id)
    return service.create_rule(
        db, dataset_id, payload.expectation_type, payload.parameters, payload.severity
    )


@router.get("/catalog/datasets/{dataset_id}/quality-rules", response_model=list[QualityRuleRead])
def list_rules(
    dataset_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    dataset = get_dataset(db, dataset_id)
    require_project_access(db, current_user.id, dataset.project_id)
    return service.list_rules(db, dataset_id)


@router.delete(
    "/catalog/datasets/{dataset_id}/quality-rules/{rule_id}", status_code=204
)
def delete_rule(
    dataset_id: str,
    rule_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    dataset = get_dataset(db, dataset_id)
    require_project_access(db, current_user.id, dataset.project_id)
    service.delete_rule(db, dataset_id, rule_id)


@router.get("/catalog/datasets/{dataset_id}/quality-runs", response_model=list[QualityRunRead])
def list_runs(
    dataset_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    dataset = get_dataset(db, dataset_id)
    require_project_access(db, current_user.id, dataset.project_id)
    return service.list_runs(db, dataset_id)
