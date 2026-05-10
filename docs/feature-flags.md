# Feature Flags

> Status: Production-ready
> Introduced: Commit `179ca0c` (core module, 36 tests)
> Per-user `live_trading_enabled` (Migration 011): Commit `2b9124b`
> Last updated: 2026-05-09

## Overview

The feature-flags module is TRADETRI's load-bearing kill-switch
substrate for product-shape changes. Every guarded feature
(live trading, marketplace, broker safety net, AI Advisor /
Doctor / Coach surfaces, indicator backtesting, etc.) reads its
on/off state from this module. Flags resolve via a 3-tier
priority that lets ops flip a flag without a deploy:

```
1. Environment variable (TRADETRI_FF_<FLAG_NAME>) — re-read every call.
2. In-process runtime override (set_flag()).
3. Hardcoded default in registry.
```

Mutating a `CRITICAL_FLAG` (the broker safety net, the
live-trading gate, etc.) emits an audit event so disabling them
always leaves a paper trail. The audit dependency is
**one-way** — `audit` doesn't import `feature_flags`, so flag
state never feeds back into audit emission.

## Why It Exists

Two concerns sit at opposite ends of the deploy spectrum:

- **Crisis flips need to be instant.** A bug in the broker
  guard requires turning that gate off in seconds, not a
  rollback-to-stable. Env-var resolution lets ops flip a flag
  by changing one container variable + bouncing the pod.
- **Product-shape changes need to be testable.** The marketplace
  was hidden for months before launch by `MARKETPLACE_ENABLED`.
  In-process overrides let tests pin behaviour without
  monkey-patching `os.environ` mid-test.

The 3-tier resolution puts the env var first because crisis
beats convenience.

## 13 Locked Flags

The full list lives in `feature_flags/registry.py`. Headline
ones:

| Flag | Default | Critical | Notes |
|---|---|---|---|
| `LIVE_TRADING_ENABLED` | `False` | yes | Global gate above per-user. |
| `MARKETPLACE_ENABLED` | `False` | yes | Hides marketplace UI + endpoints. |
| `INDICATORS_BACKTEST_ENABLED` | `True` | no | Whole-engine kill switch. |
| `AI_ADVISOR_ENABLED` | `True` | no | Hides Advisor advice list. |
| `AI_DOCTOR_ENABLED` | `True` | no | Hides Doctor + Apply Fix. |
| `STRATEGY_COACH_ENABLED` | `True` | no | Hides Coach panel. |
| `MARKET_REGIME_ENABLED` | `True` | no | Hides Regime Panel. |
| `DEVIATION_MONITOR_ENABLED` | `True` | no | Hides Deviation Panel. |
| `BROKER_SAFETY_NET_ENABLED` | `True` | yes | Bypassing this is a critical action. |

The set of `CRITICAL_FLAGS` is locked by
`tests/strategy_engine/feature_flags/test_feature_flags.py::TestCriticalFlagAudit`
so accidentally adding/removing a flag from the critical set
trips a regression.

## Public API

```python
from app.strategy_engine.feature_flags import (
    is_enabled,
    set_flag,
    list_flags,
)

# Read.
if is_enabled("MARKETPLACE_ENABLED"):
    # render marketplace UI
    ...

# Runtime override (typically in tests / admin tooling).
set_flag("MARKETPLACE_ENABLED", True)

# Audit dump for the admin dashboard.
all_flags: list[FlagState] = list_flags()
```

Source: `backend/app/strategy_engine/feature_flags/manager.py`.

## Per-User vs Global Flags

Most flags are global — one boolean covers every user. One flag
needs per-user precision:

- **`live_trading_enabled`** is BOTH:
  1. A global flag in the feature-flags module
     (`LIVE_TRADING_ENABLED`).
  2. A per-user column on `users.live_trading_enabled` (Migration
     011, commit `2b9124b`).

The combinator function
`is_live_trading_enabled_for_user(user)` returns `True` only
when:

```
global LIVE_TRADING_ENABLED is True
AND user.live_trading_enabled is True
```

This is **defence in depth**. The global flag gates the whole
platform — flipping it off pauses live trading for everyone.
The per-user flag gates each user individually — admin tooling
can re-enable a single user without touching the global state.
Both must be `True` for live trading to proceed; either one
being `False` blocks.

The combinator lives in
`app.strategy_engine.live_orders.user_flags`, NOT in the core
`feature_flags` package — that's deliberate. See [AST purity](#ast-purity-rule)
below.

## AST Purity Rule

The core `feature_flags` package imports nothing from
`app.db`, `app.api`, or any DB-aware module. AST-inspected by
`test_feature_flags.py::test_no_db_imports_in_core`.

Why: feature-flag resolution is on every request hot path. If
`is_enabled()` could trigger a lazy DB import (or worse, a DB
query), a database glitch could brown out flag resolution for
the entire app — including critical flags like
`BROKER_SAFETY_NET_ENABLED` whose whole purpose is to stay up
when other things break.

The per-user flag combinator that DOES need a `User` row
(`live_orders/user_flags.py`) sits at a separate boundary
where DB access is already expected.

## Audit Trail for Critical Flags

When `set_flag()` mutates a flag in `CRITICAL_FLAGS`, the
manager emits an audit event:

```python
emit_event(
    actor_id=actor_id,
    event_type="feature_flag.mutated",
    severity="critical",
    payload={
        "flag": flag_name,
        "old_value": old,
        "new_value": new,
        "source": "env" | "runtime" | "default",
    },
)
```

The audit row is append-only — the audit-logs table (see
[`/docs/audit-logs.md`](./audit-logs.md)) is the source of
truth for "who turned the broker safety net off and when".

## Configuration

Every flag is settable via env var with the prefix
`TRADETRI_FF_`. Examples:

```bash
TRADETRI_FF_LIVE_TRADING_ENABLED=true
TRADETRI_FF_MARKETPLACE_ENABLED=true
TRADETRI_FF_BROKER_SAFETY_NET_ENABLED=false  # ← critical, audited
```

Truthy values (case-insensitive): `"true"`, `"1"`, `"yes"`,
`"on"`. Falsy values: `"false"`, `"0"`, `"no"`, `"off"`. Any
other value falls through to the runtime override / default.

Env vars are re-read on every `is_enabled` call (intentional —
ops needs hot reloads). Runtime overrides win over the default
but lose to env vars.

## Edge Cases & Limitations

- **Re-reading env vars on every call has overhead.** Profiling
  on Phase 11 shipped acceptable performance for the typical
  hot-path flag count. If a far-future change pushes the call
  count up by 10x, a per-process cache with a watcher would be
  the optimisation.
- **No per-user override of non-`live_trading` flags.** The
  framework supports per-user overrides as a pattern but only
  `live_trading_enabled` actually uses one today.
- **No A/B / percentage rollout.** A flag is on or off, never
  "on for 10% of users". A future phase will add a hash-based
  rollout primitive.
- **No flag history beyond audit log.** Can't ask "what was
  `MARKETPLACE_ENABLED` at midnight last Friday?" without
  walking the audit log. Acceptable today.

## Testing

- `tests/strategy_engine/feature_flags/test_feature_flags.py` —
  36 tests covering the 3-tier priority, env-var truthy/falsy
  parsing, runtime override correctness, audit emission for
  critical flags, the locked `CRITICAL_FLAGS` set, and the
  AST purity rule.
- `tests/strategy_engine/live_orders/test_user_flags.py` —
  the `is_live_trading_enabled_for_user` combinator's truth
  table.

## Future Work

- **Percentage-based rollouts.** A hash-of-user-id primitive
  that returns deterministic on/off per user lets us ship a
  feature to 5% → 50% → 100% over time.
- **Flag-config UI.** The admin dashboard surfaces the audit
  log of flag mutations; a UI to flip flags directly (with the
  audit emission preserved) would replace today's
  env-var-and-redeploy loop.
- **Time-bound flags.** "Enable this for 24 hours then auto-
  revert" — useful for emergency response. The runtime override
  layer is the natural place.

## References

- Module source: `backend/app/strategy_engine/feature_flags/`
- Per-user combinator: `backend/app/strategy_engine/live_orders/user_flags.py`
- Migration 011 (per-user column): `backend/migrations/versions/011_users_live_trading_enabled.py`
- Tests: `backend/tests/strategy_engine/feature_flags/`
- Sister doc: [`/docs/audit-logs.md`](./audit-logs.md)
- Sister doc: [`/docs/auto-kill-switch-integration.md`](./auto-kill-switch-integration.md)
- Sister doc: [`/docs/broker-execution-guard.md`](./broker-execution-guard.md)
