# ADR-0008: Pull `edm-alerting` forward into the MVP module list

- **Status:** Accepted
- **Date:** 2026-06-28

## Context
`edm-alerting` was scoped as V2 in [01-product-architecture.md](../01-product-architecture.md).
[ADR-0005](0005-quality-pulled-into-mvp.md) explicitly flagged the gap it left behind: *"'Raise
alert' from the vision doc is satisfied today by the Job's own status/error_message... a
dedicated edm-alerting notification channel is still V2, not implemented by this ADR."* In
practice that meant a failed job or a quality warning was easy to miss — you had to know to go
check a specific job's status or a specific dataset's quality runs. There was no "what's
currently broken across this project" view, which `00-vision-and-requirements.md` Section 2.12
(Monitoring & Observability — "error tracking... alerting") calls for directly.

The data needed already existed: `edm-job`'s `run_pipeline` already had a `try/except` around
every failure mode and already computed `quality_outcome`. Recording an `Alert` there is a
direct function call, not a new subsystem.

## Decision
Implement `edm-alerting` now. `Alert` per [02-domain-model.md](../02-domain-model.md):
`sourceEntityType`/`sourceEntityId`, `severity` (`info`/`warning`/`critical`), `message`,
`status` (`open`/`acknowledged`/`resolved`). Scoped to a `project_id` (not just the source
entity) so listing can be permission-checked the same way as every other project-scoped resource.

Alerts are created by **direct call from `edm-job`**, not via the in-process event subscriber
pattern `app/events.py` offers — `pipeline.failed` and `quality.failed` events are still
published for any future listener, but the alert itself is written in the same transaction as
the job/quality-run records, consistent with how `edm-lineage`'s `record_edge` and
`edm-quality`'s `evaluate_rules` are already called directly from `run_pipeline` rather than
reactively. One `except Exception` block covers every failure mode (including
`QualityCheckFailedError`), so a single `create_alert` call there handles both generic pipeline
failures and quality-blocking failures; a second call on the success path covers
`passed_with_warnings`.

Full-stack coverage in this change, matching how every other module has been built: backend
(model/service/router + 4 tests), CLI (`edm alert list/acknowledge/resolve`), UI (an Alerts tab
on the project page, filterable by status), and the e2e smoke test extended to drive a real
failure through to acknowledge/resolve.

## Alternatives Considered
- **Wait for V2** — rejected for the same reason as ADR-0005/0006: "raise alert" was specific
  enough in the original requirements, and cheap enough given data already produced elsewhere,
  that deferring it ships something that doesn't do what was asked.
- **Route alert creation through the event bus instead of a direct call** — rejected: would mean
  an alert-creation failure becomes invisible (logged, not raised) since `app/events.py`
  subscribers run fire-and-forget with no error propagation back to the job. A direct call keeps
  alert creation in the same failure-handling path as everything else `run_pipeline` does, so if
  it breaks, the job's own error handling surfaces it.
- **Real notification channels (email/Slack/webhook) now** — rejected: that's
  `edm-notification`, a distinct V2 module per the original module map, and still has no clear
  requirement pulling it forward the way "see what's currently broken" did for alerting itself.
  The `Alert.severity`/`status` model is designed so a notification module can subscribe to
  `alert.created` later without changing this one.

## Consequences
- `edm-governance` (beyond RBAC), `edm-notification`, `edm-monitoring`, `edm-audit`, `edm-ai`
  remain V2-scoped; this ADR does not pull any of those forward.
- Every workspace member can see every alert in projects they belong to (no alert-specific
  permission tier beyond project membership) — matches how quality runs and lineage are also
  visible to any project member today.
- The UI's Alerts tab defaults to filtering by `status=open`. Acknowledging or resolving an
  alert correctly removes it from that filtered view — this surprised the e2e smoke test on
  first write (it assumed the card would stay put), not the feature; the test was fixed to
  switch to the "all" filter while exercising the transitions.
