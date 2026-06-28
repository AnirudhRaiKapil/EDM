# ADR-0003: Trimmed Phase 1 stack for a modest single laptop

- **Status:** Accepted
- **Date:** 2026-06-28

## Context
The full Phase 1+ stack from [01-product-architecture.md](../01-product-architecture.md)
(Kafka, Spark, Flink, Trino, Airflow, MinIO, OpenMetadata, Great Expectations, Keycloak, Vault,
Prometheus, Grafana, Loki, NiFi, SeaTunnel, Debezium, Superset) cannot run simultaneously on a
~16GB RAM Windows laptop, and at the time of this decision the machine has neither Docker nor
WSL installed yet. We need to start producing a working, demoable MVP slice
([16-build-roadmap.md](../16-build-roadmap.md)) today, not after weeks of infrastructure setup.

Per Engineering Principle "Product First" ([03-engineering-principles.md](../03-engineering-principles.md)),
users and module APIs never see the underlying engine — so swapping the engine behind a module
later is explicitly a non-breaking change. That makes it safe to start with lightweight
substitutes now.

## Decision
For the MVP, each module uses a lightweight engine behind its existing API/domain-model
contract, swapped for the "real" engine once infra exists:

| Capability | MVP implementation | Swapped in later (unchanged module contract) |
|---|---|---|
| Relational storage | SQLite (file-based, zero install) | PostgreSQL via Docker Compose |
| Object storage (Bronze/Silver/Gold files) | Local disk under a configurable data dir | MinIO |
| Event bus | In-process publish/subscribe (logged, same event envelope/topic names as [08-event-contracts.md](../08-event-contracts.md)) | Apache Kafka |
| Batch transformation engine | pandas, run in a FastAPI background task | Apache Spark |
| Query engine | DuckDB (embedded, queries Parquet directly with full SQL, MIT licensed) | Trino |
| Authentication | Self-issued JWT (passlib + python-jose) | Keycloak (OIDC) |
| Secrets | `.env` file (never committed; `.env.example` checked in instead) | HashiCorp Vault |
| Orchestration/scheduling | FastAPI background tasks / simple cron-like trigger | Apache Airflow |
| Metadata & catalog | Our own `edm-catalog`/`edm-metadata` tables (always the product surface per Section 10.1 — OpenMetadata, if ever added, is an optional sync target, not a hard dependency) | unchanged |
| Data quality | Deferred to V2 (`edm-quality` not in MVP scope) | Great Expectations |
| Monitoring | `/health` endpoint + structured JSON logs to stdout | Prometheus + Grafana + Loki |

## Alternatives Considered
- **Stand up the full stack via Docker Compose immediately** — rejected: requires installing
  Docker/WSL first (a separate, user-driven step) and would consume most of the laptop's RAM
  before a single line of product code exists.
- **Redpanda instead of Kafka** for a lighter single-binary broker — rejected: Redpanda's core is
  BSL-licensed (source-available, not OSI-approved open source), which conflicts with the
  platform's "Open Source Only" requirement ([00-vision-and-requirements.md](../00-vision-and-requirements.md)
  Section 2.1). Apache Kafka in **KRaft mode** (no separate ZooKeeper, single broker) is the
  lightweight option that stays Apache-2.0 licensed.

## Consequences
- The MVP is runnable today with nothing installed beyond Python — no Docker/WSL dependency to
  reach the first working vertical slice.
- `infrastructure/docker/docker-compose.yml` defines Postgres + MinIO + Kafka (KRaft, single
  broker) so that switching `DATABASE_URL`, the storage adapter, and the event bus adapter to
  "real" infra is a config change, not a code change, once Docker/WSL is installed
  (see ADR-0002 and the WSL2/Docker setup steps tracked outside this repo's docs).
- `edm-quality`, `edm-lineage`, `edm-governance`, `edm-notification`, `edm-monitoring`,
  `edm-audit`, `edm-alerting`, `edm-ai` (the V2 module list) remain out of scope until the
  Core/MVP module list is working end to end, per [16-build-roadmap.md](../16-build-roadmap.md).
