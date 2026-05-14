# PATCH INSTRUCTIONS — Phase A markers (manual review)

Branch: `feat/phase-a-markers`  •  Author: Claude (parallel-CC session)  •  Date: 2026-05-15

The Phase A trade-markers stack landed as **eight new files only** — no
existing file was edited, per the new-files-only rule for parallel-CC
branches. Two cross-cutting wire-ups remain. Both are one-liners that
Jayesh applies by hand before merging.

---

## 1. Register the router in `main.py`

The new HTTP router `app.api.trade_markers.router` is **not** mounted
yet. Add the import and the `include_router` call next to the other
`app.include_router(...)` lines.

**File:** `backend/app/main.py`

Add to the imports block:

```python
from app.api.trade_markers import router as trade_markers_router
```

Add next to the other `app.include_router(...)` calls:

```python
app.include_router(trade_markers_router)
```

The router has its own `prefix="/api/markers"` and `tags=["trade-markers"]`
baked in, so no `prefix=` / `tags=` arguments are needed at the
registration site. After this edit:

- `GET /api/markers?strategy_id=...&mode=...` becomes reachable.
- `GET /api/markers/strategy/{id}/summary?mode=...` becomes reachable.

The legacy `GET /api/chart/markers` route remains **unregistered** and
**unchanged**. Both stay separate during Phase B+ migration.

---

## 2. Add `TradeMarker` to the models registry

The model is fully functional today via direct import (the service,
API, and tests all import it explicitly). The package-level registry
in `app/db/models/__init__.py` is a *convenience* index used by
`migrations/env.py` for autogenerate workflows. Adding it here keeps
the registry coherent for any future `alembic revision --autogenerate`
runs.

**File:** `backend/app/db/models/__init__.py`

Add the import (alphabetical insertion, between `support_ticket` and
`trade`):

```python
from app.db.models.trade_marker import (
    MarkerExitReason,
    MarkerMode,
    MarkerSide,
    TradeMarker,
)
```

Add to `__all__` (alphabetical insertion):

```python
    "MarkerExitReason",
    "MarkerMode",
    "MarkerSide",
    "TradeMarker",
```

---

## 3. Run the migration on prod-equivalent Postgres

In the unit-test harness, the schema is exercised via
`Base.metadata.create_all` against in-memory aiosqlite — **not** via
`alembic upgrade head`. That existing CI pattern is unchanged.

For the production deploy, the migration is `025_add_trade_markers`
and chains cleanly off `024_indicator_approval_queue`:

```bash
cd backend && alembic upgrade head
```

Migration 025 is additive only (one new table, seven CHECK
constraints, six indexes, one PG-only partial unique index). The
PG-only `date_trunc` dedup index is dialect-gated inside the upgrade
function — it executes only when `op.get_bind().dialect.name ==
"postgresql"`, so a SQLite test run of the migration would skip it
without erroring.

Reversibility verified by structural tests in
`tests/test_trade_marker_model.py::TestMigration025`.

---

## 4. (Optional) Tighten Strategy → TradeMarker back-relationship

Currently `TradeMarker.strategy_id` carries a one-way FK to
`strategies.id`. The reverse relationship (`Strategy.trade_markers`)
is intentionally **NOT** declared on the `Strategy` model (would
require editing an existing file — out of scope for this branch).

If/when the read path migrates to consume from `trade_markers`
(Phase B+), add this to `app/db/models/strategy.py`:

```python
trade_markers: Mapped[list[TradeMarker]] = relationship(
    back_populates="strategy", cascade="all, delete-orphan"
)
```

…and the mirror on `TradeMarker`:

```python
strategy: Mapped[Strategy] = relationship(back_populates="trade_markers")
```

Skipping this for now keeps the diff to net-new files. Service-layer
queries explicitly join via `strategy_id` so the relationship
attribute is purely an ergonomic convenience.

---

## Summary of what Jayesh needs to type

```diff
# backend/app/main.py
+ from app.api.trade_markers import router as trade_markers_router
  ...
+ app.include_router(trade_markers_router)

# backend/app/db/models/__init__.py
+ from app.db.models.trade_marker import (
+     MarkerExitReason,
+     MarkerMode,
+     MarkerSide,
+     TradeMarker,
+ )
  ...
+     "MarkerExitReason",
+     "MarkerMode",
+     "MarkerSide",
+     "TradeMarker",

# Then, on the prod / staging DB host:
$ cd backend && alembic upgrade head
```

Three small edits, one shell command. Reversible. Zero impact on the
existing `chart_markers` route or `paper_trade` derivation path.
