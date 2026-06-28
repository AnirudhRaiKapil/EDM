from datetime import datetime

from pydantic import BaseModel, ConfigDict


class TransformationCreate(BaseModel):
    type: str
    order: int = 0
    parameters: dict = {}


class TransformationRead(BaseModel):
    id: str
    type: str
    order: int
    parameters: dict

    model_config = ConfigDict(from_attributes=True)


class PipelineCreate(BaseModel):
    name: str
    source_id: str
    output_dataset_name: str
    output_layer: str = "silver"
    transformations: list[TransformationCreate] = []


class PipelineRead(BaseModel):
    id: str
    project_id: str
    source_id: str
    name: str
    version: int
    output_dataset_name: str
    output_layer: str
    status: str
    owner_id: str
    created_at: datetime
    transformations: list[TransformationRead]

    model_config = ConfigDict(from_attributes=True)
