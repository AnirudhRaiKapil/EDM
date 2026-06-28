from sqlalchemy import select
from sqlalchemy.orm import Session

from app.events import publish
from app.modules.catalog.models import Dataset, Tag
from app.modules.core.exceptions import NotFoundError

DATASET_ENTITY_TYPE = "dataset"


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


def update_classification(db: Session, dataset: Dataset, classification: list[str]) -> Dataset:
    dataset.classification = classification
    db.add(dataset)
    db.commit()
    db.refresh(dataset)
    return dataset


def get_dataset_by_name(db: Session, project_id: str, name: str, layer: str) -> Dataset | None:
    stmt = select(Dataset).where(
        Dataset.project_id == project_id, Dataset.name == name, Dataset.layer == layer
    )
    return db.execute(stmt).scalar_one_or_none()


def list_datasets(
    db: Session,
    project_id: str | None = None,
    search: str | None = None,
    tag_key: str | None = None,
    tag_value: str | None = None,
) -> list[Dataset]:
    stmt = select(Dataset)
    if project_id:
        stmt = stmt.where(Dataset.project_id == project_id)
    if search:
        stmt = stmt.where(Dataset.name.ilike(f"%{search}%"))
    if tag_key:
        tag_filters = [Tag.entity_type == DATASET_ENTITY_TYPE, Tag.key == tag_key]
        if tag_value:
            tag_filters.append(Tag.value == tag_value)
        tagged_dataset_ids = select(Tag.entity_id).where(*tag_filters)
        stmt = stmt.where(Dataset.id.in_(tagged_dataset_ids))
    return list(db.execute(stmt).scalars())


def get_dataset(db: Session, dataset_id: str) -> Dataset:
    dataset = db.get(Dataset, dataset_id)
    if dataset is None:
        raise NotFoundError(f"dataset '{dataset_id}' not found")
    return dataset


def add_tag(db: Session, dataset_id: str, key: str, value: str) -> Tag:
    tag = Tag(entity_type=DATASET_ENTITY_TYPE, entity_id=dataset_id, key=key, value=value)
    db.add(tag)
    db.commit()
    db.refresh(tag)
    publish("dataset.tagged", {"datasetId": dataset_id, "key": key, "value": value})
    return tag


def list_tags(db: Session, dataset_id: str) -> list[Tag]:
    stmt = select(Tag).where(Tag.entity_type == DATASET_ENTITY_TYPE, Tag.entity_id == dataset_id)
    return list(db.execute(stmt).scalars())


def remove_tag(db: Session, dataset_id: str, tag_id: str) -> None:
    tag = db.get(Tag, tag_id)
    if tag is None or tag.entity_type != DATASET_ENTITY_TYPE or tag.entity_id != dataset_id:
        raise NotFoundError(f"tag '{tag_id}' not found on dataset '{dataset_id}'")
    db.delete(tag)
    db.commit()
