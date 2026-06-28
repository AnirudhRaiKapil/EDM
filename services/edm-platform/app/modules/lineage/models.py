from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.modules.core.models import TimestampMixin, UUIDPrimaryKeyMixin


class LineageEdge(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """02-domain-model.md Section 2: a directed edge recording that one entity produced or
    consumed another. The union of all edges is the lineage graph."""

    __tablename__ = "lineage_edges"

    from_entity_type: Mapped[str] = mapped_column(String(50), nullable=False)
    from_entity_id: Mapped[str] = mapped_column(String(36), nullable=False)
    to_entity_type: Mapped[str] = mapped_column(String(50), nullable=False)
    to_entity_id: Mapped[str] = mapped_column(String(36), nullable=False)
    job_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("job_jobs.id"), nullable=True
    )
