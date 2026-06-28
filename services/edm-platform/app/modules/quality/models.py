from sqlalchemy import JSON, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.modules.core.models import TimestampMixin, UUIDPrimaryKeyMixin


class QualityRule(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "quality_rules"

    dataset_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("catalog_datasets.id"), nullable=False
    )
    expectation_type: Mapped[str] = mapped_column(String(50), nullable=False)
    parameters: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    severity: Mapped[str] = mapped_column(String(20), nullable=False, default="blocking")


class QualityRun(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "quality_runs"

    dataset_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("catalog_datasets.id"), nullable=False
    )
    job_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("job_jobs.id"), nullable=True
    )
    results: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    outcome: Mapped[str] = mapped_column(String(30), nullable=False)
