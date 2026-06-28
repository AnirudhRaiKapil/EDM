# ADR-0011: Security hardening, audit trail, notification channels, and PII masking

- **Status:** Accepted
- **Date:** 2026-06-28

## Context
The user asked to "continue building whatever is pending" overnight, autonomously, with
two explicit, repeated priorities: be "very rigorous with testing" and make the platform "as
secure as possible." That's a mandate to both finish genuinely pending work (notification
channels were explicitly scoped out of the MVP in [ADR-0008](0008-alerting-pulled-into-mvp.md);
an audit trail entity existed in [02-domain-model.md](../02-domain-model.md) since the original
domain model but was never implemented) and to actively look for and close real security gaps in
what already existed, not just add features.

A real dependency vulnerability scan (`pip-audit`) and a hands-on review of the auth and query
code surfaced more, and more serious, findings than expected. This ADR covers all of it: what was
found, what was fixed, what was built, and what's still an accepted, documented limitation.

## Decision

### Dependency upgrades
`pip-audit` against `requirements.txt` found 33 known vulnerabilities across 6 packages,
including the JWT library, the crypto library, and FastAPI's underlying ASGI framework. Each was
triaged against *this app's actual usage* (most PyJWT findings, for example, only affect
`PyJWKClient`/`PyJWK`-based verification, which this codebase never uses — plain HS256 with a
string secret isn't exploitable by them) rather than upgraded reflexively, but every package was
still upgraded to a patched version regardless of exploitability today, since pinning a known-
vulnerable version is latent risk for any future code change that does touch the affected path:
- `pyjwt` 2.10.1 -> 2.13.0, `cryptography` 44.0.0 -> 49.0.0, `python-multipart` 0.0.20 -> 0.0.32,
  `fastapi` 0.115.6 -> 0.138.1 (pulls a patched `starlette` 0.41.3 -> 1.3.1), `pytest` 8.3.4 ->
  9.1.1.
- `pyarrow` was deliberately **not** upgraded: its one finding (`PYSEC-2026-113`, a C++
  use-after-free) explicitly states "the functionality is not exposed in language bindings
  (Python...), so these bindings are not vulnerable" — upgrading anyway would trade a real
  major-version migration risk (pandas/parquet compatibility) for zero actual exposure reduction.
- The full suite (71 tests at the time) was re-run after the upgrade before anything else
  changed, specifically to isolate "did the upgrade itself break anything" from the hardening
  work that followed. It also surfaced a real, previously-silent bug: PyJWT's new
  `InsecureKeyLengthWarning` fired on every test, because the test JWT secret was shorter than
  32 bytes. Investigating *why* a `monkeypatch.setenv("JWT_SECRET", ...)` wasn't producing the
  intended value led to the same root cause as the `ENABLE_SCHEDULER` bug from ADR-0010: `Settings`
  is a module-level singleton constructed at first import, so an env var set inside a fixture can
  be too late. Fixed the same way: `monkeypatch.setattr(settings, "jwt_secret", ...)` directly.

### Critical fix: local file inclusion via the query endpoint
`POST /query`'s only check was `sql.strip().lower().startswith("select")`. That blocks
non-`SELECT` statements but **not** what a `SELECT` can call: DuckDB's `read_csv`/`read_parquet`
table functions take a path argument and were reachable from inside the user's SQL string, e.g.
`SELECT * FROM read_csv('/path/to/.env')`. Confirmed exploitable against this exact code before
the fix: a real local file's contents came back in the response. The same gap also exposed
exfiltration (`COPY (...) TO '<path>'`) and `ATTACH` to an arbitrary file.

Fix: the dataset's Parquet file is now read through the existing storage adapter (`pandas`, never
a DuckDB SQL function) and handed to DuckDB via `connection.register("dataset", dataframe)` --
an in-memory handoff, not a filesystem operation. The connection used for the *user's* SQL is then
opened with `duckdb.connect(config={"enable_external_access": False})`, which blocks every
filesystem/network primitive DuckDB has. Verified directly (not just inferred from the option's
name) against `read_csv`, `read_parquet`, `ATTACH` to a real path, `COPY ... TO`, `INSTALL` of the
`httpfs` extension, and scanning an `https://` URL directly -- all blocked; a `register()`-ed
DataFrame still queries normally. A DuckDB exception from a blocked or malformed query is now also
caught and converted to a clean 422 instead of propagating as an unhandled exception.

### Auth hardening
- **Timing side-channel (user enumeration):** `authenticate_user` only ran the (expensive)
  PBKDF2 check when a matching user existed, so "no such user" returned measurably faster than
  "wrong password" -- an attacker could enumerate valid emails by timing alone. Fixed by always
  running a PBKDF2 check, against a fixed `DUMMY_HASH` when there's no real user, so both paths
  cost the same.
- **PBKDF2 iterations:** raised from 200,000 to 600,000 (OWASP 2023 guidance). The iteration count
  is now embedded in the stored hash itself (`"{iterations}${salt}${digest}"`) rather than a bare
  constant, specifically so a *future* increase doesn't invalidate every already-stored hash the
  way the original format would have.
- **Password policy:** a 10-128 character length bound (NIST SP 800-63B: length matters more than
  mandatory character-class rules, which mostly just push users toward predictable patterns; the
  upper bound exists because PBKDF2's cost scales with input size, so an unbounded password is a
  cheap CPU-burn lever for an attacker).
- **Rate limiting:** `/auth/login` and `/auth/register` are limited by both client IP and target
  email (IP-only misses credential stuffing spread across source IPs; email-only misses one IP
  brute-forcing many accounts). In-process only (`app/rate_limit.py`) -- no Redis is available
  (ADR-0003/0004), so this doesn't hold across multiple server instances behind a load balancer;
  documented as a real, accepted limitation rather than papered over.
- **Security response headers:** `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`,
  `Referrer-Policy: no-referrer`, `Cache-Control: no-store` on every response.
- **Upload size limit:** `POST /sources/{id}/upload` read the entire multipart body into memory
  with no cap at all. Now reads in bounded 1MB chunks and aborts (413) the moment the configured
  `MAX_UPLOAD_MB` (default 100) is crossed, instead of buffering an arbitrarily large upload
  first and checking after.
- **Weak-secret startup warning:** `app/main.py`'s lifespan now logs a loud warning if
  `JWT_SECRET`/`SECRET_ENCRYPTION_KEY` are still at their `change-me-dev-only` defaults or shorter
  than 32 bytes. Not enforced (a hard failure would break the zero-config first run
  `.env.example` is designed for) -- the goal is making "running insecurely" a visible choice.

### `edm-audit`: immutable audit trail
`AuditEvent` (`app/modules/audit/`) was in the original domain model's entity catalog from the
start but never built. Records, append-only (no update/delete function exists): registration,
login success/failure, role assignment, a source's credentials being set (never the credential
*value*), and pipeline schedule changes. `subject_email` is stored alongside the nullable
`actor_user_id` specifically so a failed login against an email with no account is still
attributable to *that email* (`GET /users/me/audit-events` answers "has anyone been trying to log
into my account"), even though there's no real actor to record. `GET /workspaces/{id}/audit-events`
is owner-only -- this log can reveal who has access to what and when credentials changed, which a
plain member shouldn't see about their own workspace.

### `edm-notification`: webhook and email alert channels
Explicitly out of scope for the MVP per ADR-0008 ("not implemented... alerts are in-app/API-only
until edm-notification exists"). `NotificationChannel` is project-scoped (`webhook` config: `url`;
`email` config: `to_address`); `alerting.service.create_alert` fans out to every enabled channel
on the alert's project after the alert itself is committed. Delivery failure is always caught and
logged, never raised -- a dead webhook endpoint or a rejecting SMTP server must never turn into a
failed request for whatever *triggered* the alert. SMTP server settings (`SMTP_HOST` etc.) are
operator-level config, not per-channel, since the channel only needs to know a recipient.

Verified beyond unit tests with mocked transports: a webhook was sent to and received `200 OK`
from a real local `http.server` listener; an email was sent through `smtplib` to and successfully
parsed by a real local `aiosmtpd` SMTP server (full EHLO/MAIL/RCPT/DATA/QUIT exchange, not just a
constructed message object) -- the same "field-verify if at all possible" standard
[ADR-0009](0009-encrypted-secrets-and-enterprise-connectors.md) applied to S3 via `moto`. No real
SMTP server or public webhook endpoint exists to test against beyond that, which is the honest
limit of what's verifiable in this environment.

### Governance: PII column masking
There is no per-column classification model yet -- only `Dataset.classification: list[str]`,
already settable via the existing `PATCH /catalog/datasets/{id}` endpoint. Building a full
column-level tagging subsystem (new entity, new endpoints, UI to flag individual columns) to
satisfy "mask PII/classified columns" was judged disproportionate to a one-night autonomous pass;
instead, `query/service.py` masks any column whose *name* matches a fixed list of common PII
patterns (`email`, `ssn`, `phone`, `password`, `address`, `dob`, `credit_card`, ...) whenever the
queried dataset's classification includes `"pii"`, for every caller except the workspace owner.
This is dataset-level classification driving column-level masking by name heuristic, not true
column-level governance -- a real implementation would need per-column tags and is left for when
that's worth building deliberately rather than as a side effect of a security pass.

### CI: Playwright e2e now runs on every push/PR
`ui/e2e/smoke.mjs` existed but was explicitly "not wired into CI yet (would need both the backend
and Vite dev server running simultaneously)" per `17-codebase-map.md`. Added an `e2e` job to
`.github/workflows/test.yml`: installs both stacks, starts the backend and the Vite dev server in
the background with a `curl`-retry readiness wait, runs the smoke test, and uploads screenshots
plus both servers' logs as artifacts on failure.

## Alternatives Considered
- **Trust pip-audit's CVE list without checking exploitability against actual usage** --
  rejected: several PyJWT findings only apply to `PyJWKClient`/`PyJWK`, which this codebase
  doesn't use. Upgrading regardless was still right (free risk reduction), but blindly treating
  every CVE as equally urgent would have misdirected effort.
- **Block the query endpoint's `read_csv`/`read_parquet`/etc. by string-matching the SQL for
  dangerous function names** -- rejected: a blocklist of function names is exactly the kind of
  filter that's trivially bypassed (aliasing, case variation, DuckDB adding a new table function
  later that isn't on the list). `enable_external_access=False` is an allowlist at the engine
  level -- it disables the *capability*, not specific spellings of it.
- **A full per-column tagging subsystem for PII masking** -- rejected for now (see above); the
  name-pattern heuristic on top of the existing dataset-level classification ships a real,
  if narrower, version of the same protection without a disproportionate new subsystem.
- **Shared (Redis-backed) rate limiting** -- rejected: no Redis is available (ADR-0003/0004); an
  in-process limiter is honestly weaker (per-instance, not global) but is the only option that
  doesn't require new infrastructure this environment can't run.

## Consequences
- The rate limiter and weak-secret warnings only protect a single server process; a real
  multi-instance deployment needs a shared backend for the former and should treat the latter as
  a deploy-time gate (fail CI/CD if secrets are still default), not just a runtime log line.
- PII masking is a name-heuristic, not a real governance feature -- a column legitimately named
  something that happens to match a pattern gets masked with no way to override it per-column yet,
  and a sensitive column named something that *doesn't* match (e.g. a free-text `notes` field
  containing someone's address) isn't caught at all.
- Every new module (audit, notification) follows the same full-stack pattern as ADR-0009/0010:
  backend + tests + CLI commands, verified against a live server. Neither has a dedicated UI page
  yet (the CLI is the only non-API interface for them today) -- left for a future pass rather than
  rushed here.
- `email-test` verification used a real local SMTP server (`aiosmtpd`, a dev-only dependency not
  added to `requirements.txt` since it's not used by the application itself) -- this is stronger
  than a mock but still not a real-world deliverable/inbox; genuine email delivery still needs a
  real SMTP provider's credentials to verify end-to-end.
