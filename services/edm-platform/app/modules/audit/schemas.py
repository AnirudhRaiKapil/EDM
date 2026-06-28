from datetime import datetime

from pydantic import BaseModel, ConfigDict


class AuditEventRead(BaseModel):
    id: str
    actor_user_id: str | None
    subject_email: str | None
    workspace_id: str | None
    action: str
    entity_type: str | None
    entity_id: str | None
    event_metadata: dict
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
