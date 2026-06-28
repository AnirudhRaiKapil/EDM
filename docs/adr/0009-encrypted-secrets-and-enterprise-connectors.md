# ADR-0009: Encrypted-at-rest credentials, and Oracle/S3/REST/ServiceNow/Jira/Confluence connectors

- **Status:** Accepted
- **Date:** 2026-06-28

## Context
The user asked to expand ingestion beyond CSV/JSON/SQLite to real enterprise systems —
ServiceNow, Atlassian (Jira/Confluence), Oracle, and AWS — matching
[00-vision-and-requirements.md](../00-vision-and-requirements.md) Section 2.4's "Enterprise
Applications" and "Cloud Storage" categories, which were always in scope but unimplemented.

Every one of these needs real credentials. [ADR-0003](0003-trimmed-phase-1-stack.md) explicitly
deferred this: *"Network databases (Postgres/MySQL/etc.) are intentionally not yet supported:
they need per-source credential storage, which is out of scope until Vault lands."* That
deferral can't hold anymore — these connectors are pointless without a real way to store a
password. Vault itself is still out of scope (it's real infrastructure requiring Docker, which
[ADR-0004](0004-wsl2-docker-deferred-on-dev-laptop.md) ruled out on this machine indefinitely).

## Decision
**Secrets:** `app/secrets.py` — credentials are JSON-serialized and encrypted with Fernet
(symmetric, authenticated encryption) using a key derived from a new `SECRET_ENCRYPTION_KEY`
setting (SHA-256 of the passphrase, base64-encoded — so any string works as a key, not just a
pre-formatted Fernet key). Stored in a new `Source.encrypted_credentials` column, separate from
the existing non-secret `connection_config` JSON column — this is exactly the
`connectionConfig`/`secretRef` split [02-domain-model.md](../02-domain-model.md) specified for
`Source` from the start, just implemented as a column instead of a Vault pointer. The API never
returns the encrypted blob or anything decrypted — `SourceRead` exposes only a `has_credentials`
boolean (a `@property` on the ORM model, so `from_attributes` picks it up with no extra plumbing).

This is **not** Vault: no key rotation, no per-secret access policy, no audit log, no dynamic
secrets. It is a real improvement over plaintext-in-`connection_config` (which is what blocked
Postgres/MySQL/Oracle before), and an honest, documented middle ground until Vault is feasible.

**Connectors**, all added to `app/modules/ingestion/connectors.py`:
- **Oracle** — `python-oracledb` in thin mode (pure Python, no Oracle Instant Client install
  needed). `SELECT`-only, same table-name/query validation pattern as the existing SQLite
  connector.
- **S3** — `boto3`. Credentials are optional: if omitted, falls back to boto3's default
  credential chain (env vars / IAM role), which is the AWS-recommended approach where available
  rather than forcing every source to hold a static key pair.
- **Generic REST API** (`rest_api`) — `app/modules/ingestion/rest_client.py`: configurable
  base URL/path/method, three auth modes (bearer/basic/api_key_header), two pagination styles
  (page-number, offset/limit), and a dotted `records_path` to locate the records array in an
  arbitrary JSON response shape. This is the answer to "etc." — any REST API that isn't
  ServiceNow/Jira/Confluence by name still works through this connector type directly.
- **ServiceNow, Jira, Confluence** — each a thin preset on top of the REST engine: ServiceNow's
  Table API (`api/now/table/{table}`, `sysparm_offset`/`sysparm_limit`), Jira's search endpoint
  (`rest/api/3/search`, JQL, `startAt`/`maxResults`), Confluence's content endpoint
  (`wiki/rest/api/content`, CQL or space key, `start`/`limit`). Jira/Confluence both use
  Atlassian's email+API-token Basic auth convention; the connector maps `{email, api_token}`
  credentials onto the REST engine's `{username, password}` basic-auth shape internally.

Per-connector-type config/credential requirements are centralized in
`app/modules/ingestion/specs.py` so `edm-source` (validates at creation time) and `edm-ingestion`
(uses the same fields at run time) can't drift apart from each other.

## Alternatives Considered
- **Keep deferring credentialed connectors entirely** — rejected: that's not "modify ingestion to
  support these systems," that's declining the request.
- **Bespoke connector per enterprise system, no shared REST engine** — rejected: doesn't scale to
  "etc.", and ServiceNow/Jira/Confluence's pagination/auth differences are small enough that a
  shared engine is clearly the right abstraction level, not a premature one.
- **Environment-variable secret references instead of encryption** (e.g.
  `connection_config.password_env = "ORACLE_PW"`) — rejected: works for a single source per
  operator-managed env var, but doesn't scale to many sources each with their own credentials,
  which is the actual shape of this platform (Rule 7: every object has an owner; sources are
  per-project, not global).

## Consequences
- `SECRET_ENCRYPTION_KEY` must be set to a real secret in any non-dev deployment (same posture as
  `JWT_SECRET` — both ship a loud `change-me-dev-only` default). Losing/rotating this key makes
  every stored credential undecryptable; there is no rotation story yet.
- None of the new connectors can be integration-tested against a real ServiceNow/Jira/Confluence/
  Oracle/AWS instance from this environment — no accounts, no Docker for a local emulator.
  ServiceNow/Jira/Confluence/REST API are tested with `httpx.MockTransport` (verifies our
  request-building logic: URLs, auth headers, pagination, JSON-path extraction — not real-system
  behavior). Oracle is tested with a mocked `oracledb.connect` (same caveat). **S3 is tested with
  `moto`**, which emulates the actual S3 API in-memory, the strongest verification of the group.
  Treat the non-S3 connectors as logic-verified, not field-verified, until run against a real
  account.
