import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.metadata.models import Column, Schema

_PANDAS_TO_LOGICAL_TYPE = {
    "object": "string",
    "int64": "integer",
    "float64": "float",
    "bool": "boolean",
    "datetime64[ns]": "timestamp",
}


def create_new_schema_version(db: Session, dataset_id: str, df: pd.DataFrame) -> Schema:
    """Schema lifecycle (02-domain-model.md): previous versions become 'superseded',
    never deleted, so Dataset history/time-travel stays intact."""
    existing = list(
        db.execute(select(Schema).where(Schema.dataset_id == dataset_id)).scalars()
    )
    for previous in existing:
        previous.status = "superseded"
        db.add(previous)
    next_version = max((s.version for s in existing), default=0) + 1

    schema = Schema(dataset_id=dataset_id, version=next_version, status="active")
    schema.columns = [
        Column(
            name=column_name,
            data_type=_PANDAS_TO_LOGICAL_TYPE.get(str(dtype), str(dtype)),
            nullable=bool(df[column_name].isnull().any()),
        )
        for column_name, dtype in df.dtypes.items()
    ]
    db.add(schema)
    db.commit()
    db.refresh(schema)
    return schema
