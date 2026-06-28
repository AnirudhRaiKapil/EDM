"""Restricted Python execution for user-authored notebook/pipeline code.

Security model (see ADR-0010): this is defense-in-depth against accidental
mistakes (typos, infinite loops, obviously dangerous calls), NOT a security
boundary against a determined attacker. The executed code runs in a separate
OS process (so a hang/crash can't take down the API server, and a hard
wall-clock timeout can actually kill it -- threads can't be force-killed in
Python), with a restricted `__import__` and a restricted builtins namespace.
But it is the same OS user with the same filesystem/network access as the
server itself, and Python's introspection (`().__class__.__bases__`, etc.)
can reach unrestricted builtins even without `__import__` -- a sufficiently
motivated user *could* escape this. Real isolation needs OS-level sandboxing
(a container per execution, gVisor, nsjail), which needs Docker, which
ADR-0004 ruled out on this machine. Do not expose this to untrusted users.
"""

import builtins
import io
import multiprocessing
from contextlib import redirect_stdout

import pandas as pd

ALLOWED_MODULES = {"pandas", "numpy", "re", "datetime", "math", "json", "statistics", "decimal"}
EXECUTION_TIMEOUT_SECONDS = 15
PREVIEW_ROW_LIMIT = 50

_SAFE_BUILTIN_NAMES = [
    "abs", "all", "any", "bool", "dict", "enumerate", "filter", "float", "int", "len",
    "list", "map", "max", "min", "print", "range", "round", "set", "sorted", "str",
    "sum", "tuple", "zip", "isinstance", "Exception", "ValueError", "TypeError",
    "KeyError", "IndexError", "AttributeError", "StopIteration", "True", "False", "None",
]


def _restricted_import(name, *args, **kwargs):
    root = name.split(".")[0]
    if root not in ALLOWED_MODULES:
        raise ImportError(f"import of '{name}' is not allowed in sandboxed code")
    return builtins.__import__(name, *args, **kwargs)


def _safe_builtins() -> dict:
    safe = {n: getattr(builtins, n) for n in _SAFE_BUILTIN_NAMES}
    safe["__import__"] = _restricted_import
    return safe


def _execute_one(code: str, df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    sandbox_globals = {"__builtins__": _safe_builtins(), "pd": pd, "df": df}
    stdout_capture = io.StringIO()
    with redirect_stdout(stdout_capture):
        exec(compile(code, "<cell>", "exec"), sandbox_globals)
    result_df = sandbox_globals.get("df")
    if not isinstance(result_df, pd.DataFrame):
        raise TypeError("cell code must leave 'df' bound to a pandas DataFrame")
    # "data" is the FULL result, used to reconstruct the real DataFrame for the next
    # cell or for a pipeline run; "preview" is capped, for UI display only. A caller
    # that mistakenly used "preview" to continue processing would silently truncate
    # real data past PREVIEW_ROW_LIMIT rows -- keep these two uses distinct.
    info = {
        "status": "ok",
        "stdout": stdout_capture.getvalue(),
        "data": result_df.to_dict(orient="records"),
        "preview": result_df.head(PREVIEW_ROW_LIMIT).to_dict(orient="records"),
        "row_count": len(result_df),
        "columns": list(result_df.columns),
    }
    return result_df, info


def _run_in_subprocess(code_blocks: list[str], records: list[dict], columns: list[str], queue) -> None:
    df = pd.DataFrame(records, columns=columns if not records else None)
    results = []
    for code in code_blocks:
        try:
            df, info = _execute_one(code, df)
            results.append(info)
        except Exception as exc:
            results.append({"status": "error", "stdout": "", "error": f"{type(exc).__name__}: {exc}"})
            break
    queue.put(results)


def execute_code_cells(
    df: pd.DataFrame, code_blocks: list[str], timeout_seconds: float = EXECUTION_TIMEOUT_SECONDS
) -> list[dict]:
    """Runs each code block in order in one fresh subprocess, sharing `df` across
    blocks the way sequential Jupyter cells share kernel state. Stops at the first
    failing block. Returns one result dict per block actually executed."""
    if not code_blocks:
        return []

    ctx = multiprocessing.get_context("spawn")
    queue = ctx.Queue()
    process = ctx.Process(
        target=_run_in_subprocess,
        args=(code_blocks, df.to_dict(orient="records"), list(df.columns), queue),
    )
    process.start()
    process.join(timeout_seconds)
    if process.is_alive():
        process.terminate()
        process.join()
        raise TimeoutError(f"code execution exceeded {timeout_seconds}s and was terminated")
    if queue.empty():
        raise RuntimeError("sandboxed process exited without returning a result (likely crashed)")
    return queue.get()
