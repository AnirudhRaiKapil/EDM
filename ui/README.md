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
- `src/pages/` — one file per route. `ProjectDetailPage.tsx` holds a Sources tab and a Pipelines
  tab (with an inline transformation-step builder); `DatasetDetailPage.tsx` holds schema, tags,
  classification, data quality (rules + run history), lineage, and a SQL query runner — every
  backend capability has a corresponding place to use it from here.

## Routes

```
/login, /register
/workspaces                                          list + create
/workspaces/:workspaceId                              projects + members
/workspaces/:workspaceId/projects/:projectId          sources + pipelines tabs
/pipelines/:pipelineId                                transformations, run, job history
/catalog                                              dataset search
/datasets/:datasetId                                  schema, tags, classification, quality, lineage, query
```

## End-to-end smoke test

There's no browser available to a coding agent directly, so verifying this app means launching a
real (headless) browser against it — see `e2e/smoke.mjs`, which drives the entire golden path
(register → workspace → project → source → upload → pipeline → run → tag/classify → quality rule
→ lineage → query) through actual clicks and form fills, then screenshots every step.

```
npm run e2e:install   # once, downloads the Chromium binary
npm run dev            # in one terminal — leave running
npm run e2e             # in another — requires the backend running too
```

Screenshots land in `e2e/shots/` (gitignored). Exits non-zero on failure or on any browser
console error, so a passing run is a real signal, not just "it compiled."

This is how the CORS bug below was actually found — `curl`/`pytest` can't catch it, since CORS is
a browser-enforced policy, not something a direct HTTP client ever encounters.

## Known gap this UI exposed

Running this in a real browser for the first time immediately failed on CORS: the backend had
never had `CORSMiddleware` configured (nothing before this UI ever made a cross-origin request to
it — `pytest`'s `TestClient` and `curl` both bypass the browser's CORS enforcement entirely). Fixed
in `services/edm-platform/app/main.py` + a new `CORS_ORIGINS` setting; see
[ADR-0007](../docs/adr/0007-react-ui-and-cors-fix.md).
