# EDM Platform — Product Architecture

## 1. Design Principles

Every technology or design decision in this platform must satisfy these principles:

| Principle | Description |
|---|---|
| Open Source Only | No paid licenses or proprietary dependencies. |
| Cloud Agnostic | Deployable on-prem, AWS, Azure, GCP, or hybrid. |
| Kubernetes Native | Every service runs as a container orchestrated by Kubernetes (with a Docker Compose path for local/small deployments). |
| Horizontally Scalable | Scale by adding nodes, not upgrading hardware. |
| Fault Tolerant | No single point of failure. |
| Event-Driven | Support both streaming and batch processing. |
| Metadata Driven | Pipelines are driven by metadata, not hard-coded logic. |
| API First | Every capability is exposed through an API. |
| Modular | Any component can be replaced without affecting the rest of the platform. |
| Observable | Everything emits metrics, logs, and traces. |

## 2. The Core Rule

> **The EDM Platform owns the user experience. Open-source tools provide capabilities behind
> the scenes.**

Users and external integrators interact with the **EDM Platform's** UI, REST/GraphQL APIs, CLI,
and SDKs — never directly with Kafka, Spark, Airflow, Trino, MinIO, etc. If an underlying engine
is replaced later, the platform's APIs, UI, and user workflows stay unchanged. This is the same
approach used by Databricks, Snowflake, and similar products: the open-source ecosystem is an
implementation detail hidden behind a coherent product surface.

## 3. Logical Layered Architecture

```
                          +--------------------------------------+
                          |           Data Producers              |
                          +--------------------------------------+
          Databases | APIs | Files | IoT | Logs | ERP | CRM | SaaS
                                   |
                                   v
  LAYER 1 — INGESTION
    Batch | Streaming | CDC | File | API ingestion
                                   |
                                   v
  LAYER 2 — MESSAGE BUS
    Event streaming | Queue management | Event persistence & replay
                                   |
                                   v
  LAYER 3 — DATA PROCESSING
    Validation | Cleansing | Standardization | Transformation | Enrichment
    Data quality | Business rules | Aggregation  (Batch ETL + real-time streaming)
                                   |
                                   v
  LAYER 4 — STORAGE  (Medallion)
    Bronze (raw) -> Silver (validated) -> Gold (business-ready) -> Warehouse/Lakehouse
                                   |
                                   v
  LAYER 5 — METADATA
    Metadata repository | Data catalog | Schema registry | Lineage | Business glossary | Ownership
                                   |
                                   v
  LAYER 6 — GOVERNANCE
    RBAC/ABAC | Masking | Policies | Encryption | Audit logs | Compliance | Retention | Versioning
                                   |
                                   v
  LAYER 7 — DATA SERVING
    SQL | REST | GraphQL | Data products | Feature store | ML/BI consumption
                                   |
                                   v
  LAYER 8 — CONSUMERS
    BI | Analytics | Data science | ML | Enterprise apps | Dashboards | Reports | AI agents | External APIs

  CROSS-CUTTING PLATFORM SERVICES (available to every layer above)
    Monitoring | Logging | Alerting | Scheduling/Orchestration | Secrets management
    Identity management | CI/CD | Infrastructure as Code | Container orchestration | Backup & DR
```

### Layer responsibilities

**Layer 1 — Ingestion.** Brings data in regardless of source: batch, streaming, CDC,
incremental/full loads, schema discovery, pluggable connector framework.

**Layer 2 — Event & Messaging.** The central nervous system: decouples producers from
consumers, buffers traffic spikes, enables replay, supports many downstream consumers,
guarantees durability.

**Layer 3 — Processing.** The ETL/ELT engine: validation, schema checks, cleansing,
standardization, dedup, enrichment, lookups/joins, SCD, business rules, quality checks,
aggregation, feature engineering, streaming transforms. Supports batch and real-time.

**Layer 4 — Storage.** Medallion architecture (Bronze/Silver/Gold) over a Lakehouse: object
storage + data lake + warehouse semantics in one system.

**Layer 5 — Metadata.** Stores information *about* the data: catalog, lineage, business
glossary, technical/operational metadata, schema registry, dataset documentation. Solves "what
data exists, where did it come from, who owns it, can I trust it, what does this column mean."

**Layer 6 — Governance.** Enterprise-grade control: authn/authz, RBAC/ABAC, encryption, masking,
tokenization, audit logging, compliance policies, retention, version control.

**Layer 7 — Serving.** Makes processed data available: SQL, REST, GraphQL, materialized views,
semantic layer, data products, ML feature store, data sharing.

**Layer 8 — Consumers.** BI tools, reporting, dashboards, AI/ML systems, enterprise apps,
mobile/web apps, analysts, business users.

### Data flow example (lineage trace)

```
Sales.csv -> Kafka -> Spark -> Iceberg (Bronze->Silver->Gold) -> Trino -> Dashboard
```

Every field in a report should be traceable back to its originating record.

## 4. Product Architecture — Control Plane vs. Data Plane

```
                    +-------------------------------+
                    |          EDM Platform          |
                    |---------------------------------|
                    |  Web UI | REST API | GraphQL API |
                    |  CLI | SDKs                      |
                    +---------------+-----------------+
                                    |
                    +---------------v-----------------+
                    |        EDM Control Plane          |
                    +---------------+-----------------+
                                    |
   +--------------------------------+--------------------------------+
   |                                |                                 |
   v                                v                                 v
 Data Services                Platform Services                 Infrastructure
 Sources                      Metadata                          Kubernetes
 Pipelines                    Governance                        Object Storage
 Jobs                         Security                          Databases
 Datasets                     Monitoring                        Kafka
 Catalog                      Logging                           Spark / Flink
 Query                        Alerts                            Trino
 Lineage                      Audit                              ...
```

**Control Plane** — manages the platform: users, projects, pipeline *definitions*, metadata,
permissions, scheduling, configuration, monitoring, catalog. **Never** touches data directly; it
tells the Data Plane what to do.

**Data Plane** — executes workloads: reads sources, runs Spark/Flink jobs, streams, queries via
Trino, writes Iceberg tables. **Never** stores user/business/permission data.

This separation is what lets the control plane stay small, stable, and highly available while
the data plane scales independently (and elastically) with workload volume.

## 5. Microservice / Module Map

Rather than 20+ independently deployed microservices from day one, the platform is decomposed
into **modules** (`edm-*`). Each module is a clear bounded context with its own API, data, and
events. Multiple modules can be co-deployed inside one process for small installs (modular
monolith) or split into independently deployed services as load demands — the module boundary,
not the deployment topology, is the architectural contract. See
[16-build-roadmap.md](16-build-roadmap.md) for which modules ship as one deployable unit in the
MVP.

### Core (MVP / P0)

| Module | Responsibility |
|---|---|
| `edm-core` | Shared kernel: common types, error model, event envelope |
| `edm-auth` | Authentication & authorization (Identity Service) |
| `edm-workspace` | Organizations, projects, environments |
| `edm-source` | Register and manage data sources |
| `edm-ingestion` | Connector framework, batch/stream/CDC ingestion |
| `edm-pipeline` | Pipeline definitions and orchestration triggers |
| `edm-job` | Job execution and monitoring |
| `edm-storage` | Lakehouse storage abstraction (Bronze/Silver/Gold) |
| `edm-catalog` | Search and discovery over registered datasets |
| `edm-metadata` | Metadata repository, schema registry |
| `edm-query` | SQL execution / federated query access |
| `edm-quality` | Validation rules, evaluated on every job run before publication. Pulled forward from V2 — see [ADR-0005](adr/0005-quality-pulled-into-mvp.md) |
| `edm-lineage` | Source/pipeline -> dataset edges recorded on every job run. Pulled forward from V2 — see [ADR-0006](adr/0006-lineage-pulled-into-mvp.md) |

### Enterprise (V2)

| Module | Responsibility |
|---|---|
| `edm-governance` | Policies, retention, classification |
| `edm-notification` | Email, Slack, Teams, webhooks |
| `edm-monitoring` | Metrics, health checks, SLAs |
| `edm-audit` | Immutable audit trail |
| `edm-alerting` | Alert rules and routing |
| `edm-ai` | Copilot, NL-to-SQL, pipeline recommendations |

### Interfaces

| Module | Responsibility |
|---|---|
| `edm-ui` | React + TypeScript web application |
| `edm-cli` | Scriptable command-line interface (`edm <noun> <verb>`) |
| `edm-sdk` | Client libraries for programmatic access |

## 6. Service Communication

**Synchronous** (immediate response): REST and GraphQL for external/UI traffic; gRPC for
internal, performance-critical service-to-service calls.

**Asynchronous** (long-running / fan-out): Kafka events. No service calls every other service
directly — events reduce coupling:

```
Pipeline Service -> Kafka -> Job Service -> Metadata Service -> Notification Service
```

## 7. Platform API Surface (illustrative)

```
/api/v1/auth
/api/v1/users
/api/v1/workspaces
/api/v1/projects

/api/v1/sources
/api/v1/connectors
/api/v1/pipelines
/api/v1/jobs

/api/v1/catalog
/api/v1/datasets
/api/v1/metadata
/api/v1/lineage

/api/v1/query
/api/v1/quality
/api/v1/governance

/api/v1/admin
/api/v1/monitoring
```

Full request/response contracts live in [06-api-specifications.md](06-api-specifications.md)
(to be written per-module as each module is implemented).

## 8. Open-Source Engine Selections (Data Plane)

| Layer | Technology | Why |
|---|---|---|
| File/API/legacy ingestion | Apache NiFi | 300+ connectors, visual flows, back-pressure, provenance |
| High-volume DB sync / CDC-adjacent ETL | Apache SeaTunnel | Parallel batch+stream, strong DB connector set |
| Change Data Capture | Debezium | Log-based CDC, low latency, no polling |
| Event streaming / bus | Apache Kafka (+ Kafka Connect, Schema Registry) | Mature, high-throughput, durable, replayable, huge ecosystem |
| Batch processing | Apache Spark | Mature large-scale batch/ML/SQL engine |
| Stream processing | Apache Flink | Millisecond-latency stateful streaming, exactly-once |
| Object storage | MinIO | S3-compatible, distributed, self-hosted |
| Table format | Apache Iceberg | ACID, schema/partition evolution, time travel |
| Query engine | Trino | Federated distributed SQL across Iceberg + external DBs |
| Orchestration | Apache Airflow | DAG scheduling, retries, backfills |
| Metadata & catalog | OpenMetadata | Unified catalog + lineage + glossary + ownership + quality scores |
| Data quality | Great Expectations | Declarative validation, profiling |
| Identity provider | Keycloak | SSO, OAuth2/OIDC, LDAP/AD, MFA |
| Secrets management | HashiCorp Vault | Dynamic secrets, encryption keys, certs |
| Metrics | Prometheus | Pull-based metrics from every component |
| Dashboards | Grafana | Visualization over Prometheus/Loki |
| Log aggregation | Loki | Centralized, searchable logs |
| Tracing | OpenTelemetry | End-to-end distributed traces |
| BI / dashboards | Apache Superset | Self-service analytics on top of Trino |

These are **data-plane implementation details**. Per Section 2, none of them are exposed
directly to platform users — they sit behind `edm-*` module APIs.

## 9. Platform (Control-Plane) Tech Stack

| Layer | Technology | Why |
|---|---|---|
| Backend services | Java 21 + Spring Boot | Mature, high-performance, strong enterprise ecosystem |
| API Gateway | Spring Cloud Gateway | Integrates with Spring-based auth/services |
| Frontend | React + TypeScript | Modern, component-based, scalable UI |
| Internal RPC | gRPC | Efficient service-to-service calls |
| Event bus | Apache Kafka | Shared with the data plane |
| Service databases | PostgreSQL (one schema/DB per service) | Reliable, widely supported relational storage |
| Cache | Redis | Sessions, hot-path caching |
| Containerization | Docker | Consistent packaging |
| Orchestration | Kubernetes | HA, autoscaling, self-healing |
| Service discovery | Kubernetes DNS | No extra moving parts |
| Configuration | Git-based config (+ Spring Cloud Config if needed) | Centralized, versioned |
| Observability | OpenTelemetry | Standard metrics/logs/traces across services |

> **Superseded for the MVP by [ADR-0002](adr/0002-python-fastapi-modular-monolith.md):** the
> backend is **Python + FastAPI**, deployed as a **modular monolith**
> (`services/edm-platform`) rather than independent Spring Boot microservices, until the
> platform has more than one contributor. Module boundaries are unchanged. The table above
> remains the target stack for when modules are split into independent deployments.
>
> **Further trimmed for local dev by [ADR-0003](adr/0003-trimmed-phase-1-stack.md):** several
> Section 8 engines (Kafka, MinIO, Spark, Trino, Keycloak, Vault, Airflow, Prometheus/Grafana)
> are temporarily replaced by lightweight in-process/embedded equivalents (SQLite, local disk,
> an in-process event bus, pandas, DuckDB, self-issued JWT) behind the same module contracts,
> until Docker/WSL infrastructure is set up on the dev machine.

## 10. Enterprise Platform Services (Phase 2 detail)

### 10.1 Metadata Platform (OpenMetadata)
Responsibilities: data catalog, metadata repository, dataset documentation, table discovery,
column descriptions, business glossary, team ownership, lineage, usage analytics, schema
tracking, quality-score integration. Integrates with Kafka, Trino, Spark, Airflow, Iceberg,
Postgres/MySQL, Superset, Great Expectations, Prometheus.

```
Database -> NiFi -> Spark Job -> Iceberg Table -> OpenMetadata
                                                     (owner, schema, description, tags,
                                                      lineage, freshness, quality, usage)
```

### 10.2 Governance
- **Access control:** Users -> Roles -> Permissions -> Policies -> Data. Example roles: Data
  Engineer, Data Scientist, Business Analyst, Auditor, Admin.
- **Classification:** every dataset tagged — Public, Internal, Confidential, Restricted, PII,
  Financial, Legal, HR.
- **Lineage:** full traceability of every transformation a field went through.
- **Lifecycle policies:** e.g. retain 7 years, archive after 1 year, delete after 10 years, keep
  raw forever, purge temp data after 30 days.

### 10.3 Data Quality (Great Expectations)
Validates nulls, duplicates, types, ranges, regex formats, FK/referential integrity, freshness,
completeness, distribution anomalies. On failure: reject batch -> raise alert -> log issue ->
block downstream publication.

### 10.4 Security
- **Identity (Keycloak):** SSO, OAuth2, OIDC, LDAP/AD, MFA, user federation — every component
  authenticates through it.
- **Secrets (Vault):** DB passwords, Kafka credentials, API keys, encryption keys, certs, tokens
  — fetched at runtime, never stored in config files.
- **Authorization flow:** Keycloak -> RBAC engine -> permissions -> dataset access -> column
  masking -> row filtering.

### 10.5 Monitoring & Observability
- **Prometheus:** metrics from Kafka, Spark, Flink, Airflow, Trino, MinIO, Kubernetes (CPU,
  memory, disk, throughput, job duration, queue lag, storage usage, query latency).
- **Grafana:** dashboards (pipeline health, Kafka topics, Spark jobs, storage usage, data
  freshness, cluster capacity).
- **Loki:** centralized, searchable logs across all services.
- **OpenTelemetry:** end-to-end request tracing, e.g. `API -> NiFi -> Kafka -> Spark -> Iceberg
  -> Trino -> Dashboard`.

## 11. Related Documents

- [00-vision-and-requirements.md](00-vision-and-requirements.md) — why this platform exists
- [02-domain-model.md](02-domain-model.md) — canonical entities and relationships
- [03-engineering-principles.md](03-engineering-principles.md) — the 11 rules every change must follow
- [04-repository-structure.md](04-repository-structure.md) — monorepo layout
- [16-build-roadmap.md](16-build-roadmap.md) — phased build order
- [adr/](adr/) — Architecture Decision Records for any deviation from this document
