import pandas as pd

from app.modules.core.exceptions import ValidationFailedError
from app.sandbox import execute_code_cells

SUPPORTED_TRANSFORMATION_TYPES = [
    "standardize",
    "dedupe",
    "select_columns",
    "rename_columns",
    "fill_nulls",
    "filter_rows",
    "python_code",
]


def _standardize(df: pd.DataFrame, parameters: dict) -> pd.DataFrame:
    df = df.copy()
    df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]
    string_columns = df.select_dtypes(include="object").columns
    for column in string_columns:
        df[column] = df[column].str.strip()
    return df


def _dedupe(df: pd.DataFrame, parameters: dict) -> pd.DataFrame:
    subset = parameters.get("subset")
    return df.drop_duplicates(subset=subset).reset_index(drop=True)


def _select_columns(df: pd.DataFrame, parameters: dict) -> pd.DataFrame:
    columns = parameters.get("columns")
    if not columns:
        raise ValidationFailedError("select_columns requires a non-empty 'columns' parameter")
    missing = [c for c in columns if c not in df.columns]
    if missing:
        raise ValidationFailedError(f"select_columns: unknown column(s) {missing}")
    return df[columns]


def _rename_columns(df: pd.DataFrame, parameters: dict) -> pd.DataFrame:
    mapping = parameters.get("mapping")
    if not mapping:
        raise ValidationFailedError("rename_columns requires a non-empty 'mapping' parameter")
    return df.rename(columns=mapping)


def _fill_nulls(df: pd.DataFrame, parameters: dict) -> pd.DataFrame:
    value = parameters.get("value")
    if value is None:
        raise ValidationFailedError("fill_nulls requires a 'value' parameter")
    columns = parameters.get("columns")
    df = df.copy()
    if columns:
        df[columns] = df[columns].fillna(value)
    else:
        df = df.fillna(value)
    return df


def _filter_rows(df: pd.DataFrame, parameters: dict) -> pd.DataFrame:
    column = parameters.get("column")
    operator = parameters.get("operator", "eq")
    value = parameters.get("value")
    if not column or column not in df.columns:
        raise ValidationFailedError(f"filter_rows: unknown column '{column}'")

    operators = {
        "eq": lambda s: s == value,
        "ne": lambda s: s != value,
        "gt": lambda s: s > value,
        "gte": lambda s: s >= value,
        "lt": lambda s: s < value,
        "lte": lambda s: s <= value,
        "not_null": lambda s: s.notna(),
        "is_null": lambda s: s.isna(),
    }
    if operator not in operators:
        raise ValidationFailedError(f"filter_rows: unsupported operator '{operator}'")
    return df[operators[operator](df[column])].reset_index(drop=True)


def _python_code(df: pd.DataFrame, parameters: dict) -> pd.DataFrame:
    """Runs notebook-authored code (see app/sandbox.py and app/modules/notebook/) as a
    pipeline step, so code promoted from a notebook behaves identically scheduled as it
    did in interactive dev -- same restricted execution, same timeout."""
    code = parameters.get("code")
    if not code:
        raise ValidationFailedError("python_code requires a 'code' parameter")
    results = execute_code_cells(df, [code])
    result = results[0]
    if result["status"] != "ok":
        raise ValidationFailedError(f"python_code failed: {result['error']}")
    return pd.DataFrame(result["data"], columns=result["columns"])


_HANDLERS = {
    "standardize": _standardize,
    "dedupe": _dedupe,
    "select_columns": _select_columns,
    "rename_columns": _rename_columns,
    "fill_nulls": _fill_nulls,
    "filter_rows": _filter_rows,
    "python_code": _python_code,
}


def apply_transformation(df: pd.DataFrame, transformation_type: str, parameters: dict) -> pd.DataFrame:
    handler = _HANDLERS.get(transformation_type)
    if handler is None:
        raise ValidationFailedError(f"unsupported transformation type '{transformation_type}'")
    return handler(df, parameters)
