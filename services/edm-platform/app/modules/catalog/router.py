from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.modules.auth.models import User
from app.modules.catalog import service
from app.modules.catalog.schemas import (
    DatasetClassificationUpdate,
    DatasetDetailRead,
    DatasetRead,
    TagCreate,
    TagRead,
)
from app.modules.metadata.models import Schema
from app.permissions import require_project_access

router = APIRouter(tags=["catalog"])


@router.get("/catalog/datasets", response_model=list[DatasetRead])
def search_datasets(
    project_id: str | None = None,
    q: str | None = None,
    tag_key: str | None = None,
    tag_value: str | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return service.list_datasets(db, project_id, q, tag_key, tag_value)


@router.get("/catalog/datasets/{dataset_id}", response_model=DatasetDetailRead)
def get_dataset(
    dataset_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    dataset = service.get_dataset(db, dataset_id)
    schema = db.get(Schema, dataset.current_schema_id) if dataset.current_schema_id else None
    tags = service.list_tags(db, dataset_id)
    return DatasetDetailRead(
        **DatasetRead.model_validate(dataset).model_dump(),
        schema_info=schema,
        tags=tags,
    )


@router.patch("/catalog/datasets/{dataset_id}", response_model=DatasetRead)
def update_dataset_classification(
    dataset_id: str,
    payload: DatasetClassificationUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    dataset = service.get_dataset(db, dataset_id)
    require_project_access(db, current_user.id, dataset.project_id)
    return service.update_classification(db, dataset, payload.classification)


@router.post("/catalog/datasets/{dataset_id}/tags", response_model=TagRead, status_code=201)
def add_tag(
    dataset_id: str,
    payload: TagCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    dataset = service.get_dataset(db, dataset_id)
    require_project_access(db, current_user.id, dataset.project_id)
    return service.add_tag(db, dataset_id, payload.key, payload.value)


@router.delete("/catalog/datasets/{dataset_id}/tags/{tag_id}", status_code=204)
def remove_tag(
    dataset_id: str,
    tag_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    dataset = service.get_dataset(db, dataset_id)
    require_project_access(db, current_user.id, dataset.project_id)
    service.remove_tag(db, dataset_id, tag_id)
