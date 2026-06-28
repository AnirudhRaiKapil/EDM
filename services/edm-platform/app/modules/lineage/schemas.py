from datetime import datetime

from pydantic import BaseModel, ConfigDict


class LineageEdgeRead(BaseModel):
    id: str
    from_entity_type: str
    from_entity_id: str
    to_entity_type: str
    to_entity_id: str
    job_id: str | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class LineageGraphRead(BaseModel):
    entity_type: str
    entity_id: str
    upstream: list[LineageEdgeRead]
    downstream: list[LineageEdgeRead]
