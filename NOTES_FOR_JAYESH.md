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
