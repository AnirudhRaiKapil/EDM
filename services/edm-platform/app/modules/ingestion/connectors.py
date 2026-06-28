import pandas as pd

from app.modules.core.exceptions import ValidationFailedError
from app.modules.source.models import Source
from app.modules.storage.adapter import storage


def load_source_dataframe(source: Source) -> pd.DataFrame:
    if source.connector_type != "csv":
        raise ValidationFailedError(f"no connector implementation for '{source.connector_type}'")
    if not source.raw_file_path:
        raise ValidationFailedError(f"source '{source.id}' has no file attached yet")
    return pd.read_csv(storage.absolute_path(source.raw_file_path))
