# edm-ui

`edm-ui` — the React + TypeScript web client, per
[01-product-architecture.md](../docs/01-product-architecture.md). Built with Vite, React Router,
TanStack Query, and axios. No UI component library — plain CSS (`src/index.css`), since this is
an internal admin-style tool, not a marketing site.

## Run locally

The backend (`services/edm-platform/`) must be running on `http://localhost:8000` first (see its
README). Then:

```
npm install
copy .env.example .env.local
npm run dev
```

Open `http://localhost:5173`. `VITE_API_URL` in `.env.local` points at the API; defaults to
`http://localhost:8000/api/v1`.

## Structure

- `src/api/client.ts` — axios instance with a request interceptor that injects the bearer token
  and a response interceptor that normalizes errors into `ApiError`.
- `src/api/types.ts` — TypeScript interfaces mirroring every backend Pydantic schema.
- `src/api/endpoints.ts` — one typed function per API call, grouped by resource.
- `src/context/AuthContext.tsx` — login/register/logout, token persisted to `localStorage`.
- `src/pages/` — one file per route. `ProjectDetailPage.tsx` holds a Sources tab (generic
  `connection_config`/`credentials` JSON fields cover all 7 non-file connector types — not
  bespoke fields per type, since that stopped scaling once Oracle/S3/REST/ServiceNow/Jira/
  Confluence joined sqlite), a Pipelines tab (with an inline transformation-step builder), a
  Notebooks tab (create + list, links into `NotebookDetailPage.tsx`), and an Alerts tab
  (status-filterable, acknowledge/resolve); `PipelineDetailPage.tsx` also holds a Schedule
  section (set/clear a cron expression); `NotebookDetailPage.tsx` holds per-cell editors with
  run/delete controls and inline results, a "run all" button, and a promote-to-pipeline form
  (ADR-0010); `DatasetDetailPage.tsx` holds schema, tags, classification, data quality (rules +
  run history), lineage, and a SQL query runner. `edm-audit` and `edm-notification` (ADR-0011)
  have no dedicated page yet — `edm-cli`'s `audit`/`notification` commands are the only interface
  to them today. PII column masking (ADR-0011) needed no UI changes at all: it happens server-side
  on the query response itself, so the existing query runner in `DatasetDetailPage.tsx` already
  shows masked values to a non-owner with zero changes on this side.

## Routes

```
/login, /register
/workspaces                                          list + create
/workspaces/:workspaceId                              projects + members
/workspaces/:workspaceId/projects/:projectId          sources + pipelines + notebooks + alerts tabs
/pipelines/:pipelineId                                transformations, schedule, run, job history
/notebooks/:notebookId                                cells (edit/run/delete), promote to pipeline
/catalog                                              dataset search
/datasets/:datasetId                                  schema, tags, classification, quality, lineage, query
```

## End-to-end smoke test

There's no browser available to a coding agent directly, so verifying this app means launching a
real (headless) browser against it — see `e2e/smoke.mjs`, which drives the entire golden path
(register → workspace → project → source → upload → pipeline → run → set/clear a cron schedule →
tag/classify → quality rule → lineage → query → create a notebook, write and run cells that share
state across each other, promote it to a pipeline and run that too → deliberately-failing pipeline
→ acknowledge/resolve the resulting alert) through actual clicks and form fills, then screenshots
every step.

```
npm run e2e:install   # once, downloads the Chromium binary
npm run dev            # in one terminal — leave running
npm run e2e             # in another — requires the backend running too
```

Screenshots land in `e2e/shots/` (gitignored). Exits non-zero on failure or on any browser
console error, so a passing run is a real signal, not just "it compiled." This now also runs on
every push/PR via the `e2e` job in `.github/workflows/test.yml` (ADR-0011) — the steps above are
for running it locally during development.

This is how the CORS bug below was actually found — `curl`/`pytest` can't catch it, since CORS is
a browser-enforced policy, not something a direct HTTP client ever encounters.

## Known gap this UI exposed

Running this in a real browser for the first time immediately failed on CORS: the backend had
never had `CORSMiddleware` configured (nothing before this UI ever made a cross-origin request to
it — `pytest`'s `TestClient` and `curl` both bypass the browser's CORS enforcement entirely). Fixed
in `services/edm-platform/app/main.py` + a new `CORS_ORIGINS` setting; see
[ADR-0007](../docs/adr/0007-react-ui-and-cors-fix.md).
