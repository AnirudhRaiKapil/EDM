import pandas as pd
import pytest

from app.modules.core.exceptions import ValidationFailedError
from app.modules.pipeline.transformations import apply_transformation


def test_select_columns_keeps_only_requested():
    df = pd.DataFrame({"a": [1, 2], "b": [3, 4], "c": [5, 6]})
    result = apply_transformation(df, "select_columns", {"columns": ["a", "c"]})
    assert list(result.columns) == ["a", "c"]


def test_select_columns_rejects_unknown_column():
    df = pd.DataFrame({"a": [1]})
    with pytest.raises(ValidationFailedError):
        apply_transformation(df, "select_columns", {"columns": ["nope"]})


def test_rename_columns():
    df = pd.DataFrame({"old_name": [1, 2]})
    result = apply_transformation(df, "rename_columns", {"mapping": {"old_name": "new_name"}})
    assert list(result.columns) == ["new_name"]


def test_fill_nulls_specific_columns():
    df = pd.DataFrame({"a": [1, None], "b": [None, 2]})
    result = apply_transformation(df, "fill_nulls", {"value": 0, "columns": ["a"]})
    assert result["a"].tolist() == [1, 0]
    assert result["b"].isna().sum() == 1


def test_filter_rows_gt():
    df = pd.DataFrame({"age": [10, 20, 30]})
    result = apply_transformation(df, "filter_rows", {"column": "age", "operator": "gt", "value": 15})
    assert result["age"].tolist() == [20, 30]


def test_filter_rows_not_null():
    df = pd.DataFrame({"x": [1, None, 3]})
    result = apply_transformation(df, "filter_rows", {"column": "x", "operator": "not_null"})
    assert result["x"].tolist() == [1, 3]
