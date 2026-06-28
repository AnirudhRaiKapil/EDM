from datetime import datetime

from pydantic import BaseModel, ConfigDict

SUPPORTED_CONNECTOR_TYPES = ["csv", "json", "sqlite"]
FILE_BASED_CONNECTOR_TYPES = ["csv", "json"]


class SourceCreate(BaseModel):
    name: str
    connector_type: str = "csv"
    ingestion_mode: str = "batch"
    connection_config: dict | None = None


class SourceRead(BaseModel):
    id: str
    project_id: str
    name: str
    connector_type: str
    ingestion_mode: str
    status: str
    raw_file_path: str | None
    connection_config: dict | None
    owner_id: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
