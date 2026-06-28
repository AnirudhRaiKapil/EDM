from datetime import datetime

from pydantic import BaseModel, ConfigDict

SUPPORTED_CONNECTOR_TYPES = ["csv"]


class SourceCreate(BaseModel):
    name: str
    connector_type: str = "csv"
    ingestion_mode: str = "batch"


class SourceRead(BaseModel):
    id: str
    project_id: str
    name: str
    connector_type: str
    ingestion_mode: str
    status: str
    raw_file_path: str | None
    owner_id: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
