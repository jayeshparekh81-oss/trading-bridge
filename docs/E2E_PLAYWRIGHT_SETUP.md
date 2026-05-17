# Playwright E2E Setup

**Branch:** `feat/e2e-playwright`
**Cut from:** `origin/main`

---

## TL;DR

5 critical-flow E2E tests at repo root in `./e2e/`. Each spec asserts
a page loads + NO console errors fire during render. This is the
class of test that would have caught the IndicatorPanel runtime crash
(the crash was visible in the browser console but no test was
watching for console errors).

Stack:
- `@playwright/test` ^1.60.0 (pre-authorized install)
- Chromium only (most common browser; firefox/webkit added later)
- Sequential workers (1) to avoid auth-cookie collisions

---

## Running locally

```sh
# Terminal 1: start the frontend dev server
cd frontend
npm run dev    # listens on http://localhost:3000

# Terminal 2: run e2e tests
cd /Users/jayeshparekh/trading-bridge-chart
npx playwright test                   # all specs
npx playwright test e2e/login.spec.ts  # one spec
npx playwright test --ui              # interactive UI mode
npx playwright test --headed          # see browser
```

CI mode: `playwright.config.ts`'s `webServer` block auto-starts the
frontend when `CI=true` is set, so no manual dev-server start needed.

## Test file layout

```
e2e/
    fixtures.ts                  # shared test fixtures (auth, mocks, console-error watcher)
    login.spec.ts                # /login renders, no console errors
    strategies-list.spec.ts      # /strategies loads empty state, no console errors
    templates-gallery.spec.ts    # /strategies/templates shows ≥ 1 card, no console errors
    template-clone.spec.ts       # clone flow → detail page → "Cloned from template" badge
    chart-load.spec.ts           # /chart renders, no fatal console errors (ws errors filtered)
```

## What each test catches

| Test | Catches |
|---|---|
| `login.spec.ts` | Hard crash on initial /login render |
| `strategies-list.spec.ts` | API-shape mismatch on /api/strategies GET |
| `templates-gallery.spec.ts` | The exact bug class as the IndicatorPanel crash (API envelope mismatch); also paging fetch errors |
| `template-clone.spec.ts` | Regression of May-17 clone-flow UX fix (template_origin must surface on detail page) |
| `chart-load.spec.ts` | Chart module + WebSocket + lightweight-charts integration crashes |

## Auth strategy

`fixtures.ts::setupFakeAuth` injects a fake JWT into `localStorage`
via `page.addInitScript`. NO real credentials in tests. The fake
token's `exp` field is set 1 hour in the future so frontend guards
don't redirect to /login.

## Backend mocking

`fixtures.ts::mockBackend` registers `page.route` handlers for the
core API endpoints used by every page:
- `GET /api/strategies/indicators` (returns array, NOT envelope)
- `GET /api/strategies`
- `GET /api/templates*`
- `GET /api/users/me`

Per-test mocks for specific endpoints (e.g. `POST /api/templates/.../clone`)
are added inline in the test that needs them.

## Adding a new test

1. Create `e2e/your-flow.spec.ts`
2. Import `test, expect, mockBackend, setupFakeAuth` from `./fixtures`
3. In the test body:
   ```ts
   await setupFakeAuth(page);
   await mockBackend(page);
   await page.route("**/api/your/endpoint", ...);
   await page.goto("/your-route");
   ```
4. Assert page state + assert `consoleErrors` empty

## CI activation

`docs/e2e-workflow.yml.staged` is the GitHub Actions workflow,
staged outside `.github/workflows/` because the automation PAT lacks
the `workflow` scope. Founder activates with:

```sh
git mv docs/e2e-workflow.yml.staged .github/workflows/e2e.yml
git commit -m "ci(e2e): activate Playwright workflow"
git push
```

This mirrors the pattern established by Queue I Task 3
(`integration-workflow.yml.staged`).

## What's NOT in v1

- Multi-browser (firefox, webkit) — Chromium only for now
- Visual regression (screenshot diff) — too noisy for v1
- Real backend integration — uses route mocks
- Login flow that actually authenticates — needs test credentials
- Mobile viewport tests — desktop only

These ship as v2 if E2E coverage proves valuable.

## See also

- `playwright.config.ts` — root config
- `frontend/package.json` — `@playwright/test` + `playwright` deps
- `MANUAL_INSTALL_CI_WORKFLOW.md` — the same staged-YAML pattern as
  the integration test workflow
