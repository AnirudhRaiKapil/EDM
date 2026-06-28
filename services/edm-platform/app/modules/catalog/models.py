from sqlalchemy import JSON, Float, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.modules.core.models import OwnedMixin, TimestampMixin, UUIDPrimaryKeyMixin


class Dataset(Base, UUIDPrimaryKeyMixin, TimestampMixin, OwnedMixin):
    __tablename__ = "catalog_datasets"

    project_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("workspace_projects.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    layer: Mapped[str] = mapped_column(String(20), nullable=False, default="bronze")
    physical_location: Mapped[str] = mapped_column(String(1000), nullable=False)
    current_schema_id: Mapped[str] = mapped_column(String(36), nullable=True)
    classification: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="available")
    quality_score: Mapped[float] = mapped_column(Float, nullable=True)


class Tag(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "catalog_tags"

    entity_type: Mapped[str] = mapped_column(String(50), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(36), nullable=False)
    key: Mapped[str] = mapped_column(String(100), nullable=False)
    value: Mapped[str] = mapped_column(String(255), nullable=False)
