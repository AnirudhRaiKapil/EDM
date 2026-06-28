# edm-platform

The MVP modular monolith: `edm-core`, `edm-auth`, `edm-workspace`, `edm-source`,
`edm-ingestion`, `edm-pipeline`, `edm-job`, `edm-storage`, `edm-catalog`, `edm-metadata`,
`edm-quality`, `edm-lineage`, and `edm-query` as internal Python packages behind one FastAPI app
(`edm-quality` and `edm-lineage` were originally scoped as V2 in 01-product-architecture.md but
were pulled forward because data quality and lineage were explicit, heavily-emphasized
requirements in 00-vision-and-requirements.md). See
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

## The golden path (matches the MVP definition in docs/16-build-roadmap.md)

1. `POST /api/v1/auth/register`, `POST /api/v1/auth/login` -> bearer token
2. `POST /api/v1/workspaces` (creator is auto-assigned the `owner` role) -> `POST /api/v1/workspaces/{id}/projects`
3. `POST /api/v1/projects/{id}/sources` (`connector_type: csv`, `json`, or `sqlite`)
4. `POST /api/v1/sources/{id}/upload` (multipart file upload — `csv`/`json` only; `sqlite`
   sources read directly from `connection_config.db_path` on each job run, no upload needed)
5. `POST /api/v1/projects/{id}/pipelines` with a `transformations` list (see Transformation types below)
6. `POST /api/v1/pipelines/{id}/jobs` -> triggers execution, returns a `Job` with `status`
7. `GET /api/v1/catalog/datasets` / `GET /api/v1/catalog/datasets/{id}` -> the resulting Dataset + Schema
8. `POST /api/v1/query` with `{"dataset_id": "...", "sql": "SELECT * FROM dataset LIMIT 10"}`

Every workspace-scoped endpoint requires the caller to hold a `RoleAssignment` on that
workspace (`owner` or `member`) — see `app/permissions.py`. Owners can manage membership via
`POST /api/v1/workspaces/{id}/members` (`{"email": "...", "role": "owner"|"member"}`) and
`GET /api/v1/workspaces/{id}/members`.

### Connector types (`app/modules/ingestion/connectors.py`)
`csv`, `json` (file upload), `sqlite` (`connection_config: {"db_path": "...", "table": "..."}`
or `{"db_path": "...", "query": "SELECT ..."}` — SELECT-only, table names validated against an
identifier pattern). Network databases (Postgres/MySQL/etc.) are intentionally not yet supported:
they need per-source credential storage, which is out of scope until Vault lands (ADR-0003)  —
stuffing a plaintext password into `connection_config` would contradict the platform's own
security principles, so SQLite (no credentials needed) is the connector for now.

### Transformation types (`app/modules/pipeline/transformations.py`)
`standardize`, `dedupe`, `select_columns`, `rename_columns`, `fill_nulls`, `filter_rows`

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
rather than replace edges.

## Swapping in real infrastructure later

Nothing above changes. Update `.env`:

- `DATABASE_URL` -> the Postgres URL from `infrastructure/docker/docker-compose.yml`
- Swap `app/modules/storage/adapter.py`'s `storage` singleton for a MinIO-backed adapter
- `EVENT_BUS=kafka` once a real producer is wired into `app/events.py`
