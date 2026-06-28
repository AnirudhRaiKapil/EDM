# ADR-0006: Pull `edm-lineage` forward into the MVP module list

- **Status:** Accepted
- **Date:** 2026-06-28

## Context
Like `edm-quality` ([ADR-0005](0005-quality-pulled-into-mvp.md)), `edm-lineage` was originally
scoped as a V2 module in [01-product-architecture.md](../01-product-architecture.md). The
original vision conversation was specific about lineage too: governance Section 9.3 of
[00-vision-and-requirements.md](../00-vision-and-requirements.md) gives a worked example
(`Sales.csv -> Kafka -> Spark -> Iceberg -> Gold Table -> Dashboard`) and states plainly *"you
can identify the source of every field in a report."* That's a concrete capability, not an
aspiration, and the data needed to support it (`Job.pipeline_id`, `Pipeline.source_id`,
`Job.dataset_id`) already existed in `edm-job`/`edm-pipeline` — recording it as queryable edges
was a small addition on top of code already being written, not a new subsystem.

## Decision
Implement `edm-lineage` now. Scope: a single `LineageEdge` table per
[02-domain-model.md](../02-domain-model.md) Section 2 (`fromEntityType`, `fromEntityId`,
`toEntityType`, `toEntityId`, `jobId`). `edm-job`'s `run_pipeline` records two edges on every
successful run: `(Source, source_id) -> (Dataset, dataset_id)` and
`(Pipeline, pipeline_id) -> (Dataset, dataset_id)`, both tagged with the job that produced them.
Edges are append-only — reruns add new edges rather than replacing old ones, so the full history
of what produced a dataset is preserved, matching the "everything is versioned" principle
(Rule 6) rather than just the latest run.

Three read endpoints (`GET /lineage/datasets/{id}`, `/lineage/sources/{id}`,
`/lineage/pipelines/{id}`) each return `{upstream, downstream}` by querying the same table from
either direction — there's no separate "graph" data structure, the graph is just the union of
rows, exactly as the domain model says.

## Alternatives Considered
- **Wait for V2** — rejected for the same reason as ADR-0005: this was specific enough in the
  original requirements, and cheap enough given data already produced elsewhere, that deferring
  it produces an MVP that can't do something explicitly asked for.
- **Multi-hop dataset-to-dataset lineage now** (e.g. Bronze -> Silver -> Gold chains) — rejected
  for now: `Pipeline.source_id` only points at a `Source`, not at another `Dataset`, so a
  pipeline can't yet declare "my input is that other dataset." Modeling that is a `edm-pipeline`
  schema change, not a lineage-module change, and is left for whenever multi-layer pipeline
  chaining is actually built.

## Consequences
- `edm-governance`, `edm-notification`/`edm-alerting`, `edm-monitoring`, `edm-audit`, `edm-ai`
  remain V2-scoped; this ADR does not pull any of those forward.
- Lineage is currently only as deep as one hop per job (source/pipeline directly to the dataset
  that job produced). A consumer wanting the full Bronze->Silver->Gold chain today has to follow
  multiple datasets' edges manually until/unless multi-hop pipeline inputs are built.
