# 44 pre-existing test-failure triage

**Branch:** `chore/test-triage` · **Date:** 2026-06-17 (overnight, unattended) · **Tests fixed: 0** (rationale below — the triage found several failures are catching **real changes**, not test debt; auto-editing them would mask the change).

Source: the 44 nodeids in `ci/known_failures.txt`. Local full-suite run (macOS, no DB) reproduced 68 failures — the extra ~23 are **local-only** (no Postgres/Redis on this box) and pass in CI (CI is green = current failures ⊆ the 45-allow-list), so they are pure local-env artifacts, not triaged here.

## Categories

### A. Environmental — need real Postgres/Redis (26) — **leave baselined**
- `tests/integration/test_live_order_flow.py` ×13
- `tests/backtest_extension/test_api.py` ×6
- `tests/integration/test_strategy_webhook_paper_e2e.py` ×2, `test_reconciliation_loop.py` ×2, `test_telegram_alerts.py` ×1, `test_strategy_webhook_tv_ip_bypass.py` ×1

These need asyncpg/aioredis behaviour + real cross-session visibility (`docker-compose-test.yml`). They error without a DB and are correctly baselined. **No action** — they pass in a DB-equipped CI/container; they are not bugs. (The HMAC-401 ones also depend on `webhook_require_hmac` defaulting differently — env, not logic.)

### B. CI-environment pollution (1) — see Module A
- `tests/test_main.py::TestRouters::test_placeholder_prefixes_registered` — flaky router-registration pollution, CI-env-specific. Full analysis in `docs/QUEUE_III_POLLUTION_ANALYSIS.md` (branch `chore/queue-iii`). **Leave baselined** (TEMPORARY).

### C. Seed-data drift (4) — **FOUNDER DECISION needed (test stale vs seed regression)**
| Test | Failure | Read |
|---|---|---|
| `test_seed_shape.py::test_active_count_is_45` | `assert 27 == 45` | seed now has **27 active** templates; test hardcodes 45. **27 matches MASTER_CONTEXT §7 ("27 active")** → test likely just stale. |
| `test_seed_shape.py::test_inactive_equity_count_is_5` | `assert 23 == 5` | 23 inactive-equity now vs 5 expected — seed evolved. |
| `test_seed_shape.py::test_inactive_entries_have_empty_config_json` | inactive `pdh-pdl-breakout` has non-empty `config_json` | a deactivated template kept its config — seed-shape invariant violated. |
| `test_seed_shape.py::test_active_template_slugs_match_spec` | active slugs drifted (missing `heikin-ashi-trend`, `bollinger-pct-b-extreme`, `keltner-channel-…`) | spec list vs seed diverged. |

**Why not auto-fixed:** these are *seed-vs-test* drift. If the current seed (27 active) is **intentional**, update the tests to the new counts/slugs (a clean test-only fix). If templates were **wrongly deactivated**, the tests are correctly failing and the **seed** must be fixed. That intent call is the founder's — editing the tests blind risks cementing a seed regression. **Recommendation:** confirm 27-active is intended, then update `test_seed_shape.py` constants (45→27, 5→23, refresh the slug spec) and un-baseline these 4.

### D. "coming_soon → active" indicator-status change (9) — **POSSIBLY REAL, do not auto-fix**
- `compliance/test_evaluator.py` ×4 (`assert 'active' == 'coming_soon'`, scores `100` vs `90`/`80`, `0` vs `1`)
- `indicator_admin/test_resolver.py` ×3 + `test_approval_lifecycle.py` ×1 (`assert 'active' == 'coming_soon'`)
- `strategy_engine/api/test_compliance.py` ×2 (downstream of the same)

**Single root cause:** indicators the tests expect to resolve as `coming_soon` now resolve as `active`, so the coming-soon compliance penalty (which would drop scores to 90/80) no longer applies → score 100. This is a **behaviour/data change**, not test debt. It is **intentional if** indicators were genuinely promoted to active; it is a **regression if** the coming-soon resolver or seed status broke. **Recommendation:** founder confirms whether those indicators are intended `active`. If yes → update the test fixtures' expected status; if no → the resolver/seed has a regression these tests correctly caught. **Do NOT mask by editing tests until intent is confirmed.**

### E. Kill-switch task removed/renamed (2) — **sacred-adjacent, do not touch**
- `test_celery_tasks.py::TestAutoSquareOff::test_runs` — `AttributeError: module 'app.tasks.kill_switch_tasks' has no attribute 'auto_square_off_intraday'`
- `test_celery_tasks.py::TestCeleryApp::test_beat_schedule_populated` — `'auto-square-off'` missing from the beat schedule

`auto_square_off_intraday` no longer exists in `kill_switch_tasks`. Either renamed (test stale) or removed (a real change to the kill-switch/square-off path — **sacred zone: `kill_switch_*`**). **Do NOT edit** without the founder confirming the square-off task's current name/wiring. Flagged for review — this touches live-trading risk controls.

### F. Registry subset drift (1)
- `strategy_engine/test_registry.py::test_beginner_recommended_subset` — the beginner-recommended indicator set drifted from the test's expected set. Registry-data change; founder confirms the intended beginner set, then update the test. Low risk but still a "which-is-right" judgment.

### G. Product-type default changed (1) — 🔴 **SACRED, do not touch**
- `test_strategy_engine.py::test_resolve_product_type_default_intraday_when_missing` — `assert <ProductType.MARGIN> is <ProductType.INTRADAY>`. `_resolve_product_type` now defaults to **MARGIN** where the test expects **INTRADAY**. This is **strategy-execution / F&O product-type logic** (FUTURES = NRML/MARGIN only is a sacred rule). The test failing may be **correctly catching** a deliberate default change — or a regression. **Absolutely do not edit the test or the resolver** unattended. Founder must confirm the intended default; this is exactly the kind of behaviour the sacred rules protect.

## Bottom line
- **Genuinely "clearly test-only and safe to fix unattended": none.** The seed-shape four (C) are the closest, but each carries seed-regression risk and several (D/E/G) are catching real, possibly-intentional changes in compliance/kill-switch/product-type areas — masking them by editing tests would be harmful.
- **Highest-value follow-ups for the founder (attended):** (1) confirm 27-active seed is intentional → fix the 4 seed-shape tests; (2) confirm the coming_soon→active indicator promotion → fix the 9 compliance/resolver tests or fix the resolver; (3) **review E (kill-switch square-off removal)** and **G (product-type default INTRADAY→MARGIN)** — these are risk-control/sacred areas where a failing test is a feature, not debt.
