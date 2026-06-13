# TRADETRI — Session Handoff (paste into any new chat)

**Last updated:** 2026-06-13 (after gates a/b/c/e-enqueue + Queue EEE merged to main via PR #13)

Paste this whole file into a fresh Claude session before asking for anything. It is the single living source of truth — overwritten each session-end, never appended.

---

## 1. Branches

| Branch | HEAD | What it contains | Push state |
|---|---|---|---|
| `feat/queue-ccc-historical-candles-skeleton` | `75c38d5` | Sprint 2 (F1–F7 + report) + Queue DDD 027 fix folded in + Phase 3 code (rate_limit_guard, jobs, orchestrator, celery task, 22-sym script) + gate (a) test-unskip + gate (b) celery include. **Active branch.** | pushed |
| `fix/queue-ddd-migration-027-uuid-cast` | `20a8044` | DDD 027 UUID-cast fix (2-line `CAST(:live_id AS uuid)`). Already merged into the skeleton branch via `3b50e74`. | pushed |
| `design/queue-ccc-real-dhan-design` | `6c667fd` | v1 discovery + v2 approved design docs only (no code). | pushed |
| `main` (local) | `0075d08` | 14 commits behind `origin/main`. None of those 14 touch the 3 files this skeleton imports from (`schemas/candle.py`, `strategy_engine/schema/ohlcv.py`, `brokers/dhan_historical.py`) — drift-checked. | UNTOUCHED |
| `feat/queue-eee-indicator-smoketests` | (parallel worktree; **MERGED** to `main` 2026-06-13 via PR #13) | Queue EEE indicator smoketests — 137 indicators, 127 PASS / 6 WARN / 0 FAIL. Lives in `../trading-bridge-smoketests`. **STILL never touch from this repo / session.** Remote ref pending delete. | merged |

---

## 2. Production state

| Surface | State |
|---|---|
| Production EC2 backend (AWS Mumbai, Elastic IP `13.127.224.68`) | `55047df` (tag `release-cutover-8`) — Sprint 8 bundle (VWAP fix + translator extensions). UNTOUCHED this weekend. |
| Production Vercel frontend (`tradetri.com`) | `0075d08` (tag `release-cutover-9`) — badges + tooltips + nav. UNTOUCHED this weekend. |
| Sprint 9 deploy scope | Frontend-only — EC2 backend unchanged since `cutover-8`. |
| Brokers | Live on Fyers + Dhan. |
| Production DB migration | Past `028_add_backtest_runs` (verified during DDD-1 — that's why the 027 bug was bootstrap-only, not a prod-side bug). |
| BSE LTD strategy `89423ecc-c76e-432c-b107-0791508542f0` | LIVE, is_paper=FALSE. Runs Monday 09:15 IST. |
| Local Postgres (this dev box) | At `030_historical_backfill_jobs` head; 5 NIFTY daily bars in `historical_candles` (gate c); 22 PENDING rows in `historical_backfill_jobs` (gate e enqueue). |

---

## 3. Sacred zones + hard rules (from CLAUDE.md, restated for paste-ability)

### NEVER edit without explicit "is_paper=false confirmed" gate
- `is_paper` column anywhere
- `app/strategy_engine/` (strategy_executor)
- `app/brokers/direct_exit.py`
- webhook handler
- `app/services/kill_switch_*`
- broker adapters: `app/brokers/dhan.py`, `app/brokers/fyers.py`
- ANY `backend/migrations/versions/*_strategies_*.py`

### Protected zones (don't touch unless explicitly named)
R:R block · Brahmastra trail · entry/exit logic · JSON DSL builder

### F&O contract
**FUTURES = NRML only.** MIS / INTRADAY for F&O = forbidden. Equity intraday is fine.

### Workflow
- One module per task. Never one-shot.
- Plan first, edit after founder approves.
- Work on a branch, never commit to `main` directly.
- Show actual diff before commit.
- Run FULL test suite, not subset.
- Two deploy hard-stops max: before migrations, before container restart.
- Founder gates every deploy.

### Push discipline
- Never push during a session unless explicitly authorised.
- NEVER push to `main`. NEVER force-push to `main`.
- `commit_discipline` memory: ~30-min source commits, tests batched, no per-session push (founder gates).

### Communication
- Hinglish + engineering-grade detail. User-facing errors in Hinglish.
- Structured logs: JSON with named fields. Never per-item logs in a loop.

---

## 4. DONE this weekend (Friday night → Saturday morning)

| Item | Commit / artifact | Status |
|---|---|---|
| Queue DDD 027 UUID-cast fix | `20a8044` on fix branch → merged into skeleton via `3b50e74` | applied locally, in container, prod unaffected |
| Sprint 2 (F1 model + F2 mig 029 + F3 pkg + F4 repo + F5 bridge + F6 tests + F7 manual smoke) | `93cf3b6` → `5482f0b` → `fb1347e` → `2d74013` (report) | all on skeleton branch, pushed |
| Sprint 2 G2 + G3 founder gates | approved with revisions | done |
| Phase 3 code authoring (overnight) | `6db7016` rate_limit_guard, `e3bf405` jobs+mig 030, `96d581e` orchestrator, `91531ed` celery task, `bb93266` 22-sym seed | code-complete, tests all-pass |
| Sprint 2 final coverage | 100% on 6 of 7 files; jobs_repository was skip-gated | resolved gate (a) → 100% on all 7 |
| Gate (a) migration 030 apply + unskip | local DB at `030_historical_backfill_jobs (head)`. Commit `3e1a411`. | 111/111 tests pass |
| Gate (b) celery include +1 line | `backend/app/tasks/celery_app.py` +1 / 0. Commit `75c38d5`. | committed, BACKFILL_ENABLED still OFF |
| Gate (c) Phase 2c manual Dhan smoke test | 5 NIFTY daily bars Mon-Fri last week round-tripped Dhan → bridge → repo → coverage. Idempotent verified by design. | green, no commit (operational only) |
| Gate (e) 22-symbol enqueue | `python -m scripts.phase3_seed_22_symbols_backfill` → 22/22 PENDING rows. All state-machine invariants hold (no premature `started_at`/`completed_at`/`error_json`). No Dhan calls. Flag still OFF. | green, no commit (operational only) |
| Branches pushed | `fix/queue-ddd-…` + `feat/queue-ccc-…-skeleton` | done |

---

## 5. PARKED (with exact gates)

| Gate | Blocks | Specific action needed | Notes |
|---|---|---|---|
| **(d) main merge** | nothing today | merge `feat/queue-ccc-historical-candles-skeleton` → `origin/main` after weekend gate | drift-check clean at session-start; founder decides timing |
| **(e) 22-symbol backfill ENQUEUE** | ✅ DONE | 22 PENDING rows in local dev DB. | re-running would create duplicate PENDING rows (no PK uniqueness on symbol+window by design); only run again after dedup or after drain |
| **(e) 22-symbol backfill DRAIN** | A5 + flag + worker restart | set `BACKFILL_ENABLED=true` on celery_worker env + restart worker + flip A5 (below) | needs A5 fixed first or every drain attempt raises `NotImplementedError` |
| **A5 — Dhan credential factory** | drain | replace `_dhan_client_factory_for_job` in `app/tasks/historical_backfill_tasks.py:_dhan_client_factory_for_job` with real per-user `BrokerCredential` lookup (or service-account fallback) | currently raises `NotImplementedError`; marked `# pragma: no cover`; load-bearing for drain only |
| ~~**Smoke-test PR** (Queue EEE)~~ | ✅ DONE — **MERGED to main 2026-06-13** (origin/main `34357dd`) via PR #13 | n/a | merged |
| **F2 migration 029 main-merge note** | nothing | when (d) lands, EC2 dev/staging needs `alembic upgrade head` to pick up 029 + 030 | EC2 prod separately — prod already past 028, will need both new migrations |

---

## 6. Active queue pointers

| Queue | Current state |
|---|---|
| **Queue CCC** (this weekend) | Sprint 2 ✅ done · Phase 3 code ✅ done · gates (a) (b) (c) (e-enqueue) ✅ done · gate (d) main merge pending · (e) drain blocked on A5 |
| **Queue DDD** (this weekend) | 027 fix ✅ done, folded into CCC skeleton, prod unaffected |
| **Queue EEE** (parallel) | Running in `../trading-bridge-smoketests` on `feat/queue-eee-indicator-smoketests`. Not visible from here — don't infer state. |
| **Queue AAA / BBB** | Older work; docs in `docs/QUEUE_AAA_*` and `docs/QUEUE_BBB_*` (untracked at last check). Not active this weekend. |
| **Queue Z** | Template validation sprint, completed earlier — branch `chore/template-validation-sprint` on origin. |
| **BSE LTD strategy `89423ecc`** | LIVE, untouched, dormant until Monday 09:15 IST market open. |

---

## 7. Anomalies — A1 through A5 status

| ID | What | Status |
|---|---|---|
| **A1** | SQLAlchemy `MetaData` naming convention auto-prepends `ck_<tablename>_` to CHECK names → ends up as `ck_historical_candles_ck_hc_*` (and same on 030 → `ck_historical_backfill_jobs_ck_hbj_*`) | Cosmetic only. Constraints fire correctly. Not blocking anything. Defer to one-off rename pass if alembic autogen ever runs. |
| **A2** | Local `main` 14 commits behind `origin/main` | Still true. Drift-checked clean for the 3 files we depend on. Resolves naturally at gate (d) (main merge). |
| **A3** | DDD fix mechanism — `::uuid` suffix collided with SQLAlchemy `text()` parser, switched to `CAST(:live_id AS uuid)` | Resolved. Informational. No action needed. |
| **A4** | Runtime Docker image omits `pyproject.toml`, runtime `/app/` not writable for appuser → had to `docker cp pyproject.toml`, run pytest from `/tmp`, disable pytest cache for overnight tests | Production unaffected. Optional Dockerfile cleanup: add pyproject + a writable test dir. Defer. |
| **A5** | `_dhan_client_factory_for_job` raises `NotImplementedError` | **Still load-bearing for drain.** No action taken today. Blocks any worker drain attempt. Phase 3+ follow-up: per-user `BrokerCredential` resolution OR service-account fallback. |

---

## 8. One-line state summary

**Queue CCC Sprint 2 + Phase 3 skeleton committed and pushed on `feat/queue-ccc-historical-candles-skeleton`; migration 030 applied; celery task registered; Dhan pipeline proven via NIFTY smoke test; 22 PENDING backfill jobs enqueued; drain blocked on A5; main merge (gate d) deferred to founder's call.**

---

## 9. Parked decisions & cross-track items

| # | Item | Detail | Status |
|---|---|---|---|
| 9.1 | **Gate (d) main merge — reconciliation needed** | 3 branches on origin NOT yet on main: `feat/queue-ccc-historical-candles-skeleton`, `fix/queue-ddd-migration-027-uuid-cast`, `feat/queue-eee-indicator-smoketests`. `origin/main` has advanced to `f62585d` via parallel work since the skeleton's `0075d08` base. Pre-merge drift-check + reconciliation required. | parked |
| 9.2 | **Queue EEE PR** | `feat/queue-eee-indicator-smoketests` — 137/137 indicators tested: **127 PASS · 6 WARN · 0 FAIL**. **MERGED to main 2026-06-13 via PR #13** (origin/main `34357dd`). Remote branch ref still present, pending delete. | MERGED |
| 9.3 | **Frontend Sprint 9 — already LIVE** | Vercel `0075d08` (tag `release-cutover-9`) live on `tradetri.com`. Ships: verification badges, convention tooltips, sidebar nav (Learn Indicators + Indicator Library + Builder "Add Indicators"). Frontend-only — EC2 still on `cutover-8`. | live |
| 9.4 | **Sprint 10 — NOT started, design only** | Founder direction: verification status should be **INTERNAL only**, not customer-facing. Pre-launch so no urgency; final decision deferred to pre-launch window. | design-only |
| 9.5 | **Template reality (current snapshot)** | 27 active templates · **26 fire backtests** · 1 xfail (`inside-bar-breakout`) · 2 deactivated (`vwap-bounce`, `camarilla` — need real-Dhan 30d verify) · 86 unbuilt placeholders. | active rollout |
| 9.6 | **Next obvious sprint — Queue FFF (proposed)** | A5 credential factory + drain + 22-symbol backfill execution. The end-to-end backfill capstone of Queue CCC Phase 3. ~2h with plan-first gate trail. | proposed |
