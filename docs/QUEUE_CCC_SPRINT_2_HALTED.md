# Queue CCC Sprint 2 — HALTED (Phase 2b suspended)

**Date:** 2026-06-03 evening
**Branch:** `feat/queue-ccc-historical-candles-skeleton` (local only, NOT pushed)
**Halt commit:** _this doc_ — preserves state for Saturday resume
**Halt reason:** Pre-existing migration `027_strategies_is_paper.py` UUID/VARCHAR type-cast bug. Sacred-zone rule (CLAUDE.md L6: *"strategies migrations: NEVER modify without me confirming is_paper=false first"*) prevents fix in this session.
**Resume target:** Saturday morning. **Queue DDD** (027 bug fix) must land first; **Queue CCC Sprint 2 Phase 2b** resumes from commit (a) `93cf3b6` after.

---

## What was attempted

| Step | Action | Result |
|---|---|---|
| Phase 2a plan | Read v2 design §2.2, §4. Presented 7-file inventory + 4 scope clarifications (C1-C4). | ✅ Founder approved C1-C4 (NIFTY 50 test, historical_candles only, defer rate_limit_guard, tests-home confirmed). |
| Branch creation | `git checkout -b feat/queue-ccc-historical-candles-skeleton` off main `0075d08`. | ✅ Branch live, local. |
| Commit (a) | F1 `backend/app/db/models/historical_candle.py` (159 LOC) + F3 `backend/app/services/historical_candles/__init__.py` (21 LOC). | ✅ Commit `93cf3b6`. |
| G1 prep — alembic state probe | `docker compose exec backend alembic current/heads/history`. | ⚠ Container at `009_strategy_json_column`; host has migrations 001-028. Container image stale (23h, pre-May 11). F1 model missing in container. |
| Path C executed (founder authorised) | `docker compose down -v` (volume wiped) → `docker compose up -d --build` (image rebuilt) → `docker compose exec backend alembic upgrade head`. | ✅ Container rebuilt, F1 present in container, 28 migrations visible. ❌ alembic upgrade halted at 027. |
| Halt point | Migration `027_strategies_is_paper.py` raises `operator does not exist: uuid <> character varying` for `UPDATE strategies SET is_paper = TRUE WHERE id != $1::VARCHAR`. Parameter is BSE LTD live strategy `89423ecc-c76e-432c-b107-0791508542f0`. | 🟥 STOP per CLAUDE.md sacred-zone rule. |

## Where the system is right now

| Surface | State |
|---|---|
| Branch `feat/queue-ccc-historical-candles-skeleton` | Exists locally with one commit `93cf3b6`. Working tree clean before this halt doc. |
| `main` | Untouched. HEAD at `0075d08`. Vercel + production unaffected. |
| `design/queue-ccc-real-dhan-design` | Untouched. v1 + v2 docs preserved on it. |
| Local docker compose stack | UP — postgres healthy, backend healthy, redis healthy. celery_beat + celery_worker may be unhealthy post-rebuild (not blocking; not investigated). Founder discretion to leave running or `docker compose down`. |
| Local Postgres DB revision | **`021_user_onboarding`** — broken intermediate state. Migrations 022-028 absent. **Will be wiped Saturday** before Queue DDD work. No data of value in it. |
| Container image `trading_bridge_backend:latest` | Freshly built with current host code; includes F1 + all 28 migration files. |
| Production EC2 / Vercel | UNTOUCHED. No SSH, no deploy, no env mutation. |
| Push state | NO push tonight (per founder direction + `feedback_commit_discipline`). |

## The 027 bug (informational only — NOT being fixed tonight)

File: `backend/migrations/versions/027_strategies_is_paper.py`
Failing statement (approximate — not pulled from disk in this session):
```sql
UPDATE strategies SET is_paper = TRUE WHERE id != $1::VARCHAR
-- with parameter ('89423ecc-c76e-432c-b107-0791508542f0',)
```
`strategies.id` column is `UUID`. Postgres rejects `UUID <> VARCHAR` without explicit cast. Single-character bug — `::VARCHAR` should be `::UUID` (or `CAST($1 AS uuid)`, or pass via SQLAlchemy `.cast(UUID)`).

This is the pre-existing **"DR / new-environment bootstrap hazard"** founder flagged — it surfaces only on a fresh DB rebuild, which is rare in normal dev flow. Production DB is past this migration so production is unaffected.

## Saturday resume plan (founder-authored)

1. **Queue DDD** (Saturday calm hours, BSE LTD dormant — weekend, market closed):
   - Fix 027 UUID cast surgically.
   - Test on fresh local DB: `docker compose down -v && docker compose up -d --build && docker compose exec backend alembic upgrade head` reaches `028_add_backtest_runs` cleanly.
   - Commit + push as separate PR before resuming Sprint 2.
2. **Queue CCC Sprint 2 Phase 2b — resume from commit (a) `93cf3b6`:**
   - Re-run seeds (`scripts.seed_dev` + `app.templates.scripts.seed_strategy_templates`).
   - G1: `alembic revision -m "create historical_candles table"`, parent `028_add_backtest_runs`.
   - G2: founder reviews migration content before `alembic upgrade head`.
   - Continue through commits (c) schema_bridge → (d) repository → (e) tests → (f) manual NIFTY 50 Dhan read-only test (G4) → (g) Sprint 2 report.

## Pending tasks (preserved for Saturday)

- commit (b) F2 alembic migration — paused, target `028_add_backtest_runs` as down_revision
- commit (c) F5 schema_bridge
- commit (d) F4 repository
- commit (e) F6 skeleton tests (G3 gate)
- commit (f) F7 manual NIFTY 50 Dhan test (G4 gate)
- commit (g) Sprint 2 report

## Hard-stop compliance — confirmed honoured tonight

- [x] No sacred-zone code edited (027 left alone despite the failure).
- [x] No production / EC2 / Vercel touch.
- [x] No main branch touch (main untouched at `0075d08`).
- [x] No branch push.
- [x] No Dhan API call (G4 never reached).
- [x] Plan-first founder gate honoured (C1-C4 approved).
- [x] Alembic migration content founder-review gate (G2) honoured by not generating any migration tonight.
- [x] Container/DB state isolation respected (no production DB touched; only local docker volume wiped on founder authorization).

— end of halt doc —
