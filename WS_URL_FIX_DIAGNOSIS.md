# WS URL + /health 404 diagnosis — Path A (env-var-only fix)

**Date:** 2026-05-17 (T-1 from May-18 launch)
**Symptom:** `tradetri.com/chart` browser console shows
- `WebSocket connection to 'wss://tradetri.com/ws/chart/NIFTY/5m?token=…' failed` (repeating)
- `Failed to load resource: /health 404`
**Diagnosis scope:** read-only.
**Outcome:** Path A confirmed. One Vercel env var to set; **no code changes required**.

---

## TL;DR

The frontend already has the correct WS URL construction code. The bug is that **`NEXT_PUBLIC_API_URL` is not set in the Vercel production environment** (or set to the wrong value). Without it, the WS URL builder falls back to `window.location.origin` (= `https://tradetri.com`) and rewrites the scheme → `wss://tradetri.com/…` — but Vercel doesn't proxy WebSocket upgrades for non-Enterprise plans, so the connect fails. The same env var also drives the `/health` URL.

**Fix**: In the Vercel project's production environment, set:

```
NEXT_PUBLIC_API_URL=https://api.tradetri.com
```

That single change fixes both the WS connect + the `/health` 404 simultaneously. Then redeploy the Vercel production build (or push a no-op commit) to pick up the new env var.

---

## 1. WS URL construction site

**File:** `frontend/src/lib/chart/api.ts:190-214`

```typescript
export function buildChartWsUrl(opts: {
  symbol: string;
  timeframe: Timeframe;
  token: string;
}): string {
  const apiBase =
    process.env.NEXT_PUBLIC_API_URL ??
    (typeof window !== "undefined" ? window.location.origin : "");
  const wsBase = apiBase.replace(/^http/i, "ws");
  const symbol = encodeURIComponent(opts.symbol.toUpperCase());
  const tf = encodeURIComponent(opts.timeframe);
  const token = encodeURIComponent(opts.token);
  return `${wsBase}/ws/chart/${symbol}/${tf}?token=${token}`;
}
```

Behaviour:
- If `NEXT_PUBLIC_API_URL=https://api.tradetri.com` → produces `wss://api.tradetri.com/ws/chart/…` ✓ (correct, working)
- If `NEXT_PUBLIC_API_URL` unset AND `window.location.origin === "https://tradetri.com"` → produces `wss://tradetri.com/ws/chart/…` ✗ (current production behaviour, broken)
- If `NEXT_PUBLIC_API_URL=http://localhost:8000` → produces `ws://localhost:8000/ws/chart/…` ✓ (dev default per `.env.example:13`)

**The code is correct.** The env var is the configuration knob, and it is unset (or wrong) in Vercel production.

## 2. /health URL construction site

**File:** `frontend/src/app/(dashboard)/page.tsx:108-110`

```typescript
const HEALTH_URL = process.env.NEXT_PUBLIC_API_URL
  ? `${process.env.NEXT_PUBLIC_API_URL}/health`
  : "/health";
```

Behaviour:
- With env var set → `https://api.tradetri.com/health` ✓
- Without env var → `/health` (relative to Vercel host) → Vercel serves nothing on that path → **404** ✗

Note: `frontend/next.config.ts:36-43` defines a rewrite `/api/:path* → https://api.tradetri.com/api/:path*` which is why REST API calls (`/api/...`) still work in production WITHOUT the env var. But:
- `/health` is NOT under `/api/`, so the rewrite doesn't catch it
- WebSocket upgrades aren't routed through Next.js rewrites at all
→ Both fail in production.

## 3. Env var inventory

| Var | Where used | Current dev (`.env.local`) | `.env.example` default | Required in Vercel prod |
|---|---|---|---|---|
| `NEXT_PUBLIC_API_URL` | WS URL, /health URL, `lib/api.ts:9`, `paper-mode-banner.tsx:13`, `useSystemMode.ts:13`, `(dashboard)/page.tsx:108` | not set (only `NEXT_PUBLIC_USE_MOCK=true` is in `.env.local`) | `http://localhost:8000` | **`https://api.tradetri.com`** ← THE FIX |
| `NEXT_PUBLIC_USE_MOCK` | mock WS toggle | `true` | (commented in example) | should be unset or `false` in prod |

## 4. Backend WS endpoint verification (EC2 13.127.224.68)

| Check | Result |
|---|---|
| WS route registered in `app/api/chart.py:507` | ✓ `@router.websocket("/ws/chart/{symbol}/{timeframe}")` |
| `chart_router` mounted in `main.py:268` | ✓ `app.include_router(chart_router)` |
| Localhost probe (proper WS Upgrade headers + valid `Sec-WebSocket-Key`) | ✓ `400 Bad Request: invalid Sec-WebSocket-Key` (parser reached; would proceed with real handshake) |
| Localhost probe (bad `Sec-WebSocket-Key`) | ✓ Same 400 — proves route is alive |
| Localhost `/health` | ✓ `200 OK` |
| Localhost `/api/chart/markers` (no auth) | ✓ `401` (auth-gated, route alive) |
| Nginx config: WS upgrade headers | ✓ `Upgrade $http_upgrade` + `Connection 'upgrade'` present (server_name `api.tradetri.com`) |
| Nginx `proxy_read_timeout` | `300s` (way > any reconnect cycle — not a contributing factor) |
| **Public probe through nginx**: `curl -i ... https://api.tradetri.com/ws/chart/NIFTY/5m?token=invalid` with proper Upgrade headers | ✓ `400 Bad Request: invalid Sec-WebSocket-Key` — **WS reaches FastAPI through nginx** |

**Backend + nginx are fully wired.** No backend/nginx changes needed. The bug is purely on the Vercel/frontend side.

---

## 5. Why this is Path A (env-var-only)

Per the spec's three paths:

| Path | When applicable | Verdict for this bug |
|---|---|---|
| A — env var only | URL comes from `NEXT_PUBLIC_*`, code is correct | ✓ **YES** — this is the case |
| B — code change | URL hardcoded or built wrongly | ✗ NO — code uses env var correctly |
| C — backend missing endpoint | Backend doesn't serve `/ws/chart/...` | ✗ NO — backend + nginx serve the WS endpoint cleanly through `api.tradetri.com` |

---

## 6. The fix — action items for Jayesh

### Step 1 — Set the env var in Vercel

Vercel dashboard → `tradetri` project → Settings → Environment Variables.

Add (or update if present with a different value):

| Key | Value | Environment scopes |
|---|---|---|
| `NEXT_PUBLIC_API_URL` | `https://api.tradetri.com` | **Production** (and optionally Preview, see below) |

**Critical**: this is a `NEXT_PUBLIC_*` var, so it's baked into the client bundle at build time, not read at runtime. Setting it in Vercel ALONE is not sufficient — you also need to:

### Step 2 — Trigger a Vercel rebuild

After saving the env var, the next deploy will bake it in. Two ways:

- **Cleanest**: Vercel dashboard → Deployments → click the latest production deploy → "Redeploy" (the option to "Use existing Build Cache" should be UNCHECKED so the env var actually goes into the bundle).
- **Or**: push any new commit to `main` (will trigger Vercel automatically).

### Step 3 — Preview environment (optional but recommended)

For Preview deployments (PR builds), set the same var with value `https://api.tradetri.com` so PR previews talk to prod backend. Or use a staging backend URL if you have one — for now, prod backend is the only live target.

### Step 4 — Verify post-deploy

After the redeploy completes (~2-3 min):

1. Hard-refresh `tradetri.com/chart` (Cmd+Shift+R).
2. DevTools → Network → WS filter. Should see a connection to `wss://api.tradetri.com/ws/chart/NIFTY/5m?token=…` (NOT `tradetri.com`).
3. Status pill should transition `Connecting…` → `Live` (or stay on the new "Last close" pill from the A2 fix if market is closed when you test).
4. Console: no `WebSocket connection … failed` errors.
5. `/health` polling on dashboard `(dashboard)/page.tsx:108` should return 200 (no more 404).

If WS still fails post-deploy, the next investigation step is the token validation — that's a backend concern and outside this diagnosis scope.

---

## 7. Why this regressed (root cause hypothesis)

The env var `NEXT_PUBLIC_API_URL` was probably set in Vercel originally during initial deploy, then either:
- Removed during a Vercel project reconfiguration, OR
- Set with a value other than `https://api.tradetri.com` (e.g., relative `/` or empty string), OR
- Set for Preview/Dev scope but not Production, OR
- Vercel project was re-created at some point and the env vars weren't migrated.

The `next.config.ts:36-43` rewrite (`/api/:path* → https://api.tradetri.com/api/:path*`) was added as a partial workaround — it papered over the REST API broken-ness but didn't catch:
- WebSocket upgrades (Next rewrites don't proxy WS)
- The `/health` endpoint (not under `/api/`)

Setting `NEXT_PUBLIC_API_URL` makes the rewrite redundant for REST too (every call goes directly to api.tradetri.com), which is the cleaner architecture going forward.

---

## 8. Effort estimate

- **Time to fix**: 5 minutes in Vercel dashboard + 2-3 minutes for redeploy build + 30 seconds for browser verification. **Total ~10 minutes.**
- **Code changes**: zero.
- **Backend changes**: zero.
- **Nginx changes**: zero.
- **Risk**: very low. Only affects which URL the client bundle talks to. If wrong, easily reverted in Vercel.

---

## 9. What I checked / what I did NOT

### Checked (read-only)
- ✓ `frontend/src/lib/chart/api.ts:190-214` (WS URL builder)
- ✓ `frontend/src/lib/chart/chart_ws_transport.ts:95` (WebSocket factory)
- ✓ `frontend/src/lib/chart/types.ts:112` (WS envelope comments)
- ✓ `frontend/src/app/(dashboard)/page.tsx:108-110` (/health URL builder)
- ✓ `frontend/src/lib/api.ts:9` (REST base URL builder)
- ✓ `frontend/src/components/dashboard/paper-mode-banner.tsx:13` (paper-mode REST base)
- ✓ `frontend/src/hooks/useSystemMode.ts:13` (system-mode REST base)
- ✓ `frontend/.env.example` (dev defaults)
- ✓ `frontend/.env.local` (local dev overrides — only `NEXT_PUBLIC_USE_MOCK=true`)
- ✓ `frontend/next.config.ts` (rewrite config)
- ✓ Backend WS route at `app/api/chart.py:507` (via SSH grep inside container)
- ✓ Backend WS mount at `app/main.py:268` (via SSH grep)
- ✓ Localhost WS handshake probe on EC2 (FastAPI parser reached)
- ✓ Public WS handshake probe through nginx (`api.tradetri.com`) — WS reaches FastAPI cleanly
- ✓ Nginx config WS upgrade headers + read timeout

### Did NOT
- ✗ Did not modify any code
- ✗ Did not change Vercel env vars (per spec — Jayesh does this manually)
- ✗ Did not commit / push / deploy
- ✗ Did not create a new branch (Path A doesn't need one)
- ✗ Did not test browser end-to-end (can't access browser; Jayesh verifies post-deploy)

## 10. Hand-off

Jayesh, the entire fix is:

1. Vercel dashboard → set `NEXT_PUBLIC_API_URL=https://api.tradetri.com` (Production scope).
2. Redeploy without build cache.
3. Verify in browser per Step 4 above.

No code review needed. No PR. No backend deploy. ~10 minutes end-to-end.
