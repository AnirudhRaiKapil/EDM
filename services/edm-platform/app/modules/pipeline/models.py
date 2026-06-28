from sqlalchemy import JSON, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.modules.core.models import OwnedMixin, TimestampMixin, UUIDPrimaryKeyMixin


class Pipeline(Base, UUIDPrimaryKeyMixin, TimestampMixin, OwnedMixin):
    __tablename__ = "pipeline_pipelines"

    project_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("workspace_projects.id"), nullable=False
    )
    source_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("source_sources.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    output_dataset_name: Mapped[str] = mapped_column(String(255), nullable=False)
    output_layer: Mapped[str] = mapped_column(String(20), nullable=False, default="silver")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    schedule_cron: Mapped[str | None] = mapped_column(String(100), nullable=True)

    transformations: Mapped[list["Transformation"]] = relationship(
        back_populates="pipeline", order_by="Transformation.order", cascade="all, delete-orphan"
    )


class Transformation(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "pipeline_transformations"

    pipeline_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("pipeline_pipelines.id"), nullable=False
    )
    type: Mapped[str] = mapped_column(String(50), nullable=False)
    order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    parameters: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)

    pipeline: Mapped[Pipeline] = relationship(back_populates="transformations")
