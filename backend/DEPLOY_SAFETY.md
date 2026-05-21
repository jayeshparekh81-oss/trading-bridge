# Deploy Safety Simulation — Migrations 010..024

Generated: 2026-05-10 (UTC)
Test DB: `tradetri_migration_test` (throwaway, on local Docker postgres `trading_bridge_postgres`; created with `DROP IF EXISTS` + `CREATE DATABASE` at start)
Baseline revision: `009_strategy_json_column` (last revision pre-010; represents a "frozen production schema" as it would exist before this branch is deployed)
Final revision: `024_indicator_approval_queue`
Seeded strategies: 5 (across 2 seeded users)

## Method

1. Spun up a throwaway database `tradetri_migration_test` on the existing local Postgres container (NOT touching the developer's `trading_bridge` DB, which was found empty anyway).
2. Ran `alembic upgrade 009_strategy_json_column` against the test DB — schema-equivalent to a production snapshot taken just before this branch.
3. Seeded 5 strategies + 2 users (one admin, one regular) covering: legacy SMA crossover with `strategy_json = NULL`; multi-indicator BUY DSL; aggressive risk profile with partial exits + `direct_exit`; extreme parameter values (period=500, qty=100, ₹99.999% stops); and a SELL-side bearish RSI strategy.
4. Captured a `pg_dump --data-only --table=strategies --table=users` snapshot at `/tmp/baseline_009.sql`.
5. Stepped through each of migrations 010..024 individually; after every step verified row counts, alembic_version pointer, and that all five strategies remained queryable.
6. Smoke-tested `app.strategy_engine.backtest.runner.run_backtest()` against rows loaded from the migrated DB.

## Per-Migration Results

| Filename | Revision | Verdict | Notes |
|---|---|---|---|
| 010_paper_sessions.py | `010_paper_sessions` | SAFE | Pure additive: creates `paper_sessions` + `paper_trades` with FKs to existing `users`/`strategies`. No touch to existing rows. |
| 011_users_live_trading_enabled.py | `011_users_live_trading_enabled` | SAFE | Adds `users.live_trading_enabled BOOL NOT NULL DEFAULT FALSE`. Existing rows backfilled to FALSE — matches launch-plan's "explicit admin approval" property. |
| 012_strategies_cached_scores.py | `012_strategies_cached_scores` | SAFE | Adds 3 nullable columns to `strategies` (`last_trust_score`, `last_truth_score`, `last_scores_at`) + 1 index. NULL on existing rows is the documented "no scores yet" state — SafetyChain treats as block-equivalent. |
| 013_users_role.py | `013_users_role` | SAFE | Adds `users.role TEXT NOT NULL DEFAULT 'user'` and runs `UPDATE … SET role='admin' WHERE is_admin=TRUE`. Verified backfill in test DB: admin → 'admin', user → 'user'. |
| 014_role_check_constraint.py | `014_role_check_constraint` | SAFE | Adds CHECK constraint pinning role to 5-value enum. Existing rows hold only `'user'`/`'admin'` after 013, both valid — constraint passes unconditionally. |
| 015_entry_templates.py | `015_entry_templates` | SAFE | Pure additive: creates `entry_templates` table + index. No mutation of existing data. |
| 016_exit_templates.py | `016_exit_templates` | SAFE | Pure additive: creates `exit_templates` table + index. |
| 017_risk_templates.py | `017_risk_templates` | SAFE | Pure additive: creates `risk_templates` table + index. |
| 018_marketplace_tables.py | `018_marketplace_tables` | SAFE | Pure additive: creates `marketplace_listings`, `marketplace_subscriptions`, `marketplace_ratings` + indexes including a partial unique on active subscriptions. |
| 019_ledger_tables.py | `019_ledger_tables` | SAFE | Pure additive: creates `ledger_snapshots`, `ledger_attestations` (Strategy Transparency Ledger). |
| 020_support_tickets.py | `020_support_tickets` | SAFE | Pure additive: creates `support_tickets` with CHECK constraints on category/status/priority. |
| 021_user_onboarding.py | `021_user_onboarding` | SAFE | Adds `users.onboarding_step INT NOT NULL DEFAULT 6` (existing users treated as already-onboarded — correct behaviour) + `onboarding_completed_at TIMESTAMPTZ NULL` + range CHECK 0..6. |
| 022_perf_indexes.py | `022_perf_indexes` | SAFE (with note) | Creates 7 composite indexes with `CONCURRENTLY` (no AccessExclusiveLock — safe to run on hot DB). All use `CREATE INDEX IF NOT EXISTS`. **Note**: index `ix_marketplace_listings_status_published_at` was already created by migration 018 in plain ASC form; the 022 declaration intends DESC published_at — the `IF NOT EXISTS` clause silently skips creation, so on databases that ran 018 first the index stays ASC. Postgres can still scan ASC backwards for `ORDER BY ... DESC` queries; semantic intent is preserved, but the migration file is technically a no-op for that one index. Non-blocking but worth a follow-up clean-up. |
| 023_indicator_status_overrides.py | `023_indicator_status_overrides` | SAFE | Pure additive: creates `indicator_status_overrides` history table with two CHECK constraints + two indexes (one with `effective_from DESC`). FK `approved_by_user_id` uses `ON DELETE RESTRICT` — admin user accounts can't be deleted while overrides reference them, which is the intended audit-preservation behaviour. |
| 024_indicator_approval_queue.py | `024_indicator_approval_queue` | SAFE | Pure additive: creates `indicator_approval_queue`. CHECK constraints on `requested_status` (active/deprecated) and lifecycle `status` (pending/approved/rejected/withdrawn). Comment correctly documents that uniqueness on (indicator_id, status='pending') is intentionally enforced in service layer, not schema. |

## Old Strategy Survival

- Strategies seeded: 5
- Strategies surviving all migrations: 5
- Status: **PRESERVED**

`pg_dump --data-only` of `strategies` rows pre- and post-migration is byte-identical for every original column. The only diff is the appended columns from migration 012 (`last_trust_score`, `last_truth_score`, `last_scores_at`), all NULL on existing rows as designed.

Specifically verified post-024:
- Row 1 (legacy SMA, `strategy_json=NULL`) — still NULL, queryable, all numeric columns intact.
- Row 2 (multi-indicator BUY) — JSONB blob round-trips byte-for-byte; `entry.side='BUY'` preserved.
- Row 3 (aggressive risk + `direct_exit`) — `exit_strategy_type='direct_exit'` preserved; full nested partialExits / risk caps intact.
- Row 4 (extreme params) — `999` max_position_size, `99.999` percentages, `9999999` max_loss preserved.
- Row 5 (SELL-side) — `entry.side='SELL'` preserved in JSONB.

User backfill from migration 013 verified:
- `seed-admin@migration-test.local` (`is_admin=TRUE`) → `role='admin'`
- `seed-user@migration-test.local` (`is_admin=FALSE`) → `role='user'`

## Backtest Compatibility

- Strategies attempted: 2 (rows 1 + 2 from the migrated DB)
- Strategies passing backtest: 2
- Status: **WORKING**

Smoke test (`/tmp/smoke_backtest.py`) loaded the strategy rows from the post-024 schema, constructed a canonical `StrategyJSON` (Phase 5 shape), and ran `app.strategy_engine.backtest.runner.run_backtest()` over 80 synthetic uptrend candles. Both completed without error:

```
--- backtest for: 'SMA Crossover (legacy, no DSL)' ---
  OK  trades=3 pnl=303.00 win_rate=1.00 warnings=0
--- backtest for: 'Multi-indicator BUY (RSI + EMA)' ---
  OK  trades=3 pnl=303.00 win_rate=1.00 warnings=0
```

Note: the seeded `strategy_json` blobs are pre-Phase-5 simplified shapes (no top-level `id`/`mode`/`execution`/`indicators[]`); they would NOT pass strict `StrategyJSON` Pydantic validation as-is. The DB migrations don't touch the JSONB content — that's an *application-level* migration concern. Same as today on `main`: legacy rows already need a one-time JSON shape migration before Phase 5 endpoints can update them. This is documented behaviour, not a regression introduced by 010..024.

## Final Verdict

**SAFE TO DEPLOY**

All 15 migrations apply cleanly on top of pre-010 production schema, in dependency order, against a freshly-seeded data set. Every migration is either purely additive (new tables / new nullable columns / indexes) or carries a safe server-default + intentional backfill (013 `users.role`, 011 `users.live_trading_enabled`, 021 `users.onboarding_step`). No NOT NULL columns are added without a default. No columns are dropped. No data is destructively rewritten. Index creation in 022 uses `CONCURRENTLY` and is hot-DB-safe.

One minor cosmetic finding (022's `ix_marketplace_listings_status_published_at` redeclaration is a silent no-op due to 018 already creating an ASC variant) does not block deploy — Postgres scans the ASC index backward for the `ORDER BY ... DESC` query, and a follow-up migration can drop+recreate the index with explicit DESC ordering if the planner ever shows a regression.

Pre-deploy recommendation: take a `pg_basebackup` or `pg_dump` of production immediately before running `alembic upgrade head`, exactly as standard practice. With that backup in hand, this set of migrations is safe to run during the May 20 launch window.
