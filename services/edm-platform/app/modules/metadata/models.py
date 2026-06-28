from sqlalchemy import Boolean, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.modules.core.models import UUIDPrimaryKeyMixin


class Schema(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "metadata_schemas"

    dataset_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("catalog_datasets.id"), nullable=False
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")

    columns: Mapped[list["Column"]] = relationship(
        back_populates="schema", cascade="all, delete-orphan"
    )


class Column(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "metadata_columns"

    schema_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("metadata_schemas.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    data_type: Mapped[str] = mapped_column(String(50), nullable=False)
    nullable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    description: Mapped[str] = mapped_column(String(500), nullable=False, default="")

    schema: Mapped[Schema] = relationship(back_populates="columns")
