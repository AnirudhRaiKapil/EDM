from pydantic import BaseModel


class QueryRequest(BaseModel):
    dataset_id: str
    sql: str


class QueryResponse(BaseModel):
    columns: list[str]
    rows: list[dict]
    row_count: int
