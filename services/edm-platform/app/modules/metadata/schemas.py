from pydantic import BaseModel, ConfigDict


class ColumnRead(BaseModel):
    name: str
    data_type: str
    nullable: bool
    description: str = ""

    model_config = ConfigDict(from_attributes=True)


class SchemaRead(BaseModel):
    id: str
    dataset_id: str
    version: int
    status: str
    columns: list[ColumnRead]

    model_config = ConfigDict(from_attributes=True)
