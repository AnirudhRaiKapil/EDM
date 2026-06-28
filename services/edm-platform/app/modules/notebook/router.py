from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.modules.auth.models import User
from app.modules.notebook import service
from app.modules.notebook.schemas import (
    NotebookCellCreate,
    NotebookCellRead,
    NotebookCellUpdate,
    NotebookCreate,
    NotebookPromote,
    NotebookRead,
    NotebookRunResult,
)
from app.modules.pipeline.schemas import PipelineRead
from app.permissions import require_notebook_access, require_project_access

router = APIRouter(tags=["notebook"])


@router.post("/projects/{project_id}/notebooks", response_model=NotebookRead, status_code=201)
def create_notebook(
    project_id: str,
    payload: NotebookCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_project_access(db, current_user.id, project_id)
    return service.create_notebook(
        db, current_user.id, project_id, payload.source_id, payload.name, payload.sample_size
    )


@router.get("/projects/{project_id}/notebooks", response_model=list[NotebookRead])
def list_notebooks(
    project_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_project_access(db, current_user.id, project_id)
    return service.list_notebooks(db, project_id)


@router.get("/notebooks/{notebook_id}", response_model=NotebookRead)
def get_notebook(
    notebook_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_notebook_access(db, current_user.id, notebook_id)
    return service.get_notebook(db, notebook_id)


@router.post("/notebooks/{notebook_id}/cells", response_model=NotebookCellRead, status_code=201)
def add_cell(
    notebook_id: str,
    payload: NotebookCellCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_notebook_access(db, current_user.id, notebook_id)
    return service.add_cell(db, notebook_id, payload.code, payload.order)


@router.patch("/notebooks/{notebook_id}/cells/{cell_id}", response_model=NotebookCellRead)
def update_cell(
    notebook_id: str,
    cell_id: str,
    payload: NotebookCellUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_notebook_access(db, current_user.id, notebook_id)
    return service.update_cell(db, notebook_id, cell_id, payload.code)


@router.delete("/notebooks/{notebook_id}/cells/{cell_id}", status_code=204)
def delete_cell(
    notebook_id: str,
    cell_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_notebook_access(db, current_user.id, notebook_id)
    service.delete_cell(db, notebook_id, cell_id)


@router.post("/notebooks/{notebook_id}/run", response_model=NotebookRunResult)
def run_notebook(
    notebook_id: str,
    up_to_cell_id: str | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_notebook_access(db, current_user.id, notebook_id)
    return NotebookRunResult(results=service.run_notebook(db, notebook_id, up_to_cell_id))


@router.post("/notebooks/{notebook_id}/promote", response_model=PipelineRead)
def promote_notebook(
    notebook_id: str,
    payload: NotebookPromote,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_notebook_access(db, current_user.id, notebook_id)
    return service.promote_notebook(
        db,
        current_user.id,
        notebook_id,
        payload.output_dataset_name,
        payload.output_layer,
        payload.pipeline_name,
    )
