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
