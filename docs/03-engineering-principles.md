# EDM Platform — Engineering Principles

These ten rules apply to every module, every PR, every design decision. When in doubt, the rule
wins over local convenience.

## Rule 1 — Product First
We are not integrating tools; we are building a product. A user should never have to know
whether a feature is implemented with Spark, Flink, Kafka, or Airflow.

## Rule 2 — API First
Every capability must be exposed through an API.

```
UI -> API Gateway -> Platform Services -> Infrastructure
```

The UI never talks directly to Kafka, PostgreSQL, Spark, or any infrastructure component.

## Rule 3 — Event Driven
Long-running operations publish events rather than making synchronous calls across services.

```
Pipeline Created -> Kafka Event -> Job Service -> Metadata Update -> Notification -> Monitoring
```

This keeps services loosely coupled and independently scalable.

## Rule 4 — Everything Is Metadata
Nothing is hardcoded. Instead of code that reads `customer.csv`, we define:

```
Dataset:
    name: customer
Source:
    type: postgres
Schedule:
    daily
Destination:
    bronze
Transformations:
    - customer-standardization
```

The platform executes based on metadata, not embedded logic.

## Rule 5 — Configuration Over Code
Users configure the platform through UI/API instead of writing code wherever possible: creating
pipelines, registering sources, configuring schedules, defining quality rules, setting
governance policies. This lowers the barrier for business and operations users.

## Rule 6 — Everything Is Versioned
Pipelines, schemas, datasets, quality rules, policies, connectors, and API definitions all carry
version history, enabling rollback and auditability.

## Rule 7 — Every Object Has an Owner
Each resource has an owner, team, environment, project, lifecycle status, documentation, and
tags — required for governance and accountability.

## Rule 8 — Build for Scale from Day One
Never assume one Kafka broker, one Spark node, one Airflow instance, or one PostgreSQL database.
Every component is designed to scale horizontally or support high availability, even if the
first deployment runs it as a single replica.

## Rule 9 — Developer Experience Matters
Contributors and integrators get a CLI, SDKs, APIs, documentation, and a local dev environment.
Good DX drives adoption and contribution.

## Rule 10 — Every Decision Is Documented
Major choices are recorded as Architecture Decision Records in [adr/](adr/). See
[adr/0000-adr-template.md](adr/0000-adr-template.md) and
[adr/0001-apache-iceberg-as-table-format.md](adr/0001-apache-iceberg-as-table-format.md) for the
format.

## How These Rules Are Enforced in Practice

| Rule | Enforced by |
|---|---|
| API First | No module may expose a DB connection, broker, or filesystem path to another module or the UI — only its own REST/gRPC API |
| Event Driven | Cross-module side effects (notify, re-index, audit) are wired via Kafka topics defined in [08-event-contracts.md](08-event-contracts.md), not direct calls |
| Metadata Driven | Pipeline/Transformation definitions are JSON/YAML documents validated against a schema, stored in `edm-pipeline`, never as ad hoc scripts |
| Versioned | Every entity in [02-domain-model.md](02-domain-model.md) marked with a `version` field has an append-only history table, not in-place mutation |
| Owned | `owner`, `projectId`, `status` are non-nullable columns on every top-level entity |
