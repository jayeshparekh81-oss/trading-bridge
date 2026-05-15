# PATCH INSTRUCTIONS — Phase B strategy tester (manual review)

Branch: `feat/phase-b-strategy-tester` • Author: Claude (parallel-CC session) • Date: 2026-05-15

The Phase B strategy-tester aggregation API landed as **seven new files
only** — no existing file was edited, per the new-files-only rule for
parallel-CC branches. One cross-cutting wire-up remains. Single one-liner
that Jayesh applies by hand before merging.

---

## 1. Register the router in `main.py`

The new HTTP router `app.api.strategy_tester.router` is **not** mounted
yet. Add the import and the `include_router` call next to the other
`app.include_router(...)` lines.

**File:** `backend/app/main.py`

Add to the imports block inside `_register_routers` (alphabetical
insertion — between `strategy_signals_router` and
`strategy_webhook_router` keeps the existing alphabetical ordering of
imports under `app.api.*`):

```python
from app.api.strategy_tester import router as strategy_tester_router
```

Add next to the other `app.include_router(...)` calls (group with the
chart / markers cluster at the bottom is fine — order within the group
is not load-bearing because the router carries its own
`prefix="/api/strategy-tester"` which doesn't collide with any other
mounted route):

```python
app.include_router(strategy_tester_router)
```

The router has its own `prefix="/api/strategy-tester"` and
`tags=["strategy-tester"]` baked in, so no `prefix=` / `tags=`
arguments are needed at the registration site. After this edit:

- `GET /api/strategy-tester/{strategy_id}/metrics` becomes reachable.
- `GET /api/strategy-tester/{strategy_id}/equity` becomes reachable.
- `GET /api/strategy-tester/{strategy_id}/trades` becomes reachable.

The Phase A `GET /api/markers` and the legacy `GET /api/chart/markers`
routes remain **unchanged**. All three coexist.

---

## 2. (No model registry change needed)

Phase B introduces no new ORM models. The reads use the existing
`TradeMarker` model registered in Phase A.

---

## 3. (No migration needed)

Phase B is read-only over the `trade_markers` table created by
Phase A migration `025_add_trade_markers`. Nothing to run.

---

## Summary of what Jayesh needs to type

```diff
# backend/app/main.py
+ from app.api.strategy_tester import router as strategy_tester_router
  ...
+ app.include_router(strategy_tester_router)
```

Two lines. Reversible. Zero impact on existing routes — strict prefix
isolation under `/api/strategy-tester`.

---

## Verification after the patch

```bash
# Boot the app locally and curl one of the endpoints (auth-gated, so
# expect 401 without a Bearer token — that's the success signal).
curl -s -o /dev/null -w "%{http_code}\n" \
  http://localhost:8000/api/strategy-tester/00000000-0000-0000-0000-000000000000/metrics?mode=PAPER
# Expected: 401
```

If you see `404`, the import or `include_router` call didn't land.
If you see `500`, the strategy-tester service module itself failed to
import — check the lifespan logs.
