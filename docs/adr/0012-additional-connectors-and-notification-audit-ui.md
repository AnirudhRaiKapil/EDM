# ADR-0012: Postgres/MySQL/MongoDB/Google Sheets connectors, Slack/Teams channels, and an
audit-log/notification-channels UI

- **Status:** Accepted
- **Date:** 2026-06-29

## Context
The user asked to keep adding connectors and to keep building features that make sense, with the
choice of what delegated. Two gaps stood out as the highest-value next steps because they were
already-named, already-precedented gaps rather than new scope:

1. `edm-ingestion` had Oracle/S3/REST-API/ServiceNow/Jira/Confluence (ADR-0009) but none of the
   three most common general-purpose databases (Postgres, MySQL, MongoDB) or a common
   spreadsheet-as-a-source case (Google Sheets) that plenty of real EDM deployments ingest from
   before a real warehouse exists.
2. ADR-0011 built `edm-notification` (webhook/email) and `edm-audit` full-stack but explicitly left
   them CLI-only ("Neither has a dedicated UI page yet... left for a future pass") and
   `docs/16-build-roadmap.md` explicitly called out Slack/Teams channels as unbuilt.

Both are direct continuations of existing, already-justified work rather than speculative new
modules — consistent with how ADR-0009/0010/0011 each picked up a previously-deferred or
explicitly-out-of-scope item.

## Decision

### Four new ingestion connectors
Added to `app/modules/ingestion/specs.py` (`_VALIDATORS`) and `connectors.py`
(`_CONNECTOR_LOADERS`), the same per-connector-type dict-dispatch pattern every connector since
Oracle/S3 has used:

- `postgres` / `mysql` — `connection_config: {"host", "port", "database", "query"|"table"}`,
  `credentials: {"username", "password"}`. Mirror Oracle's existing pattern exactly: a `query` must
  be `SELECT`-only, a bare `table` is validated against an identifier regex and turned into
  `SELECT * FROM` (double-quoted for postgres, backtick-quoted for mysql, matching each engine's
  own identifier-quoting convention) — closes the same SQL-injection angle Oracle's loader already
  closes. `psycopg2`/`pymysql` are both pure-Python-wheel-friendly (no compiler needed, consistent
  with every other dependency choice in this repo per ADR-0003's Windows-wheel constraint).
- `mongodb` — `connection_config: {"host", "port", "database", "collection", "filter"?, "limit"?}`.
  Credentials are **optional** here, unlike postgres/mysql/oracle: a real, common MongoDB
  deployment pattern (local dev, a cluster behind network-level auth) runs with no application
  credentials, the same precedent `s3`'s optional-credentials-falls-back-to-default-chain already
  set. `_id` is stripped from every returned document — it's a MongoDB-internal identifier, not
  part of the source data's actual schema, and would otherwise show up as a spurious column in
  every downstream pipeline/dataset.
- `google_sheets` — `connection_config: {"spreadsheet_id", "range", "auth_type"?, "header_row"?}`.
  Unlike every other connector, this one talks to a fixed, single external API
  (`sheets.googleapis.com`) rather than something `rest_api` could already express generically, so
  it gets its own loader (a direct `httpx.Client` call, not the `rest_client.py` pagination engine
  — Sheets' `values.get` endpoint returns the whole range in one response, no pagination exists to
  build). Two auth modes: `api_key` (a Sheets API key as a query param — read-only public/shared
  sheets) and `bearer` (an OAuth token — needed for anything requiring real access control).
  `header_row` (default `true`) controls whether the first returned row becomes column names;
  short rows are padded with `None` rather than dropped, since Sheets' API itself trims trailing
  empty cells per-row.

`SUPPORTED_CONNECTOR_TYPES` (13 total now) and `CREDENTIALED_CONNECTOR_TYPES` in
`app/modules/source/schemas.py`, the CLI's `click.Choice(...)` list, and the UI's `ConnectorType`
union were all updated together — the same three-places-must-agree set ADR-0009 already
established for the prior six connectors.

### Verification tier per connector (same honesty standard as ADR-0009)
- `mongodb` is verified against a real `mongomock.MongoClient()` monkeypatched onto
  `pymongo.MongoClient` — genuine MongoDB wire-protocol-compatible behavior (a real query engine,
  not a hand-written stub), the same tier `moto` gives S3. This is the strongest tier available for
  a connector this pass added.
- `postgres`/`mysql` are verified at the request-building level only (a fake
  `psycopg2.connect`/`pymysql.connect` returning a fake cursor/connection, mirroring
  `test_oracle_connector.py`'s existing pattern) — no real Postgres/MySQL server or Docker-based
  emulator is available in this environment (ADR-0004), the same limitation already accepted for
  Oracle.
- `google_sheets` is verified via `httpx.MockTransport` (the same pattern
  `test_enterprise_connectors.py` already uses for ServiceNow/Jira/Confluence) — no real Google
  Cloud project/API key was available to test against an actual spreadsheet.

### Slack and Teams notification channels
`app/modules/notification/senders.py` gained `send_slack` (posts `{"text": "[SEVERITY] message"}`
to a Slack incoming-webhook URL) and `send_teams` (posts an Office 365 Connector `MessageCard`
payload with a severity-keyed `themeColor`) — both follow the exact same injectable-`client`
shape `send_webhook` already used, so they're unit-testable the same way without a real network
call. `SUPPORTED_CHANNEL_TYPES` is now `["webhook", "email", "slack", "teams"]`; both new types
reuse the existing `config: {"url": ...}` shape (Slack/Teams webhooks are themselves just
HTTP POST URLs, structurally identical to a generic webhook from the channel-config model's
perspective) rather than inventing new config fields, and `_SENDERS`'s dispatch dict and the
`channel_type in ("webhook", "slack", "teams")` URL-requirement check were extended accordingly.

### Audit log and notification-channel UI pages
Both modules had a CLI but no UI surface, called out explicitly as a gap in ADR-0011's
Consequences. Added:
- A **Notifications tab** on `ProjectDetailPage.tsx` (alongside Sources/Pipelines/Notebooks/Alerts)
  — list existing channels (type, destination, delete) and a generic create form: a type
  `<select>` (webhook/email/slack/teams) driving a conditional destination input (an `email`-typed
  field for `email`, a `url`-typed field with a type-specific placeholder for the other three) —
  the same "one generic form, not bespoke fields per type" pattern the Sources tab already uses
  for `connection_config`/`credentials`.
- An **Audit Log section** on `WorkspaceDetailPage.tsx`, gated client-side on
  `members.some(m => m.email === user.email && m.role_name === "owner")` to match the
  `GET /workspaces/{id}/audit-events` endpoint's actual owner-only enforcement — the UI check is
  cosmetic (hide a tab a non-owner's request would 403 on anyway), not a security boundary; the
  real enforcement is and remains server-side in `permissions.py`/`require_workspace_role`.

### `ui/e2e/smoke.mjs` extended, not duplicated
Rather than writing a separate one-off script to visually verify the two new pages, the existing
canonical smoke test gained new steps: create a webhook/Slack/email channel and delete the Slack
one (covering the create-list-delete cycle and that the type-conditional form actually swaps
fields), then navigate back to the workspace page and assert the audit log shows the
`source.credentials_set` event the script's pre-existing Oracle-source-with-credentials step
already produces — no new backend trigger was invented just to exercise the UI. This both
verifies the new surfaces in a real browser (this repo's standing verification bar — see
ADR-0007's CORS-bug story) and keeps the one source-of-truth smoke test in sync with new features
per [Rule 11](../03-engineering-principles.md#rule-11--docs-stay-in-sync-with-code).

### Two incidental bugs fixed during this verification pass
- **Favicon 404 console error:** `index.html` never declared a `<link rel="icon">`, so every
  browser navigation issued an implicit `GET /favicon.ico` that 404'd, which Chrome logs as a
  console error — and `smoke.mjs` fails the whole run on *any* console error by design (the same
  strictness that caught the original CORS bug). Fixed with the standard `<link rel="icon"
  href="data:,">` no-favicon marker, which stops the browser from requesting one at all. Unrelated
  to this pass's feature work, but it was silently making every full run of the smoke test fail
  (non-zero exit) even on a script that printed `RESULT: PASS`, which would have made CI's `e2e`
  job red on every single run, including ones with no real regression — worth fixing the moment it
  was found rather than working around it in the test.
- **Stale doc claim:** `docs/17-codebase-map.md`'s `ui/e2e/smoke.mjs` row still said "Not wired
  into CI yet" — true when ADR-0007 first wrote that sentence, but ADR-0011 added the `e2e` job to
  `.github/workflows/test.yml` and updated the top-level CI summary row in the same doc without
  updating this second, more detailed mention of the same fact. Fixed to match the verified ground
  truth in the workflow file itself.

## Alternatives Considered
- **A bespoke Google Sheets OAuth flow (full 3-legged OAuth, refresh tokens)** — rejected: every
  other credentialed connector in this codebase stores a static credential blob
  (username/password, API token) and expects the operator to provide it; a full OAuth flow would
  be the first connector needing token refresh logic and a callback endpoint, disproportionate to
  what this pass set out to do. The `bearer` auth mode still supports a real OAuth token — it just
  has to be supplied and refreshed externally, the same limitation Jira/Confluence/ServiceNow's
  basic-auth-style credentials already accept.
- **Separate dedicated form fields per connector type in the Sources tab UI** (e.g. distinct
  Postgres host/port/database inputs) instead of the existing generic JSON textareas — rejected
  for the same reason `ui/README.md` already documents for the prior six connectors: bespoke
  fields per type stop scaling past a couple of connector types, and the existing generic-JSON
  approach already covers these four with zero UI changes needed.
- **A new `slack`/`teams`-specific config shape** (e.g. separate `channel`/`username` override
  fields some Slack integrations support) — rejected: the incoming-webhook URL alone is sufficient
  for this platform's one-line alert-message use case, and reusing the existing `{"url": ...}`
  shape means zero new schema/validation code beyond the type-list extension itself.
- **A standalone verification script for the new UI pages instead of extending `smoke.mjs`** —
  rejected: this repo treats one end-to-end script as the source of truth for "does the UI actually
  work," and a second script would immediately start drifting from it (Rule 11 again, applied to
  tests rather than docs).

## Consequences
- Connector count is now 13 (`csv`, `json`, `sqlite`, `oracle`, `s3`, `rest_api`, `servicenow`,
  `jira`, `confluence`, `postgres`, `mysql`, `mongodb`, `google_sheets`); any future change to the
  supported-type list still has to touch the same four places (`source/schemas.py`,
  `ingestion/specs.py`, `ingestion/connectors.py`, the CLI's `click.Choice`, the UI's
  `ConnectorType` union) — a fifth place to keep in sync, same risk ADR-0009 already accepted, not
  a new one.
- `mongodb`'s optional credentials mean a misconfigured-but-publicly-reachable MongoDB instance
  with no auth is ingestible with zero credential prompt — this mirrors a real, known MongoDB
  footgun (unauthenticated instances exposed to the internet are a well-documented class of
  incident) rather than introducing a new one; the platform doesn't and can't enforce that an
  operator's MongoDB deployment itself requires auth.
- `google_sheets`'s `api_key` auth mode only works against a sheet shared as "anyone with the
  link can view" (a restricted private sheet needs `bearer` + a token with access) — this is a
  real-world Google Sheets API constraint, not a gap in this connector.
- Slack/Teams channels are still only verified against `httpx.MockTransport`/a fake client at the
  unit level, like the generic webhook channel's own "no real public webhook endpoint exists to
  test against" limitation already documented in ADR-0011 — this pass doesn't change that
  verification ceiling, it just adds two more channel types at the same tier.
- `edm-audit` and `edm-notification` now have a real UI surface; the CLI commands documented in
  ADR-0011 remain unchanged and equally valid — the UI doesn't replace them, it's a second
  interface onto the same API, consistent with every other module's CLI+UI dual-interface pattern.
