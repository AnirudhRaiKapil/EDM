from sqlalchemy import select
from sqlalchemy.orm import Session

from app.events import publish
from app.modules.core.exceptions import NotFoundError, ValidationFailedError
from app.modules.ingestion.connectors import load_source_dataframe
from app.modules.notebook.models import Notebook, NotebookCell
from app.modules.source.service import get_source
from app.modules.workspace.service import get_project
from app.sandbox import execute_code_cells


def create_notebook(
    db: Session, owner_id: str, project_id: str, source_id: str, name: str, sample_size: int = 100
) -> Notebook:
    get_project(db, project_id)
    get_source(db, source_id)  # 404s if missing
    notebook = Notebook(
        project_id=project_id,
        source_id=source_id,
        name=name,
        sample_size=sample_size,
        owner_id=owner_id,
    )
    db.add(notebook)
    db.commit()
    db.refresh(notebook)
    publish("notebook.created", {"id": notebook.id, "projectId": project_id, "name": name})
    return notebook


def list_notebooks(db: Session, project_id: str) -> list[Notebook]:
    return list(db.execute(select(Notebook).where(Notebook.project_id == project_id)).scalars())


def get_notebook(db: Session, notebook_id: str) -> Notebook:
    notebook = db.get(Notebook, notebook_id)
    if notebook is None:
        raise NotFoundError(f"notebook '{notebook_id}' not found")
    return notebook


def add_cell(db: Session, notebook_id: str, code: str, order: int | None = None) -> NotebookCell:
    notebook = get_notebook(db, notebook_id)
    if order is None:
        order = max((c.order for c in notebook.cells), default=-1) + 1
    cell = NotebookCell(notebook_id=notebook_id, code=code, order=order)
    db.add(cell)
    db.commit()
    db.refresh(cell)
    return cell


def update_cell(db: Session, notebook_id: str, cell_id: str, code: str) -> NotebookCell:
    cell = db.get(NotebookCell, cell_id)
    if cell is None or cell.notebook_id != notebook_id:
        raise NotFoundError(f"cell '{cell_id}' not found on notebook '{notebook_id}'")
    cell.code = code
    db.add(cell)
    db.commit()
    db.refresh(cell)
    return cell


def delete_cell(db: Session, notebook_id: str, cell_id: str) -> None:
    cell = db.get(NotebookCell, cell_id)
    if cell is None or cell.notebook_id != notebook_id:
        raise NotFoundError(f"cell '{cell_id}' not found on notebook '{notebook_id}'")
    db.delete(cell)
    db.commit()


def run_notebook(db: Session, notebook_id: str, up_to_cell_id: str | None = None) -> list[dict]:
    notebook = get_notebook(db, notebook_id)
    source = get_source(db, notebook.source_id)
    df = load_source_dataframe(source).head(notebook.sample_size)

    cells = list(notebook.cells)
    if up_to_cell_id is not None:
        index = next((i for i, c in enumerate(cells) if c.id == up_to_cell_id), None)
        if index is None:
            raise NotFoundError(f"cell '{up_to_cell_id}' not found on notebook '{notebook_id}'")
        cells = cells[: index + 1]

    if not cells:
        return []

    raw_results = execute_code_cells(df, [c.code for c in cells])
    # execute_code_cells stops at the first failing cell, so raw_results can be shorter
    # than cells -- pad with "skipped" so the response always lines up with what was asked.
    output = []
    for i, cell in enumerate(cells):
        if i < len(raw_results):
            result = dict(raw_results[i])
            result.pop("data", None)  # internal-only; never serialize the full result over the API
            result["cell_id"] = cell.id
        else:
            result = {"cell_id": cell.id, "status": "skipped", "stdout": "", "preview": []}
        output.append(result)
    return output


def promote_notebook(
    db: Session,
    owner_id: str,
    notebook_id: str,
    output_dataset_name: str,
    output_layer: str,
    pipeline_name: str | None = None,
):
    # Imported here, not at module load, to avoid a notebook<->pipeline import cycle:
    # pipeline/service.py has no reason to know about notebooks, only the reverse.
    from app.modules.pipeline.schemas import TransformationCreate
    from app.modules.pipeline.service import create_pipeline

    notebook = get_notebook(db, notebook_id)
    if not notebook.cells:
        raise ValidationFailedError("cannot promote a notebook with no cells")

    combined_code = "\n\n".join(cell.code for cell in notebook.cells)
    pipeline = create_pipeline(
        db,
        owner_id,
        notebook.project_id,
        notebook.source_id,
        pipeline_name or f"{notebook.name} (promoted)",
        output_dataset_name,
        output_layer,
        [TransformationCreate(type="python_code", order=0, parameters={"code": combined_code})],
    )
    notebook.status = "promoted"
    notebook.promoted_pipeline_id = pipeline.id
    db.add(notebook)
    db.commit()
    db.refresh(notebook)
    publish("notebook.promoted", {"notebookId": notebook.id, "pipelineId": pipeline.id})
    return pipeline
