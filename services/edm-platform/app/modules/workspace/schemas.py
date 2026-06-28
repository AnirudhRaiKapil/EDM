from datetime import datetime

from pydantic import BaseModel, ConfigDict


class WorkspaceCreate(BaseModel):
    name: str
    description: str = ""


class WorkspaceRead(BaseModel):
    id: str
    name: str
    description: str
    status: str
    owner_id: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ProjectCreate(BaseModel):
    name: str
    environment: str = "dev"


class ProjectRead(BaseModel):
    id: str
    workspace_id: str
    name: str
    environment: str
    status: str
    owner_id: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class MemberAssign(BaseModel):
    email: str
    role: str = "member"


class MemberRead(BaseModel):
    user_id: str
    email: str
    role_name: str
