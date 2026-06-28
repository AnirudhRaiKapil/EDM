import duckdb
import pandas as pd

from app.modules.catalog.models import Dataset
from app.modules.core.exceptions import ValidationFailedError
from app.modules.storage.adapter import storage

MASK_VALUE = "***MASKED***"

# Column-name substrings (case-insensitive) treated as personally-identifying.
# Dataset-level, not a per-column tagging system: there's no column-level
# classification model yet (only Dataset.classification, already a list[str] set via
# PATCH .../classification), so this masks by name pattern on any dataset classified
# "pii", rather than requiring a whole new column-tagging feature to flag individual
# columns one at a time. See ADR-0011.
PII_COLUMN_PATTERNS = [
    "email",
    "ssn",
    "social_security",
    "password",
    "phone",
    "address",
    "dob",
    "date_of_birth",
    "credit_card",
    "ip_address",
    "secret",
    "token",
]


def _is_pii_column(column_name: str) -> bool:
    lowered = column_name.lower()
    return any(pattern in lowered for pattern in PII_COLUMN_PATTERNS)


def _mask_pii_columns(df: pd.DataFrame, dataset: Dataset, role: str) -> pd.DataFrame:
    if role == "owner" or "pii" not in dataset.classification:
        return df
    masked = df.copy()
    for column in masked.columns:
        if _is_pii_column(column):
            masked[column] = MASK_VALUE
    return masked


def run_query(dataset: Dataset, sql: str, role: str) -> tuple[list[str], list[dict]]:
    if not sql.strip().lower().startswith("select"):
        raise ValidationFailedError("only SELECT statements are allowed against the query endpoint")

    # The dataset itself is loaded through our own storage adapter (pandas), never
    # through a DuckDB SQL function -- read_parquet()/read_csv()/ATTACH/COPY TO are all
    # callable from *within* a user's "SELECT ..." string (it only has to start with
    # SELECT; what follows is unrestricted), which would otherwise let any
    # authenticated caller read or exfiltrate arbitrary files on the server
    # (e.g. "SELECT * FROM read_csv('/path/to/.env')") via this endpoint.
    # enable_external_access=False blocks every filesystem/network primitive DuckDB
    # has (verified: read_csv/read_parquet, ATTACH to a real file, COPY TO, INSTALL of
    # an extension like httpfs, and scanning an https:// URL directly) while still
    # allowing a DataFrame registered via `register()` to be queried normally, since
    # that's an in-memory handoff, not a filesystem/network operation.
    dataframe = storage.read_dataframe(dataset.physical_location)
    connection = duckdb.connect(config={"enable_external_access": False})
    connection.register("dataset", dataframe)
    try:
        result_df = connection.execute(sql).fetchdf()
    except duckdb.Error as exc:
        # Covers both a malformed/invalid query and the PermissionException raised by
        # enable_external_access=False rejecting a filesystem/network primitive -- both
        # are "the caller's SQL was rejected" (a 422), not a server error (a 500 with an
        # unhandled-exception traceback, which is what reached the caller before this).
        # DuckDB's own error text (parse errors, the permission message above) doesn't
        # contain anything sensitive, so it's safe to return as-is.
        raise ValidationFailedError(f"query failed: {exc}") from exc
    result_df = _mask_pii_columns(result_df, dataset, role)
    return list(result_df.columns), result_df.to_dict(orient="records")
