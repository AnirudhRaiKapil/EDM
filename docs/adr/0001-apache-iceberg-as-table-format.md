# ADR-0001: Use Apache Iceberg as the Lakehouse table format

- **Status:** Accepted
- **Date:** 2026-06-28

## Context
The Storage layer (Layer 4) needs a table format over object storage (MinIO) that gives
warehouse-like guarantees — ACID transactions, schema evolution, time travel — without giving up
the cost and flexibility of plain object storage, and without any licensing cost.

## Decision
Use **Apache Iceberg** as the table format for all Bronze/Silver/Gold datasets in `edm-storage`.

## Alternatives Considered
- **Delta Lake** — strong Spark integration, but historically tighter coupling to the Spark/Databricks
  ecosystem; Trino/Flink support has lagged Iceberg's.
- **Apache Hudi** — strong upsert/CDC story, but smaller ecosystem of query engines and a
  steeper operational learning curve for a solo/small team.

Iceberg wins on broadest engine support (Spark, Flink, Trino all have first-class Iceberg
support), which matters because Layer 3 explicitly runs both Spark and Flink against the same
tables.

## Consequences
- All `edm-storage` table metadata is Iceberg metadata; `edm-catalog`/`edm-metadata` read schema
  and snapshot info from the Iceberg catalog rather than maintaining a parallel copy.
- Time travel and snapshot rollback are available "for free" for Dataset versioning.
- We take on Iceberg's REST/Hive/JDBC catalog as another stateful component to run (likely the
  Iceberg REST catalog backed by Postgres) — accounted for in
  [11-infrastructure-architecture.md](../11-infrastructure-architecture.md) once written.
