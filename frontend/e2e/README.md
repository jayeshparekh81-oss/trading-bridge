# Chart E2E suite

Playwright smoke tests for the chart route. Phase-6 scope is mock-mode
only — the suite has no dependency on a live backend or paper-trading
data.

## Run

From `frontend/`:

```bash
npm run test:e2e             # headless, default chromium
npm run test:e2e -- --headed # see the browser
npm run test:e2e -- --ui     # Playwright UI mode (interactive picker)
```

The first run installs the chromium browser if it isn't cached:

```bash
npx playwright install chromium
```

## How auth is bypassed

The chart route lives under `(dashboard)/`, whose layout enforces auth
via `useAuth()` — unauthenticated users get redirected to `/login`.
The E2E suite handles this in `chart.spec.ts::beforeEach`:

1. **Token seeding** — `context.addInitScript` writes
   `tb_access_token` + `tb_refresh_token` to `localStorage` BEFORE the
   page mounts so `AuthProvider`'s mount effect sees a token.
2. **`/api/auth/me` interception** — `page.route(...)` returns a
   synthetic `User` payload that satisfies the dashboard layout's
   `onboarding_step >= 6` check.

Every other `/api/*` call is left untouched. The chart hooks
(`useChartHistory`, `useChartWebSocket`, `useChartMarkers`,
`useChartScrollback`) all short-circuit to in-memory mock fixtures
when `NEXT_PUBLIC_USE_MOCK=true` is set — and the playwright
`webServer` block in `playwright.config.ts` injects exactly that env
var, so the suite never touches the backend at all.

## Mock-mode vs real-backend

| Mode      | Backend running? | `NEXT_PUBLIC_USE_MOCK` | Notes                          |
| --------- | ---------------- | ---------------------- | ------------------------------ |
| Mock (default) | No          | `true`                 | Phase-6 scope. Auto-started by `playwright.config.ts`'s webServer block on port 3100. |
| Real      | Yes (8000)       | `false`                | After smoke green tomorrow. Set `E2E_BASE_URL=http://localhost:3000` to point at the operator's existing dev server. |

To run against a pre-warmed dev server (skips the auto-start
webServer):

```bash
E2E_BASE_URL=http://localhost:3000 npm run test:e2e
```

## What the suite covers (Phase 6 smoke)

* Chart route loads, canvas renders.
* Symbol switch updates the input.
* Timeframe switch sets the active button.
* Status pill flips to live after WS open (mock).
* Strategy selector populates with mock strategies.
* Indicators dropdown opens with all 5 toggles.
* Paper trade list shows the "select a strategy" empty state.
* Header info row shows the symbol + price after candles load.

## What's NOT in scope for Phase 6

* Real-backend integration (deferred until smoke green).
* Marker click → list scroll handshake (canvas-coordinate
  interactions are tricky in Playwright; covered in unit tests).
* Scroll-back lazy-load trigger (timing-sensitive; covered in unit
  tests).
* Touch gestures (Phase 5; can't synthesise multi-finger gestures
  reliably in chromium-headless).
