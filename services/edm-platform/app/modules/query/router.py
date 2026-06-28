from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.modules.auth.models import User
from app.modules.catalog.service import get_dataset
from app.modules.query import service
from app.modules.query.schemas import QueryRequest, QueryResponse

router = APIRouter(tags=["query"])


@router.post("/query", response_model=QueryResponse)
def query(
    payload: QueryRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    dataset = get_dataset(db, payload.dataset_id)
    columns, rows = service.run_query(dataset, payload.sql)
    return QueryResponse(columns=columns, rows=rows, row_count=len(rows))
