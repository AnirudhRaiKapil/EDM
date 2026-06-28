from sqlalchemy import select
from sqlalchemy.orm import Session

from app.events import publish
from app.modules.core.exceptions import NotFoundError, ValidationFailedError
from app.modules.source.models import Source
from app.modules.source.schemas import SUPPORTED_CONNECTOR_TYPES
from app.modules.workspace.service import get_project


def create_source(
    db: Session, owner_id: str, project_id: str, name: str, connector_type: str, ingestion_mode: str
) -> Source:
    get_project(db, project_id)  # 404s if missing
    if connector_type not in SUPPORTED_CONNECTOR_TYPES:
        raise ValidationFailedError(
            f"connector_type '{connector_type}' not supported; choose from {SUPPORTED_CONNECTOR_TYPES}"
        )

    source = Source(
        project_id=project_id,
        name=name,
        connector_type=connector_type,
        ingestion_mode=ingestion_mode,
        owner_id=owner_id,
    )
    db.add(source)
    db.commit()
    db.refresh(source)
    publish("source.created", {"id": source.id, "projectId": project_id, "name": name})
    return source


def list_sources(db: Session, project_id: str) -> list[Source]:
    return list(db.execute(select(Source).where(Source.project_id == project_id)).scalars())


def get_source(db: Session, source_id: str) -> Source:
    source = db.get(Source, source_id)
    if source is None:
        raise NotFoundError(f"source '{source_id}' not found")
    return source


def attach_raw_file(db: Session, source: Source, raw_file_path: str) -> Source:
    source.raw_file_path = raw_file_path
    db.add(source)
    db.commit()
    db.refresh(source)
    publish("source.file_attached", {"id": source.id, "path": raw_file_path})
    return source
