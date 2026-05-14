# Chart frontend — manual smoke-test scenarios

These five scenarios compensate for the Day-5 `useChartWebSocket`
unit-test coverage gap (9%) until Day-4 closes it via `msw/ws`.

**When to run:** before every merge of `feat/frontend-chart` →
`feat/charting-module`, and before every production deploy of the
chart module. Execute all five at least once. Document the result
(✅ pass / ❌ fail + repro notes) in the PR description or release
checklist.

**Environment setup for each scenario:**
- Logged-in user with an active Dhan link.
- Browser DevTools open with Network tab + Console + WS frames
  panel visible (Chrome: Network → WS filter; Firefox: Network →
  Messages tab on the WebSocket entry).
- `NEXT_PUBLIC_USE_MOCK` should be **unset** for scenarios A–D
  (live backend) and set to `true` only for scenario E (mock
  toggle).

---

## Scenario A — Token refresh + WS reconnect

**Goal:** Verify the 12-min token-refresh flow and the resulting
WS reconnect.

**Steps:**
1. Open `/chart` in a logged-in browser. Confirm initial render
   (200 candles visible, status indicator says connected).
2. In DevTools → Network tab, filter for `ws-token`. Note the
   timestamp of the first `GET /api/chart/ws-token` request.
3. Keep the tab focused. Watch for ≥ 15 minutes.
4. At ~12 min from the first token call, a SECOND
   `GET /api/chart/ws-token` should appear in Network.
5. Within ~1 second of the second token call, the existing
   WebSocket entry should show "Closed" and a NEW WebSocket
   entry should open.
6. The new WS URL's `?token=` query parameter should differ from
   the original (different JWT value).
7. After reconnect, live ticks should resume without page reload.

**Pass criteria:**
- ✅ Exactly one `ws-token` call at ~12 min.
- ✅ Exactly one WS close + reopen sequence.
- ✅ Live ticks resume.
- ✅ No errors in Console.

**Common failure modes:**
- Token refresh skipped (interval cleared by accidental hot-reload).
- New WS opens but old one stays alive → leak (R2 hygiene bug).
- Console error about JWT parsing → backend `aud="ws"` work
  scheduled for Day-4 has landed prematurely.

---

## Scenario B — Backend restart mid-session, exp backoff reconnect

**Goal:** Verify the client mirrors the backend's
1s/2s/4s/8s/16s/32s ±25% jitter reconnect schedule.

**Steps:**
1. Open `/chart` and confirm live ticks are flowing.
2. SSH to the EC2 host (or whatever runs the backend in your env)
   and stop the backend service: `sudo systemctl stop tradetri-backend`
   (or equivalent — see backend deploy docs).
3. In DevTools Console, you should see a WS close event almost
   immediately (within 1s).
4. Watch the Console output for reconnect attempts. Each attempt
   should log something like `dhan_ws.disconnected attempt=1 …`
   on the backend AND a corresponding `WebSocket` open attempt on
   the frontend (the open won't succeed yet).
5. Restart the backend: `sudo systemctl start tradetri-backend`.
6. The next frontend reconnect attempt should succeed.

**Pass criteria:**
- ✅ Frontend logs reconnect attempts at intervals roughly matching
  the exponential schedule (1s, then ~2s, then ~4s, etc.). Exact
  timings vary by ±25% jitter.
- ✅ After backend comes back, live ticks resume within one
  backoff interval (≤ 60s).
- ✅ Chart history candles never disappear during the outage —
  only live updates pause.

**Common failure modes:**
- Reconnect fires at fixed 1s interval (jitter or backoff broken).
- Reconnect stops after 6 attempts (cap math wrong).
- Chart goes blank on disconnect (full setData fires erroneously).

---

## Scenario C — Rapid symbol / timeframe switching, no WS leaks

**Goal:** Verify React 19 Strict-Mode WS hygiene (R2) holds under
rapid input.

**Steps:**
1. Open `/chart`. In DevTools → Network → WS filter, note the
   current WebSocket entry count is **1**.
2. Within 30 seconds, click 10 different (symbol, timeframe)
   combinations as fast as you can — e.g.:
   - NIFTY 5m → NIFTY 15m → BANKNIFTY 15m → BANKNIFTY 5m →
     RELIANCE 1m → RELIANCE 5m → NIFTY 1h → NIFTY 1d →
     BANKNIFTY 1h → NIFTY 5m.
3. After the last click, wait 3 seconds for state to settle.
4. Count the active (state = "open" or "connecting") WS
   connections in DevTools.

**Pass criteria:**
- ✅ Exactly **1** active WS connection at the end. Earlier WS
  entries should all show "Closed".
- ✅ The single active WS URL matches the LAST clicked
  (symbol, timeframe) — i.e. `wss://…/ws/chart/NIFTY/5m?token=…`.
- ✅ No console warnings about "found multiple WebSocket
  instances" or similar.

**Common failure modes:**
- Stacking active connections (R2 hygiene bug) — each click
  spawns a new WS without closing the previous one. Memory leak
  in production.
- Chart freezes after rapid switches (WS handlers attached to
  closed sockets).

---

## Scenario D — Stale-tab survival

**Goal:** Verify the chart survives 10+ minutes in a background
tab without breaking the WS or the candle stream.

**Steps:**
1. Open `/chart` in a tab. Confirm live ticks.
2. Switch to a different tab (Gmail, Twitter, whatever) and
   leave the chart tab in the background for at least 10 minutes.
3. Refocus the chart tab.
4. Within 5 seconds of refocus, observe whether new ticks resume.

**Pass criteria:**
- ✅ Live ticks resume within 5 seconds of refocus.
- ✅ The WS connection is the SAME instance that was open before
  the background period (no automatic close+reopen on focus).
- ✅ No "WebSocket frozen" warnings in console (Chrome's
  background-tab freezing can throttle but should not kill the
  WS — backend's 20s heartbeat keeps it warm).

**Common failure modes:**
- WS killed by browser during background, no auto-reconnect on
  refocus (the 12-min token-refresh interval may have fired
  while backgrounded — verify that token refresh AND WS reconnect
  both happened correctly).
- Chart shows stale data — last live tick was from 10 min ago,
  no catch-up fetch on refocus.

**Phase 2 enhancement (not required for Day 5):** when the tab
refocuses after a long background period, re-fetch
`/api/chart/history` for the gap. Day-5 ships without this; the
WS will eventually catch up but recent missed candles may not
appear until the next bucket close.

---

## Scenario E — BROKER_DISCONNECTED handling (mock toggle)

**Goal:** Verify the disconnect overlay UI renders correctly
without waiting for a real 5-minute backend outage.

**Steps:**
1. Set `NEXT_PUBLIC_USE_MOCK=true` in `frontend/.env.local`.
   Restart `npm run dev`.
2. Open `/chart`. Confirm mock ticks are flowing (~5s cadence).
3. Open the browser Console and run:
   ```js
   // Access the global mock-WS server handle for the chart.
   // (The mock instance is module-local; expose via a window
   // hook for manual testing — see useChartWebSocket source
   // for the dev-only window stash if added.)
   ```
   For Day-5, the manual trigger requires patching
   `useChartWebSocket.ts` temporarily to expose
   `mockServerRef.current` on `window`. The Day-4
   `msw/ws`-based tests will replace this with a clean
   dev-tools hook.
4. Call `window.__chartMockServer.emitDisconnected("manual test")`.
5. Verify the chart shows the broker-disconnected overlay
   ("Broker connection toot gaya…") above the candle canvas.
   History candles should still be visible underneath.
6. Call `window.__chartMockServer.emitReconnected()`.
7. Verify the overlay disappears and the status returns to
   "open". Subsequent mock ticks should append normally.

**Pass criteria:**
- ✅ Overlay appears within ~50ms of `emitDisconnected`.
- ✅ Overlay copy reads "Broker connection toot gaya…" (Hinglish
  per the brief's communication-style rule).
- ✅ History candles remain rendered behind the overlay.
- ✅ `emitReconnected` clears the overlay cleanly.

**Common failure modes:**
- Overlay renders but covers the entire chart (z-index or layout
  bug).
- Overlay never disappears after `emitReconnected` (event handler
  for reconnect not wired through reducer).
- Chart canvas blanks during disconnect (CandlestickChart
  unmounts instead of staying mounted).

**Note for Day 4:** the `window.__chartMockServer` exposure is a
manual-debug-only hack. Day-4 ws-mock-based tests cover this
flow programmatically. After Day 4 lands, this scenario can be
demoted from manual-smoke to a CI-enforced test.

---

## Sign-off

| Scenario | Date | Tester | Result | Notes / repro |
|---|---|---|---|---|
| A — Token refresh + WS reconnect | | | | |
| B — Backend restart + exp backoff | | | | |
| C — Rapid switching, no WS leaks | | | | |
| D — Stale-tab survival | | | | |
| E — BROKER_DISCONNECTED overlay | | | | |

Fill in this table for every release. Attach to the PR description.
