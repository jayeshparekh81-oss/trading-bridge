# Chart WebSocket reconnect + layout-shift diagnosis

**Date:** 2026-05-17 (Sunday, market closed; T-1 from May-18 launch)
**Branch:** `diagnose/ws-reconnect`
**Scope:** Read-only investigation. No fixes shipped. Two fix paths proposed with effort + risk.

## Symptom recap (from Jayesh)

1. On `https://tradetri.com/chart` (any symbol), the "Reconnecting…" status badge appears every ~4 seconds.
2. On each reconnect, the X-axis shifts left and the visible viewport resets — the user's pan/zoom is lost.
3. Pre-existing — predates the BB stddev backend fix that just deployed (commit `78379c0` on `main`). The /chart route hasn't been touched in this sprint.

## TL;DR

Two separate bugs producing one combined UX failure:

- **Bug A (the loop):** Frontend WS client retries forever with no market-hours awareness. On weekends + after-hours, the backend WS likely closes the connection promptly (broker feed has no data to push) → exponential backoff bottoms out at the 1s → 2s → 4s phase → user sees "Reconnecting…" every few seconds in perpetuity.
- **Bug B (the shift):** Every successful WS reopen dispatches a full `{type: "init"}` to the candles reducer regardless of whether the symbol/timeframe actually changed. That replaces the candle array reference, which makes `CandlestickChart` call `series.setData(...)` instead of `series.update(...)`, which **resets Lightweight Charts' viewport** to default fit. User's pan/zoom is silently destroyed every ~4 seconds.

Both bugs ship today; both have small, surgical fixes.

---

## 1. Findings

### Frontend (Next.js, frontend/src/)

**WS endpoint construction** — `lib/chart/api.ts:201-214` builds:

```
wss://{NEXT_PUBLIC_API_URL or current origin}/ws/chart/{SYMBOL}/{TIMEFRAME}?token={JWT}
```

Token comes from `GET /api/chart/ws-token` (15-min JWT, refreshed every 12 min by `useWsToken.ts:47-106`). Token fetch confirmed working in prod (200 OK in backend logs).

**Reconnect logic** — `lib/chart/chart_ws_transport.ts:52-73`:

| Aspect | Value |
|---|---|
| Backoff | Exponential with ±25% jitter |
| Base delay | 1 s |
| Max delay | 60 s (plateau) |
| Sequence | 1, 2, 4, 8, 16, 32, 60, 60, 60… |
| Max retries | **Infinite** (no hard cap) |
| Exit conditions | `sessionExpired=true` (2 token failures), component unmount, close codes `{4400, 4401}` |
| Market-hours check | **NONE** — anywhere |
| Manual reconnect button | Yes (`StatusPill.tsx:51-107`); resets attempt counter |

The "~4 seconds" cadence the user observes is the attempt-3 / attempt-4 region of the backoff sequence (4s, 8s averaged). After a few minutes of failure the cadence would slow to 60s plateaus.

**Viewport reset path** — `components/chart/CandlestickChart.tsx:889-1014` (data-sync effect):

```
- First paint (prev === null)              → series.setData(...) + fitContent()  [resets viewport]
- Tail-only update (1 new candle appended) → series.update(...)                  [preserves viewport]
- Head changed (older bars prepended)      → series.setData(...) (no fitContent) [preserves viewport]
- Tail went backward / symbol or timeframe → series.setData(...) + fitContent()  [resets viewport]
```

On a WS reopen with the SAME symbol/timeframe, the reducer at `useChartWebSocket.ts:49-50` dispatches `{type: "init", candles: initialCandles}` unconditionally — that produces a NEW array reference even if the candle data is identical. `CandlestickChart`'s `sortedCandles` memo sees the ref change → the data-sync effect runs → hits the "first paint" branch (since live candles were prev=null on reconnect) → `setData()` + `fitContent()` → **viewport reset**.

No `timeScale().getVisibleRange()` / `setVisibleRange()` save-restore exists anywhere in the chart code path.

**Indicator recompute** — `CandlestickChart.tsx:1047-1231` recomputes every active indicator (SMA20, EMA50, RSI, MACD, BB) every time `sortedCandles` changes ref, so each reconnect also triggers 5 indicator recomputes. Cheap (N=200 bars, O(N·period)), but unnecessary churn. Not the visible bug.

### Backend (EC2 13.127.224.68, container `trading_bridge_backend`)

**Token endpoint**: `/api/chart/ws-token` returns 200 OK consistently for the affected user (multiple per minute in logs). No 401/403/5xx for this route.

**Chart WS endpoint** (`wss://api.tradetri.com/ws/chart/...`): NO connect / close / disconnect events found in 3000 lines of recent logs. Either:
- The WS endpoint's lifecycle isn't INFO-logged (most likely), or
- The handshake completes but the application-layer close happens before any log fires

**No BROKER_DISCONNECTED events** in the last 3000 lines of backend logs. The disconnect is NOT broker-triggered — it's either the chart WS endpoint itself closing the socket, or the frontend interpreting some payload as needing reconnect.

**Weekend signal in backend logs**: `event: dhan_historical.empty_window` for NIFTY 5m at `2026-05-17T08:24:19` — confirms broker returns no data for the live window on Sunday (correct broker behavior, but it means the chart WS has nothing to stream).

### Nginx (production, /etc/nginx/sites-enabled/)

```
proxy_pass http://localhost:8000;
proxy_http_version 1.1;
proxy_set_header Upgrade $http_upgrade;
proxy_set_header Connection 'upgrade';
proxy_cache_bypass $http_upgrade;
proxy_read_timeout 300s;
```

WS upgrade headers correctly configured. `proxy_read_timeout 300s` (5 min) — **way above** the ~4s observed cycle. **Nginx is NOT the cause.**

---

## 2. Root cause hypotheses (ranked)

### Hypothesis #1 (most likely, ~80% confidence) — Backend closes the chart WS quickly on weekends

Suspected behavior: the chart WS handler at the FastAPI layer (around `app/api/chart_ws.py` or wherever `/ws/chart/...` is registered) subscribes to a per-symbol broker feed on connect. On weekends:

- The broker feed has no ticks to push (NSE closed 09:15-15:30 IST, Mon-Fri only).
- The subscription may immediately fail or be closed by the broker WS upstream.
- The chart WS handler closes the client connection in response (close code TBD — wasn't visible in logs).

Frontend doesn't recognize this as a non-retriable close (close code isn't in `{4400, 4401}`), so it reconnects at 1s → 2s → 4s → 8s and never breaks the loop.

**Why this fits**: matches the cadence, matches the "pre-existing on weekends" framing, matches the absence of BROKER_DISCONNECTED log events (the broker isn't sending a graceful event — the backend's own handler is closing).

### Hypothesis #2 (~15% confidence) — Backend sends a sentinel envelope; frontend mis-handles it

Backend writes a single `{"event": "broker_disconnected"}` envelope on connect, then the connection stays open. Frontend's message handler dispatches a state transition that *manifests* as the disconnect badge (because the WS-status reducer flips on broker-disconnect events too). The WS isn't actually closing — it just looks closed from the user's POV.

**Why I don't lead with this**: would need to read the actual chart WS handler code (`backend/app/api/chart_ws.py` or sibling) to confirm. Beyond the scope I can verify without backend code access in this session.

### Hypothesis #3 (~5% confidence) — Token rejection cycle

JWT minted by `/api/chart/ws-token` could be rejected by the chart WS endpoint (e.g., audience/issuer mismatch in a recent deploy). Each connect: handshake passes nginx, backend rejects token → 4401 close → frontend SHOULD treat as non-retriable per `NO_RECONNECT_CODES`. But if the code is different (e.g., 1008 policy violation), frontend would retry.

**Why I don't lead with this**: token endpoint returns 200 consistently AND the same user's tokens work for other API endpoints (`/api/brokers/dhan/status`, `/api/chart/markers`, etc.). Token validity is fine; chart WS would be specifically broken.

---

## 3. Quick UX fix proposal (ship before May-18 launch)

Two-line-of-attack fix that addresses both symptoms without touching backend or nginx.

### Fix A1 — Preserve viewport across reconnects (~30 min)

**File:** `frontend/src/components/chart/CandlestickChart.tsx` data-sync effect (lines 889-1014).

**Change:** Before `series.setData(...)`, capture `timeScale().getVisibleRange()`. After the `setData` call, if the saved range is non-null, call `timeScale().setVisibleRange(saved)`. Guard with a "skip fitContent if viewport was preserved" flag.

**Result:** Even when the WS reopens and the candle array ref churns, the user's pan/zoom is restored within the same frame. The X-axis shift is invisible to the user.

**Risk:** Low. Lightweight Charts' `setVisibleRange` is well-documented and stable. Doesn't change ANY data path — only viewport state.

### Fix A2 — Skip the reconnect badge on weekends + after-hours (~45 min)

**File:** `frontend/src/components/chart/StatusPill.tsx` (or in the WS hook itself).

**Change:** Add an `isMarketOpen()` helper (NSE 09:15-15:30 IST Mon-Fri; allow ±15 min buffer for pre-open/post-close). When market is closed:

- Suppress the "Reconnecting…" badge entirely OR replace with a "Market closed — chart shows last close" static label.
- Optionally extend the reconnect base delay to 60s during off-hours (still retry occasionally, but not every 4s).

**Result:** Weekend / overnight users see a calm chart with a market-status indicator. No visible reconnect churn.

**Risk:** Low-medium. The IST timezone math is the only fragile part — needs a `Intl.DateTimeFormat` with `timeZone: "Asia/Kolkata"` to be DST-safe (India doesn't observe DST, but the code should still be explicit). Edge cases: NSE holidays (Republic Day, etc.) — could ship without holiday awareness for now; the badge would briefly appear and then settle.

### Combined ship plan

- 2 file edits, ~1.5 hours including a manual visual verification (open /chart in both themes, both timeframes, both weekday and Sunday).
- No backend deploy. No nginx change. No new dependencies.
- Visual diff is unambiguous: before = reconnect badge every 4s + X-axis dance; after = static chart with optional market-closed label, no shift.

---

## 4. Root cause fix proposal (post-launch)

The quick fix masks the symptom; the underlying loop still happens (just invisibly). Real fixes:

### Fix B1 — Backend: stop closing chart WS on weekends (~3-4 hours)

**Files (likely):** `backend/app/api/chart_ws.py` (or wherever the `/ws/chart/{symbol}/{timeframe}` route is registered) + the broker subscription wrapper.

**Change:** On connect, if market is closed, the WS handler should:

- Accept the connection and hold it open (don't close on absent broker feed).
- Send an initial `{"event": "market_closed"}` envelope (typed properly in `app/schemas/chart_event.py`).
- Keep the connection alive with periodic ping frames (every 30s, well under nginx 300s timeout).
- On market open, resume normal tick stream.

**Risk:** Medium. The chart WS handler probably has a "wait for ticks" pattern that needs careful refactoring to "hold open + heartbeat". Need to verify against existing tests + the live-market path.

### Fix B2 — Frontend: cap retries + escalate to manual-reconnect UI (~1 hour)

**File:** `frontend/src/lib/chart/chart_ws_transport.ts`.

**Change:** After N=10 consecutive failed reconnect attempts (~5 minutes of trying), stop the backoff loop. Surface a "Connection lost — click to retry" CTA via `StatusPill`. The manual-reconnect button already exists at attempt >= 7; just hard-stop at attempt 10.

**Risk:** Low. Self-contained transport-layer change. Existing manual-reconnect UI just needs a new entry point.

### Fix B3 — Frontend: don't dispatch `init` on every WS reopen (~30 min)

**File:** `frontend/src/hooks/useChartWebSocket.ts:49-50, 166-169`.

**Change:** Track which (symbol, timeframe) tuple was last seeded. Only dispatch `{type: "init"}` when that tuple changes. On a same-tuple reopen, dispatch `{type: "resumed"}` (new action type) that's a no-op for the candle array — just flips connection state.

**Risk:** Low. Localized to one hook; existing reducer covers the new action type via a default branch.

### Combined post-launch ship plan

B1 + B2 + B3 together remove the loop entirely. B3 alone (~30 min) ALSO fixes Bug B by itself — so even without B1/B2, the user's viewport survives. Worth doing B3 in the same PR as A1+A2 if there's bandwidth pre-launch.

---

## 5. Effort + risk matrix

| Fix | Effort | Risk | Customer impact | Ship pre-launch? |
|---|---:|---|---|---|
| **A1** preserve viewport on reconnect | ~30 min | **Low** | High (eliminates the layout-shift symptom) | ✅ recommended |
| **A2** market-hours badge gate | ~45 min | Low-medium | Medium (cosmetic, weekend-only) | ✅ recommended |
| **B3** don't dispatch init on same-tuple reopen | ~30 min | Low | Medium (root cause of layout shift) | ✅ if A1 wasn't enough |
| **B2** cap retries + manual-CTA escalation | ~1 hr | Low | Low (helps after long failures only) | optional |
| **B1** backend hold-open on weekends | ~3-4 hr | Medium | High (root cause of the loop) | ❌ post-launch (risk-of-regression too high pre-launch) |

## 6. Recommendation

**Pre-launch (today, T-1):** Ship A1 + A2 together. Tested via the local dev server in both themes + both market states (mock the clock to test "weekend"). Total: ~1.5 hrs including review. Visible UX win, zero deploy risk on the backend.

**Post-launch (week of May 19):** B3 first (cheap, localized) to make A1 redundant; then B1 (broader refactor) as a quality-of-life follow-up.

**Don't ship pre-launch:** B1 (backend WS rework). Risk-of-regression in the chart subsystem the night before launch outweighs the benefit. A1+A2 mask the symptom safely; B1 can wait a week.

---

## 7. Open questions for Jayesh

1. Want me to draft the A1+A2 PR on a new branch (`fix/chart-ws-reconnect-ux`) with the exact diffs ready for review?
2. Or keep this branch (`diagnose/ws-reconnect`) read-only for now and you'll decide which path after reading this doc?
3. Any concern about the BB-fix-deploy and this diagnosis happening on the same day? They're independent — chart WS code path is untouched by the BB fix — but I want to confirm you're comfortable with the timing.
4. For the market-closed UI (Fix A2), prefer: silent reconnect (no badge) OR explicit "Market closed" label OR "Last close: 09:30 IST" with the closing price displayed? Each has UX tradeoffs.

## 8. Files referenced (read-only this session)

```
frontend/src/lib/chart/api.ts                          (lines 177-214 — WS URL + token fetch)
frontend/src/lib/chart/chart_ws_transport.ts           (lines 52-73, 154-188, 314-424 — reconnect logic)
frontend/src/hooks/useChartWebSocket.ts                (lines 49-50, 102-210 — reducer + lifecycle)
frontend/src/hooks/useWsToken.ts                       (lines 47-106 — token refresh)
frontend/src/components/chart/CandlestickChart.tsx     (lines 889-1014 — data-sync effect; 1047-1231 — indicator recomputes)
frontend/src/components/chart/StatusPill.tsx           (lines 51-107 — manual reconnect surfacing)

EC2 production logs (via SSH):
  docker compose logs --tail 3000 backend
  /etc/nginx/sites-enabled/* (WS proxy config)
```

Zero edits, zero pushes, zero deploys.
