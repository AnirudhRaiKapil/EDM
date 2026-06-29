# EDM Platform — Build Roadmap

## Phased Build Order

**Phase 1 — Foundation (infrastructure only, no platform code yet)**
Kubernetes (or Docker Compose for local dev) · PostgreSQL · MinIO · Kafka · Airflow

**Phase 2 — Core Services**
API Gateway · Identity/Auth · Workspace · Metadata · Source · Pipeline

**Phase 3 — Processing**
Spark · Flink · Trino · Iceberg wiring into `edm-storage` / `edm-query`

**Phase 4 — Governance**
OpenMetadata · Great Expectations · Keycloak · Vault wired into `edm-governance` / `edm-quality`

**Phase 5 — UI**
React frontend · dashboards · catalog browser · pipeline builder

**Phase 6 — AI**
Natural-language SQL · pipeline generation · metadata assistant · lineage assistant · intelligent
monitoring

## MVP Definition (what "usable" means before Phase 4+)

The platform is *usable* once a user can, end to end, through the UI/API/CLI only (never
touching Kafka/Spark/Postgres directly):

1. Create a Workspace and Project.
2. Register a Source (start with: file upload / CSV, and one database type).
3. Define a Pipeline with at least one Transformation (e.g. standardize + dedupe) targeting a
   Dataset in the Bronze/Silver layer.
4. Trigger a Job (manual first, scheduled second — both done; see
   [ADR-0010](adr/0010-notebook-sandbox-and-pipeline-scheduling.md)) and watch it succeed/fail.
5. Find the resulting Dataset in the Catalog and query it.

That vertical slice exercises `edm-auth`, `edm-workspace`, `edm-source`, `edm-ingestion`,
`edm-pipeline`, `edm-job`, `edm-storage`, `edm-catalog`, `edm-metadata`, `edm-query` — i.e. the
entire Core/MVP module list in
[01-product-architecture.md](01-product-architecture.md#5-microservice--module-map) — and is the
recommended first milestone rather than building all eleven modules to completion in parallel.

## Longer-Term Vision

| Version | Focus |
|---|---|
| V1 — Enterprise Data Platform | Ingestion, ETL/ELT, Lakehouse, catalog, governance, query engine, monitoring |
| V2 — AI-Native Platform | AI copilot, NL-to-SQL, pipeline generation, data-quality recommendations, metadata generation, root-cause analysis, lineage explanations |
| V3 — Autonomous Data Platform | Self-healing pipelines, automatic schema evolution, intelligent workload optimization, auto-scaling, cost-aware scheduling, AI-driven governance, predictive data quality |

## Status

Locked in via ADR: backend is Python + FastAPI as a modular monolith
([ADR-0002](adr/0002-python-fastapi-modular-monolith.md)), running against lightweight
substitutes for Postgres/MinIO/Kafka/Spark/Trino/Keycloak/Airflow
([ADR-0003](adr/0003-trimmed-phase-1-stack.md)). WSL2 + Docker Engine were installed but the
WSL2 VM proved unstable on this laptop (VBS/nested-virtualization conflict); Docker-based infra
is deferred indefinitely, not just until install ([ADR-0004](adr/0004-wsl2-docker-deferred-on-dev-laptop.md)).
The MVP module list (`auth`, `workspace`, `source`, `ingestion`, `pipeline`, `job`, `storage`,
`catalog`, `metadata`, `query`) is implemented in `services/edm-platform/` and verified working
end to end (register → workspace/project → source → upload → pipeline → job → catalog → query),
with workspace-scoped RBAC, dataset tagging/classification, a SQLite ingestion connector
alongside CSV/JSON, `edm-quality` (pulled forward from V2 — [ADR-0005](adr/0005-quality-pulled-into-mvp.md)),
and `edm-lineage` (also pulled forward — [ADR-0006](adr/0006-lineage-pulled-into-mvp.md))
all implemented and tested on top of that slice. `edm-cli` (`cli/`) is implemented as a thin
client over the same API, covers every module including lineage, and was used to drive the full
golden path by hand — that exercise caught and fixed a real path-handling bug in the upload flow
that the test suite alone had missed. CI (`.github/workflows/test.yml`) now runs the full pytest
suite plus a CLI smoke check on every push/PR to `main`. `edm-ui` (`ui/`) is built — Vite + React
+ TypeScript, one page per route, covering the same full golden path as the CLI
([ADR-0007](adr/0007-react-ui-and-cors-fix.md)) — and was verified by launching a real headless
browser against it (`ui/e2e/smoke.mjs`), which immediately caught a backend CORS
misconfiguration that no direct-HTTP-client test (`pytest`, `curl`, the CLI) could ever have
caught. `edm-alerting` (also pulled forward from V2 — [ADR-0008](adr/0008-alerting-pulled-into-mvp.md))
is built: `edm-job` raises an `Alert` directly on any failure or quality warning, with an
open/acknowledged/resolved lifecycle exposed through the API, CLI (`edm alert
list/acknowledge/resolve`), and a UI tab — covered by both backend tests and an extended
`ui/e2e/smoke.mjs` run that drives a real failure through to resolution. Ingestion now reaches
real enterprise systems, not just files/SQLite: Oracle, AWS S3, a generic REST API connector,
and ServiceNow/Jira/Confluence presets built on it ([ADR-0009](adr/0009-encrypted-secrets-and-enterprise-connectors.md)),
backed by encrypted-at-rest credential storage (`Source.encrypted_credentials`, Fernet) since
Vault remains out of reach (ADR-0003/0004). S3 is verified against a real in-memory S3 emulation
(`moto`); Oracle/ServiceNow/Jira/Confluence/generic-REST are verified at the request-building
level only (mocked transport/connection) — there's no real account or Docker-based emulator
available in this environment to integration-test the others against.

`edm-notebook` is built ([ADR-0010](adr/0010-notebook-sandbox-and-pipeline-scheduling.md)): an
interactive, code-first ETL dev experience — write Python in ordered cells, run them against a
sample of a Source's data through a restricted `multiprocessing`-isolated sandbox (import
allowlist, restricted builtins, hard timeout), see each cell's stdout/preview/error immediately,
then promote the notebook into a real `python_code` Pipeline transformation that runs the exact
same code against the full dataset. `edm-pipeline` gained cron scheduling on top of this
(`Pipeline.schedule_cron`, backed by APScheduler) — verified not just by unit-testing the
registration logic but by actually setting a live `* * * * *` schedule against a running server
and watching a `trigger: "scheduled"` job appear at the real minute boundary. Both features are
covered end to end through every interface this platform exposes: pytest (`test_sandbox.py`,
`test_notebook.py`, `test_scheduler.py`), `edm-cli` (`edm notebook ...`, `edm pipeline schedule
...`), and `edm-ui` (a Notebooks tab + notebook detail page with per-cell run/promote controls, a
Schedule section on the pipeline detail page) — all driven against a live backend, with the CLI
and UI flows verified by hand and via an extended `ui/e2e/smoke.mjs`, per this project's standing
rule of verifying through a real interface rather than trusting `pytest`'s `TestClient` alone.

A security-focused pass ([ADR-0011](adr/0011-security-hardening-audit-and-notifications.md))
followed: a real `pip-audit` scan found and fixed 33 known vulnerabilities across 6 dependencies
(including the JWT and crypto libraries and FastAPI's own ASGI framework); a hands-on review of
the query endpoint found and fixed a **critical local file inclusion / exfiltration**
vulnerability (`SELECT * FROM read_csv('/path/to/.env')` could read or write arbitrary files on
the server through DuckDB's table functions — closed via `enable_external_access=False` plus
loading datasets through pandas instead of a DuckDB SQL function); and auth gained a timing-safe
login check, future-proofed PBKDF2 iteration storage, a password length policy, IP+email rate
limiting, security response headers, and a bounded file-upload size limit. `edm-audit` (an
immutable log of security-sensitive actions — logins, role/credential/schedule changes; in the
domain model's entity catalog since the start, never built until now) and `edm-notification`
(webhook + email alert delivery, explicitly deferred at MVP time by ADR-0008) were both pulled
forward and built full-stack (backend + tests + `edm-cli` commands), verified against a real local
webhook receiver and a real local SMTP server, not just mocks. A dataset-classification-driven PII
column-masking heuristic was added to the query endpoint for non-owner roles. `ui/e2e/smoke.mjs`
is now wired into CI (`.github/workflows/test.yml`) instead of being a manual-only check.

A follow-up pass ([ADR-0012](adr/0012-additional-connectors-and-notification-audit-ui.md)) added
four more ingestion connectors — Postgres, MySQL (both mirroring Oracle's SELECT-only/identifier-
validated pattern), MongoDB (verified against a real `mongomock` instance, the same tier `moto`
gives S3; credentials optional, matching S3's default-chain precedent), and Google Sheets
(`api_key`/`bearer` auth against the real Sheets API shape) — bringing the connector count to 13.
It also built the two notification channel types ADR-0008 had left unbuilt, `slack` and `teams`
(both webhook-shaped, reusing the existing `NotificationChannel` config model), and closed the one
gap ADR-0011 explicitly deferred: `edm-audit` and `edm-notification` now have dedicated `edm-ui`
pages (an owner-only Audit Log section on the workspace page, a Notifications tab on the project
page) instead of being CLI-only. Both were verified through this project's standing real-browser
bar by extending `ui/e2e/smoke.mjs` rather than writing a separate check.

`edm-governance` (beyond dataset classification and the PII-masking heuristic above — no real
per-column tagging/policy engine), `edm-monitoring`, `edm-ai`, and the SDK remain unbuilt. See
[17-codebase-map.md](17-codebase-map.md) for the file-level picture, kept current per
[Rule 11](03-engineering-principles.md#rule-11--docs-stay-in-sync-with-code).
