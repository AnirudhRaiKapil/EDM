# EDM Platform — Repository Structure

The project starts as a single monorepo. If specific modules later need independent release
cycles or separate access control, they can be extracted — the module boundaries defined in
[02-domain-model.md](02-domain-model.md) and [01-product-architecture.md](01-product-architecture.md)
are designed so that split is mechanical, not a redesign.

```
edm-platform/                  (this repo)
│
├── docs/
│   ├── 00-vision-and-requirements.md
│   ├── 01-product-architecture.md
│   ├── 02-domain-model.md
│   ├── 03-engineering-principles.md
│   ├── 04-repository-structure.md
│   ├── 05-functional-requirements.md        (per-module, added as built)
│   ├── 06-api-specifications.md             (per-module, added as built)
│   ├── 07-database-design.md                (per-module, added as built)
│   ├── 08-event-contracts.md
│   ├── 09-ui-ux-design.md
│   ├── 10-security-architecture.md
│   ├── 11-infrastructure-architecture.md
│   ├── 12-deployment-architecture.md
│   ├── 13-devops.md
│   ├── 14-ai-architecture.md
│   ├── 15-testing-strategy.md
│   ├── 16-build-roadmap.md
│   ├── adr/                                  Architecture Decision Records
│   └── diagrams/                              source files for diagrams (excalidraw/mermaid/drawio)
│
├── services/                                  one directory per edm-* module
│   ├── edm-core/
│   ├── edm-auth/
│   ├── edm-workspace/
│   ├── edm-source/
│   ├── edm-ingestion/
│   ├── edm-pipeline/
│   ├── edm-job/
│   ├── edm-storage/
│   ├── edm-catalog/
│   ├── edm-metadata/
│   └── edm-query/
│       (V2 modules — edm-quality, edm-lineage, edm-governance, edm-notification,
│        edm-monitoring, edm-audit, edm-alerting, edm-ai — added when Phase 2 starts)
│
├── ui/                                         edm-ui (React + TypeScript)
├── sdk/                                         edm-sdk (generated/hand-written client libraries)
├── cli/                                         edm-cli
│
├── infrastructure/
│   ├── docker/                                 docker-compose for local dev
│   ├── kubernetes/                              raw manifests
│   ├── helm/                                    Helm charts per module
│   └── terraform/                               optional cloud provisioning (kept cloud-agnostic)
│
├── integrations/                                connector definitions for edm-ingestion
├── examples/                                     sample pipelines / source configs for demos
├── tests/                                        cross-module integration & e2e tests
└── README.md
```

## Conventions

- Every module under `services/` is independently buildable and independently deployable, even
  while several of them are co-deployed in one process for local/small installs.
- A module never imports another module's persistence layer or internal package — only its
  published API client (generated into `sdk/`) or its Kafka event contracts.
- Docs are numbered to reflect the order they were designed in, not necessarily the order
  they're read — `02-domain-model.md` is the one every other doc depends on.
