from sqlalchemy import select
from sqlalchemy.orm import Session

from app.events import publish
from app.modules.catalog.models import Dataset
from app.modules.core.exceptions import NotFoundError


def register_dataset(
    db: Session,
    owner_id: str,
    project_id: str,
    name: str,
    layer: str,
    physical_location: str,
) -> Dataset:
    dataset = Dataset(
        project_id=project_id,
        name=name,
        layer=layer,
        physical_location=physical_location,
        owner_id=owner_id,
    )
    db.add(dataset)
    db.commit()
    db.refresh(dataset)
    publish("dataset.created", {"id": dataset.id, "projectId": project_id, "name": name})
    return dataset


def attach_schema(db: Session, dataset: Dataset, schema_id: str) -> Dataset:
    dataset.current_schema_id = schema_id
    db.add(dataset)
    db.commit()
    db.refresh(dataset)
    return dataset


def get_dataset_by_name(db: Session, project_id: str, name: str, layer: str) -> Dataset | None:
    stmt = select(Dataset).where(
        Dataset.project_id == project_id, Dataset.name == name, Dataset.layer == layer
    )
    return db.execute(stmt).scalar_one_or_none()


def list_datasets(db: Session, project_id: str | None = None, search: str | None = None) -> list[Dataset]:
    stmt = select(Dataset)
    if project_id:
        stmt = stmt.where(Dataset.project_id == project_id)
    if search:
        stmt = stmt.where(Dataset.name.ilike(f"%{search}%"))
    return list(db.execute(stmt).scalars())


def get_dataset(db: Session, dataset_id: str) -> Dataset:
    dataset = db.get(Dataset, dataset_id)
    if dataset is None:
        raise NotFoundError(f"dataset '{dataset_id}' not found")
    return dataset
