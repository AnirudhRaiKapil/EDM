# EDM Platform — Domain Model

> This is the foundation document. The canonical entities defined here become the single
> source of truth for the database schema, REST APIs, UI, permission model, and Kafka event
> contracts. Every module (`edm-*`) speaks this language. Changing an entity here is a breaking
> change to the platform and should go through an ADR.

## 1. Entity Catalog

| Entity | Owning module | Summary |
|---|---|---|
| Workspace | `edm-workspace` | Top-level tenant / organizational boundary |
| Project | `edm-workspace` | Logical grouping of sources, pipelines, datasets within a Workspace (typically maps to an environment or business domain) |
| User | `edm-auth` | A platform identity (federated via Keycloak) |
| Role | `edm-auth` | Named bundle of permissions, assignable to a User within a Workspace/Project |
| Policy | `edm-governance` | A governance rule (access, masking, retention, classification) attached to a scope |
| Source | `edm-source` | A registered external system instance data is read from |
| Connector | `edm-ingestion` | The technical plugin/driver that knows how to talk to a class of Source |
| Pipeline | `edm-pipeline` | A versioned definition of how data moves and transforms from Source(s) to Dataset(s) |
| Transformation | `edm-pipeline` | A single reusable step within a Pipeline's DAG |
| Job | `edm-job` | One execution instance of a Pipeline at a point in time |
| Cluster | `edm-job` | The compute resource (Spark/Flink execution environment) a Job runs on |
| Dataset | `edm-catalog` / `edm-storage` | A discoverable, logical data asset backed by physical storage |
| Schema | `edm-metadata` | The versioned structure of a Dataset |
| Column | `edm-metadata` | A field within a Schema |
| Tag | `edm-catalog` | A label (free-form or controlled vocabulary) attachable to Dataset/Column/Pipeline |
| Quality Rule | `edm-quality` | A declarative expectation evaluated against a Dataset |
| Quality Run | `edm-quality` | The result of evaluating Quality Rules against a Dataset version |
| Lineage Edge | `edm-lineage` | A directed edge recording that one Dataset/Job produced or consumed another |
| Alert | `edm-alerting` | A notification triggered by an event or condition |
| Audit Event | `edm-audit` | An immutable record of who did what, when |

## 2. Entity Definitions

### Workspace
The root of multi-tenancy. Everything else belongs to exactly one Workspace.

| Field | Type | Notes |
|---|---|---|
| id | UUID | |
| name | string | unique |
| description | string | |
| status | enum | `active`, `suspended`, `archived` |
| createdBy | User ref | |
| createdAt / updatedAt | timestamp | |

### Project
A grouping inside a Workspace — typically a business domain or environment (dev/qa/uat/prod).

| Field | Type | Notes |
|---|---|---|
| id | UUID | |
| workspaceId | FK -> Workspace | |
| name | string | unique within Workspace |
| environment | enum | `dev`, `qa`, `uat`, `prod` |
| status | enum | `active`, `archived` |
| owner | User ref | |

### User / Role
| Field (User) | Type | Notes |
|---|---|---|
| id | UUID | maps to Keycloak subject |
| email | string | |
| displayName | string | |
| status | enum | `active`, `disabled` |

| Field (Role) | Type | Notes |
|---|---|---|
| id | UUID | |
| name | string | e.g. `data-engineer`, `data-scientist`, `business-analyst`, `auditor`, `admin` |
| permissions | string[] | e.g. `pipeline:write`, `dataset:read`, `governance:admin` |
| scope | enum | `workspace`, `project`, `dataset` |

A **RoleAssignment** join entity binds `(User, Role, scope, scopeId)`.

### Source
A configured instance of a Connector — "the Postgres database for the Orders service."

| Field | Type | Notes |
|---|---|---|
| id | UUID | |
| projectId | FK -> Project | |
| connectorType | string | e.g. `postgres`, `kafka`, `rest-api`, `s3` |
| name | string | |
| connectionConfig | JSON | non-secret config only |
| secretRef | string | pointer into Vault, never the secret itself — implemented today as `Source.encrypted_credentials` (Fernet-encrypted column) rather than a real Vault pointer; see [ADR-0009](adr/0009-encrypted-secrets-and-enterprise-connectors.md) |
| ingestionMode | enum | `batch`, `streaming`, `cdc` |
| status | enum | `draft`, `active`, `disabled`, `archived` |
| owner | User ref | |

### Connector
The catalog of *types* of Source the platform knows how to ingest from (NiFi/SeaTunnel/Debezium
flow templates under the hood). Connectors are platform-shipped or contributed; Sources are
user-created instances of a Connector.

| Field | Type | Notes |
|---|---|---|
| id | UUID | |
| type | string | unique key, e.g. `postgres-cdc` |
| category | enum | `database`, `file`, `api`, `messaging`, `cloud-storage`, `streaming`, `enterprise-app` |
| capabilities | string[] | `batch`, `streaming`, `cdc`, `schema-discovery` |
| configSchema | JSON Schema | drives the dynamic UI form for creating a Source |

### Pipeline
A versioned, declarative definition of a data flow: inputs, ordered/DAG Transformations,
outputs, schedule/trigger. **Metadata-driven, not code** (Rule 4 in
[03-engineering-principles.md](03-engineering-principles.md)).

| Field | Type | Notes |
|---|---|---|
| id | UUID | |
| projectId | FK -> Project | |
| name | string | |
| version | int | incremented on every published change |
| sourceIds | FK[] -> Source | inputs |
| outputDatasetIds | FK[] -> Dataset | outputs |
| transformations | Transformation[] | ordered/DAG steps |
| trigger | enum/JSON | `schedule(cron)`, `event(topic)`, `manual` |
| engine | enum | `batch` (Spark), `streaming` (Flink) |
| status | enum | `draft`, `active`, `paused`, `deprecated`, `archived` |
| owner | User ref | |

### Transformation
A single named, parameterized step inside a Pipeline (validation, standardization, enrichment,
lookup/join, SCD, business rule, aggregation). Stored as metadata + parameters, not bespoke code,
so the same Transformation type can be reused across Pipelines.

| Field | Type | Notes |
|---|---|---|
| id | UUID | |
| pipelineId | FK -> Pipeline | |
| type | string | e.g. `standardize`, `dedupe`, `scd2`, `business-rule`, `aggregate` |
| order | int | position in the DAG |
| parameters | JSON | type-specific config |

### Job
One execution of a Pipeline. The Control Plane creates Jobs; the Data Plane executes them.

| Field | Type | Notes |
|---|---|---|
| id | UUID | |
| pipelineId | FK -> Pipeline | |
| pipelineVersion | int | pinned at trigger time |
| clusterId | FK -> Cluster | where it ran |
| status | enum | `queued`, `running`, `succeeded`, `failed`, `cancelled` |
| trigger | enum | `scheduled`, `manual`, `event`, `backfill` |
| startedAt / finishedAt | timestamp | |
| metrics | JSON | rows processed, bytes, duration, retries |
| retryOf | FK -> Job, nullable | links retry attempts |

### Cluster
A compute resource definition the Job Service hands work to.

| Field | Type | Notes |
|---|---|---|
| id | UUID | |
| engine | enum | `spark`, `flink` |
| sizing | JSON | executors, memory, autoscaling bounds |
| status | enum | `provisioning`, `ready`, `busy`, `terminated` |

### Dataset / Schema / Column
A Dataset is the discoverable unit in the Catalog; a Schema is one versioned structure of it.

| Field (Dataset) | Type | Notes |
|---|---|---|
| id | UUID | |
| projectId | FK -> Project | |
| name | string | |
| layer | enum | `bronze`, `silver`, `gold` |
| physicalLocation | string | Iceberg table identifier / MinIO path |
| currentSchemaId | FK -> Schema | |
| classification | enum[] | `public`, `internal`, `confidential`, `restricted`, `pii`, `financial`, `legal`, `hr` |
| owner | User ref | |
| status | enum | `registered`, `ingesting`, `available`, `deprecated`, `archived` |
| qualityScore | float, nullable | derived from latest Quality Run |

| Field (Schema) | Type | Notes |
|---|---|---|
| id | UUID | |
| datasetId | FK -> Dataset | |
| version | int | |
| columns | Column[] | |
| status | enum | `active`, `superseded` |

| Field (Column) | Type | Notes |
|---|---|---|
| name | string | |
| dataType | string | |
| nullable | boolean | |
| classification | enum, nullable | for column-level masking |
| description | string | |

### Tag
Free-form or controlled-vocabulary label. Attachable to Dataset, Column, or Pipeline.
`(entityType, entityId, key, value)`.

### Quality Rule / Quality Run
| Field (Quality Rule) | Type | Notes |
|---|---|---|
| id | UUID | |
| datasetId | FK -> Dataset | |
| expectationType | string | `not_null`, `unique`, `regex`, `range`, `referential_integrity`, ... |
| parameters | JSON | |
| severity | enum | `warning`, `blocking` |

| Field (Quality Run) | Type | Notes |
|---|---|---|
| id | UUID | |
| datasetId | FK -> Dataset | |
| jobId | FK -> Job, nullable | run that produced the data being checked |
| results | JSON | per-rule pass/fail + stats |
| outcome | enum | `passed`, `passed-with-warnings`, `failed` |

### Lineage Edge
`(fromEntityType, fromEntityId, toEntityType, toEntityId, jobId, createdAt)` — e.g.
`(Source, Dataset)`, `(Dataset, Dataset)` across Bronze->Silver->Gold, `(Dataset, Pipeline)`.
The lineage graph is the union of all edges.

### Alert
| Field | Type | Notes |
|---|---|---|
| id | UUID | |
| projectId | FK -> Project | added beyond the original spec, so listing is permission-checkable the same way as every other project-scoped resource (ADR-0008) |
| sourceEntity | (type, id) | what triggered it, e.g. a failed Job or Quality Run |
| message | string | added beyond the original spec — the human-readable reason, since there's no `channel` to format a notification for yet |
| severity | enum | `info`, `warning`, `critical` |
| channel | enum | `email`, `slack`, `teams`, `webhook` — **not implemented in the MVP** (ADR-0008); alerts are in-app/API-only until `edm-notification` exists |
| status | enum | `open`, `acknowledged`, `resolved` |

### Audit Event
Immutable: `(actorUserId, action, entityType, entityId, before, after, timestamp)`.

## 3. Relationship Overview

```
Workspace 1───* Project
Workspace 1───* User            (via RoleAssignment)

Project   1───* Source
Project   1───* Pipeline
Project   1───* Dataset

Source    *───1 Connector       (Source is a configured instance of a Connector type)
Pipeline  *───* Source          (inputs)
Pipeline  1───* Transformation  (ordered DAG steps)
Pipeline  1───* Dataset         (outputs)
Pipeline  1───* Job             (execution history)

Job       *───1 Cluster
Job       1───* QualityRun      (quality checks tied to the data a Job produced)
Job       1───* Alert           (on failure / SLA breach)

Dataset   1───* Schema          (version history, exactly one `active`)
Schema    1───* Column
Dataset   *───* Tag
Dataset   1───* QualityRule
Dataset   *───* LineageEdge     (as either endpoint)

User      *───* Role            (via RoleAssignment, scoped to Workspace/Project/Dataset)
Policy    *───1 (Workspace|Project|Dataset|Column)   (scope it governs)
```

## 4. Lifecycle State Machines

```
Source:      draft -> active -> disabled -> archived

Pipeline:    draft -> active <-> paused -> deprecated -> archived

Job:         queued -> running -> succeeded
                                -> failed   -> (retry) -> queued
                                -> cancelled

Dataset:     registered -> ingesting -> available -> deprecated -> archived

Schema:      (new version) active -> superseded   [previous version becomes superseded,
                                                     never deleted — enables time travel]

Alert:       open -> acknowledged -> resolved
```

## 5. Why This Matters

Every later document derives from this one:

- **Database design** ([07-database-design.md](07-database-design.md)) — each owning module
  gets its own schema/database for these entities (Rule: each service owns its data).
- **REST API shapes** ([06-api-specifications.md](06-api-specifications.md)) — resources map
  1:1 to entities (`/api/v1/sources`, `/api/v1/pipelines`, `/api/v1/datasets`, ...).
- **Kafka event contracts** ([08-event-contracts.md](08-event-contracts.md)) — topics are named
  `<entity>.<lifecycle-transition>` (`source.created`, `pipeline.started`, `dataset.updated`,
  `quality.failed`, ...), and event payloads are the entity shape at the time of transition.
- **UI** — modules (Sources, Pipelines, Jobs, Catalog, Lineage, Quality, Governance, Users) are
  literally CRUD + lifecycle views over these entities.
- **Permission model** — RoleAssignment scope and Policy scope are defined directly in terms of
  these entities.
