# ADR-0005: Pull `edm-quality` forward into the MVP module list

- **Status:** Accepted
- **Date:** 2026-06-28

## Context
[01-product-architecture.md](../01-product-architecture.md) originally scoped `edm-quality` as
a V2 ("Enterprise") module, built only after the Core/MVP list
(auth/workspace/source/ingestion/pipeline/job/storage/catalog/metadata/query) was complete.

[00-vision-and-requirements.md](../00-vision-and-requirements.md) Section 2.10 and the Layer 10
description in [01-product-architecture.md](../01-product-architecture.md) both specify a very
concrete behavior: *"If validation fails -> Reject batch -> Raise alert -> Log issue -> Prevent
downstream publication."* This was one of the most specific, emphasized requirements in the
original design conversation — closer to a hard correctness requirement ("don't publish bad
data") than an enterprise nice-to-have.

## Decision
Implement `edm-quality` now, as part of the MVP module list, rather than waiting for the V2
phase. Scope is deliberately narrow: `QualityRule`/`QualityRun` per
[02-domain-model.md](../02-domain-model.md), six expectation types (`not_null`, `unique`, `min`,
`max`, `regex`, `allowed_values`), two severities (`warning`, `blocking`). No profiling,
anomaly detection, or Great Expectations integration yet — that remains the eventual V2 upgrade
path noted in [ADR-0003](0003-trimmed-phase-1-stack.md).

Rules attach to a `Dataset`, which means they can only be created after a pipeline's first
successful run (nothing to validate against before that). `edm-job`'s `run_pipeline` evaluates
existing rules against the newly-transformed data *before* overwriting storage or creating a new
schema version — a `blocking` failure raises before either happens, so the previously published
dataset is genuinely untouched, not just flagged.

## Alternatives Considered
- **Wait for V2 as originally planned** — rejected: data quality enforcement was specific enough
  in the original requirements that shipping an MVP without it means shipping something that
  doesn't do what was asked, not just a smaller version of it.
- **Integrate Great Expectations now instead of hand-rolled checks** — rejected for the MVP:
  Great Expectations is a substantial dependency with its own data-context/checkpoint model;
  hand-rolled pandas checks deliver the same blocking-publication behavior with a fraction of the
  integration surface. Revisit once the rule catalog needs to grow past what's listed above.

## Consequences
- `edm-lineage`, `edm-governance`, `edm-notification`, `edm-monitoring`, `edm-audit`,
  `edm-alerting`, `edm-ai` remain V2-scoped; this ADR does not pull any of those forward.
- `Job.metrics.qualityOutcome` is `null` until a dataset has at least one quality rule;
  `"passed"`, `"passed_with_warnings"`, or `"failed"` thereafter.
- "Raise alert" from the vision doc is satisfied today by the Job's own `status`/`error_message`
  surfaced through the existing Job API — a dedicated `edm-alerting` notification channel
  (email/Slack/webhook) is still V2, not implemented by this ADR.
