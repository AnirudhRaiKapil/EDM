# EDM Platform

**Open Enterprise Data Management Platform** — a 100% open-source, zero-cost, enterprise-scale
data platform: ingestion, ETL/ELT, lakehouse storage, catalog, governance, data quality, and
query, unified behind one product (API + UI + CLI), not a pile of disconnected open-source tools.

The MVP backend, a web UI, and a CLI are implemented and tested end to end. Start here:

| Doc | What it covers |
|---|---|
| [docs/00-vision-and-requirements.md](docs/00-vision-and-requirements.md) | Why this exists, what it must do |
| [docs/01-product-architecture.md](docs/01-product-architecture.md) | Layered architecture, control/data plane split, module map, tech stack |
| [docs/02-domain-model.md](docs/02-domain-model.md) | Canonical entities every API/DB/event/UI is built from |
| [docs/03-engineering-principles.md](docs/03-engineering-principles.md) | The 11 rules every change follows |
| [docs/04-repository-structure.md](docs/04-repository-structure.md) | Intended monorepo layout |
| [docs/17-codebase-map.md](docs/17-codebase-map.md) | What every file/folder in the repo actually does, kept current |
| [docs/16-build-roadmap.md](docs/16-build-roadmap.md) | Phased build order, MVP definition, and what's built vs. open |
| [docs/adr/](docs/adr/) | Architecture Decision Records — why things are the way they are |

## Run it

```
cd services/edm-platform
py -3 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
copy .env.example .env
.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000
```

Then drive it with the web UI (`ui/README.md`, `npm install && npm run dev`), the CLI
(`cli/README.md`), or `curl` — see `services/edm-platform/README.md` for the full golden path.

## Core constraint

Every component must be free and open source — no paid licenses, no SaaS dependency, deployable
on local infra, Kubernetes, or any cloud.
