# edm-platform

The MVP modular monolith: `edm-core`, `edm-auth`, `edm-workspace`, `edm-source`,
`edm-ingestion`, `edm-pipeline`, `edm-job`, `edm-storage`, `edm-catalog`, `edm-metadata`, and
`edm-query` as internal Python packages behind one FastAPI app. See
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
2. `POST /api/v1/workspaces`, `POST /api/v1/workspaces/{id}/projects`
3. `POST /api/v1/projects/{id}/sources` (`connector_type: csv`)
4. `POST /api/v1/sources/{id}/upload` (multipart file upload)
5. `POST /api/v1/projects/{id}/pipelines` with `transformations: [{"type": "standardize"}, {"type": "dedupe"}]`
6. `POST /api/v1/pipelines/{id}/jobs` -> triggers execution, returns a `Job` with `status`
7. `GET /api/v1/catalog/datasets` / `GET /api/v1/catalog/datasets/{id}` -> the resulting Dataset + Schema
8. `POST /api/v1/query` with `{"dataset_id": "...", "sql": "SELECT * FROM dataset LIMIT 10"}`

## Tests

```
.venv\Scripts\python.exe -m pytest
```

`tests/test_golden_path.py` exercises steps 1-8 end to end against a temporary SQLite DB and
local data directory.

## Swapping in real infrastructure later

Nothing above changes. Update `.env`:

- `DATABASE_URL` -> the Postgres URL from `infrastructure/docker/docker-compose.yml`
- Swap `app/modules/storage/adapter.py`'s `storage` singleton for a MinIO-backed adapter
- `EVENT_BUS=kafka` once a real producer is wired into `app/events.py`
