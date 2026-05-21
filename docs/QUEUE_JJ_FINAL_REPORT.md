# Queue JJ — Final Report

**Mission:** Fix the 2 deploy blockers surfaced by Queue II audit before
tonight's 4 PM IST main merge.
**Date:** 2026-05-21
**Status:** ✅ Both blockers fixed in a single commit on `feat/milestone-1-ship`.

---

## New `feat/milestone-1-ship` HEAD

| Field | Value |
|---|---|
| Pre-fix HEAD | `3c701a0` (Queue FF) |
| **Post-fix HEAD** | **`5f37984`** |
| Local + origin in sync | ✅ pushed |
| Commits added | **1** (exactly per brief: "ONE commit only") |

```
5f37984 fix(deploy): rebase migration 028 onto 027 + add alembic step to runbook
3c701a0 docs(queue-ff): final report for Milestone 3 patch application + branch merge
f2ff70f merge: chart panel (Milestone 3) into Milestone 1 ship ...
```

## Files changed

```
backend/migrations/versions/028_add_backtest_runs.py | 11 +++++++++--
docs/MILESTONE_1_DEPLOY.md                           | 17 +++++++++++++++--
2 files changed, 24 insertions(+), 4 deletions(-)
```

## Blocker #1 — Alembic branched head: FIXED ✅

**Edit:** `backend/migrations/versions/028_add_backtest_runs.py`
- `down_revision: str | None = "026_add_strategy_templates"` → `"027_strategies_is_paper"`
- Updated the docstring `Revises:` header to match (avoid future-reader mismatch)
- Added an inline note explaining the rebase (Queue JJ provenance + why 027 ordering is safe)

### Local `alembic heads` verification — **REPRODUCED + VERIFIED**

Local environment HAD `alembic` available (3.14 system Python install).
To reproduce the branched-head condition that would occur post-merge, I
temporarily copied `027_strategies_is_paper.py` from `main` into the
local `versions/` directory (verification-only — removed before commit).

| Step | `alembic heads` output |
|---|---|
| Pre-fix (027 + unfixed 028 coexisting) | `027_strategies_is_paper (head)` + `028_add_backtest_runs (head)` — **2 heads, broken** |
| Post-fix (027 + rebased 028 coexisting) | `028_add_backtest_runs (head)` — **1 head, linear chain** |

The temp 027 was removed before commit; `git status` confirmed only the
intended `028_add_backtest_runs.py` modification was staged.

## Blocker #2 — Missing `alembic upgrade head` deploy step: FIXED ✅

**Edit:** `docs/MILESTONE_1_DEPLOY.md` Step 2

Inserted between `docker compose build ...` and `docker compose up -d
celery_worker ...`:

```bash
docker compose run --rm backend alembic upgrade head
# Expected output ends with:
#   "Running upgrade 027_strategies_is_paper -> 028_add_backtest_runs, ..."
# Verify the 3 new tables landed:
#   docker compose exec db psql -U $POSTGRES_USER -d $POSTGRES_DB -c "\dt backtest_*"
# Expected: backtest_runs, backtest_trades, backtest_metrics
# Rollback on failure: docker compose run --rm backend alembic downgrade 027_strategies_is_paper
```

## Bonus fix (same-file, transparently flagged)

The deploy doc still had **two `ssh ubuntu@43.205.195.227` lines** —
the stale IP we caught and corrected in Queue HH but which had not yet
been propagated to `MILESTONE_1_DEPLOY.md` (Queue HH only updated
`POST_DEPLOY_VERIFICATION.md`). Pasting from this doc tonight would
SSH to a dead target. Fixed in the same edit to `13.127.224.68`
(current Elastic IP, post-May-15 incident). Called out explicitly in
the commit message rather than slipped silently.

---

## Hard-stop confirmations

| Check | Result |
|---|---|
| Only 2 files in commit (migration + runbook) | ✅ verified by `git status` + diff stat |
| `feat/milestone-1-ship` has ONE new commit on top of `3c701a0` | ✅ commit `5f37984` is the only addition |
| No push/merge to main | ✅ pushed only to `feat/milestone-1-ship` and (this branch) `docs/queue-jj-report` |
| No live-trading code modified | ✅ no `live_orders/`, `order_router.py`, `webhook.py`, `executor.py`, `direct_exit.py`, broker connectors, `kill_switch_service.py` touched |
| Live BSE LTD strategy `89423ecc-c76e-432c-b107-0791508542f0` untouched | ✅ no code path touches it |
| Migration 028 upgrade()/downgrade() bodies unchanged | ✅ only the docstring + `down_revision` line touched; schema mechanics intact |
| `alembic heads` post-fix shows single head | ✅ verified locally with both migrations present |

## Items deliberately NOT addressed this queue (scope discipline)

Per brief §"soft items NOT addressed":

- 🟨 `BACKTEST_RATE_LIMIT_PER_HOUR=30` / `BACKTEST_RATE_LIMIT_CONCURRENT=5`
  in `.env.production` — Jayesh sets manually on EC2 before deploy
  (defaults work without; explicit is for visibility).
- 🟨 `pre-milestone-1-deploy` git tag on `origin/main` — Jayesh creates
  manually before merge (precise rollback marker).

## Tonight's deploy sequence — now safe

1. `git tag pre-milestone-1-deploy origin/main && git push --tags` (optional rollback marker)
2. `git checkout main && git pull && git merge --no-ff origin/feat/milestone-1-ship && git push`
3. SSH to EC2 at `13.127.224.68` per updated `MILESTONE_1_DEPLOY.md` Step 2
4. `docker compose build ...` → **`alembic upgrade head`** → `docker compose up -d ...`
5. `POST_DEPLOY_VERIFICATION.md` §C smoke tests
6. `POST_DEPLOY_VERIFICATION.md` §D live BSE LTD health check (within 30 min)

Both blockers neutralised. Path to 4 PM IST deploy is clear.
