# Overnight autonomous chain — summary (2026-06-16 → 17)

Brutally honest. **Nothing was merged to `main`** (per instruction) — `origin/main` = `3aae1d8` (the PART-1 docs merge, #32). Everything below is on a branch for your review. No prod/EC2/Dhan touch, no migrations applied to prod, no sacred change, BSE LTD `89423ecc` untouched.

> Env note: I started **Docker Desktop** locally (was off) to attempt Module A's reproduction — it's left running, **no containers were brought up**, nothing to clean up.

## PART 1 — docs finalize ✅ DONE (merged)
MASTER_CONTEXT §10 HHH go-live row added; docs PR **#32 merged** → `main` = `3aae1d8`; SESSION_HANDOFF/MASTER_CONTEXT/PROJECT_MAP copied to `~/Desktop/`.

## Module-by-module

| Module | Branch | State | Your call in the morning |
|---|---|---|---|
| **A** Queue III pollution | `chore/queue-iii` | 📄 **Documented + STOPPED** | Read `docs/QUEUE_III_POLLUTION_ANALYSIS.md`. Decide if/when to reproduce-in-container + bisect. |
| **B** webhook-URL backend | `fix/webhook-url-backend` | ⚠️ **Fix DONE + tested, lint-diff RED** | Review the **B023 latent bug** (below), finish users.py ruff cleanup, then merge. |
| **C** test triage | `chore/test-triage` | 📄 **DONE (doc)** | Read `docs/TEST_FAILURES_TRIAGE.md` — several per-group **decisions** needed. Mergeable (docs). |
| **D** analytics | `feat/analytics-real` | ✅ **Backend DONE + tested**; frontend pending | Review the endpoint; build the `/analytics` UI on top; verify aggregation vs real DB. |
| **E** settings | — | ❌ **NOT BUILT (budget)** | Build plan below. |
| **F** alerts | — | ❌ **NOT BUILT (budget)** | Build plan below (note: M10 page + mig 031 already on `feat/hhh-alerts`). |
| **G** planning docs | `docs/overnight-chain` | 📄 **DONE** | Read `PLAN_REAL_DHAN_DEPLOY.md` (run it for Phase 2) + `PLAN_BILLING.md`. |
| **H** this summary | `docs/overnight-chain` | 📄 **DONE** | — |

### A — Queue III (`chore/queue-iii`)
**Premise was wrong:** the pollution is **NOT DB-related** — CI runs the suite with no Postgres/Redis (no `services:` block), same as local. It **fails in CI but passes locally**, so it's a CI-environment/collection-order flake that **cannot be reproduced or verified on this macOS box**. I did NOT apply a speculative fix or un-baseline (would risk turning CI red). The `app` fixture is function-scoped (fresh `create_app()`), so it's a module/import-level poisoning. Full reproduce-in-container + bisect plan is in the doc. **Baseline stays (correctly TEMPORARY).**

### B — webhook-URL backend (`fix/webhook-url-backend`)
- ✅ `users.py:387` now returns `https://api.tradetri.com/api/webhook/strategy/<token>` (was the relative legacy path that 404s on prod). Unit test added (mock_db) — **passes**.
- ✅ Added ruff `extend-immutable-calls` (FastAPI `Depends`/etc.) — the standard config — which cleared **37 pre-existing B008** false-positives on users.py (41 ruff errors → 4) and unblocks all future router-file edits.
- ⚠️ **lint-diff will be RED:** 4 PRE-EXISTING users.py errors in **unrelated** functions remain (the diff-scoped gate lints the whole changed file): import-sort (auto-fixable), 2× B904 (error handlers, safe `from None`), and 🐞 **a real latent bug: `B023` at `users.py:481` — a closure that doesn't bind loop variable `s`.** I did **not** auto-fix or `# noqa`-hide it (masking a latent bug unattended is wrong). **Action:** review/fix B023 + run `ruff check --fix` + `ruff format` on users.py, then lint-diff goes green and you can merge.

### C — test triage (`chore/test-triage`)
44 known failures triaged in `docs/TEST_FAILURES_TRIAGE.md`. **Fixed 0** — the triage *found real signal*: ~9 failures = a `coming_soon → active` indicator-status change (possibly intentional, possibly a resolver/seed regression); 2 = a **kill-switch `auto_square_off_intraday` task removal** (sacred-adjacent); 1 = **product-type default flipped INTRADAY→MARGIN** (🔴 sacred F&O logic). Editing those tests would *mask* the change. 4 seed-shape tests are stale-vs-seed (founder: confirm 27-active is intended → update tests). Per-group recommendations inside.

### D — analytics (`feat/analytics-real`) ✅ real deliverable
New additive **`GET /api/users/me/analytics/summary`** (`backend/app/api/analytics.py`) — full-history aggregation over the user's closed trades: totals, win-rate, best/worst, per-symbol, monthly P&L series. Mounted in `main.py`; `create_app()` still registers all 165 routes (no pollution); **ruff + format clean** on all 3 files; **2 unit tests pass**. Caught+fixed a real bug (`TradeStatus.FILLED` doesn't exist → `COMPLETE`/`SQUARED_OFF`). **CI should be green** (additive + clean). **Remaining:** wire the `/analytics` page to it (headline tiles + by_month chart + by_symbol table), and verify aggregation correctness against the DB-backed suite. **Not merged.**

### E — settings: NOT BUILT — build plan
Additive user-preferences backend. **Steps:** (1) net-new migration + `user_preferences` model (user_id PK/FK, timezone, date_format, theme/display prefs, created/updated) — **do NOT apply to prod**; (2) `GET/PUT /api/users/me/preferences` (additive, JWT-gated, **safe fields only** — timezone/display); (3) unit tests (mock_db, like analytics); (4) wire the `/settings` page. 🔴 **Explicitly excluded:** password change + 2FA — flag for a **separate security review**, do NOT build. Use the analytics module as the clean-additive template (Annotated deps → B008-clean).

### F — alerts: NOT BUILT — build plan
Storage + a non-production evaluation **skeleton**. Note `feat/hhh-alerts` (unmerged) already has the `/alerts` page + `alerts` model + **migration 031** + a basic CRUD router (storage-only). **Steps for a new `feat/alerts-build`:** (1) reuse/extend that storage; (2) add an evaluation **skeleton** (a function that, given a latest price, would mark `last_triggered_at`) **clearly flagged not-production — NO live notification/order path, NO celery wiring**; (3) tests for the storage + the pure-evaluation function; (4) keep migration 031 net-new, **NOT applied to prod**. 🔴 Never connect alerts to the order/notification path here.

## Honest caveats
- **Budget:** I completed A–D + G + H well; E + F are plans, not builds — they each need a net-new migration + DB-backed testing better done attended. I stopped rather than half-build them.
- **No branch's CI was polled** (push-only, you review). Expected: C/G/H green (docs), D green (clean additive), **B red** (the pre-existing users.py lint debt described above).
- **Nothing is merged.** All feature/fix branches await your review.
