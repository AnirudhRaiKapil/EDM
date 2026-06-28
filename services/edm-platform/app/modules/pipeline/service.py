from sqlalchemy import select
from sqlalchemy.orm import Session

from app.events import publish
from app.modules.core.exceptions import NotFoundError, ValidationFailedError
from app.modules.pipeline.models import Pipeline, Transformation
from app.modules.pipeline.schemas import TransformationCreate
from app.modules.pipeline.transformations import SUPPORTED_TRANSFORMATION_TYPES
from app.modules.source.service import get_source
from app.modules.workspace.service import get_project


def create_pipeline(
    db: Session,
    owner_id: str,
    project_id: str,
    source_id: str,
    name: str,
    output_dataset_name: str,
    output_layer: str,
    transformations: list[TransformationCreate],
) -> Pipeline:
    get_project(db, project_id)
    get_source(db, source_id)
    for t in transformations:
        if t.type not in SUPPORTED_TRANSFORMATION_TYPES:
            raise ValidationFailedError(
                f"unsupported transformation type '{t.type}'; choose from {SUPPORTED_TRANSFORMATION_TYPES}"
            )

    pipeline = Pipeline(
        project_id=project_id,
        source_id=source_id,
        name=name,
        output_dataset_name=output_dataset_name,
        output_layer=output_layer,
        owner_id=owner_id,
    )
    pipeline.transformations = [
        Transformation(type=t.type, order=t.order, parameters=t.parameters)
        for t in transformations
    ]
    db.add(pipeline)
    db.commit()
    db.refresh(pipeline)
    publish("pipeline.created", {"id": pipeline.id, "projectId": project_id, "name": name})
    return pipeline


def list_pipelines(db: Session, project_id: str) -> list[Pipeline]:
    return list(
        db.execute(select(Pipeline).where(Pipeline.project_id == project_id)).scalars()
    )


def get_pipeline(db: Session, pipeline_id: str) -> Pipeline:
    pipeline = db.get(Pipeline, pipeline_id)
    if pipeline is None:
        raise NotFoundError(f"pipeline '{pipeline_id}' not found")
    return pipeline
