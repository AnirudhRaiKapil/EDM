# EDM Platform

**Open Enterprise Data Management Platform** — a 100% open-source, zero-cost, enterprise-scale
data platform: ingestion, ETL/ELT, lakehouse storage, catalog, governance, query, and
observability, unified behind one product (API + UI + CLI), not a pile of disconnected
open-source tools.

This repository is currently in the **design phase**: no infrastructure or service code has been
written yet. Start here:

| Doc | What it covers |
|---|---|
| [docs/00-vision-and-requirements.md](docs/00-vision-and-requirements.md) | Why this exists, what it must do |
| [docs/01-product-architecture.md](docs/01-product-architecture.md) | Layered architecture, control/data plane split, module map, tech stack |
| [docs/02-domain-model.md](docs/02-domain-model.md) | Canonical entities every API/DB/event/UI is built from |
| [docs/03-engineering-principles.md](docs/03-engineering-principles.md) | The 10 rules every change follows |
| [docs/04-repository-structure.md](docs/04-repository-structure.md) | Monorepo layout |
| [docs/05-build-roadmap.md](docs/16-build-roadmap.md) | Phased build order and MVP definition |
| [docs/adr/](docs/adr/) | Architecture Decision Records |

## Core constraint

Every component must be free and open source — no paid licenses, no SaaS dependency, deployable
on local infra, Kubernetes, or any cloud.
