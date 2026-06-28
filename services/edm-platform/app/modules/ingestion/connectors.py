import pandas as pd

from app.modules.core.exceptions import ValidationFailedError
from app.modules.source.models import Source
from app.modules.storage.adapter import storage

_READERS = {
    "csv": pd.read_csv,
    "json": pd.read_json,
}


def load_source_dataframe(source: Source) -> pd.DataFrame:
    reader = _READERS.get(source.connector_type)
    if reader is None:
        raise ValidationFailedError(f"no connector implementation for '{source.connector_type}'")
    if not source.raw_file_path:
        raise ValidationFailedError(f"source '{source.id}' has no file attached yet")
    return reader(storage.absolute_path(source.raw_file_path))
