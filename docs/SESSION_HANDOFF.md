# TRADETRI — Session Handoff (paste into any new chat)

**Last updated:** 2026-06-14 (Sunday — **Queue HHH overnight buildout: 10 branches on origin, zero merged** + **decided 2-phase next-session plan**; on top of the Saturday 5-PR landing #13–#17)

Paste this whole file into a fresh Claude session before asking for anything. It is the single living source of truth — overwritten each session-end, never appended.

---

## 0. CURRENT STATE — Sunday 2026-06-14 (START HERE)

> Newest state on top. Sections 1–9 below are the CCC/FFF weekend history — still accurate, lower priority for the next session.

### 0.1 — Where everything stands

- **`origin/main` = `62f84f3`** — after **5 PRs merged Saturday 2026-06-13**: #13 EEE (indicator smoketests), #14 gate-(d) CCC+DDD, #15 docs, #16 A5 credential factory, #17 docs.
- **A5 Dhan credential factory = MERGED** (PR #16, `c602aca`). Drain code is ready; blocked **only** on EC2 deploy + `BACKFILL_ENABLED` flag — **no code work left**.
- **EC2 prod backend STILL at `cutover-8` (`55047df`)** — way behind `main`. ⚠️ Real-Dhan go-live = a **full backend jump `cutover-8` → `main`**, NOT just running migrations. The whole Sprint-9 / CCC / FFF backend bundle ships at once.
- **Local `main` was behind `origin`** — run `git checkout main && git pull` before any work next session.
- **BSE LTD `89423ecc` LIVE, `is_paper=FALSE`** — untouched all weekend. Must stay untouched through Monday 09:15 IST.

### 0.2 — Queue HHH: overnight buildout (the 9 Coming-Soon pages)

**10 feature branches on `origin`, ZERO merged, prod untouched.** Each builds out one of the previously-"Coming Soon" pages (see `PROJECT_MAP.md` §1 / §5). Built but unreviewed — customer-facing UI that **CC cannot self-verify**; founder's eyes required before any merge.

| Module | Branch (origin) | HEAD | State |
|---|---|---|---|
| **M1** admin auth guard | `feat/hhh-admin-auth-guard` | `35e5b2f` | ✅ COMPLETE |
| **M2** webhooks page | `feat/hhh-webhooks` | `f74a785` | ✅ COMPLETE — **customer-facing TOP priority** (TradingView token CRUD) |
| **M3** admin users | `feat/hhh-admin-users` | `ccbd9dd` | 🟡 SCAFFOLDED |
| **M4** admin announcements | `feat/hhh-admin-announcements` | `412e688` | ✅ COMPLETE |
| **M5** admin audit | `feat/hhh-admin-audit` | `522577f` | ✅ COMPLETE |
| **M6** admin kill-switch-events | `feat/hhh-admin-kill-switch-events` | `fa5c586` | ✅ COMPLETE |
| **M7** admin home | `feat/hhh-admin-home` | `732e04b` | ✅ COMPLETE |
| **M8** settings | `feat/hhh-settings` | `79db7fc` | 🟡 SCAFFOLDED |
| **M9** analytics | `feat/hhh-analytics` | `7ee3fda` | 🟡 SCAFFOLDED — recent-100-trades; full-history flagged |
| **M10** alerts | `feat/hhh-alerts` | `4ffebba` | 🟡 SCAFFOLDED — storage only; **engine NOT built** (load-bearing amber banner on page); needs **migration 031** on EC2 to work |
| _docs_ | `docs/hhh-summary` | `4092b44` | `docs/QUEUE_HHH_SUMMARY.md` — per-module review steps |

⚠️ **migration 031_alerts**: LOCAL dev DB only + on the M10 branch. **NOT on `main`, NOT on prod.**

### 0.3 — DECIDED NEXT-SESSION PLAN (2 phases — do NOT bundle into one autonomous prompt)

**PHASE 1 — HHH visual review + merge** (founder's eyes; CC cannot verify customer-facing UI):
1. Founder reviews each branch via Vercel preview URLs **OR** local `npm run dev`.
2. Review order: **M1 auth-guard → M2 webhooks → M3–M7 admin → M8/M9 → M10** (verify the amber banner on M10).
3. Merge **only** founder-approved branches — **one PR each**, after visual review.

**PHASE 2 — Real-Dhan go-live** (GATED deploy; founder gates every step; NOT autonomous):
1. **DB backup FIRST**, then full backend deploy `cutover-8` → `main` (health check, verify BSE LTD intact).
2. Apply **migrations 029 + 030** on EC2 (dev → staging → prod; **before-migrations hard-stop**).
3. Configure creds: `BACKFILL_DHAN_USER_ID` (β tier) **OR** `BACKFILL_DHAN_CLIENT_ID` + `BACKFILL_DHAN_ACCESS_TOKEN` (α tier).
4. Restart `celery_worker` + `celery_beat` (**before-restart hard-stop**).
5. Flag `BACKFILL_ENABLED=true` → drain **1–2 symbols first** (not all 22) → verify real data.
6. **CONFIRM BSE LTD `89423ecc` untouched** before Monday 09:15 IST.

---

## 1. Branches

| Branch | HEAD | What it contains | Push state |
|---|---|---|---|
| `feat/queue-ccc-historical-candles-skeleton` | `5ab0ef4` | Sprint 2 (F1–F7 + report) + Queue DDD 027 fix folded in + Phase 3 code (rate_limit_guard, jobs, orchestrator, celery task, 22-sym script) + lint-fix + module-skipif tests. **MERGED to main 2026-06-13 via PR #14** (origin/main `96fc3a1`). Remote ref pending delete. | merged |
| `fix/queue-ddd-migration-027-uuid-cast` | `20a8044` | DDD 027 UUID-cast fix (2-line `CAST(:live_id AS uuid)`). Folded into the CCC skeleton via `3b50e74`; **subsumed by PR #14 merge** — DDD content now on main. Remote ref pending delete. | merged (via CCC) |
| `design/queue-ccc-real-dhan-design` | `6c667fd` | v1 discovery + v2 approved design docs only (no code). | pushed |
| `main` (local) | `0075d08` | Behind `origin/main` (which is now `96fc3a1`). UNTOUCHED locally. | UNTOUCHED |
| `docs/post-gate-d-refresh` | (this commit) | Tiny branch carrying just the docs refresh after gate (d). Not yet pushed. | local |
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
| ~~**(d) main merge**~~ | ✅ DONE — **MERGED to main 2026-06-13** (origin/main `96fc3a1`) via PR #14, GitHub-API merge | n/a | merged |
| **(e) 22-symbol backfill ENQUEUE** | ✅ DONE | 22 PENDING rows in local dev DB. | re-running would create duplicate PENDING rows (no PK uniqueness on symbol+window by design); only run again after dedup or after drain |
| **(e) 22-symbol backfill DRAIN** | EC2 deploy of 029+030 + flag flip + worker restart | apply migrations 029+030 on EC2, set `BACKFILL_ENABLED=true` on celery_worker env (+ either `BACKFILL_DHAN_USER_ID` β or `BACKFILL_DHAN_CLIENT_ID`+`BACKFILL_DHAN_ACCESS_TOKEN` α), restart celery_worker + celery_beat | A5 code resolved; remaining blockers are deploy-side only (separate founder-gated session) |
| ~~**A5 — Dhan credential factory**~~ | ✅ CODE MERGED via PR #16 (origin/main `c602aca`) | 3-tier resolver: per-user → service-account-β (`BACKFILL_DHAN_USER_ID`) → env-direct-α (`BACKFILL_DHAN_CLIENT_ID`+`BACKFILL_DHAN_ACCESS_TOKEN`). 20 new tests, 131/131 historical_candles suite green. Drain still gated by `BACKFILL_ENABLED=true` + EC2 deploy of 029+030. | code merged, drain still needs EC2 deploy+flag |
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
| **A5** | ~~`_dhan_client_factory_for_job` raises `NotImplementedError`~~ | ✅ **RESOLVED via PR #16** (Queue FFF, origin/main `c602aca`). 3-tier resolver implemented with 20 unit tests + factory closure integration test, 131/131 suite green. Drain still requires EC2 deploy of 029+030 + `BACKFILL_ENABLED=true` flag flip — separate founder-gated session. |

---

## 8. One-line state summary

**Queue CCC Sprint 2 + Phase 3 skeleton committed and pushed on `feat/queue-ccc-historical-candles-skeleton`; migration 030 applied; celery task registered; Dhan pipeline proven via NIFTY smoke test; 22 PENDING backfill jobs enqueued; drain blocked on A5; main merge (gate d) deferred to founder's call.**

---

## 9. Parked decisions & cross-track items

| # | Item | Detail | Status |
|---|---|---|---|
| 9.1 | **Gate (d) main merge — DONE** | All 3 branches landed on main: `feat/queue-eee-indicator-smoketests` via PR #13 (2026-06-13, `34357dd`), `feat/queue-ccc-historical-candles-skeleton` + `fix/queue-ddd-migration-027-uuid-cast` via PR #14 (2026-06-13, `96fc3a1`). DDD fix subsumed by CCC merge. | ✅ DONE |
| 9.2 | **Queue EEE PR** | `feat/queue-eee-indicator-smoketests` — 137/137 indicators tested: **127 PASS · 6 WARN · 0 FAIL**. **MERGED to main 2026-06-13 via PR #13** (origin/main `34357dd`). Remote branch ref still present, pending delete. | MERGED |
| 9.3 | **Frontend Sprint 9 — already LIVE** | Vercel `0075d08` (tag `release-cutover-9`) live on `tradetri.com`. Ships: verification badges, convention tooltips, sidebar nav (Learn Indicators + Indicator Library + Builder "Add Indicators"). Frontend-only — EC2 still on `cutover-8`. | live |
| 9.4 | **Sprint 10 — NOT started, design only** | Founder direction: verification status should be **INTERNAL only**, not customer-facing. Pre-launch so no urgency; final decision deferred to pre-launch window. | design-only |
| 9.5 | **Template reality (current snapshot)** | 27 active templates · **26 fire backtests** · 1 xfail (`inside-bar-breakout`) · 2 deactivated (`vwap-bounce`, `camarilla` — need real-Dhan 30d verify) · 86 unbuilt placeholders. | active rollout |
| 9.6 | **Next obvious sprint — Queue FFF (proposed)** | A5 credential factory + drain + 22-symbol backfill execution. The end-to-end backfill capstone of Queue CCC Phase 3. ~2h with plan-first gate trail. | proposed |
