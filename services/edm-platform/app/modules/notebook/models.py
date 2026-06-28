from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.modules.core.models import OwnedMixin, TimestampMixin, UUIDPrimaryKeyMixin


class Notebook(Base, UUIDPrimaryKeyMixin, TimestampMixin, OwnedMixin):
    """Not in the original 02-domain-model.md -- added per ADR-0010. A Notebook is a
    draft, interactively-tested precursor to a Pipeline: cells run against a small
    sample of a Source's data so iteration is fast, then 'promote' turns the
    accumulated cell code into a single python_code Pipeline transformation."""

    __tablename__ = "notebook_notebooks"

    project_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("workspace_projects.id"), nullable=False
    )
    source_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("source_sources.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    sample_size: Mapped[int] = mapped_column(Integer, nullable=False, default=100)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft")
    promoted_pipeline_id: Mapped[str | None] = mapped_column(String(36), nullable=True)

    cells: Mapped[list["NotebookCell"]] = relationship(
        back_populates="notebook", order_by="NotebookCell.order", cascade="all, delete-orphan"
    )


class NotebookCell(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "notebook_cells"

    notebook_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("notebook_notebooks.id"), nullable=False
    )
    order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    code: Mapped[str] = mapped_column(String(20000), nullable=False, default="")

    notebook: Mapped[Notebook] = relationship(back_populates="cells")
