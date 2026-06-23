# NOTES FOR JAYESH — marketplace fan-out build

**Branch:** `feat/marketplace-fanout` (off `main` @ 730ce91). Pushed to origin. **NOT merged to main, NOT deployed.**
(Note: this file did not exist on `main`; the showcase NOTES live on the `feat/showcase-angelone-prep` branch. This is a fresh NOTES for the marketplace track.)

---

# Marketplace Module 0 — safety scaffold (ZERO live touch)

**Goal:** lay the foundation for subscriber fan-out WITHOUT touching the live path. After M0 **nothing executes differently** — it is purely a dormant flag + an empty, uncalled module. The owner 1→1 execution path is byte-identical.

## What was added (additive only — 3 files)
1. **Dormant feature flag** — `backend/app/core/config.py`
   - Added `marketplace_fanout_enabled: bool = Field(default=False)` (env `MARKETPLACE_FANOUT_ENABLED`), placed right after `paywall_enforced` and mirroring its style. **No existing config value was changed.**
   - Default **False** ⇒ platform stays owner-only 1→1. When later modules flip it True, the subscriber path runs **additively, alongside** the owner execution (never instead of it).
2. **Dormant stub module** — `backend/app/services/marketplace_fanout.py` (NEW)
   - `fanout_enabled() -> bool` — pure read of the flag.
   - `resolve_active_subscriptions(strategy_id) -> []` — STUB, always returns empty list. Docstring describes the future read-only query (active, non-expired `MarketplaceSubscription` rows for a strategy's listing).
   - `dispatch_subscriber_executions(signal, strategy) -> None` — STUB, no-op. Docstring describes the future additive per-subscriber dispatch (each subscriber's own `broker_credential_id` + per-subscriber qty, subscriber-scoped idempotency, per-subscriber partial-failure isolation).
   - Implements **nothing live**: zero DB access, zero broker calls, zero Celery dispatch, zero mutation. ORM types are imported **only under `TYPE_CHECKING`**, so the module is fully decoupled from the live path and importing it has no side effects.
3. **Tests** — `backend/tests/services/test_marketplace_fanout.py` (NEW), 6 tests, all green:
   - (a) flag field exists + `default is False`; runtime value False; `fanout_enabled()` False.
   - (b) **zero call sites**: each of `strategy_webhook.py`, `strategy_executor.py`, `signal_execution.py`, `direct_exit.py` is asserted to contain NO reference to `marketplace_fanout`; and a repo-wide scan asserts nothing under `app/` imports the module.
   - (c) stubs import cleanly + are no-ops (`resolve_… == []`, `dispatch_… is None`).

## Owner path untouched — confirmation
- **Tracked diff on this branch = `backend/app/core/config.py` ONLY** (one additive field). The two new files are net-new untracked additions.
- **No sacred file modified**: `strategy_webhook.py`, `strategy_executor.py`, `signal_execution.py`, `direct_exit.py`, kill_switch, broker adapters, `db/models/strategy.py`, and all migrations are byte-identical to `main`.
- **Zero call sites** in the live path — enforced by code AND by test (b), so a future accidental wiring would fail CI.
- **No DB migration** in this module. **No deploy, no EC2/prod touch, no merge to main.**

## Verify (Module 0)
- `cd backend && .venv/bin/python -m pytest tests/services/test_marketplace_fanout.py -q` → **6 passed**.
- `cd backend && .venv/bin/python -m pytest tests/test_config.py -q` → **9 passed** (additive flag broke nothing).
- `git diff --name-only main..feat/marketplace-fanout` → `backend/app/core/config.py` + the 2 new files only; no sacred files.

## What was deliberately NOT done
- Did NOT wire the module into the webhook/executor (that is a later module, behind the flag).
- Did NOT add a migration, change any model, or touch the live 1→1 path.
- No deploy, no merge to main.

---

# Marketplace Module 1 — subscriber lookup in webhook (flag-gated, LOG-ONLY)

**Goal:** when a signal arrives, resolve the strategy's ACTIVE subscribers and ONLY log them — no execution, no dispatch, no orders. Proves the lookup works while the owner 1→1 path stays byte-identical.

## What changed (2 live files + tests)
1. **`backend/app/services/marketplace_fanout.py`** — implemented `resolve_active_subscriptions(strategy_id, db)` as a real **READ-ONLY** query:
   - `SELECT` joining `marketplace_subscriptions` → `marketplace_listings` on `listing_id`, filtered by `listing.strategy_id == strategy_id` AND `subscription.status == 'active'`.
   - Returns a list of frozen `SubscriberRef` dataclasses carrying **only fields that exist today** (`subscription_id`, `subscriber_id`, `listing_id`, `status`, `subscribed_at`, `access_until`) — deliberately NOT broker_credential_id / qty (those columns don't exist yet).
   - Pure SELECT: no INSERT/UPDATE/DELETE, no flush, no commit, no session mutation.
   - `dispatch_subscriber_executions(...)` **stays a no-op stub** — no dispatch is implemented in this module.
2. **`backend/app/api/strategy_webhook.py`** — added ONE import and the additive hook **after** the owner dispatch + the owner `signal_received` log, **before** the existing success return (see the additive block below). The owner dispatch (ENTRY/PARTIAL/EXIT/SL_HIT) and the returned response are **untouched**.

### The additive block (verbatim)
```python
    # 15. Marketplace fan-out — ADDITIVE, flag-gated, LOG-ONLY (Module 1).
    if get_settings().marketplace_fanout_enabled:
        try:
            subscribers = await resolve_active_subscriptions(strategy_id, session)
            logger.info("fanout.dry_run.resolved", signal_id=..., strategy_id=...,
                        action=..., subscriber_count=len(subscribers))
            for sub in subscribers:
                logger.info("fanout.dry_run.subscriber", signal_id=..., strategy_id=...,
                            subscription_id=str(sub.subscription_id),
                            subscriber_id=str(sub.subscriber_id),
                            note="would route signal to subscriber (LOG-ONLY — no dispatch)")
        except Exception as exc:  # noqa: BLE001
            logger.warning("fanout.dry_run.failed", ..., error=str(exc))
    return { "status": "accepted", ... }   # unchanged owner response
```

## Owner path byte-identical when flag OFF — confirmation
- The whole block lives behind `if get_settings().marketplace_fanout_enabled:`. With the flag **False** (prod default), the block is skipped entirely; the **only** added cost is one short-circuiting bool read. The owner dispatch and the returned dict are byte-identical.
- The block is also wrapped in try/except so that, even with the flag ON, a subscriber-lookup failure can never affect the owner response (which has already dispatched above).
- **LOG-ONLY:** the block calls `resolve_active_subscriptions` (read-only SELECT) and `logger.info` per subscriber. **No** `dispatch_signal`, **no** broker calls, **no** order placement, **no** position writes, **no** mutation.
- **No sacred file touched:** `strategy_executor.py`, `direct_exit.py`, `kill_switch`, broker adapters, `db/models/strategy.py`, and migrations are all byte-identical. Only `strategy_webhook.py` (the one sanctioned call site) + `marketplace_fanout.py` changed. No migration.

## Tests (all green)
- `backend/tests/services/test_marketplace_fanout.py` (updated for M1): flag exists+defaults False; **call-site discipline** — the sacred execution files (`strategy_executor`/`signal_execution`/`direct_exit`) never reference the module, and the webhook is asserted to be the **only** importer under `app/`; dispatch stub still a no-op. (The M0 "zero call sites" guard was intentionally narrowed: the webhook is now the single allowed call site; the executor/worker/exit path stays sacred — and a test enforces exactly that.)
- `backend/tests/integration/test_marketplace_fanout_webhook.py` (new, against real sqlite + live webhook):
  - **(a) flag OFF** → `resolve_active_subscriptions` never called, owner `dispatch_signal` fires exactly once.
  - **(b) flag ON + 2 active + 1 cancelled seeded** → resolve returns the 2 active, handler logs `fanout.dry_run.resolved` (count=2) + one `fanout.dry_run.subscriber` per active sub; owner dispatch still exactly once (fan-out adds none); **zero** positions written.
  - **(c) read-only** → resolve returns active-only (cancelled excluded), subscription row count unchanged, nothing pending on the session.

## Verify (Module 1)
- `cd backend && .venv/bin/python -m pytest tests/services/test_marketplace_fanout.py tests/integration/test_marketplace_fanout_webhook.py tests/integration/test_strategy_webhook_async.py -q` → **21 passed** (incl. the full owner-path webhook regression suite).
- `cd backend && .venv/bin/python -m pytest tests/test_direct_exit_webhook.py tests/test_webhook_paper_mode_gate.py tests/integration/test_strategy_webhook_kill_switch.py tests/integration/test_exit_skip_reresolve.py tests/test_config.py -q` → **44 passed**.

## Deliberately NOT done
- No dispatch / no execution / no broker / no position writes — log-only, as scoped.
- No change to the owner dispatch or response; no migration; no flag flip in prod (default stays False).
- No deploy, no merge to main.

---

# Marketplace Module 2 — per-subscriber PAPER dispatch (flag-gated)

**Goal:** turn M1's log-only fan-out into actual per-subscriber dispatch — **PAPER ONLY**. Each active subscriber gets a *simulated* execution of the signal. No real broker order for any subscriber, under any config.

## What changed (2 live files + tests)
1. **`backend/app/services/marketplace_fanout.py`** — implemented `dispatch_subscriber_executions(signal, strategy, subscribers, db)` (was an M0 no-op stub):
   - For each active subscriber it runs **one simulated fill** by calling the OWNER's exact paper primitive — `app.services.strategy_executor._simulate_fill` (the same code the owner paper path runs at executor line ~193), reused via a lazy import. Returns one `PaperExecutionResult` per subscriber (new frozen dataclass), tagged `paper=True` + `subscription_id` + `subscriber_id`; logs `fanout.paper.executed` per subscriber + a `fanout.paper.summary`.
   - Default qty = `strategy.entry_lots or 1` (paper lot_size 1) — a sensible default; **per-subscriber qty is M4**.
   - Switched the module logger from stdlib to the codebase's structlog `get_logger` so per-subscriber structured logs work.
2. **`backend/app/api/strategy_webhook.py`** — the flag-gated block (after the untouched owner dispatch) now resolves subscribers (M1) → `await dispatch_subscriber_executions(...)`, replacing the M1 log loop. Still wrapped in try/except (a fan-out failure can't touch the owner response). Import + that block are the only changes; the owner dispatch and the returned response are byte-identical.

## PAPER-ONLY — how it's guaranteed
- The subscriber path's ONLY execution primitive is `_simulate_fill`, which is **pure** (builds a `PAPER-{uuid}` fill dict; no broker SDK, no network). It does **not** read or honour `strategy.is_paper` / `settings.strategy_paper_mode` for subscribers — subscribers are forced to paper regardless. A test sets BOTH flags live and asserts the result is still paper and `place_strategy_orders` (the live entry) is never called.

## Owner byte-identical — and WHY no subscriber positions are written
- When the flag is **False** (prod default) the whole block is skipped (one bool read). When True, the owner still dispatches first and unchanged.
- ⚠️ **Important design call:** M2 deliberately writes **NO** `StrategyPosition` / `StrategyExecution` rows for subscribers. Positions are keyed by `(strategy, symbol, side)` **ignoring `user_id`** (`_find_existing_open_position`), and `strategy_positions.broker_credential_id` is **NOT NULL**. So a subscriber paper position would *sum into the OWNER's live position* — inflating the owner's `remaining_quantity` and causing a real-money over-exit later. Correct per-subscriber positions need a per-subscriber scoping column (+ real creds + per-subscriber qty) — that's **Module 4** (which needs a migration, forbidden here). M2 therefore stays at the simulate-and-record layer: it proves the fan-out actually runs a paper execution per subscriber with **zero** risk to the owner. **No sacred file was modified** — `strategy_executor.py` (incl. `_simulate_fill`) is imported and reused, never edited; `direct_exit`/`kill_switch`/broker adapters/`strategy.py` model/migrations untouched.

## Per-subscriber isolation
- Each subscriber's simulation is wrapped in its own try/except: a failure is logged + recorded as `status="failed"` and the loop continues. One subscriber failing never stops the others or the owner (test (d) proves: `[filled, failed, filled]`, no exception escapes).

## Tests (all green)
- `tests/services/test_marketplace_fanout.py` (unit, no DB): N subscribers → N paper results each `paper=True` + `PAPER-` order id (b); paper even with live flags set + zero `place_strategy_orders` calls (c); one failing subscriber isolated, others proceed (d). Plus the M1 flag/call-site discipline tests.
- `tests/integration/test_marketplace_fanout_webhook.py` (real webhook): (a) flag OFF → `dispatch_subscriber_executions` never called, owner dispatches once; (b) flag ON + 2 active/1 cancelled → `_simulate_fill` called exactly 2× (cancelled excluded), owner dispatches once, **zero** live-entry calls, **zero** positions written; (c) resolve read-only/active-only.

## Verify (Module 2)
- `cd backend && .venv/bin/python -m pytest tests/services/test_marketplace_fanout.py tests/integration/test_marketplace_fanout_webhook.py tests/integration/test_strategy_webhook_async.py -q` → **23 passed**.
- Broad owner-path regression (executor paper-flag / qty / lifecycle / direct-exit / paper-gate / kill-switch / config + webhook suite): **89 passed**.
- `ruff check` clean on the new/changed module + test files. `strategy_webhook.py` has 6 **pre-existing** ruff findings (HEAD=6, after my change=6 — I introduced none and did not drive-by-fix them).

## Deliberately NOT done
- No real broker call / real order / live flag honoured for subscribers — paper only.
- No `StrategyPosition`/`StrategyExecution` writes for subscribers (see the design call above) — durable per-subscriber positions + real creds + per-subscriber qty are M4 (migration).
- No sacred file modified; no migration; no flag flip in prod (default stays False); no deploy, no merge to main.

---

# Marketplace Module 3 — subscription_id scoping (FIRST migration; additive/nullable)

**Goal:** add the scoping dimension that M2 was missing, so subscriber PAPER positions are ISOLATED from the owner's LIVE position, then persist them safely. **Migration created + validated locally only; NOT applied to prod.**

## 1. Migration (additive + nullable) — `migrations/versions/034_subscription_position_scoping.py`
Single new head off `033_strategy_state_audit`. Generated DDL (offline `alembic --sql`, both directions):
```sql
-- upgrade
ALTER TABLE strategy_positions  ADD COLUMN subscription_id UUID;          -- nullable
CREATE INDEX ix_strategy_positions_subscription_id  ON strategy_positions (subscription_id);
ALTER TABLE strategy_positions  ADD CONSTRAINT fk_strategy_positions_subscription_id  FOREIGN KEY(subscription_id) REFERENCES marketplace_subscriptions (id) ON DELETE CASCADE;
ALTER TABLE strategy_executions ADD COLUMN subscription_id UUID;          -- nullable
CREATE INDEX ix_strategy_executions_subscription_id ON strategy_executions (subscription_id);
ALTER TABLE strategy_executions ADD CONSTRAINT fk_strategy_executions_subscription_id FOREIGN KEY(subscription_id) REFERENCES marketplace_subscriptions (id) ON DELETE CASCADE;
-- downgrade drops both FKs, indexes, and columns.
```
- **Additive/nullable ONLY**: no existing column changed, no NOT-NULL, no data backfill. Every existing (owner) row keeps `subscription_id = NULL`. `ON DELETE CASCADE` so a subscriber row can never decay to NULL (which would bleed it into the owner's scope).
- ⚠️ **No local Postgres was running**, so per the repo's established pattern (its migration tests say "alembic upgrade runs against real Postgres in deployment, not the harness") I validated via: offline `--sql` (above), a structural migration test (`tests/db/test_subscription_scoping_migration.py` — nullable, chains off 033, additive+reversible source), and the integration tests which run against `create_all` with the new columns. **Migration NOT applied to prod.**

## 2. Owner-vs-subscriber position isolation (5 query files, each an additive `subscription_id IS NULL` filter)
The owner's open-position lookups key by `(strategy, symbol, side)` ignoring `user_id`, so each had to scope to NULL or a subscriber paper row would corrupt the owner:
| File | Lookup | Change |
|---|---|---|
| `strategy_executor.py` | `_find_existing_open_position` (owner entry-sum) | added optional `subscription_id` param (default None → `IS NULL`); owner caller unchanged → byte-identical. Subscriber path reuses it with its own id. |
| `direct_exit.py` | `get_open_position` (owner exit) | + `subscription_id IS NULL` |
| `position_lookup.py` | `find_open_position_by_strategy` (webhook exit-pin) | + `subscription_id IS NULL` |
| `position_manager.py` | loop poll | + `subscription_id IS NULL` — **so the loop NEVER manages a subscriber paper row** (which would otherwise fire a REAL exit on a LIVE strategy) |
| `reconciliation_loop.py` | drift poll | + `subscription_id IS NULL` — a subscriber paper row on a LIVE strategy would otherwise show as false `db_only` drift + CRITICAL alert |

Each is **behavior-preserving**: all existing owner rows are `subscription_id = NULL`, so every owner query matches *exactly* the rows it matched before the column existed. The 5 query diffs total **39 insertions / 2 deletions**. No live-order/broker code, no `kill_switch`, no `strategy.py` model touched.

## 3. Persist subscriber PAPER positions/executions — `dispatch_subscriber_executions`
For ENTRY signals, per subscriber (in its own **SAVEPOINT** for isolation) it now writes a `StrategyPosition` + `StrategyExecution` tagged with `subscription_id`, reusing the executor primitives (`_simulate_fill`, `_compute_levels`, `_resolve_side`, the now-scoped `_find_existing_open_position`). Subscriber re-entries sum **only within their own scope**. `broker_credential_id` reuses the owner strategy's as a paper placeholder (no broker is ever built/called). Non-entry (exit) actions are log-only — subscriber exit routing is M4.

## Proven (tests)
- **Owner byte-identical:** with an owner row AND a subscriber row on the same `(strategy, NIFTY, buy)`, `_find_existing_open_position` (owner) and `get_open_position` both return the OWNER row (NULL scope), never the subscriber; the scoped lookup returns the subscriber row.
- **3-way isolation, no bleed:** owner(10) + 2 subscribers, dispatched twice → 3 isolated rows; owner stays at 10; each subscriber sums to 2 within its own scope.
- **PAPER ONLY:** zero `place_strategy_orders`/broker calls even with the strategy flipped LIVE (`is_paper=False`); all subscriber fills are `PAPER-…`.
- **Persist + webhook:** flag on → one isolated paper position+execution per active subscriber (cancelled excluded), owner dispatches once, no live calls.

## Verify (Module 3)
- `cd backend && .venv/bin/python -m pytest tests/services/test_marketplace_fanout.py tests/db/test_subscription_scoping_migration.py tests/integration/test_marketplace_fanout_webhook.py tests/integration/test_strategy_webhook_async.py -q` → **27 passed**.
- **Owner regression across all 5 touched query files: 225 passed.** The 16 local failures (test_live_order_flow / reconciliation drift / product_type) are **PRE-EXISTING** — I ran the SAME suspect tests on the pre-M3 baseline (git stash) and got the identical 16 failures (they need Postgres locally). So M3 introduced **zero** new failures.
- `ruff` clean on new/changed files. The 5 sacred query files: HEAD vs now error counts are equal (14=14, 6=6, 0=0, 0=0, 2=2) — I introduced no new lint debt and did not drive-by-fix theirs.

## Deliberately NOT done
- Migration NOT applied to prod (validated locally/offline only); no flag flip (default stays False).
- Subscriber EXIT-signal routing + real per-subscriber creds/qty = Module 4. `kill_switch` left untouched (owner kill switch is naturally isolated by `user_id`; a subscriber's own kill switch never fires in M3 — noted for M4).
- No deploy, no merge to main.
