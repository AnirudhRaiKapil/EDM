from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.modules.metadata.schemas import SchemaRead


class DatasetRead(BaseModel):
    id: str
    project_id: str
    name: str
    layer: str
    physical_location: str
    classification: list[str]
    status: str
    quality_score: float | None
    owner_id: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DatasetDetailRead(DatasetRead):
    schema_info: SchemaRead | None = None
