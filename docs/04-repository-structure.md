# EDM Platform — Repository Structure

The project starts as a single monorepo. If specific modules later need independent release
cycles or separate access control, they can be extracted — the module boundaries defined in
[02-domain-model.md](02-domain-model.md) and [01-product-architecture.md](01-product-architecture.md)
are designed so that split is mechanical, not a redesign.

> For what's actually built today, file by file, see [17-codebase-map.md](17-codebase-map.md).
> This doc shows the intended monorepo shape; that one shows current reality and is kept in sync
> with every change per [Rule 11](03-engineering-principles.md#rule-11--docs-stay-in-sync-with-code).

```
edm-platform/                  (this repo)
│
├── .github/workflows/                          test.yml — CI: pytest + cli smoke check
│
├── docs/
│   ├── 00-vision-and-requirements.md
│   ├── 01-product-architecture.md
│   ├── 02-domain-model.md
│   ├── 03-engineering-principles.md
│   ├── 04-repository-structure.md
│   ├── 05-functional-requirements.md        (per-module, not yet written)
│   ├── 06-api-specifications.md             (per-module, not yet written)
│   ├── 07-database-design.md                (per-module, not yet written)
│   ├── 08-event-contracts.md                (not yet written — see app/events.py topic names)
│   ├── 09-ui-ux-design.md                   (not yet written — no UI exists yet)
│   ├── 10-security-architecture.md          (not yet written — see ADR-0003 for the MVP security posture)
│   ├── 11-infrastructure-architecture.md    (not yet written)
│   ├── 12-deployment-architecture.md        (not yet written)
│   ├── 13-devops.md                         (not yet written — see .github/workflows/test.yml for the CI that does exist)
│   ├── 14-ai-architecture.md                (not yet written)
│   ├── 15-testing-strategy.md               (not yet written — see services/edm-platform/tests/)
│   ├── 16-build-roadmap.md
│   ├── 17-codebase-map.md                    living file/folder-by-file map
│   ├── adr/                                  Architecture Decision Records (0000-0005 so far)
│   └── diagrams/                             empty — reserved for diagram source files
│
├── services/
│   └── edm-platform/                         ONE modular monolith (ADR-0002), not one folder
│       │                                      per module as originally sketched below — see
│       │                                      17-codebase-map.md for the real layout.
│       └── app/modules/
│           ├── core/        ├── auth/        ├── workspace/     ├── source/
│           ├── ingestion/    ├── pipeline/    ├── job/           ├── storage/
│           ├── catalog/      ├── metadata/    ├── quality/       └── query/
│               (edm-lineage, edm-governance, edm-notification, edm-monitoring, edm-audit,
│                edm-alerting, edm-ai remain unbuilt V2 modules)
│
├── ui/                                         edm-ui (React + TypeScript) — not yet built
├── sdk/                                         edm-sdk (client libraries) — not yet built
├── cli/                                         edm-cli — built, see cli/README.md
│
├── infrastructure/
│   ├── docker/                                 docker-compose.yml exists, unverified (ADR-0004)
│   ├── kubernetes/                              empty
│   ├── helm/                                    empty
│   └── terraform/                               empty
│
├── integrations/                                empty — not yet needed
├── examples/                                     empty — not yet needed
├── tests/                                        empty — all tests currently live under
│                                                  services/edm-platform/tests/ (only one
│                                                  deployable unit exists, so there's no
│                                                  cross-module boundary to test yet)
└── README.md
```

## Conventions

- Every module under `services/edm-platform/app/modules/` is independently *extractable* (own
  models/schemas/service/router), even while all of them run in one process today.
- A module never imports another module's `models.py` or calls into another module's internals —
  only its `service.py` functions (in-process today; would become a network/API client if split
  out later) or its published events. `app/permissions.py` is the one sanctioned exception,
  since access control is inherently cross-cutting.
- Docs are numbered to reflect the order they were designed in, not necessarily the order
  they're read — `02-domain-model.md` is the one every other doc depends on.
