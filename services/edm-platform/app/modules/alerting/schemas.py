from datetime import datetime

from pydantic import BaseModel, ConfigDict


class AlertRead(BaseModel):
    id: str
    project_id: str
    source_entity_type: str
    source_entity_id: str
    severity: str
    message: str
    status: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AlertStatusUpdate(BaseModel):
    status: str
