import re
import sqlite3
from pathlib import Path

import pandas as pd

from app.modules.core.exceptions import ValidationFailedError
from app.modules.source.models import Source
from app.modules.storage.adapter import storage

_READERS = {
    "csv": pd.read_csv,
    "json": pd.read_json,
}

_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _load_sqlite(source: Source) -> pd.DataFrame:
    config = source.connection_config or {}
    db_path = config.get("db_path")
    query = config.get("query")
    table = config.get("table")
    if not db_path:
        raise ValidationFailedError(f"source '{source.id}' is missing connection_config.db_path")
    if not Path(db_path).is_file():
        raise ValidationFailedError(f"sqlite db_path '{db_path}' does not exist")

    if query:
        if not query.strip().lower().startswith("select"):
            raise ValidationFailedError("sqlite source query must be a SELECT statement")
    elif table:
        if not _IDENTIFIER_RE.match(table):
            raise ValidationFailedError(f"invalid table name '{table}'")
        query = f'SELECT * FROM "{table}"'
    else:
        raise ValidationFailedError(f"source '{source.id}' is missing connection_config.query/.table")

    connection = sqlite3.connect(db_path)
    try:
        return pd.read_sql_query(query, connection)
    finally:
        connection.close()


def load_source_dataframe(source: Source) -> pd.DataFrame:
    if source.connector_type == "sqlite":
        return _load_sqlite(source)

    reader = _READERS.get(source.connector_type)
    if reader is None:
        raise ValidationFailedError(f"no connector implementation for '{source.connector_type}'")
    if not source.raw_file_path:
        raise ValidationFailedError(f"source '{source.id}' has no file attached yet")
    return reader(storage.absolute_path(source.raw_file_path))
