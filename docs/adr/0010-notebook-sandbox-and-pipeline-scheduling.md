# ADR-0010: Notebook-style interactive ETL dev, a restricted code sandbox, and cron pipeline scheduling

- **Status:** Accepted
- **Date:** 2026-06-28

## Context
The user asked for "something like a Jupyter notebook where we can write code and run and check
in dev and then once done we can save it automate the whole thing and runs on time schedule" —
two connected capabilities: (1) an interactive, code-first way to develop a transformation against
real (sampled) data before committing to it, and (2) turning a finished pipeline into something
that runs unattended on a schedule, not just on demand.

Neither capability existed. Pipelines (`edm-pipeline`) only supported a fixed menu of declarative
transformation types (`standardize`, `dedupe`, `select_columns`, `rename_columns`, `fill_nulls`,
`filter_rows`) — there was no way to express arbitrary logic, and no way to iterate on logic
without creating a real pipeline and running a real job for every attempt. Pipelines also had no
concept of a schedule; every job was `trigger=manual`, started only by an explicit API/CLI/UI call.

Before designing this, two genuinely open questions were put to the user (guessing wrong here
would have meant building the wrong thing):
1. How should notebook code actually execute? Embed real Jupyter, run code with no real
   isolation, or build a custom code-cell UI with restricted server-side execution? The user chose
   the custom code-cell UI, built into the platform.
2. Which AWS service should the connector ADR-0009 introduced target? The user chose S3.
   (That choice is recorded here only for the record; the connector itself is ADR-0009's.)

Real OS-level sandboxing (a container per execution) needs Docker, which
[ADR-0004](0004-wsl2-docker-deferred-on-dev-laptop.md) ruled out on this machine indefinitely. So
"restricted server-side execution" has to mean something short of real isolation, and that
limitation has to be designed in honestly rather than papered over.

## Decision

### Sandbox (`app/sandbox.py`)
User-authored code runs in a separate `multiprocessing` subprocess (`spawn` context — the only
option that's correct cross-platform, and the only one available at all on Windows, which this
dev machine is) with:
- A hard wall-clock timeout (`EXECUTION_TIMEOUT_SECONDS = 15`); on timeout the process is
  `.terminate()`-ed, since Python threads can't be force-killed.
- A restricted `__import__` — only `pandas`, `numpy`, `re`, `datetime`, `math`, `json`,
  `statistics`, `decimal` may be imported; anything else raises `ImportError`.
- A restricted `__builtins__` namespace (no `open`, `exec`, `eval`, no raw `__import__`, etc.) —
  only a fixed allowlist of safe names (`len`, `range`, `print`, the common type constructors, the
  common exception types, ...).

Every run executes the cell(s) against a fresh `pd.DataFrame` rebuilt from records passed through
a multiprocessing `Queue`; the convention is that code must leave a `pd.DataFrame` bound to `df` —
that's the only contract between a cell and the runner, deliberately mirroring how a real Jupyter
data-wrangling cell works (`df = df.something()`).

**This is explicitly defense-in-depth against accidental mistakes (typos, infinite loops, `import
os` out of habit) — not a security boundary against a determined attacker.** The subprocess is the
same OS user, with the same filesystem and network access, as the parent server process. A
sufficiently creative attacker could likely escape the import/builtins restriction (Python's
introspection is deep — e.g. reaching a forbidden object through an allowed one's attributes).
Real isolation needs an OS-level boundary (a container or VM per execution), which is the same
Docker dependency ADR-0004 already deferred. Until that's available, code execution is implicitly
scoped to users who already have legitimate write access inside this platform (project members) —
the threat model is "stop me from shooting myself in the foot," not "stop a malicious project
member," and that's a real, accepted limitation, not an oversight.

### Notebook (`app/modules/notebook/`)
A `Notebook` belongs to a `Project` and points at one `Source`; it holds an ordered list of
`NotebookCell`s (`code: str`). Execution is deliberately **stateless across runs**: every "run"
re-executes *all* cells, in order, from scratch, against a small sample of the source's data
(`Notebook.sample_size`, default 100 rows) — there is no long-lived kernel process per notebook
holding state between requests. This was chosen over a persistent-kernel model (closer to real
Jupyter) specifically because a long-lived code-execution process per open notebook multiplies the
sandbox's already-acknowledged risk surface for no commensurate benefit at this platform's current
scale; re-running a 100-row sample takes well under a second.

`POST /notebooks/{id}/run` accepts an optional `up_to_cell_id` so the UI can offer "run up to here"
without re-running cells below the one being edited.

**Promotion**: `POST /notebooks/{id}/promote` concatenates every cell's code with `"\n\n".join(...)`
into a single string and creates a real `Pipeline` with one transformation,
`{"type": "python_code", "parameters": {"code": <concatenated>}}`. This is the load-bearing design
choice that satisfies "save it, automate the whole thing": the exact code that was dev-tested,
cell by cell, against a sample, is the exact code that runs later — concatenated, but otherwise
byte-for-byte identical — against the full dataset, scheduled or on demand. No separate "compiled"
representation, no re-authoring step.

### `python_code` transformation (`app/modules/pipeline/transformations.py`)
A new transformation type that calls the same `execute_code_cells` sandbox with the pipeline's
full input DataFrame. The full (untruncated) result is used to build the output DataFrame — not
the preview, which the sandbox separately caps at 50 rows for UI display. (An early draft of this
conflated the two and would have silently truncated any pipeline run over 50 rows; caught and
fixed before it shipped, with a regression test — `test_python_code_does_not_truncate_rows_past_preview_limit`
— locking in the distinction.)

### Scheduling (`app/scheduler.py`)
`Pipeline` gained a `schedule_cron: str | None` column. A module-level APScheduler
`BackgroundScheduler` is started from `main.py`'s lifespan (gated by a new
`settings.enable_scheduler`, default `True`) and loads every pipeline with a non-null
`schedule_cron` at startup. `PATCH /pipelines/{id}/schedule` (body: `{"cron": "<expr>" | null}`)
validates the cron expression (`CronTrigger.from_crontab`) and calls `sync_schedule`, which
registers/replaces/removes that pipeline's APScheduler job immediately — no restart needed.
The scheduled callback (`_run_scheduled_pipeline`) runs on APScheduler's own background thread,
outside any HTTP request, so it opens its own `SessionLocal()` rather than using the request-scoped
`get_db()` dependency, and calls `run_pipeline(..., trigger="scheduled")` — the same job-execution
path a manual run takes, so scheduled and manual runs are indistinguishable except for the
`Job.trigger` field. Verified by actually waiting for a real minute boundary against a live server
with a `* * * * *` schedule and watching a `trigger: "scheduled"` job appear — not just unit-tested
registration logic.

`enable_scheduler` exists because the real `BackgroundScheduler` is a module-level singleton; left
unguarded, every test using the `TestClient` fixture would start it once per test process and
accumulate jobs pointed at long-gone per-test SQLite databases. Tests monkeypatch the already-
constructed `settings` object directly (`monkeypatch.setattr(settings, "enable_scheduler", False)`)
rather than setting an environment variable, because `Settings()` is itself a module-level
singleton constructed at first import — by the time any test fixture runs, some other test
module's top-level imports may already have triggered that construction during pytest's collection
phase, making an env-var-based toggle set inside a fixture too late to take effect.

## Alternatives Considered
- **Embed real Jupyter (e.g. `jupyter_client` + a kernel per notebook)** — rejected per the user's
  explicit choice, and also would have reintroduced exactly the long-lived-process risk surface
  the stateless-rerun design avoids.
- **No execution restrictions at all (plain `exec()`)** — rejected: this is server-side code
  execution reachable by any project member; the cost of a basic allowlist is low and it stops the
  large majority of accidental damage (stray `import os; os.system(...)`, infinite loops without a
  timeout) even though it doesn't stop a determined attacker.
- **Persistent per-notebook kernel state (incremental execution, like real Jupyter)** — rejected
  for now: meaningfully more complex (process lifecycle management, idle-kernel cleanup) for a
  benefit (faster iteration on slow cells) that doesn't matter yet at 100-row samples.
  Revisit if/when sample sizes or cell cost grow enough that full re-execution becomes the
  bottleneck.
- **A separate "compiled pipeline" representation distinct from the notebook's code** — rejected:
  the whole point of "automate the whole thing" is that what ran in dev is what runs on schedule;
  introducing a translation step would reopen exactly the dev/prod drift risk the user was trying
  to avoid by asking for this feature.
- **Celery beat / cron(1) / OS task scheduler for pipeline scheduling** — rejected: Celery needs a
  broker (Redis/RabbitMQ, more infrastructure ADR-0003 already chose to avoid); OS-level cron
  doesn't fit a $0, single-process, cross-platform (including Windows dev) deployment target.
  APScheduler is pure Python, already a dependency-free in-process choice, and was already sitting
  unused in `requirements.txt` from Part 1 of this phase of work.

## Consequences
- Code execution security rests on process-level isolation only (no container/VM boundary); this
  is an accepted, documented limitation, not a gap to silently work around later without
  revisiting Docker availability first.
- Every notebook run re-executes every cell from scratch; very expensive cell code would make
  iterative dev slower than a real incremental kernel would, but no such workload exists yet.
- `apscheduler` was already a listed dependency with nothing using it; this ADR is what finally
  exercises it.
- `Notebook`/`NotebookCell` were not in the original [02-domain-model.md](../02-domain-model.md)
  entity catalog — added there alongside this ADR, following the same "pulled forward, document
  why" pattern as ADR-0005/0006/0008.
- No migrations exist yet (see the backend README) — this ADR's `schedule_cron` column addition is
  what surfaced that gap concretely (a stale dev `edm_platform.db` predating the column broke
  scheduler startup with `no such column`); deleting the dev DB remains the workaround until a
  real migration tool is introduced.
