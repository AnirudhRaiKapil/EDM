from datetime import datetime

from pydantic import BaseModel, ConfigDict


class NotificationChannelCreate(BaseModel):
    type: str
    config: dict


class NotificationChannelRead(BaseModel):
    id: str
    project_id: str
    type: str
    config: dict
    enabled: bool
    owner_id: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
