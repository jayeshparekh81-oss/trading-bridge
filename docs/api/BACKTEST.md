# Backtest — API reference

Two endpoint families:

1. **Synchronous, per-strategy** (Phase D Strategy Tester, live):
   `POST /api/strategies/{id}/backtest`
2. **Asynchronous, persisted** (Day 1-5, dormant — router NOT
   registered in `main.py` yet): `POST /api/backtest` family

---

## Synchronous (live)

### `POST /api/strategies/{strategy_id}/backtest`

Source: `backend/app/strategy_engine/api/backtest.py`

**Summary:** Run a deterministic backtest + reliability + truth +
coach pipeline synchronously.

**Auth:** Required.

**Request body:** `BacktestRunRequest` (every field optional; `{}` is valid)

**Responses:**
- `200` — Full result envelope: `BacktestResult` + reliability +
  walk-forward + truth + regime + deviation + coach card +
  trade-quality report + version manifest
- `404` — Unknown id / not owned
- `422` — Strategy has no `strategy_json` (legacy or cloned row)

Sync execution takes ~5-15 seconds. The Phase D Strategy Tester UI
accepts this latency; future Day-4+ async path replaces it for new
flows.

---

## Asynchronous (dormant — Day 1-5 implementation)

These 3 endpoints exist on `feat/backtest-engine-day-5` branch but
the router is NOT registered in `main.py`. Founder mounts manually
after review. Tests exercise the full path end-to-end.

### `POST /api/backtest`

Source: `backend/app/backtest_extension/api.py`

**Summary:** Enqueue an async backtest with idempotency cache lookup.

**Auth:** Required. **Rate-limited** (Day 5): 30/hour + 5 concurrent
per user. `BACKTEST_RATE_LIMIT_PER_HOUR` and
`BACKTEST_RATE_LIMIT_CONCURRENT` env vars override.

**Request body:** `BacktestEnqueueRequest`
```json
{
  "strategy_id": "...",
  "symbol": "NIFTY",
  "timeframe": "5m",
  "start": "2026-03-17T03:45:00+00:00",
  "end": "2026-05-17T10:00:00+00:00",
  "initial_capital": 100000.0,
  "quantity": 1.0,
  "cost_settings": { ... },
  "ambiguity_mode": "conservative"
}
```

`strategy_config` (anonymous-config preview) is REJECTED with 422
until Phase 7 ships the Strategy Builder preview flow.

**Responses:**
- `202` — New run enqueued; response includes `run_id` + `cached=false`
- `200` — Cache hit on `(user_id, request_hash) WHERE status='SUCCEEDED'`;
  same `run_id` + `cached=true`
- `422` — Validation error (missing strategy_id, malformed payload)
- `429` — Rate limit exceeded. Carries `Retry-After` header
  (3600s for hourly cap, 60s for concurrent cap)

### `GET /api/backtest/{run_id}`

**Summary:** Owner-scoped fetch of a backtest_runs row + metrics.

**Auth:** Required.

**Responses:**
- `200` — `BacktestRunOut` with run metadata + (when status=SUCCEEDED)
  metrics block
- `404` — Unknown / not owned (anti-enumeration)

### `GET /api/backtest/{run_id}/trades`

**Summary:** Paginated trades for a SUCCEEDED run.

**Auth:** Required.

**Query params:**
- `cursor` (optional) — last seen `trade_index` from prior page
- `page_size` (1 ≤ N ≤ 1000, default 200)

**Responses:**
- `200` — `BacktestTradesResponse` with `trades[]` + `has_more` + `next_cursor`
- `404` — Unknown / not owned
- `409` — Run status != SUCCEEDED (trades not materialised yet)

---

## See also

- `docs/EXISTING_BACKTEST_ENGINE_AUDIT.md` — engine internals
- `docs/BACKTEST_ENGINE_EXTENSION_PLAN.md` — Days 1-7 plan
- `docs/BACKTEST_DAY_4_INTEGRATION.md` — engine ↔ extension contract
- Migration 028 (apply-ready, NOT applied):
  `backend/migrations/versions/028_add_backtest_runs.py`
