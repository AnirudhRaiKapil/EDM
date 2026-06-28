from pathlib import Path

import pandas as pd

from app.config import settings


class StorageAdapter:
    """Object storage abstraction. LocalDiskStorageAdapter is the MVP implementation
    (ADR-0003); a MinIOStorageAdapter implementing the same interface replaces it later
    with no change to callers in edm-ingestion/edm-job/edm-storage."""

    def save_raw_upload(self, source_id: str, filename: str, content: bytes) -> str:
        raise NotImplementedError

    def save_dataframe(self, layer: str, dataset_id: str, df: pd.DataFrame) -> str:
        raise NotImplementedError

    def read_dataframe(self, relative_path: str) -> pd.DataFrame:
        raise NotImplementedError

    def absolute_path(self, relative_path: str) -> Path:
        raise NotImplementedError


class LocalDiskStorageAdapter(StorageAdapter):
    def __init__(self, root: Path | None = None):
        self.root = root or settings.data_path

    def absolute_path(self, relative_path: str) -> Path:
        return self.root / relative_path

    def save_raw_upload(self, source_id: str, filename: str, content: bytes) -> str:
        safe_filename = Path(filename).name  # strip any client-supplied path components
        relative_path = f"raw/{source_id}/{safe_filename}"
        full_path = self.absolute_path(relative_path)
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_bytes(content)
        return relative_path

    def save_dataframe(self, layer: str, dataset_id: str, df: pd.DataFrame) -> str:
        relative_path = f"{layer}/{dataset_id}.parquet"
        full_path = self.absolute_path(relative_path)
        full_path.parent.mkdir(parents=True, exist_ok=True)
        df.to_parquet(full_path, index=False)
        return relative_path

    def read_dataframe(self, relative_path: str) -> pd.DataFrame:
        return pd.read_parquet(self.absolute_path(relative_path))


storage = LocalDiskStorageAdapter()
