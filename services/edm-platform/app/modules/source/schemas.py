from datetime import datetime

from pydantic import BaseModel, ConfigDict

SUPPORTED_CONNECTOR_TYPES = [
    "csv",
    "json",
    "sqlite",
    "oracle",
    "s3",
    "rest_api",
    "servicenow",
    "jira",
    "confluence",
    "postgres",
    "mysql",
    "mongodb",
    "google_sheets",
]
FILE_BASED_CONNECTOR_TYPES = ["csv", "json"]
CREDENTIALED_CONNECTOR_TYPES = [
    "oracle",
    "s3",
    "rest_api",
    "servicenow",
    "jira",
    "confluence",
    "postgres",
    "mysql",
    "google_sheets",
]


class SourceCreate(BaseModel):
    name: str
    connector_type: str = "csv"
    ingestion_mode: str = "batch"
    connection_config: dict | None = None
    credentials: dict | None = None


class SourceRead(BaseModel):
    id: str
    project_id: str
    name: str
    connector_type: str
    ingestion_mode: str
    status: str
    raw_file_path: str | None
    connection_config: dict | None
    has_credentials: bool
    owner_id: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
