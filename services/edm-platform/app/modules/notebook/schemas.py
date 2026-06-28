from datetime import datetime

from pydantic import BaseModel, ConfigDict


class NotebookCellCreate(BaseModel):
    code: str
    order: int | None = None


class NotebookCellUpdate(BaseModel):
    code: str


class NotebookCellRead(BaseModel):
    id: str
    notebook_id: str
    order: int
    code: str

    model_config = ConfigDict(from_attributes=True)


class NotebookCreate(BaseModel):
    name: str
    source_id: str
    sample_size: int = 100


class NotebookRead(BaseModel):
    id: str
    project_id: str
    source_id: str
    name: str
    sample_size: int
    status: str
    promoted_pipeline_id: str | None
    owner_id: str
    created_at: datetime
    cells: list[NotebookCellRead]

    model_config = ConfigDict(from_attributes=True)


class CellRunResult(BaseModel):
    cell_id: str
    status: str
    stdout: str = ""
    preview: list[dict] = []
    row_count: int | None = None
    columns: list[str] | None = None
    error: str | None = None


class NotebookRunResult(BaseModel):
    results: list[CellRunResult]


class NotebookPromote(BaseModel):
    output_dataset_name: str
    output_layer: str = "silver"
    pipeline_name: str | None = None
