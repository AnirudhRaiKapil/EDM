# ADR-0002: Python + FastAPI modular monolith for the MVP backend

- **Status:** Accepted
- **Date:** 2026-06-28

## Context
[01-product-architecture.md](../01-product-architecture.md) originally proposed Java 21 +
Spring Boot across ~11 independently deployed microservices. This is being built solo, unpaid,
on a single Windows laptop with no existing Kubernetes/CI investment. Hand-writing and operating
11 separate Spring Boot services and deployments alone is a multi-month effort before any
end-to-end value exists.

## Decision
1. Backend language/framework: **Python + FastAPI**.
2. Deployment topology for the MVP: a **modular monolith** — one deployable process
   (`services/edm-platform`) containing the `edm-core`, `edm-auth`, `edm-workspace`,
   `edm-source`, `edm-ingestion`, `edm-pipeline`, `edm-job`, `edm-storage`, `edm-catalog`,
   `edm-metadata`, and `edm-query` modules as internal Python packages, each with its own
   router, service layer, and ORM models — not a shared free-for-all.

Module boundaries (Section 5 of [01-product-architecture.md](../01-product-architecture.md))
are unchanged — a module still may not import another module's ORM models or call its service
functions directly. Cross-module access goes through the other module's `router`/`service`
public functions (in-process today) or its published event topic, exactly as if it were a
network call. This is what makes the later split into real microservices (per
[01-product-architecture.md Section 5](../01-product-architecture.md#5-microservice--module-map))
mechanical rather than a rewrite.

## Alternatives Considered
- **Java 21 + Spring Boot, microservices from day one** — the original plan. Rejected for now:
  too slow to bootstrap solo; revisit once the platform has paying/contributing users and the
  team is bigger than one person.
- **TypeScript + NestJS** — appealing for a single language with the React UI, but Python wins
  because most of the data-plane ecosystem we'll eventually wire in (Spark, Great Expectations,
  Airflow DAGs, pandas/DuckDB/PyArrow) is Python-native, so the control-plane and data-plane code
  can share types and tooling.
- **Go** — excellent runtime characteristics, rejected for now due to weaker fit with the
  data-plane ecosystem above and slower iteration speed for CRUD-heavy services.

## Consequences
- One `requirements.txt`/`pyproject.toml`, one process, one `docker-compose` entry for the app
  itself during MVP — much less operational surface for a solo build.
- Splitting a module out later means: give it its own FastAPI app + its own DB + a thin HTTP/gRPC
  client replacing the in-process call, and pointing its event publishing at the real Kafka
  cluster instead of the in-process bus. No domain logic changes.
- Section 9 of [01-product-architecture.md](../01-product-architecture.md) is updated to reflect
  this stack; Section 9's "provisional" note is resolved by this ADR.
- See [0003-trimmed-phase-1-stack.md](0003-trimmed-phase-1-stack.md) for which data-plane engines
  are deferred and what replaces them for the MVP.
