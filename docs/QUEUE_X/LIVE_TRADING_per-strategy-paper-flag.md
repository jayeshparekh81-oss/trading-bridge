# Queue X — Phase D1: feat/per-strategy-paper-flag (LIVE-TRADING AUDIT, READ-ONLY)

**Status:** ✅ SAFE_AFTER_MIGRATION_AUDIT — migration explicitly preserves BSE LTD live strategy
**Branch:** 1 ahead / 91 behind main, single squash-able commit `dfdfde6`
**Audit scope:** Read-only inspection. No code touched.

## Why this branch exists
Per the migration's docstring (verbatim from the branch):

> Incident 2026-05-18: the global `STRATEGY_PAPER_MODE` was flipped True on 2026-05-16 to make the May 18 multi-strategy launch paper-only, and silently converted the founder's already-running BSE LTD live strategy into paper mode. The flag was too coarse — there was no way to keep one strategy LIVE while everything else stayed paper.

The branch fixes this by adding a per-strategy `is_paper` override with a strict resolver.

## Files touched (vs merge-base `db57a856`)
| File | Lines | Type |
|------|-------|------|
| `backend/migrations/versions/027_strategies_is_paper.py` | +89 | NEW migration |
| `backend/app/db/models/strategy.py` | +15 / -0 | Model: add `is_paper: Mapped[bool]` |
| `backend/app/services/paper_mode_resolver.py` | +50 | NEW resolver module (single source of truth) |
| `backend/app/services/strategy_executor.py` | +9 / -4 | 1 import + 1-line read replaced |
| `backend/app/api/strategy_webhook.py` | +28 / -16 | Strategy resolution reordered + 1-line read replaced |
| `backend/app/services/direct_exit.py` | +7 / -5 | 2 one-line reads replaced |
| `backend/tests/test_per_strategy_paper_flag.py` | +291 | NEW tests |
| **Total** | +490 / -24 | |

## BSE LTD live strategy (89423ecc-c76e-432c-b107-0791508542f0) preservation — VERIFIED
The migration's `upgrade()` runs three statements:

1. `ALTER TABLE strategies ADD COLUMN is_paper BOOLEAN NOT NULL SERVER_DEFAULT TRUE` — every existing row → paper=TRUE by default.
2. Explicit safety-belt: `UPDATE strategies SET is_paper = TRUE WHERE id != :live_id` (re-asserts default for cross-backend correctness).
3. **`UPDATE strategies SET is_paper = FALSE WHERE id = :live_id`** with `live_id = "89423ecc-c76e-432c-b107-0791508542f0"`.

The live strategy is flipped FALSE by ID inside the migration itself — atomic with the column add. Verified at branch commit `dfdfde6` in lines:
- `_FOUNDER_LIVE_STRATEGY_ID` constant on line 41 of the migration matches the live BSE LTD strategy ID.
- The `WHERE id = :live_id` UPDATE runs on every alembic upgrade, idempotent.

## Migration chain — clean
- Branch's `down_revision = "026_add_strategy_templates"`.
- Main currently has `026_add_strategy_templates.py` at head (verified — `backend/migrations/versions/` directory walks from 007 → 026 with no gaps).
- 027 will apply cleanly on top with no chain reorganization needed.
- **Migration path is `backend/migrations/versions/`**, NOT `backend/alembic/versions/` — per repo convention.

## Resolver semantics (paper_mode_resolver.py)
```python
def resolve_paper_mode(strategy: Strategy | None) -> bool:
    if strategy is not None:
        flag = getattr(strategy, "is_paper", None)
        if flag is not None:
            return bool(flag)
    return bool(get_settings().strategy_paper_mode)
```
- Per-strategy flag wins when set.
- Defensive: `None` strategy (lookup miss) → global. Safest because a missing strategy never accidentally routes a live order.
- Defensive: Python-None attribute → global. Covers in-memory Strategy instances built outside the ORM.
- DB column is NOT NULL with `server_default TRUE`, so production rows always carry a real boolean.

## Call-site changes (3 sites in execution path)
| Site | Old | New |
|------|-----|-----|
| `strategy_executor.place_strategy_orders` | `paper_mode = settings.strategy_paper_mode` | `paper_mode = resolve_paper_mode(strategy)` |
| `direct_exit.execute_partial` | same | same |
| `direct_exit.execute_exit` | same | same |
| `strategy_webhook.receive_strategy_signal` | time-of-day guard read global | guard reads per-strategy resolver |

The webhook change also moves strategy resolution earlier in the handler (before the time-of-day guard) so the guard can consult the per-strategy flag — this is a control-flow reorder, not a semantics change. The guard still raises `403 FORBIDDEN` outside market hours when the resolved flag is FALSE.

## Risk assessment
- **No order-router changes.** `order_router.py`, `live_orders/*`, `brokers/registry.py`, and broker SDK calls are untouched.
- **No kill-switch changes.** Audit ran `grep '*kill_switch*'` — zero matches in the diff.
- **No broker credential changes.** `broker_credential.py` model untouched.
- **No schema CHANGE to existing columns.** Only ADD COLUMN with safe default + targeted UPDATE.
- **Backfill ID is hard-coded** in the migration. Correct for prod, no-op on dev DBs where the row doesn't exist — fail-safe.

## Deploy sequence (recommended for tomorrow evening)
1. **Pre-flight (5 min)**
   - Verify prod alembic head is at 026: `alembic current` on EC2.
   - Verify BSE LTD strategy exists and currently has `is_paper = (column missing)` (i.e. pre-migration row).
   - Snapshot the strategies table: `pg_dump -t strategies > /tmp/strategies_pre_027.sql`.
2. **Code deploy (5 min)**
   - Merge branch to main on GitHub (no rebase required; main is ahead but no file collisions per Phase B/C audits).
   - SSH to EC2, `git pull`, restart application IS NOT NEEDED YET — code paths route through resolver only after migration exposes the column.
3. **Migration (1 min)**
   - `alembic upgrade head` — applies 027.
   - Immediately verify: `SELECT id, name, is_paper FROM strategies WHERE id = '89423ecc-c76e-432c-b107-0791508542f0';` → must return `is_paper = false`.
   - Sample 1-2 other rows to confirm `is_paper = true`.
4. **Application restart**
   - Restart FastAPI workers so the new `Strategy.is_paper` Mapped attribute is loaded.
   - Tail logs for `time_of_day_check_bypassed_paper_mode` — confirm `strategy_id` is now present in the log line (proves new code path is live).
5. **Rollback plan**
   - `alembic downgrade -1` drops the column. Resolver falls back to `settings.strategy_paper_mode` per the None-branch — safe rollback semantics.
   - Restore from `/tmp/strategies_pre_027.sql` only if the targeted UPDATE somehow mis-ran (extremely unlikely given hard-coded ID).

## Hard rule
**Do NOT deploy this branch before 4 PM IST on a trading day.** Even though the BSE LTD strategy preservation is correct, the application restart in step 4 will briefly drop any in-flight webhook signals. Off-hours deploy only.

## Tomorrow command summary
```bash
# Open PR — main is 91 commits ahead, but per file-by-file scan, none touch the 7 files this branch modifies. Merge should be clean.
gh pr create --base main --head feat/per-strategy-paper-flag \
  --title "feat(strategy): per-strategy is_paper flag with resolver (migration 027)" \
  --body "$(cat docs/QUEUE_X/LIVE_TRADING_per-strategy-paper-flag.md)"
```

After merge:
- Run deploy sequence above.
- Delete the branch: `git push origin --delete feat/per-strategy-paper-flag`.
