# ADR-0007: Build `edm-ui` with Vite + React + TypeScript; add CORS middleware

- **Status:** Accepted
- **Date:** 2026-06-28

## Context
`01-product-architecture.md` always specified React + TypeScript for `edm-ui`; nothing had been
built yet, and `ui/` was an empty placeholder. Every prior verification of the backend
(`pytest`'s `TestClient`, `curl`, `edm-cli`) was a direct HTTP client — none of them are subject
to a browser's CORS enforcement, so the backend had silently never needed `CORSMiddleware`.

Node.js was not installed on the dev machine at the start of this work. Installing it via
`winget install --source winget --id OpenJS.NodeJS.LTS` was a standard, reversible dev-tool
install with no system feature changes or reboot required — unlike the WSL2/Hyper-V situation in
[ADR-0004](0004-wsl2-docker-deferred-on-dev-laptop.md), there was no comparable risk here.

## Decision
1. **Stack:** Vite + React 19 + TypeScript, React Router (client-side routing), TanStack Query
   (server-state caching/mutations), axios (HTTP client with interceptors for auth + error
   normalization). No UI component library — plain CSS, since this is an internal tool.
2. **Structure:** one page per route, a single `api/endpoints.ts` with one typed function per
   backend call (not one file per resource — at this size, the file-count overhead wasn't worth
   it), and a `permissions`-equivalent pattern isn't needed client-side since the backend already
   enforces every check; the UI just surfaces whatever the API returns.
3. **Verification:** per this project's standing rule to drive real interfaces rather than trust
   compilation, built a Playwright-based smoke test (`ui/e2e/smoke.mjs`) that launches headless
   Chromium and drives the entire golden path through actual clicks/fills, screenshotting every
   step. This is preserved in the repo (`npm run e2e`), not a throwaway script, because it's the
   only thing that exercises this app the way a real user would.
4. **CORS:** added `CORSMiddleware` to `services/edm-platform/app/main.py`, configured via a new
   `CORS_ORIGINS` setting (comma-separated origins, defaulting to the Vite dev server's
   `http://localhost:5173`). Locked in with `tests/test_cors.py` (allows the configured origin,
   rejects an arbitrary one).

## Alternatives Considered
- **Next.js** — rejected: this is a client-rendered admin tool talking to a separate API, not a
  content site; SSR/routing-on-the-server buys nothing here and adds a heavier build/deploy story.
- **A UI component library (MUI, Chakra, etc.)** — rejected for now: would have sped up specific
  widgets (the transformation-step builder, tag chips) but adds a dependency and a design-system
  learning curve disproportionate to an internal tool's needs. Revisit if the UI's visual
  complexity grows substantially.
- **Skip e2e verification, rely on `tsc` + manual spot-checks** — rejected: this is exactly the
  "verify via real usage, not just tests" pattern that caught the CLI's path-handling bug
  earlier; skipping it here would have shipped the CORS bug straight to anyone who actually
  opened the app in a browser.

## Consequences
- `ui/` now requires Node.js to build — documented in `ui/README.md`; not a backend dependency,
  the Python services still run standalone.
- `CORS_ORIGINS` must be updated (or set to the deployed UI's origin) for any non-localhost
  deployment — see `.env.example`.
- The e2e smoke test is not yet wired into CI (`.github/workflows/test.yml`) — running both the
  backend and the Vite dev server simultaneously in CI is a reasonable follow-up, not done here
  to keep this change scoped.
