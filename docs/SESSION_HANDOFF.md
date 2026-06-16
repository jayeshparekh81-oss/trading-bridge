# TRADETRI — Session Handoff (paste into any new chat)

**Last updated:** 2026-06-16 — **Queue HHH SHIPPED: all 6 admin pages (M1/M3–M7) + webhooks (M2) MERGED & LIVE on tradetri.com**; `origin/main` = `1919265`. Still scaffolded/unmerged: analytics (M9 #24), settings (M8 #25), alerts (M10, no PR).

Paste this whole file into a fresh Claude session before asking for anything. It is the single living source of truth — overwritten each session-end, never appended.

---

## 0. CURRENT STATE — Sunday 2026-06-14 (START HERE)

> Newest state on top. Sections 1–9 below are the CCC/FFF weekend history — still accurate, lower priority for the next session.

### 0.1 — Where everything stands

- **`origin/main` = `1919265`** — Queue HHH shipped 2026-06-15/16: **M1 auth-guard (#18), M2 webhooks (#26), M3 users (#19), M4 announcements (#20), M5 audit (#21), M6 kill-switch-events (#23), M7 admin-home (#22) all MERGED & LIVE on tradetri.com.** Plus: test-pollution baseline #29, webhooks modal URL fix #31, nav SOON-badge removal #30.
- **Prod frontend (Vercel) continuously auto-deploys `main`** → tradetri.com is at `1919265` now. (The old "cutover-9" frontend framing in §2 is stale — frontend tracks `main`.)
- **EC2 prod backend = `cutover-12` / `a63d5e8`** — ⚠️ **NOT cutover-8; the §2 "Production state" row is STALE** (verified live: prod `git describe` = `release-cutover-12`). Real-Dhan go-live = backend jump **`cutover-12` → `main`** (smaller than the docs claimed). Backend API surface is byte-identical `cutover-12 ↔ main`, so every merged frontend page calls only already-live endpoints.
- **Webhooks caveat:** the modal now hands the working `…/api/webhook/strategy/<token>` URL (built client-side). The backend `create_webhook` (`users.py:387`) still returns the wrong relative legacy URL → tracked in §6 for the Phase-2 backend deploy.
- **A5 drain** still blocked only on EC2 deploy + `BACKFILL_ENABLED` flag (Phase 2). No code work left.
- **BSE LTD `89423ecc` LIVE, `is_paper=FALSE`** — untouched throughout. Must stay untouched.

### 0.2 — Queue HHH: SHIPPED (admin + webhooks live; settings/analytics/alerts pending)

The 9 Coming-Soon pages — built overnight, then founder-reviewed + merged 2026-06-15/16. **Admin track + webhooks are MERGED & LIVE on tradetri.com** (behind the M1 auth-guard for `/admin/*`).

| Module | Page | PR | State |
|---|---|---|---|
| **M1** admin auth guard | `(dashboard)/admin/layout.tsx` | #18 | ✅ MERGED & LIVE — redirects non-admins (`router.replace("/")` + skeleton) |
| **M2** webhooks | `/webhooks` | #26 (+#31 URL fix, +#30 nav) | ✅ MERGED & LIVE — TradingView token CRUD |
| **M3** admin users | `/admin/users` | #19 | ✅ MERGED & LIVE — functional read-only user list |
| **M4** admin announcements | `/admin/announcements` | #20 | ✅ MERGED & LIVE |
| **M5** admin audit | `/admin/audit` | #21 | ✅ MERGED & LIVE |
| **M6** admin kill-switch-events | `/admin/kill-switch-events` | #23 | ✅ MERGED & LIVE |
| **M7** admin home | `/admin` | #22 | ✅ MERGED & LIVE — system-health tiles + nav cards |
| **M9** analytics | `/analytics` | #24 | 🟡 OPEN, NOT merged — scaffolded (recent-100-trades; full-history flagged) |
| **M8** settings | `/settings` | #25 | 🟡 OPEN, NOT merged — scaffolded |
| **M10** alerts | `/alerts` | (no PR) | 🟡 NOT merged — storage only, **engine NOT built**; needs **migration 031** + alerts router on EC2 (else 404s) |

All merged admin pages call already-live `/api/admin/*` endpoints (verified vs the cutover-12 prod OpenAPI). Each merge was frontend-only + a proactive `prettier@3` style fix; no backend/sacred change.

⚠️ **migration 031_alerts** still LOCAL-dev + M10-branch only. **NOT on `main`/prod.** Alerts must NOT merge until its backend (alerts router + mig 031) ships, or the page 404s.

### 0.3 — NEXT-SESSION PLAN

**PHASE 1 — HHH review + merge: ✅ MOSTLY DONE.** Merged & live: M1, M2 webhooks, M3–M7 admin. **Remaining (founder review + merge, one PR each):** **M9 analytics (#24)**, **M8 settings (#25)**. **M10 alerts** stays unmerged until its backend ships (mig 031 + alerts router on EC2).

**PHASE 2 — Real-Dhan go-live** (GATED deploy; founder gates every step; NOT autonomous):
1. **DB backup FIRST**, then full backend deploy **`cutover-12` → `main`** (health check, verify BSE LTD intact). This deploy ALSO lands: the `users.py:387` webhook-URL fix (§6), and the alerts backend if M10 is merged by then.
2. Apply **migrations 029 + 030** (+ **031** if alerts merged) on EC2 (dev → staging → prod; **before-migrations hard-stop**).
3. Configure creds: `BACKFILL_DHAN_USER_ID` (β tier) **OR** `BACKFILL_DHAN_CLIENT_ID` + `BACKFILL_DHAN_ACCESS_TOKEN` (α tier).
4. Restart `celery_worker` + `celery_beat` (**before-restart hard-stop**).
5. Flag `BACKFILL_ENABLED=true` → drain **1–2 symbols first** (not all 22) → verify real data.
6. **CONFIRM BSE LTD `89423ecc` untouched.**

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
| **Queue III — fix `test_placeholder` pollution** ⚠️ **NOT DONE** | The baseline of `tests/test_main.py::TestRouters::test_placeholder_prefixes_registered` in `ci/known_failures.txt` (added 2026-06-16) is **TEMPORARY**. To-do: stand up local PG/redis → run the full DB-backed suite → bisect the DB-dependent polluting test → fix its teardown/fixture isolation → **un-baseline** (remove the line). Proof it's pollution, not a regression: `git diff 62f84f3..68e144c -- backend/` is empty (no backend change); the test passes in isolation, whole-module, and full **local** suite; it fails **only** under CI's DB-backed ordering; and live `cutover-8` serves `/health` fine. |
| **Webhook URL backend bug** ⚠️ **NOT DONE (Phase 2 backend deploy)** | `create_webhook` in `backend/app/api/users.py:387` returns `webhook_url = f"/api/webhook/{raw_token}"` — the **legacy, relative** path that **404s on prod** (legacy route unmounted while `STRATEGY_PAPER_MODE=true`; correct mounted route is `/api/webhook/strategy/{token}`). Frontend modal now **works around it** (constructs `https://api.tradetri.com/api/webhook/strategy/${token}` client-side — shipped 2026-06-16). Backend fix: change `users.py:387` to return the absolute `…/api/webhook/strategy/…` URL — land in the **next backend deploy (Phase 2)**, then the workaround can be simplified. |
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
