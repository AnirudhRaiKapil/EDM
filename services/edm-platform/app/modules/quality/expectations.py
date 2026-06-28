import re

import pandas as pd

from app.modules.core.exceptions import ValidationFailedError

SUPPORTED_EXPECTATION_TYPES = ["not_null", "unique", "min", "max", "regex", "allowed_values"]


def _not_null(df: pd.DataFrame, parameters: dict) -> tuple[bool, dict]:
    column = parameters["column"]
    null_count = int(df[column].isna().sum())
    return null_count == 0, {"column": column, "null_count": null_count}


def _unique(df: pd.DataFrame, parameters: dict) -> tuple[bool, dict]:
    column = parameters["column"]
    duplicate_count = int(df[column].duplicated().sum())
    return duplicate_count == 0, {"column": column, "duplicate_count": duplicate_count}


def _min(df: pd.DataFrame, parameters: dict) -> tuple[bool, dict]:
    column = parameters["column"]
    threshold = parameters["value"]
    violations = int((df[column] < threshold).sum())
    return violations == 0, {"column": column, "violations": violations, "min": threshold}


def _max(df: pd.DataFrame, parameters: dict) -> tuple[bool, dict]:
    column = parameters["column"]
    threshold = parameters["value"]
    violations = int((df[column] > threshold).sum())
    return violations == 0, {"column": column, "violations": violations, "max": threshold}


def _regex(df: pd.DataFrame, parameters: dict) -> tuple[bool, dict]:
    column = parameters["column"]
    pattern = parameters["pattern"]
    compiled = re.compile(pattern)
    non_null = df[column].dropna().astype(str)
    violations = int((~non_null.str.match(compiled)).sum())
    return violations == 0, {"column": column, "violations": violations, "pattern": pattern}


def _allowed_values(df: pd.DataFrame, parameters: dict) -> tuple[bool, dict]:
    column = parameters["column"]
    allowed = set(parameters["values"])
    violations = int((~df[column].isin(allowed)).sum())
    return violations == 0, {"column": column, "violations": violations, "allowed": list(allowed)}


_EVALUATORS = {
    "not_null": _not_null,
    "unique": _unique,
    "min": _min,
    "max": _max,
    "regex": _regex,
    "allowed_values": _allowed_values,
}


def evaluate_expectation(df: pd.DataFrame, expectation_type: str, parameters: dict) -> tuple[bool, dict]:
    evaluator = _EVALUATORS.get(expectation_type)
    if evaluator is None:
        raise ValidationFailedError(f"unsupported expectation type '{expectation_type}'")
    column = parameters.get("column")
    if column and column not in df.columns:
        raise ValidationFailedError(f"expectation references unknown column '{column}'")
    return evaluator(df, parameters)
