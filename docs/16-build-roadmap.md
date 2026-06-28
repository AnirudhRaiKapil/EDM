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
4. Trigger a Job (manual first, scheduled second) and watch it succeed/fail.
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
alongside CSV/JSON, and `edm-quality` (pulled forward from V2 — [ADR-0005](adr/0005-quality-pulled-into-mvp.md))
all implemented and tested on top of that slice. `edm-cli` (`cli/`) is implemented as a thin
client over the same API and was used to drive the full golden path by hand — that exercise
caught and fixed a real path-handling bug in the upload flow that the test suite alone had
missed. `edm-lineage`, `edm-governance` (beyond RBAC), `edm-notification`/`edm-alerting`,
`edm-monitoring`, `edm-ai`, the SDK, and the UI remain unbuilt.
