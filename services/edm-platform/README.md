# edm-platform

The MVP modular monolith: `edm-core`, `edm-auth`, `edm-workspace`, `edm-source`,
`edm-ingestion`, `edm-pipeline`, `edm-notebook`, `edm-job`, `edm-storage`, `edm-catalog`,
`edm-metadata`, `edm-quality`, `edm-lineage`, `edm-alerting`, and `edm-query` as internal Python
packages behind one FastAPI app (`edm-quality`, `edm-lineage`, and `edm-alerting` were originally
scoped as V2 in 01-product-architecture.md but were each pulled forward because they served
explicit, heavily-emphasized requirements in 00-vision-and-requirements.md — see
ADR-0005/0006/0008; `edm-notebook` wasn't in the original module map at all — see ADR-0010). See
[ADR-0002](../../docs/adr/0002-python-fastapi-modular-monolith.md) and
[ADR-0003](../../docs/adr/0003-trimmed-phase-1-stack.md) for why, and
[02-domain-model.md](../../docs/02-domain-model.md) for the entities these modules implement.

## Run locally (no Docker required yet)

```
py -3 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
copy .env.example .env
.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000
```

API docs: http://localhost:8000/docs · Health check: http://localhost:8000/health

**No migrations exist yet** (no Alembic — `Base.metadata.create_all()` only creates tables that
don't exist; it never alters an existing one). Every time a model gains a column, delete your
local `edm_platform.db` (and `data/`) and let it recreate from scratch, or your server will fail
on startup with `no such column: ...` the first time something queries that table — this is
exactly the bug that motivated this warning (the scheduler querying `Pipeline.schedule_cron`
against a pre-existing dev DB file that predated the column).

## The golden path (matches the MVP definition in docs/16-build-roadmap.md)

1. `POST /api/v1/auth/register`, `POST /api/v1/auth/login` -> bearer token
2. `POST /api/v1/workspaces` (creator is auto-assigned the `owner` role) -> `POST /api/v1/workspaces/{id}/projects`
3. `POST /api/v1/projects/{id}/sources` (`connector_type`: see below; pass `credentials` for
   anything that needs them — encrypted at rest, never returned by the API)
4. `POST /api/v1/sources/{id}/upload` (multipart file upload — `csv`/`json` only; every other
   connector type reads directly from its `connection_config` on each job run, no upload needed)
5. `POST /api/v1/projects/{id}/pipelines` with a `transformations` list (see Transformation types below)
6. `POST /api/v1/pipelines/{id}/jobs` -> triggers execution, returns a `Job` with `status`
7. `GET /api/v1/catalog/datasets` / `GET /api/v1/catalog/datasets/{id}` -> the resulting Dataset + Schema
8. `POST /api/v1/query` with `{"dataset_id": "...", "sql": "SELECT * FROM dataset LIMIT 10"}`

Every workspace-scoped endpoint requires the caller to hold a `RoleAssignment` on that
workspace (`owner` or `member`) — see `app/permissions.py`. Owners can manage membership via
`POST /api/v1/workspaces/{id}/members` (`{"email": "...", "role": "owner"|"member"}`) and
`GET /api/v1/workspaces/{id}/members`.

### Connector types (`app/modules/ingestion/connectors.py`, `app/modules/ingestion/specs.py`)
- `csv`, `json` — file upload.
- `sqlite` — `connection_config: {"db_path": "...", "table": "..."}` or `{..., "query": "SELECT ..."}` (SELECT-only, table names validated against an identifier pattern). No credentials needed.
- `oracle` — `connection_config: {"host", "port", "service_name", "table"|"query"}`, `credentials: {"username", "password"}`. Uses `python-oracledb` thin mode (no Oracle Client install).
- `s3` — `connection_config: {"bucket", "key", "region"?, "file_format"?}`, `credentials` optional (falls back to boto3's default credential chain).
- `rest_api` — fully generic: `connection_config: {"base_url", "path", "method"?, "auth_type": "none"|"bearer"|"basic"|"api_key_header", "records_path"?, "pagination"?}`. This is the connector for any enterprise REST API not named below.
- `servicenow` — `connection_config: {"instance_url", "table", "query"?}`, `credentials: {"username", "password"}`. Table API, offset pagination.
- `jira` — `connection_config: {"base_url", "jql"?}`, `credentials: {"email", "api_token"}`.
- `confluence` — `connection_config: {"base_url", "cql"?|"space_key"?}`, `credentials: {"email", "api_token"}`.

Credentials are encrypted at rest (`app/secrets.py`, Fernet) since real Vault remains out of
reach (ADR-0003/0004) — see [ADR-0009](../../docs/adr/0009-encrypted-secrets-and-enterprise-connectors.md)
for the full reasoning and which connectors are field-verified vs. logic-verified-only (no real
ServiceNow/Jira/Confluence/Oracle account or Docker-based emulator available in this environment
— only S3, via `moto`, gets genuine API-level verification).

### Transformation types (`app/modules/pipeline/transformations.py`)
`standardize`, `dedupe`, `select_columns`, `rename_columns`, `fill_nulls`, `filter_rows`,
`python_code` (runs `{"code": "..."}` through the restricted sandbox — see Notebooks below;
almost always reached via promoting a notebook rather than hand-authored)

### Notebooks (`app/modules/notebook/`) and pipeline scheduling — ADR-0010
Write Python in ordered cells, run them against a sample of a Source's data, then promote into a
real scheduled Pipeline:
- `POST /api/v1/projects/{id}/notebooks` `{"name", "source_id", "sample_size"?}` (default 100 rows)
- `POST /api/v1/notebooks/{id}/cells` `{"code"}`, `PATCH`/`DELETE .../cells/{cell_id}`
- `POST /api/v1/notebooks/{id}/run` (optional `?up_to_cell_id=...`) -> each cell's
  status/stdout/preview/error, run against `sample_size` rows of the source
- `POST /api/v1/notebooks/{id}/promote` `{"output_dataset_name", "output_layer"?}` -> concatenates
  every cell's code into one `python_code` Pipeline transformation and creates that Pipeline

Code runs in `app/sandbox.py`: a separate `multiprocessing` subprocess, a 15s hard timeout, an
import allowlist (`pandas`/`numpy`/`re`/`datetime`/`math`/`json`/`statistics`/`decimal`), and a
restricted builtins namespace. **This is defense-in-depth against accidents, not a security
boundary against a determined attacker** — see ADR-0010 for the full reasoning on why, and what
would be needed for real isolation (Docker, which ADR-0004 ruled out here).

Pipelines can run on a cron schedule instead of (or in addition to) on demand:
`PATCH /api/v1/pipelines/{id}/schedule` `{"cron": "0 * * * *"}` (or `{"cron": null}` to clear).
A background APScheduler instance (`app/scheduler.py`) fires `run_pipeline(..., trigger=
"scheduled")` on its own DB session at each tick — set `ENABLE_SCHEDULER=false` to disable it
entirely (tests do this; see `tests/conftest.py`).

### Data quality (`app/modules/quality/`)
Rules attach to a Dataset (so only after its first job run): `POST
/catalog/datasets/{id}/quality-rules` with `{"expectation_type": "...", "parameters": {"column":
"..."}, "severity": "warning"|"blocking"}`. Expectation types: `not_null`, `unique`, `min`,
`max`, `regex`, `allowed_values`. Every job run evaluates existing rules against its output
*before* writing storage/schema: a `blocking` failure fails the job and leaves the previously
published dataset/schema untouched (`GET /catalog/datasets/{id}/quality-runs` for history);
`warning` failures still publish but mark `job.metrics.qualityOutcome = "passed_with_warnings"`.

### Lineage (`app/modules/lineage/`)
Every successful job records two edges: `source -> dataset` and `pipeline -> dataset` (tagged
with the job that produced them). Trace either direction via `GET /lineage/datasets/{id}`,
`GET /lineage/sources/{id}`, or `GET /lineage/pipelines/{id}` — each returns `{upstream,
downstream}`. Reruns append new edges rather than replacing old ones, so the full run history
toward a dataset is preserved, not just the latest. Multi-hop dataset-to-dataset lineage (e.g. a
Gold pipeline consuming a Silver dataset) isn't representable yet — `Pipeline.source_id` only
points at a `Source` today, not at another `Dataset`.

### Alerting (`app/modules/alerting/`)
`edm-job` raises an `Alert` directly (not via the event bus — see ADR-0008) whenever a run fails
for any reason, or succeeds with `qualityOutcome: "passed_with_warnings"`. List a project's
alerts via `GET /projects/{id}/alerts` (optional `?status=open|acknowledged|resolved`), triage
via `PATCH /alerts/{id}` with `{"status": "acknowledged"|"resolved"|"open"}`.

## Tests

```
.venv\Scripts\python.exe -m pytest
```

`tests/conftest.py` gives every test a fresh SQLite DB and local data directory (via FastAPI
dependency overrides, not env vars — `Settings`/the SQLAlchemy engine are created once at
import time, so per-test env vars alone don't isolate tests within one pytest process).
`test_golden_path.py` covers CSV and JSON ingestion end to end; `test_rbac.py` covers
membership/ownership enforcement; `test_transformations.py` unit-tests each transformation;
`test_catalog_tags.py` covers tagging/classification; `test_sqlite_connector.py` covers the
SQLite connector, including rejecting non-`SELECT` queries; `test_quality.py` covers blocking
vs. warning severity, including that a blocking failure leaves prior published data intact;
`test_lineage.py` covers tracing a dataset back to its source/pipeline and that reruns append
rather than replace edges; `test_alerting.py` covers critical alerts on failure, warning alerts
on quality warnings, the acknowledge/resolve lifecycle, and that non-members can't see them;
`test_secrets.py` covers the encryption round-trip and that credentials never leak via the API;
`test_rest_client.py` covers the generic REST pagination/auth engine; `test_enterprise_connectors.py`,
`test_oracle_connector.py`, and `test_s3_connector.py` cover the new connectors (S3 against a
real in-memory `moto` S3 emulation; the rest against a mocked transport/connection only);
`test_sandbox.py` covers the restricted code executor in isolation (blocked imports/builtins,
timeout, multi-cell state sharing); `test_notebook.py` covers the full notebook lifecycle
including promote -> run -> query end to end; `test_scheduler.py` covers cron validation and
schedule set/clear via the API (the actual cron *firing* was verified live against a running
server, not in this suite — see ADR-0010).

## Swapping in real infrastructure later

Nothing above changes. Update `.env`:

- `DATABASE_URL` -> the Postgres URL from `infrastructure/docker/docker-compose.yml`
- Swap `app/modules/storage/adapter.py`'s `storage` singleton for a MinIO-backed adapter
- `EVENT_BUS=kafka` once a real producer is wired into `app/events.py`
