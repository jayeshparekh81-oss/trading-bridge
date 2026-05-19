# Tomorrow Evening (Tuesday May 19, post-4 PM IST) — Final Backlog Clearance

> **Goal:** clear all remaining branches in under 60 minutes
> **Hard rule:** no deploys until after 4 PM IST regardless of merge readiness
> **State at start:** 13 origin branches remaining after Queue X Phase A deletions

---

## Group 1 — Conflict resolutions (15 min)

### 1a. `docs/post-may-17-retrospective` (3 min)
**Action:** rescue 2 unique files, drop the rest. Main's MASTER_ROADMAP/README are newer and win.

```bash
git fetch origin
git checkout -b docs/rescue-retrospective-may17 origin/main
git show origin/docs/post-may-17-retrospective:BLOCKERS_DOCS.md > BLOCKERS_DOCS.md
git show origin/docs/post-may-17-retrospective:docs/POST_MAY_17_RETROSPECTIVE.md > docs/POST_MAY_17_RETROSPECTIVE.md
git add BLOCKERS_DOCS.md docs/POST_MAY_17_RETROSPECTIVE.md
git commit -m "docs: rescue May-17 retrospective + blockers audit (main MASTER_ROADMAP/README kept)"
git push -u origin docs/rescue-retrospective-may17
# Fast-forward merge via gh CLI or web UI, then:
git push origin --delete docs/post-may-17-retrospective
```

Full analysis: `docs/QUEUE_X/CONFLICT_RESOLUTION_post-may-17-retrospective.md`

### 1b. `feat/indicator-content-wave-3` (12 min)
**Action:** rebase onto main. Single conflict in `registry.ts`, mechanical union merge — 20 new imports + 20 new entries to append to main's version. Zero file collisions on the 20 new content/*.ts files.

```bash
git checkout -b merge/indicator-content-wave-3 origin/feat/indicator-content-wave-3
git rebase origin/main
# When rebase pauses on frontend/src/lib/indicators/registry.ts:
#   - Take main's version: `git checkout --theirs frontend/src/lib/indicators/registry.ts`
#   - Append wave-3's 20 imports + 20 INDICATORS entries (full lists in CONFLICT_RESOLUTION doc).
git add frontend/src/lib/indicators/registry.ts
git rebase --continue

cd frontend
pnpm test -- indicators/wave-3-registry.test.ts indicators/registry.test.ts
pnpm tsc --noEmit
cd ..

git checkout main && git merge --ff-only merge/indicator-content-wave-3
git push origin main
git push origin --delete feat/indicator-content-wave-3
```

Full analysis: `docs/QUEUE_X/CONFLICT_RESOLUTION_indicator-content-wave-3.md`

---

## Group 2 — Founder-review non-live branches (5 branches, 20 min)

### 2a. `docs/marketing-kit-v2` (5 min eyeball)
2 commits ahead, 8 files. Founder-voice review only — read the marketing copy, accept or reject. No live-trading touches.

### 2b. `docs/marketing-launch-kit` (3 min)
1 commit, 6 files. Compare against `marketing-kit-v2`; if v2 is the superset, delete launch-kit. Otherwise eyeball + merge.

### 2c. `chore/brand-cleanup-batch-1` (3 min)
1 commit, 2 files. Confirm hostname/brand string consistency, merge or skip.

### 2d. `feat/phase-2-templates-part-2` (3 min)
1 commit, 3 files. **Defer decision** — read commit message, decide whether Phase 2 templates batch 2 belongs in this sprint or next. If deferring, leave the branch alive.

### 2e. `feat/test-coverage-batch-1` (6 min)
1 commit, 8 files. **14 RED tests expected** — do NOT try to fix in this session. Defer to a dedicated test-repair session. Leave the branch alive with a sticky note.

---

## Group 3 — Live-trading branches (20 min) — CAREFUL

### 3a. `feat/per-strategy-paper-flag` (8 min, SAFE)
**Status:** ✅ SAFE_AFTER_MIGRATION_AUDIT.

The migration explicitly preserves BSE LTD strategy `89423ecc-c76e-432c-b107-0791508542f0` as LIVE via a targeted `UPDATE strategies SET is_paper = FALSE WHERE id = :live_id`. Resolver design is correct, fail-safe (None → global flag).

**Deploy sequence:**
1. Pre-flight: `alembic current` on EC2 = 026; snapshot strategies table.
2. Open PR, merge to main.
3. SSH EC2: `git pull` (no restart yet).
4. `alembic upgrade head` → 027.
5. Verify: `SELECT id, is_paper FROM strategies WHERE id='89423ecc-...';` must be FALSE.
6. Restart FastAPI workers.
7. Tail logs for `time_of_day_check_bypassed_paper_mode` with `strategy_id=...`.

Rollback: `alembic downgrade -1`. Resolver's None branch handles missing column safely.

Full analysis: `docs/QUEUE_X/LIVE_TRADING_per-strategy-paper-flag.md`

### 3b. `feat/dockerfile-talib` (12 min, SPLIT INTO 3 PRs)
**Status:** ⚠️ NEEDS_DEEP_REVIEW + PR_SPLIT. The branch bundles 3 unrelated concerns.

- **PR 1 (cherry-pick `6e7d16a`):** Dockerfile + pyproject ta-lib pin — LOW RISK, merge first.
- **PR 2 (cherry-pick `9f26ee5`):** docker rebuild test script — LOW RISK, merge any time.
- **PR 3 (cherry-pick `a4801f4`):** futures resolver + webhook integration — **HOLD UNTIL JAYESH ANSWERS:**

> **Open question:** the BSE LTD live strategy's TradingView ticker — is it `NSE:BSE` (cash equity) or `BSE1!` (continuous future)?

The resolver maps `NSE:BSE → BSE` and rewrites the symbol to `BSE-MAY2026-FUT`. If BSE LTD trades cash equity, this would mis-route. If futures, it's correct. Answer this BEFORE merging PR 3.

Commands for all 3 PRs are in `docs/QUEUE_X/LIVE_TRADING_dockerfile-talib.md`.

EC2 must be `c7i-flex.large` or larger for the libta-lib compile.

---

## Group 4 — New unknowns from parallel sessions (5 min)

### 4a. `chore/content-qa-audit`
**Verdict:** DELETE. Single 226-line stale QA report from May 19 00:07; superseded by 91 main commits since.
```bash
git push origin --delete chore/content-qa-audit
```
If Jayesh wants the report saved: cherry-pick `c683484` onto a fresh `docs/qa-snapshot-may19` branch first — commands in `docs/QUEUE_X/UNKNOWN_content-qa-audit.md`.

### 4b. `feat/ui-strategy-explainers`
**Verdict:** SAFE — merge after simple rebase. 2 new files only:
- `frontend/.../strategies/templates/[slug]/page.tsx` (+452)
- `frontend/tests/strategies/explainer-page.test.tsx` (+152)

Zero live-trading touches. Earlier diff vs main showed backend model diffs only because the branch is 79 commits behind — those are main's additions, NOT branch reverts.

```bash
git checkout -b merge/ui-strategy-explainers origin/feat/ui-strategy-explainers
git rebase origin/main  # expect no conflicts
git checkout main && git merge --no-ff merge/ui-strategy-explainers
git push origin main
git push origin --delete feat/ui-strategy-explainers
```

Full analysis: `docs/QUEUE_X/UNKNOWN_ui-strategy-explainers.md`

---

## Group 5 — Keep forever (no action)

- `feat/backtest-engine-day-1-3` — prod-deployed reference, do not delete
- `feat/backtest-engine-day-6` — Day 7 will build on this; do not delete

---

## End-of-session checklist

- [ ] Group 1: 2 conflicts resolved (or branches still alive with reason logged)
- [ ] Group 2: 5 branches reviewed; merged/deferred/deleted recorded
- [ ] Group 3: per-strategy-paper-flag deployed; dockerfile-talib split into 3 PRs (PR 1 + 2 merged, PR 3 status known)
- [ ] Group 4: content-qa-audit deleted; ui-strategy-explainers merged
- [ ] BSE LTD live strategy verified `is_paper = FALSE` post-migration
- [ ] No deploys before 4 PM IST happened
- [ ] No force pushes to main
- [ ] Final origin branch count: 2 (the two backtest reference branches) + anything intentionally deferred

## Hard-stop rules (carried from Queue X)
- No SSH / docker / alembic / deploy before 4 PM IST
- No force-push to main, ever
- BSE LTD live strategy (`89423ecc-c76e-432c-b107-0791508542f0`) MUST remain LIVE (`is_paper = FALSE`) at all times
- All live-trading deploys: pre-flight snapshot → migration → verify ID → restart → tail logs
