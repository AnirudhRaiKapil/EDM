from datetime import datetime

from pydantic import BaseModel, ConfigDict


class JobRead(BaseModel):
    id: str
    pipeline_id: str
    pipeline_version: int
    status: str
    trigger: str
    started_at: datetime | None
    finished_at: datetime | None
    metrics: dict
    error_message: str | None
    dataset_id: str | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
