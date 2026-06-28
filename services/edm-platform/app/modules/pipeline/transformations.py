import pandas as pd

from app.modules.core.exceptions import ValidationFailedError

SUPPORTED_TRANSFORMATION_TYPES = ["standardize", "dedupe"]


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


_HANDLERS = {
    "standardize": _standardize,
    "dedupe": _dedupe,
}


def apply_transformation(df: pd.DataFrame, transformation_type: str, parameters: dict) -> pd.DataFrame:
    handler = _HANDLERS.get(transformation_type)
    if handler is None:
        raise ValidationFailedError(f"unsupported transformation type '{transformation_type}'")
    return handler(df, parameters)
