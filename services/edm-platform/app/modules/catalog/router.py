from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.modules.auth.models import User
from app.modules.catalog import service
from app.modules.catalog.schemas import DatasetDetailRead, DatasetRead
from app.modules.metadata.models import Schema

router = APIRouter(tags=["catalog"])


@router.get("/catalog/datasets", response_model=list[DatasetRead])
def search_datasets(
    project_id: str | None = None,
    q: str | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return service.list_datasets(db, project_id, q)


@router.get("/catalog/datasets/{dataset_id}", response_model=DatasetDetailRead)
def get_dataset(
    dataset_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    dataset = service.get_dataset(db, dataset_id)
    schema = db.get(Schema, dataset.current_schema_id) if dataset.current_schema_id else None
    return DatasetDetailRead(
        **DatasetRead.model_validate(dataset).model_dump(),
        schema_info=schema,
    )
