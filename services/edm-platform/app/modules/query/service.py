import duckdb

from app.modules.catalog.models import Dataset
from app.modules.core.exceptions import ValidationFailedError
from app.modules.storage.adapter import storage


def run_query(dataset: Dataset, sql: str) -> tuple[list[str], list[dict]]:
    if not sql.strip().lower().startswith("select"):
        raise ValidationFailedError("only SELECT statements are allowed against the query endpoint")

    absolute_path = str(storage.absolute_path(dataset.physical_location)).replace("'", "''")
    connection = duckdb.connect()
    connection.execute(f"CREATE VIEW dataset AS SELECT * FROM read_parquet('{absolute_path}')")
    result_df = connection.execute(sql).fetchdf()
    return list(result_df.columns), result_df.to_dict(orient="records")
