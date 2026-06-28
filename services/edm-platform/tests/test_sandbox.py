import pandas as pd
import pytest

from app.sandbox import execute_code_cells


def test_single_cell_transforms_dataframe():
    df = pd.DataFrame({"name": [" Ada ", " Lin "], "amount": [91, 77]})
    results = execute_code_cells(df, ["df['name'] = df['name'].str.strip()"])
    assert results[0]["status"] == "ok"
    assert results[0]["preview"][0]["name"] == "Ada"


def test_multiple_cells_share_state_in_order():
    df = pd.DataFrame({"x": [1, 2, 3]})
    results = execute_code_cells(
        df,
        [
            "df['y'] = df['x'] * 2",
            "df = df[df['y'] > 2]",
        ],
    )
    assert results[0]["status"] == "ok"
    assert results[1]["status"] == "ok"
    assert results[1]["row_count"] == 2


def test_print_output_is_captured():
    df = pd.DataFrame({"x": [1]})
    results = execute_code_cells(df, ["print('hello from sandbox')"])
    assert "hello from sandbox" in results[0]["stdout"]


def test_disallowed_import_is_blocked():
    df = pd.DataFrame({"x": [1]})
    results = execute_code_cells(df, ["import os\ndf['x'] = 1"])
    assert results[0]["status"] == "error"
    assert "not allowed" in results[0]["error"]


def test_dangerous_builtin_is_unavailable():
    df = pd.DataFrame({"x": [1]})
    results = execute_code_cells(df, ["open('C:/Windows/win.ini')"])
    assert results[0]["status"] == "error"
    assert "NameError" in results[0]["error"]


def test_stops_at_first_failing_cell():
    df = pd.DataFrame({"x": [1]})
    results = execute_code_cells(
        df,
        [
            "df['y'] = 1 / 0",
            "df['z'] = 99",
        ],
    )
    assert len(results) == 1
    assert results[0]["status"] == "error"


def test_infinite_loop_times_out():
    df = pd.DataFrame({"x": [1]})
    with pytest.raises(TimeoutError):
        execute_code_cells(df, ["while True:\n    pass"], timeout_seconds=2)


def test_cell_must_leave_df_bound():
    df = pd.DataFrame({"x": [1]})
    results = execute_code_cells(df, ["del df"])
    assert results[0]["status"] == "error"
