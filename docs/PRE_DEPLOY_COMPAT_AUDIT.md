# Pre-Deploy Compatibility Audit — Milestone 1 + 3 vs main

**Branch under audit:** `feat/milestone-1-ship` @ `3c701a0`
**Baseline:** `origin/main` @ `3f8dd65` (current; freshly pulled this session)
**Merge base:** `b90e3567` (where `feat/milestone-1-ship` diverged from main)
**Date:** 2026-05-21
**Auditor:** Queue II

---

## Executive summary

🟥 **TWO DEPLOY BLOCKERS** found. Tonight's deploy as planned will fail at the
`alembic upgrade head` step on EC2 unless these are fixed first.

| # | Severity | Issue | Required fix | ETA |
|---|---|---|---|---:|
| 1 | 🟥 BLOCKER | Alembic **branched head** — `027_strategies_is_paper` (main, 2026-05-18) and `028_add_backtest_runs` (milestone-1-ship, 2026-05-17) **both revise from `026_add_strategy_templates`**. After merge, `alembic upgrade head` errors `Multiple head revisions present`. | Edit `backend/migrations/versions/028_add_backtest_runs.py` line `down_revision = "026_add_strategy_templates"` → `down_revision = "027_strategies_is_paper"`. One-line change. | 5 min |
| 2 | 🟥 BLOCKER | `028_add_backtest_runs.py` **MUST run on EC2** before backend reboots — creates 3 new tables (`backtest_runs`, `backtest_trades`, `backtest_metrics`) the new `/api/backtest/*` routes write to. Without it, every call to those routes will 500 with `relation "backtest_runs" does not exist`. | Add `docker compose exec backend alembic upgrade head` to the deploy sequence BEFORE `docker compose up -d backend`. Brief said "no migration needed" — that was wrong; the *trade_markers* part needs none, the *backtest_runs* part needs this. | 1 min in runbook |

🟨 **Two soft items** worth setting:
- `BACKTEST_RATE_LIMIT_PER_HOUR` (default 30) and `BACKTEST_RATE_LIMIT_CONCURRENT` (default 5) — milestone-1-ship reads these via `os.environ.get` with defaults, so deploy succeeds either way. Recommend setting them explicitly in `.env.production` for visibility.

🟩 **What's NOT a problem:**
- Zero file-level merge conflicts (`comm -12` of changed-file lists = empty)
- No docker-compose or Dockerfile changes
- No frontend `.env.example` / `next.config.ts` changes
- No new Vercel env vars required

---

## §1 — Branch divergence (essential context)

```
git log main..feat/milestone-1-ship --oneline  → 19 commits ahead
git log feat/milestone-1-ship..main --oneline  → 167 commits ahead
git merge-base main feat/milestone-1-ship      → b90e3567
```

milestone-1-ship branched from main on `b90e3567` (early May). Since then,
**main has accumulated 167 commits** (including the Dhan rejection-catching
hotfix, NRML product-type guard, position creation guard, kill-switch
per-strategy fix, telegram rejection-aware alerts, reconciliation per-
strategy fix, plus 70+ indicator content commits and UI work).

**Implication:** the merge `main ← feat/milestone-1-ship` does NOT just
add Milestone 1 + 3 on top of main; the merge commit combines milestone-1-ship's
state AT MERGE-BASE with main's 167 commits. Per git-merge semantics, every
file changed in only main is taken from main; every file changed in only
milestone-1-ship is taken from milestone-1-ship; files changed in both
trigger merge conflicts.

In this case: **file-overlap = 0**, so no manual conflict resolution
needed. But the migration directory is special-cased — see §4.

---

## §2 — Env var audit (Phase 1)

### New env vars referenced by milestone-1-ship code

```python
# backend/app/backtest_extension/rate_limit.py
PER_HOUR_LIMIT:    int = _env_int("BACKTEST_RATE_LIMIT_PER_HOUR",   30)
CONCURRENT_LIMIT:  int = _env_int("BACKTEST_RATE_LIMIT_CONCURRENT",  5)
```

Both have `_env_int(..., default)` fallbacks, so deploy succeeds without
them set. Defaults match what Queue FF's final report assumed.

### Pre-existing env vars relied on (no change required)

- `REDIS_URL` — Celery broker (already on EC2; main relies on it too).
- `DHAN_ACCESS_TOKEN` / `DHAN_CLIENT_ID` — already on EC2 for the live
  BSE LTD strategy. Backtest extension does NOT consume these directly
  (it reads via `app.brokers.dhan` which already handles auth).
- `DATABASE_URL` — already on EC2.

### Action items
- 🟨 Set `BACKTEST_RATE_LIMIT_PER_HOUR=30` and `BACKTEST_RATE_LIMIT_CONCURRENT=5` in `.env.production` for explicit-ness. Not required, but Queue FF flagged the rate-limit cap as a possible UX issue once the parallel async-enqueue from the chart panel lands; an explicit env var makes a future bump a no-deploy change.

---

## §3 — Docker compose / Dockerfile diff (Phase 2)

```
git diff main..feat/milestone-1-ship -- docker-compose.yml docker-compose.prod.yml backend/Dockerfile frontend/Dockerfile
```

**Output: empty.** Zero changes to docker config across both branches'
slices. Tonight's deploy uses the existing compose definition; no new
services / ports / volumes / build-args.

---

## §4 — Migration audit (Phase 4) — THE deploy blocker

### Migrations on each side since merge-base

```
main slice          → backend/migrations/versions/027_strategies_is_paper.py     (Create Date: 2026-05-18)
milestone-1-ship   → backend/migrations/versions/028_add_backtest_runs.py        (Create Date: 2026-05-17)
```

### The alembic chain conflict (confirmed by source inspection)

```python
# backend/migrations/versions/027_strategies_is_paper.py  (main)
revision: str = "027_strategies_is_paper"
down_revision: str | None = "026_add_strategy_templates"

# backend/migrations/versions/028_add_backtest_runs.py    (milestone-1-ship)
revision: str = "028_add_backtest_runs"
down_revision: str | None = "026_add_strategy_templates"   ← SAME PARENT
```

After the merge, the migrations directory contains BOTH files. Alembic
sees two heads (027 and 028), both descending from 026. `alembic upgrade
head` fails with:

```
alembic.util.exc.CommandError: Multiple head revisions are present
for given argument 'head'; please specify a specific target revision,
'<branchname>@head' to narrow to a specific head, or 'heads' for all heads
```

### Fix — choose ONE

**Option (a) — Rebase 028 onto 027 (recommended; smallest delta).** Edit
the migration file directly:

```bash
# After merging feat/milestone-1-ship into a deploy-prep branch (NOT main):
cd backend/migrations/versions
# Edit 028_add_backtest_runs.py:
#   down_revision: str | None = "026_add_strategy_templates"
# →
#   down_revision: str | None = "027_strategies_is_paper"
```

This linearises the chain: `026 → 027 → 028`. 027 is additive (adds
`strategies.is_paper` column with `server_default TRUE`) — it has no
relationship to 028's `backtest_runs` tables, so the new ordering is safe.

**Option (b) — Generate a merge migration.** Heavier:

```bash
cd backend && alembic merge -m "merge milestone-1-ship into main" \
  027_strategies_is_paper 028_add_backtest_runs
```

Produces a new `029_merge_*.py` whose only purpose is to declare both
parents are now upstream of a single head. Functionally equivalent to (a)
but adds an extra file. Use (b) if you want a record of "this merge
happened" in the migration history; use (a) for a clean chain.

### Migration 028 MUST be applied — the brief was wrong

Queue HH/FF runbook (`docs/POST_DEPLOY_VERIFICATION.md`) and Queue II
brief both said:

> "Confirm NO new migrations need to be run (Queue CC+DD said trade
> markers use existing signal_metadata column = no migration needed)."

That was **half-right**: trade-marker *persistence* uses an existing
column. But the async backtest extension's THREE new tables
(`backtest_runs`, `backtest_trades`, `backtest_metrics`) live in 028 and
DO need to be created. The new `/api/backtest/*` routes write to them
on every enqueue / status / trades / markers call. Without 028 applied:

```
psycopg2.errors.UndefinedTable: relation "backtest_runs" does not exist
LINE 1: INSERT INTO backtest_runs (id, user_id, strategy_id, ...
                    ^
```

every POST /api/backtest will 500.

### Action items
- 🟥 **Before pushing to main:** apply fix Option (a) in the deploy-prep branch.
- 🟥 **EC2 deploy step:** add `docker compose exec backend alembic upgrade head` between `docker compose pull/build` and `docker compose up -d backend`. (Or run on host: `docker compose run --rm backend alembic upgrade head` if backend isn't already up.)
- 🟨 **Update** `docs/MILESTONE_1_DEPLOY.md` and `docs/POST_DEPLOY_VERIFICATION.md` to remove the "no migration needed" claim and add the explicit `alembic upgrade head` step.

---

## §5 — Frontend env vars (Phase 3)

```
git diff main..feat/milestone-1-ship -- 'frontend/.env*' 'frontend/next.config.ts' 'frontend/vercel.json' 'frontend/vercel.ts'
```

**Output: empty.** No changes to frontend env config, Next config, or
Vercel config. Vercel auto-deploys frontend on main push using the
existing project env vars (`NEXT_PUBLIC_API_URL`, etc.) — no Vercel
dashboard changes required.

---

## §6 — What main has that milestone-1-ship doesn't (167 commits)

Categories from `git log b90e3567..main --oneline`:

- **6 numbered live-trading fixes** (already merged + presumably deployed)
  - Fix #3: Product type NRML + hard guard
  - Fix #4: Dhan rejection catching
  - Fix #5: Position creation guard
  - Fix #6: Telegram rejection aware
  - Fix #7: Reconciliation per-strategy
  - Fix #8: Kill switch per-strategy
- **20+ Wave 3 indicator content additions** (slugs 51-70)
- **Indicator Library sidebar nav + 70+ subtitle** UI work
- **`/strategies/templates/[slug]` explainer page** UI
- **Migration 027** (`strategies.is_paper` boolean)
- **QA audit reports + UI build report**

**Key point:** all of these are ALREADY on `main` and (assuming EC2 has
been kept current) ALREADY on the production EC2. Tonight's merge does
not introduce them — it brings milestone-1-ship's stuff INTO that already-
deployed state. So tonight's blast radius is **only the 19 milestone-1-ship
commits + the alembic chain fix**.

> ⚠️ **Verify EC2 main parity:** before merging tonight, SSH and confirm
> `git log main --oneline -5` on EC2 matches `git log origin/main --oneline -5`
> locally. If EC2 is behind (e.g. last deploy was before some of those 167
> commits landed), tonight's deploy ALSO ships those commits — a larger
> surface than expected. Recommend tagging the pre-merge main SHA
> (`git tag pre-milestone-1-deploy && git push origin pre-milestone-1-deploy`)
> so rollback is precise.

---

## §7 — Action items for Jayesh BEFORE 4 PM IST deploy

In execution order:

1. 🟥 **(5 min)** Fix the alembic chain. On a deploy-prep branch:
   ```bash
   git checkout feat/milestone-1-ship
   git checkout -b deploy/milestone-1-rebased-alembic
   # Edit backend/migrations/versions/028_add_backtest_runs.py:
   #   down_revision: str | None = "027_strategies_is_paper"
   # (was: "026_add_strategy_templates")
   git add backend/migrations/versions/028_add_backtest_runs.py
   git commit -m "fix(alembic): rebase 028 onto 027 — resolve branched head pre-deploy"
   git push origin deploy/milestone-1-rebased-alembic
   ```
   Then merge `deploy/milestone-1-rebased-alembic` into main instead of `feat/milestone-1-ship`.

2. 🟥 **(2 min)** Update `docs/MILESTONE_1_DEPLOY.md` Step 2 to include the migration step BEFORE the backend restart:
   ```bash
   # After docker compose build, BEFORE docker compose up -d backend:
   docker compose run --rm backend alembic upgrade head
   ```

3. 🟨 **(1 min)** Verify EC2 main parity (see §6 ⚠️ box).

4. 🟨 **(1 min)** Add to `.env.production` on EC2:
   ```
   BACKTEST_RATE_LIMIT_PER_HOUR=30
   BACKTEST_RATE_LIMIT_CONCURRENT=5
   ```

5. 🟢 **(1 min, optional)** Tag the pre-merge main SHA for precise rollback:
   ```bash
   git fetch origin && git tag pre-milestone-1-deploy origin/main && git push origin pre-milestone-1-deploy
   ```

6. 🟢 **Then proceed** with `docs/MILESTONE_1_DEPLOY.md` Steps 1-5 + `docs/POST_DEPLOY_VERIFICATION.md` smoke tests.

---

## Hard-stop confirmations

| Check | Result |
|---|---|
| `feat/milestone-1-ship` UNTOUCHED at `3c701a0` | ✅ verified — no commits added on this branch |
| No code changes | ✅ — read-only diffs + one new doc file |
| Live BSE LTD strategy untouched | ✅ — audit-only |
| No push/merge to main | ✅ — audit branch only |
| Working tree clean | ✅ — aside from 2 pre-existing untracked items |
