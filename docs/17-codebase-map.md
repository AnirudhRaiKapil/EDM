# EDM Platform — Codebase Map

A file/folder-by-file explanation of what exists in this repo right now and what each piece is
for. This is a **living document** — per [Rule 11](03-engineering-principles.md#rule-11--docs-stay-in-sync-with-code),
it gets updated in the same change that adds, moves, or repurposes a file, not afterward. If you
find a file this doc doesn't mention, that's a bug in this doc.

Status legend: **Built** (has working code + tests) · **Placeholder** (directory exists per
[04-repository-structure.md](04-repository-structure.md), nothing implemented yet).

## Top level

| Path | Status | What it's for |
|---|---|---|
| `README.md` | Built | Entry point: states the platform's identity and links every doc below. |
| `docs/` | Built | Design baseline — vision, architecture, domain model, principles, ADRs. Read before changing anything structural. |
| `services/edm-platform/` | Built | The actual product: one FastAPI modular monolith implementing every MVP+ module. |
| `cli/` | Built | `edm-cli` — thin command-line client over the API. |
| `infrastructure/` | Partial | `docker/docker-compose.yml` (Postgres+MinIO+Kafka) exists but is unverified on this dev machine ([ADR-0004](adr/0004-wsl2-docker-deferred-on-dev-laptop.md)); `helm/`, `kubernetes/`, `terraform/` are empty placeholders for later. |
| `ui/` | Built | `edm-ui` — Vite + React + TypeScript web client, see [ADR-0007](adr/0007-react-ui-and-cors-fix.md). |
| `sdk/` | Placeholder | Future generated/hand-written client libraries (the SDK `edm-cli` itself could eventually be built on top of). Nothing here yet. |
| `integrations/` | Placeholder | Future home for connector definitions referenced by `edm-ingestion`, beyond what's inlined in `app/modules/ingestion/connectors.py` today. Nothing here yet. |
| `examples/` | Placeholder | Future sample pipelines/source configs for demos. Nothing here yet. |
| `tests/` (top level) | Placeholder | Reserved for cross-module/e2e tests per [04-repository-structure.md](04-repository-structure.md); all current tests live under `services/edm-platform/tests/` because there's only one module today. |
| `.github/workflows/test.yml` | Built | CI: runs the full `services/edm-platform` pytest suite, installs `cli/` and smoke-checks `edm --help`, and runs `ui/`'s `tsc -b && vite build` — all on every push/PR to `main`. The UI's Playwright e2e suite is not in CI yet (see `ui/README.md`). |
| `.claude/` | N/A | Claude Code tool settings for this workspace, not part of the platform itself. |

## `docs/`

| File | Covers |
|---|---|
| `00-vision-and-requirements.md` | Why the platform exists, the zero-cost/open-source constraint, every functional requirement. The frozen baseline — deviations go in an ADR, not silent edits here. |
| `01-product-architecture.md` | Layered logical architecture, control-plane/data-plane split, the full `edm-*` module map (MVP and V2), tech stack tables (data plane engines + control plane, both superseded in part by ADR-0002/0003). |
| `02-domain-model.md` | The canonical entities (Workspace, Project, Source, Pipeline, Job, Dataset, Schema, Column, QualityRule, etc.), their relationships, and lifecycle state machines. Every DB table, API resource, and event topic name traces back to this doc. |
| `03-engineering-principles.md` | The 11 rules every change follows (this map exists because of Rule 11). |
| `04-repository-structure.md` | The intended monorepo layout — this codebase map is the detailed companion to it. |
| `16-build-roadmap.md` | Phased build order, the MVP definition, and a running log of what's actually been built vs. what's still open. |
| `adr/0000-adr-template.md` | Template for new ADRs. |
| `adr/0001-apache-iceberg-as-table-format.md` | Why Iceberg is the target table format (not yet wired up — Spark/Trino/Iceberg are deferred per ADR-0003). |
| `adr/0002-python-fastapi-modular-monolith.md` | Why the backend is Python+FastAPI as one deployable process instead of 11 Java/Spring microservices. |
| `adr/0003-trimmed-phase-1-stack.md` | The full table of "real engine -> MVP substitute" swaps (Postgres->SQLite, Kafka->in-process bus, Spark->pandas, Trino->DuckDB, Keycloak->self-issued JWT, etc.) and why each is safe to defer. |
| `adr/0004-wsl2-docker-deferred-on-dev-laptop.md` | Why Docker-based infra is deferred *indefinitely* on this laptop (VBS/nested-virtualization conflict), not just until installed. |
| `adr/0005-quality-pulled-into-mvp.md` | Why `edm-quality` was pulled forward from the V2 module list into the MVP. |
| `adr/0006-lineage-pulled-into-mvp.md` | Why `edm-lineage` was pulled forward from the V2 module list into the MVP. |
| `adr/0007-react-ui-and-cors-fix.md` | UI tech stack choices, and why `CORSMiddleware` had to be added to the backend (the UI was the first cross-origin browser client). |
| `adr/0008-alerting-pulled-into-mvp.md` | Why `edm-alerting` was pulled forward from the V2 module list into the MVP, and why alerts are created by direct call from `edm-job` rather than via the event bus. |
| `diagrams/` | Empty — reserved for diagram source files (excalidraw/mermaid/drawio) if/when needed. |

## `services/edm-platform/` — the application

One FastAPI process. Internally split into `app/modules/<name>/`, each with its own
`models.py` (SQLAlchemy ORM), `schemas.py` (Pydantic request/response shapes), `service.py`
(business logic, the only thing other modules are allowed to call), and `router.py` (HTTP
endpoints under `/api/v1`). A module never imports another module's `models.py` directly.

### App-level files (`app/`)

| File | What it does |
|---|---|
| `main.py` | Builds the FastAPI app, imports every module's models so `Base.metadata` is complete before table creation, mounts every router under `/api/v1`, registers `CORSMiddleware` (added once `edm-ui` made the first cross-origin browser request — ADR-0007), and registers the `EdmError -> JSONResponse` exception handler. The single file that wires the whole monolith together. |
| `config.py` | `Settings` (pydantic-settings) — reads `.env` for `DATABASE_URL`, `DATA_DIR`, `JWT_SECRET`, `EVENT_BUS`, `CORS_ORIGINS`, etc. One instance, created at import time (see the test-isolation note in `tests/conftest.py` below for why that matters). |
| `database.py` | SQLAlchemy `engine`/`SessionLocal`/`Base`, and the `get_db` FastAPI dependency every router uses. |
| `events.py` | The in-process event bus (`publish`/`subscribe`) — logs every event and is the swap point for a real Kafka producer later (ADR-0003). Topic names match `02-domain-model.md` Section 5. |
| `deps.py` | `get_current_user` — decodes the bearer token and loads the `User`, used by every authenticated route. |
| `permissions.py` | Cross-module authorization helpers (`require_project_access`, `require_source_access`, `require_pipeline_access`, `require_job_access`) that resolve a resource back to its owning Workspace and check the caller's `RoleAssignment`. This is the one file allowed to import service functions from multiple modules, because enforcing access control is inherently cross-cutting. |

### `app/modules/core/` — shared kernel, no HTTP surface

| File | What it does |
|---|---|
| `models.py` | Mixins every other module's models inherit: `UUIDPrimaryKeyMixin`, `TimestampMixin`, `OwnedMixin` (Rule 7: every object has a non-nullable owner). |
| `exceptions.py` | The `EdmError` hierarchy (`NotFoundError` 404, `ConflictError` 409, `UnauthorizedError` 401, `ForbiddenError` 403, `ValidationFailedError` 422, `QualityCheckFailedError` 422) — `main.py`'s exception handler maps these straight to HTTP responses. |

### `app/modules/auth/` — identity and workspace-level RBAC

| File | What it does |
|---|---|
| `models.py` | `User`; `RoleAssignment` (binds a user to a `workspace`-scoped `owner`/`member` role — the MVP-scoped simplification of the full Role/Permission model in `02-domain-model.md`, documented inline and in ADR territory). |
| `security.py` | Password hashing (stdlib PBKDF2-HMAC, no extra native dependency) and JWT issue/decode (PyJWT, HS256). |
| `schemas.py` | `UserCreate`, `UserLogin`, `UserRead`, `Token`. |
| `service.py` | Register/authenticate users; `assign_workspace_role`, `get_workspace_role`, `require_workspace_role` (404s if you're not a member at all — doesn't leak existence — 403s if you are a member but lack the right role), `list_workspace_members`, `list_user_workspace_ids`. |
| `router.py` | `POST /auth/register`, `POST /auth/login`, `GET /users/me`. |

### `app/modules/workspace/` — tenancy

| File | What it does |
|---|---|
| `models.py` | `Workspace`, `Project`. |
| `schemas.py` | `WorkspaceCreate/Read`, `ProjectCreate/Read`, `MemberAssign`, `MemberRead`. |
| `service.py` | Create/list workspaces (list is filtered to the caller's memberships — no leaking other tenants' workspaces); create/list projects; `get_workspace_id_for_project` (the lookup `permissions.py` uses to resolve project-scoped requests back to a workspace). Creating a workspace auto-assigns the creator the `owner` role. |
| `router.py` | `POST/GET /workspaces`, `GET /workspaces/{id}`, `POST/GET /workspaces/{id}/members`, `POST/GET /workspaces/{id}/projects`. |

### `app/modules/source/` — registered data sources

| File | What it does |
|---|---|
| `models.py` | `Source` — `connector_type`, `connection_config` (JSON, non-secret only per the domain model's `Source.connectionConfig`/`secretRef` split), `raw_file_path` for file-based connectors. |
| `schemas.py` | `SUPPORTED_CONNECTOR_TYPES = ["csv", "json", "sqlite"]`; `SourceCreate/Read`. |
| `service.py` | Create/list/get a Source; validates `connection_config` shape per connector type (e.g. `sqlite` needs `db_path` + `table`/`query`); `attach_raw_file` after an upload. |
| `router.py` | `POST/GET /projects/{id}/sources`, `GET /sources/{id}` — all permission-checked via `app/permissions.py`. |

### `app/modules/ingestion/` — turning a Source into a DataFrame

| File | What it does |
|---|---|
| `connectors.py` | `load_source_dataframe(source)` — dispatches to `pd.read_csv`/`pd.read_json` for file sources, or `_load_sqlite` for `connector_type="sqlite"` (validates the query is `SELECT`-only, validates table names against an identifier pattern, reads via stdlib `sqlite3` + `pd.read_sql_query`). Network databases (Postgres/MySQL/etc.) are intentionally not supported yet — they'd need per-source credential storage that doesn't exist until Vault lands (ADR-0003); see the README note in `services/edm-platform/README.md`. |
| `router.py` | `POST /sources/{id}/upload` (multipart) — saves the file via the storage adapter and calls `attach_raw_file`. |

### `app/modules/pipeline/` — declarative transform definitions

| File | What it does |
|---|---|
| `models.py` | `Pipeline` (source, output dataset name/layer, version, status), `Transformation` (ordered steps, JSON parameters) — metadata-driven per Rule 4, not bespoke scripts. |
| `transformations.py` | The six transformation implementations: `standardize`, `dedupe`, `select_columns`, `rename_columns`, `fill_nulls`, `filter_rows` — each a pure `(DataFrame, parameters) -> DataFrame` function, dispatched by `apply_transformation`. |
| `schemas.py` | `TransformationCreate/Read`, `PipelineCreate/Read`. |
| `service.py` | Create/list/get a Pipeline, validating its source and transformation types up front. |
| `router.py` | `POST/GET /projects/{id}/pipelines`, `GET /pipelines/{id}`. |

### `app/modules/job/` — pipeline execution

| File | What it does |
|---|---|
| `models.py` | `Job` — status, trigger, timestamps, `metrics` (rows in/out, quality outcome), `error_message`, `dataset_id` produced. |
| `schemas.py` | `JobRead`. |
| `service.py` | `run_pipeline` — the orchestration core: load source data -> apply transformations in order -> if the output Dataset already exists, evaluate its quality rules *before* touching storage (a `blocking` failure raises and the previously published data is left untouched) -> write Parquet via the storage adapter -> create a new Schema version -> record `source->dataset` and `pipeline->dataset` lineage edges -> raise an `Alert` if quality passed with warnings -> mark the Job succeeded, or on any exception (including a quality `blocking` failure) mark it failed and raise a `critical` `Alert` — publishing `pipeline.started`/`completed`/`failed` events throughout. |
| `router.py` | `POST /pipelines/{id}/jobs` (trigger), `GET /pipelines/{id}/jobs`, `GET /jobs/{id}`. |

### `app/modules/storage/` — object storage abstraction

| File | What it does |
|---|---|
| `adapter.py` | `StorageAdapter` interface + `LocalDiskStorageAdapter` (today's implementation, ADR-0003) — `save_raw_upload` (sanitizes the filename to its basename, closing a path-traversal angle regardless of what a client sends), `save_dataframe`/`read_dataframe` (Parquet under `bronze/`, `silver/`, or `gold/`), `absolute_path`. A `MinIOStorageAdapter` implementing the same interface is the planned swap-in, no caller changes needed. |

### `app/modules/catalog/` — discovery, tags, classification

| File | What it does |
|---|---|
| `models.py` | `Dataset` (layer, physical location, current schema pointer, classification list, quality score), `Tag` (generic `entity_type`/`entity_id`/`key`/`value` — currently only used for datasets). |
| `schemas.py` | `DatasetRead/DetailRead`, `DatasetClassificationUpdate`, `TagCreate/Read`. |
| `service.py` | Register a dataset, attach a schema version, `get_dataset_by_name` (the find-or-create lookup `edm-job` uses so a pipeline's repeated runs update the *same* dataset rather than creating duplicates), search/list (with optional tag filtering via a subquery), tag add/list/remove, classification update. |
| `router.py` | `GET /catalog/datasets` (search, open to any authenticated user — metadata-only, no real data), `GET /catalog/datasets/{id}` (includes schema + tags), `PATCH /catalog/datasets/{id}` (classification), `POST/DELETE /catalog/datasets/{id}/tags[/{tag_id}]` (these mutations *are* permission-checked, resolved via the dataset's project). |

### `app/modules/metadata/` — schema registry

| File | What it does |
|---|---|
| `models.py` | `Schema` (versioned, `active`/`superseded`), `Column` (name, inferred type, nullable, description). |
| `schemas.py` | `ColumnRead`, `SchemaRead`. |
| `service.py` | `create_new_schema_version` — infers column types/nullability from a pandas DataFrame's dtypes, marks the dataset's previous schema `superseded` (never deleted, so history/time-travel stays intact) and creates the new `active` version. |

### `app/modules/quality/` — validation that blocks bad publications

| File | What it does |
|---|---|
| `models.py` | `QualityRule` (attached to a Dataset — `expectation_type`, `parameters`, `severity`), `QualityRun` (the result of evaluating a dataset's rules at a point in time, optionally tied to the `Job` that triggered it). |
| `expectations.py` | Six expectation evaluators: `not_null`, `unique`, `min`, `max`, `regex`, `allowed_values` — each `(DataFrame, parameters) -> (passed, details)`. |
| `service.py` | `create_rule`/`list_rules`/`delete_rule`; `evaluate_rules` — runs every rule for a dataset against a candidate DataFrame, records a `QualityRun`, and returns `"passed"`/`"passed_with_warnings"`/`"failed"` (failed = at least one `blocking` rule failed). Publishes `quality.evaluated`/`quality.failed` events. |
| `router.py` | `POST/GET /catalog/datasets/{id}/quality-rules`, `DELETE .../quality-rules/{rule_id}`, `GET /catalog/datasets/{id}/quality-runs`. |

### `app/modules/lineage/` — where did this dataset's data come from

| File | What it does |
|---|---|
| `models.py` | `LineageEdge` — generic directed edge (`from_entity_type`/`from_entity_id` -> `to_entity_type`/`to_entity_id`), optionally tied to the `Job` that created it. The graph is just the union of rows in this table, per `02-domain-model.md`. |
| `schemas.py` | `LineageEdgeRead`, `LineageGraphRead` (`{entity_type, entity_id, upstream, downstream}`). |
| `service.py` | `record_edge` (publishes `lineage.edge_recorded`), `get_upstream`/`get_downstream` (query the same table from either direction — edges are append-only, so reruns add new edges rather than overwriting). `edm-job` calls `record_edge` twice per successful run. |
| `router.py` | `GET /lineage/datasets/{id}`, `GET /lineage/sources/{id}`, `GET /lineage/pipelines/{id}` — each resolves the entity back to its project for the permission check, then returns its upstream+downstream edges. |

### `app/modules/alerting/` — what's currently broken

| File | What it does |
|---|---|
| `models.py` | `Alert` — `project_id` (so listing is permission-checkable the same way as every other project-scoped resource), generic `source_entity_type`/`source_entity_id`, `severity` (`info`/`warning`/`critical`), `message`, `status` (`open`/`acknowledged`/`resolved`). |
| `schemas.py` | `AlertRead`, `AlertStatusUpdate`. |
| `service.py` | `create_alert` (publishes `alert.created`), `list_alerts` (optional `status` filter), `update_status`. Called directly from `edm-job`, not via the event bus — see [ADR-0008](adr/0008-alerting-pulled-into-mvp.md) for why. |
| `router.py` | `GET /projects/{id}/alerts` (optional `?status=`), `PATCH /alerts/{id}` (`{"status": "acknowledged"\|"resolved"\|"open"}`). |

### `app/modules/query/` — read access to published data

| File | What it does |
|---|---|
| `schemas.py` | `QueryRequest` (`dataset_id`, `sql`), `QueryResponse` (`columns`, `rows`, `row_count`). |
| `service.py` | `run_query` — rejects anything that isn't a `SELECT`, registers the dataset's Parquet file as a DuckDB view named `dataset`, executes the caller's SQL against it. DuckDB is the MVP substitute for Trino (ADR-0003). |
| `router.py` | `POST /query` — the one query endpoint that *is* permission-checked (it returns real row data, unlike catalog search), resolved via the dataset's project. |

### `services/edm-platform/tests/`

| File | What it covers |
|---|---|
| `conftest.py` | The shared `client` fixture — gives every test a fresh SQLite DB and local data directory via FastAPI's `dependency_overrides` (not env vars: `Settings`/the engine are created once at import time, so per-test `monkeypatch.setenv` alone doesn't isolate tests within one pytest process — this fixture is the fix for a real bug that bug caused). |
| `test_golden_path.py` | End-to-end: register -> workspace/project -> source -> upload -> pipeline -> job -> catalog -> query, for both a CSV source and a JSON source with `filter_rows`/`select_columns`. |
| `test_rbac.py` | Workspace creator becomes owner; non-members get 404 (not 403, to avoid leaking existence) on every workspace-scoped resource; members gain access after being added but can't manage membership themselves. |
| `test_transformations.py` | Unit tests for each of the six transformation functions. |
| `test_catalog_tags.py` | Tag add/list/filter/remove; classification update. |
| `test_sqlite_connector.py` | SQLite source via `table`, and that a non-`SELECT` query is rejected. |
| `test_quality.py` | A `blocking` rule failure rejects the batch and leaves the previously published dataset's row count unchanged; a `warning` rule failure still publishes but flags `qualityOutcome`. |
| `test_storage_adapter.py` | `save_raw_upload` strips path components from a client-supplied filename (the bug the CLI caught, plus an explicit traversal-attempt case). |
| `test_lineage.py` | A dataset's lineage correctly names its source and pipeline as upstream (and vice versa downstream); reruns append a new edge per job rather than replacing the old one. |
| `test_cors.py` | The configured UI origin gets `Access-Control-Allow-Origin` on preflight; an arbitrary origin doesn't. Regression test for the bug `edm-ui`'s first real run caught. |
| `test_alerting.py` | A failing job raises a `critical` alert; a quality-warning job still succeeds but raises a `warning` alert; acknowledge/resolve transitions; non-members get 404 on a project's alerts. |

### Other files in `services/edm-platform/`

| File | What it does |
|---|---|
| `requirements.txt` | Pinned dependencies — all chosen to have prebuilt Windows wheels (no compiler needed): fastapi, uvicorn, sqlalchemy, pydantic-settings, email-validator, pyjwt, pandas, duckdb, pyarrow, python-multipart, httpx, pytest. |
| `.env.example` | Every setting `config.py` reads, with inline comments on what to change to swap in real Postgres/MinIO/Kafka later. `.env` itself is gitignored. |
| `README.md` | How to run locally, the golden path as literal `curl`-able steps, connector/transformation/quality-rule reference, test notes. |

## `cli/` — the command-line client

| File | What it does |
|---|---|
| `edm_cli/config.py` | Where credentials persist (`~/.edm/credentials.json`) and where the API base URL comes from (`EDM_API_URL` env var, default `localhost:8000`). |
| `edm_cli/client.py` | `ApiClient` — injects the bearer token, raises `ApiError` with the server's `detail` message on any 4xx/5xx so the CLI can print something readable instead of a stack trace. |
| `edm_cli/main.py` | Every command, grouped by resource (`auth`, `workspace`, `project`, `source`, `pipeline`, `job`, `catalog`, `quality`, `lineage`, `alert`, `query`) — a thin 1:1 mapping onto the REST API, output as pretty-printed JSON. |
| `pyproject.toml` | Packages `edm_cli` and registers the `edm` console-script entry point. |
| `README.md` | Install steps, the golden path as CLI commands, and why this exists (it's what caught the path-handling bug in `app/modules/storage/adapter.py` — see `docs/16-build-roadmap.md`). |

## `ui/` — the web client (`edm-ui`)

Vite + React + TypeScript, per [ADR-0007](adr/0007-react-ui-and-cors-fix.md). One page per route;
no UI component library (plain CSS in `src/index.css`).

| File | What it does |
|---|---|
| `src/api/client.ts` | The axios instance every API call goes through — a request interceptor injects the bearer token from `localStorage`, a response interceptor turns any error into `ApiError` with the server's `detail` message. |
| `src/api/types.ts` | TypeScript interfaces mirroring every backend Pydantic schema (`Workspace`, `Source`, `Pipeline`, `Job`, `Dataset`, `QualityRule`, `LineageGraph`, etc.). |
| `src/api/endpoints.ts` | One typed async function per backend endpoint, grouped by resource in a single file (kept as one file deliberately — splitting into ten near-empty files wasn't worth the navigation overhead at this size). |
| `src/context/AuthContext.tsx` | `login`/`register`/`logout` + the current `User`; token persisted to `localStorage`, rehydrated via `whoami()` on load. |
| `src/components/ProtectedRoute.tsx` | Redirects to `/login` when there's no authenticated user; everything under it assumes `useAuth()` returns a real user. |
| `src/components/Layout.tsx` | The header/nav shell every authenticated page renders inside. |
| `src/components/StatusBadge.tsx` | Color-codes the status strings the backend returns (`succeeded`/`failed`/`passed_with_warnings`/etc.) consistently everywhere they appear. |
| `src/components/ErrorBanner.tsx` | Renders an `ApiError` (or any thrown error) as a one-line banner; every mutation's `error` state gets passed straight to this. |
| `src/pages/LoginPage.tsx`, `RegisterPage.tsx` | Auth forms; redirect to `/workspaces` on success. |
| `src/pages/WorkspacesPage.tsx` | List the caller's workspaces (membership-filtered by the backend, not the UI), create a new one. |
| `src/pages/WorkspaceDetailPage.tsx` | Projects (list + create) and members (list + add, owner-only enforced server-side) for one workspace. |
| `src/pages/ProjectDetailPage.tsx` | The densest page: a Sources tab (create, upload for file connectors, inline `connection_config` fields for `sqlite`), a Pipelines tab (create, with an inline repeatable transformation-step builder — type dropdown + a raw JSON `parameters` field per step), and an Alerts tab (status-filterable list, acknowledge/resolve). |
| `src/pages/PipelineDetailPage.tsx` | Transformation list, a "Run pipeline" button, and job history (status, rows in/out, quality outcome, link to the produced dataset) — polls while a job is `running`/`queued`. |
| `src/pages/CatalogPage.tsx` | Dataset search (by name substring, optionally scoped to a project via `?project_id=`). |
| `src/pages/DatasetDetailPage.tsx` | Everything about one dataset in one place: schema, tags + classification (editable), data quality (add/remove rules, run history), lineage (upstream/downstream), and a SQL query runner against it — one component per concern (`SchemaSection`, `TagsAndClassificationSection`, `QualitySection`, `LineageSection`, `QuerySection`). |
| `e2e/smoke.mjs` | A Playwright script (headless Chromium) that drives the *entire* golden path through real clicks/fills — register, workspace, project, source, upload, pipeline (with transformations), run, view dataset, tag, classify, add a quality rule, check lineage, run a query, then deliberately trigger a failing pipeline and walk its alert through acknowledge -> resolve — screenshotting every step and failing on any browser console error. This is what actually caught the CORS bug; see `ui/README.md`. Not wired into CI yet (would need both the backend and Vite dev server running simultaneously). |
| `package.json` | `npm run dev`/`build`/`e2e`/`e2e:install`. Dependencies: `react-router-dom` (routing), `@tanstack/react-query` (server-state caching/mutations), `axios` (HTTP). Dev-only: `playwright` (e2e), `vite`, `typescript`. |
| `.env.example` | `VITE_API_URL`, defaulting to `http://localhost:8000/api/v1`. |
| `README.md` | Run instructions, route map, e2e instructions, and the CORS bug story. |

## `infrastructure/docker/docker-compose.yml`

Postgres 16 + MinIO + Apache Kafka (KRaft mode, single broker, no ZooKeeper) — the target
Phase 1 stack for when Docker is available. Written and present in the repo, but **not verified
working** on the current dev machine (ADR-0004); treat it as a starting point to debug, not a
known-good baseline, until it's been brought up successfully somewhere.
