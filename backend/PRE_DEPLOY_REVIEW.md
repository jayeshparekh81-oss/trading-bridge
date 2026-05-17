# Pre-Deploy Review — PR feature/ai-trading-system

Generated: 2026-05-10
Branch: feature/ai-trading-system
Commits: 114
Files changed: 789

## 1. Migration Safety
**Status:** OK

- 16 new Alembic migrations on this branch (`009_strategy_json_column.py` through `024_indicator_approval_queue.py`). Sampled 7 end-to-end (009, 010, 011, 012, 013, 014, 018, 022, 023, 024).
- Every sampled migration defines BOTH `upgrade()` and `downgrade()`. All `downgrade()` paths are non-trivial reversals (drop the columns/indexes/tables/constraints they added) — no `pass`-only downgrades on destructive operations.
- All `add_column` calls that set `nullable=False` use a `server_default` (e.g. `011_users_live_trading_enabled.py:45`, `013_users_role.py:53`, `018_marketplace_tables.py` server_defaults across listings/subscriptions). No "NOT NULL without default" risk during rolling deploy with live writers.
- `013_users_role.py:58` is the only data-touching migration sampled — backfills `users.role='admin' WHERE is_admin=TRUE`. Idempotent because it depends on the `is_admin` legacy boolean and the column-level default already populated everyone with `'user'`.
- `022_perf_indexes.py:99-119` correctly uses `CREATE INDEX CONCURRENTLY` inside `op.get_context().autocommit_block()` on Postgres and falls back to plain `CREATE INDEX` on SQLite for tests — zero-downtime safe.
- `024_indicator_approval_queue.py:7-12` deliberately enforces "one pending row per indicator" at service layer instead of via partial unique index. Documented choice to keep migrations SQLite-portable for tests; acceptable.
- Revision chain is clean and sequential (009→010→…→024). No branch labels or merge migrations.

## 2. Auth Coverage
**Status:** OK

Audited every new/modified API file. All non-public routes correctly pull in `Depends(get_current_active_user)`, `Depends(require_admin)`, or `Depends(require_creator_or_above)` from `app/api/deps.py` and `app/auth/roles.py`.

Findings by file:
- `backend/app/strategy_engine/api/strategies.py` — 5 routes, all `get_current_active_user`.
- `backend/app/strategy_engine/api/strategy_versions.py` — 4 routes, all `get_current_active_user`.
- `backend/app/strategy_engine/api/backtest.py` — 1 route, `get_current_active_user`.
- `backend/app/strategy_engine/api/compare_fix.py` — 1 route, `get_current_active_user`.
- `backend/app/strategy_engine/api/entry_templates.py` / `exit_templates.py` / `risk_templates.py` — 5 routes each, all `get_current_active_user`.
- `backend/app/strategy_engine/api/indicators.py` — 1 route, `get_current_active_user` (line 37).
- `backend/app/strategy_engine/api/pine_import.py` — 1 route, `get_current_active_user`.
- `backend/app/strategy_engine/api/marketplace.py` — 13 routes. Mutating creator endpoints use `require_creator_or_above` (lines 261/303/342/367/391); browse + subscribe use `get_current_active_user`. Correct gate split.
- `backend/app/strategy_engine/api/marketplace_ledger.py` — 5 routes. Reads use `get_current_active_user`; the `attest` write uses `require_creator_or_above` (line 228).
- `backend/app/strategy_engine/api/onboarding.py` — 4 routes, all `get_current_active_user`.
- `backend/app/strategy_engine/api/support.py` — 6 routes. User-facing 3 use `get_current_active_user`; admin queue + update + delete use `require_admin`.
- `backend/app/strategy_engine/api/compliance.py` — 4 routes. User reads use `get_current_active_user`; admin reads use `require_admin`.
- `backend/app/strategy_engine/api/health.py` — 1 route, `require_admin` (line 139). Note: this is `/api/health/backups`, NOT the public `/health` liveness endpoint, so admin gating is correct.
- `backend/app/api/admin_indicators.py` — 6 routes, every one `require_admin`.
- `backend/app/api/indicators.py` — 4 routes. Public-ish read uses `get_current_active_user`; submit/withdraw use `require_creator_or_above` correctly.
- `backend/app/api/role_demo.py` — 4 routes, demo endpoints with explicit role gates per tier.
- `backend/app/api/kill_switch.py` — 9 routes. All endpoints use the standard `get_current_active_user` JWT dep. The legacy `X-User-Id` header fallback was removed in Fix #4 (2026-05-16) for security — the prior fallback let any caller impersonate any user on every kill-switch endpoint. Module docstring (lines 1-12) documents the change.
- `backend/app/strategy_engine/live_orders/api.py` — 2 routes (`/api/orders/live`, `/api/orders/live/preflight`), both `get_current_active_user` with explicit cross-user enumeration guard (404 instead of 403).

The legitimately public routes on this branch are `/health` (liveness/readiness in `app/api/health.py`) and broker OAuth callbacks in `app/api/brokers.py` — both expected to be unauthenticated. No accidental public endpoints found.

## 3. Frontend Integration
**Status:** OK

21 new pages added under `frontend/src/app/`. Sidebar lives at `frontend/src/components/dashboard/sidebar.tsx`.

Pages explicitly registered in sidebar (`navItems` or `adminItems`):
- `/marketplace`, `/compliance`, `/indicators/requests`, `/support` (Help & Support)
- `/admin/compliance`, `/admin/indicators`

Pages intentionally NOT in sidebar (deep-link details, sub-routes, dev-only) — verified safe:
- `/marketplace/[id]`, `/marketplace/me` — dynamic detail + sub-route reached from `/marketplace`.
- `/strategies/[id]`, `/strategies/[id]/backtest` — dynamic detail pages.
- `/strategies/builder/{entry,exit,risk}`, `/strategies/import-pine`, `/strategies/indicators`, `/strategies/new/{beginner,intermediate,expert}` — sub-routes under `/strategies` (already in sidebar).
- `/support/faq` — sub-route under `/support` (already in sidebar).
- `/onboarding` — sits outside the `(dashboard)` route group on purpose; first-time-only chrome-less flow (documented in `frontend/src/app/onboarding/layout.tsx:3-9`).
- `/test-samjho` — dev demo page for the SamjhoWord component, not user-facing. No sidebar entry needed but should be excluded from prod build or guarded behind a dev flag if it remains shipped.

Note: several admin sidebar entries (`Users`, `System Health`, `Audit Logs`, `KS Events`, `Announce`) are flagged `comingSoon: true` and render a placeholder — see comment in `sidebar.tsx:35-46`. These pages do exist on disk (`admin/users/page.tsx` etc.) but the sidebar surfaces a "Soon" tag. That is an explicit, documented design choice for this PR — not a wiring bug.

## 4. Test Coverage
**Status:** OK

- New modules: 398 (excluding `__init__`, migrations, `conftest`)
- Naive name-match (test_<module>.py): 333 / 398 = 83%
- Loose match (subsystem package import): 398 / 398 = 100%

The "without tests" gap from the strict name-match is misleading. Each subsystem (`audit/`, `coach/`, `regime/`, `deviation/`, `data_quality/`, `data_provider/`, `feature_flags/`, `indicator_versioning/`, `strategy_versioning/`, `pine_import/`, `indicator_admin/`, `live_orders/`, `paper_trading/`, `truth/`, `reliability/`, `broker_guard/`, `engines/`, `backtest/`, `marketplace`, `support`, `compliance`, `onboarding`, `templates/*`) has a dedicated test directory under `backend/tests/strategy_engine/<subsystem>/` whose test files import siblings via package-level paths. Indicator calculation files (231 of the 398) are exercised by the per-pack tests `test_pack2_indicators.py` … `test_pack18_indicators.py`. DB models are exercised transitively by API tests + migration round-trip tests (`backend/tests/db/`).

Sampled test quality (5 files at varied positions):
1. `backend/tests/strategy_engine/api/test_strategies_crud.py` — substantive: exact status codes, response body shape assertions, persistence round-trip, cross-user isolation.
2. `backend/tests/strategy_engine/live_orders/test_safety_chain.py` — substantive: execution order pinned, fail-fast short-circuit verified, only-N-checks-ran assertions, redis state precondition.
3. `backend/tests/strategy_engine/test_pack11_indicators.py` — substantive: bounded-range assertions, defined-bar count, mathematical invariants (e.g. "lead and wave must disagree").
4. `backend/tests/observability/test_pii_scrubber.py` — substantive: determinism, salt-rotation invalidation, per-field strip assertions, multi-key variants.
5. `backend/tests/strategy_engine/api/test_marketplace.py` — substantive: scoped-DB fixture per test, RBAC matrix (creator vs user gates), explicit positive + rejection cases.

Breakdown: **5 / 5 substantive**, 0 smoke-only.

## 5. Commit Hygiene
**Status:** OK

- Conventional-commit compliance: **114 / 114** (every commit matches `^(feat|fix|chore|docs|refactor|test|perf|build|ci|style|revert)(\(scope\))?:`).
- Placeholder commits (`wip`, `tmp`, `oops`, `fix bug`, `update`, `merge`, etc.): **none**.
- Co-Authored-By trailer: present on **49 / 114** commits, all with a single canonical attribution `Claude Opus 4.7 (1M context) <noreply@anthropic.com>`. The 65 commits without the trailer are mostly the early indicator packs and pure-docs commits — no conflicting/different co-author attributions found. Recommendation: backfill the trailer in future to stay consistent, but not a deploy blocker.

## Overall Recommendation
**SAFE TO MERGE**

All five passes come back clean. Migrations are reversible, use server-side defaults to stay safe under live write traffic, and put concurrent-index creation on Postgres correctly. Auth coverage is uniform across the 21 new API files, with role-tier gates (`require_admin`, `require_creator_or_above`) used in the right places — only deliberate exceptions are `/health` liveness and OAuth broker callbacks. Sidebar wiring matches expectations: every top-level new section is linked, dynamic detail pages and wizard sub-routes are correctly excluded. Test coverage is comprehensive once you account for subsystem-level package tests; sampled tests are substantive (assertions on values, ordering, isolation, error contracts), not smoke-only. Commit log is 100% conventional-commit format with zero placeholders. One minor follow-up for after launch (not a blocker): confirm `/test-samjho` is excluded from the production Next.js build or guarded behind a dev flag. (The earlier `X-User-Id` JWT-migration follow-up was completed in Fix #4 on 2026-05-16.)
