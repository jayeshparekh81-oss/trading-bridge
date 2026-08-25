# B3 — Paywall Enforcement: Implementation Plan (no code)

**Status:** plan for review. Build module-by-module after sign-off.
**Recon basis:** see this session's B3 recon. Today there is **no plan-based gate** —
every premium surface sits behind `get_current_active_user` only; B2's
`plan_status`/`active_plan_id`/`plan_expires_at` are read nowhere.

## Guiding invariants (apply to every module)
- **Billing ⟂ RBAC.** The gate reads `plan_status` + `plan_expires_at` ONLY.
  It NEVER reads or writes `role`, `is_admin`, or `live_trading_enabled`.
- **Sacred/execution paths are NEVER gated.** Webhook (`strategy_webhook`),
  `live_orders`, `kill_switch`, `brokers`, `strategy_executor`, `direct_exit` —
  no plan dependency, ever. Gating execution on billing is forbidden.
- **Fail-open to free.** Free surfaces are never gated. A user who is
  `none`/`expired`/`cancelled` (or anything unexpected) keeps full FREE access.
  The dependency only *grants* premium to `active` + non-expired users.
- **Default OFF.** The whole enforcement is behind a feature flag that defaults
  to OFF, so merging/deploying any B3 module changes nothing in prod until the
  flag is flipped.
- No migration in B3 — B2 already shipped the columns (alembic head `032`).

---

## 1. Feature flag — `PAYWALL_ENFORCED` (default OFF)
- New setting `PAYWALL_ENFORCED: bool = False` in app settings, env-driven —
  same pattern as the existing global `LIVE_TRADING_ENABLED` flag.
- **OFF** ⇒ `require_active_plan` is a pure pass-through (identical to
  `get_current_active_user`); backtest returns all sections. = today's behavior,
  everyone sees all.
- **ON** ⇒ enforcement active.
- **Why:** (a) decouples *shipping* the code from *turning it on* — land all
  modules now, flip when Razorpay (B4–6) can actually mint `active`; (b) instant
  global kill-switch → flip OFF to fail-open everyone if a gate ever wrongly
  locks users out.
- **Toggle mechanism:** env var → container recreate (a normal cutover). Baseline
  recommendation is the env/Settings flag (matches `LIVE_TRADING_ENABLED`). If a
  *runtime* (no-recreate) kill is required, back the flag with Redis/DB instead —
  call out at build time; default plan is env.
- The flag is read in exactly two places: `require_active_plan` (§2) and the
  backtest response-gating (§6). One helper (`paywall_enforced()`), one source of
  truth.

## 2. `app/auth/entitlements.py` — `require_active_plan`
New module, parallel to `app/auth/roles.py` but independent of the role track.

- `require_active_plan` composes on `get_current_active_user`, so 401 (auth) and
  403 (inactive account) fire first, unchanged.
- Logic:
  - if `not paywall_enforced()` → return user (pass-through).
  - else compute `entitled = (plan_status == "active") AND (plan_expires_at is
    None OR plan_expires_at > now_utc())`.
  - `entitled` → return user; otherwise raise the paywall response (§3).
- **Fail-open semantics (explicit):**
  - `none` / `expired` / `cancelled` / unknown → NOT entitled → premium denied,
    but these users retain **all FREE access** because free endpoints never call
    this dep.
  - Expiry is checked **inline** (`plan_expires_at < now` ⇒ treated as free) so
    correctness does not depend on a future "expire sweep" job (that job is B4–6).
  - On any ambiguity/error (null/garbage status, flag read failure) → behave as
    free / flag-OFF. Never 500, never hard-lock.
- **Placement rule (hard):** attach ONLY to premium endpoints in §4/§6. NEVER on
  `get_current_active_user`, free endpoints, `auth`, `onboarding`, `system`,
  `pricing`, or any sacred/execution path.

## 3. Paywall response — machine-distinguishable
- **Decision: HTTP `402 Payment Required` + body `{"detail": {"code":
  "PLAN_REQUIRED", "message": <Hinglish>, "upgrade_url": "/pricing"}}`.**
- **Why 402:** it is the HTTP status literally reserved for "payment required,"
  so it is unambiguously distinct from `401` (not authenticated) and `403`
  (authenticated-but-forbidden / RBAC). The frontend can branch on status alone
  to render the upgrade wall — no string matching.
- **Why also a `code` field:** the typed `code: "PLAN_REQUIRED"` is the real
  contract. If any infra in front of the API (CDN/WAF/proxy) mishandles the
  uncommon `402`, we can fall back to `403` + the same `code` with a one-line
  change and the frontend keeps working off `code`. Status is the signal, `code`
  is the guarantee.
- Centralize the raise in one helper so all premium endpoints emit an identical,
  testable shape.

## 4. Gate the 3 clean premium endpoints (own PR)
Swap `get_current_active_user` → `require_active_plan` on exactly these
(all currently active-user-only):

1. **Analytics**
   - `GET /api/users/me/trades/stats`  (`app/api/users.py`)
2. **Complete trade history**
   - `GET /api/strategies/executions`  (`app/strategy_engine/api/strategies.py`)
   - `GET /api/users/me/trades`  (`app/api/users.py`)
   - `GET /api/users/me/trades/export`  (`app/api/users.py`)
3. **Transparency Ledger**
   - `GET /api/marketplace/listings/{id}/ledger`  (`app/strategy_engine/api/marketplace.py`)
   - `GET /api/marketplace/listings/{id}/ledger/history`
   - `POST /api/marketplace/listings/{id}/ledger/verify`  *(confirm at build: same premium surface — include unless product wants verify free)*

These are clean because each is a dedicated premium endpoint — a one-line dep
swap, no response reshaping. (Backtest is the exception → §6.)

## 5. `UserResponse` — expose plan fields (prerequisite)
- Add to the `/api/users/me` response (`UserResponse`): `plan_status`, plan
  `tier`/name (via the `active_plan` view-only relationship → plan name/tier),
  and `plan_expires_at`.
- Additive, safe, no enforcement by itself. Prerequisite for the frontend to
  label the current plan and render walls (§8).
- Land in the foundation PR so frontend can build against it early.

## 6. Backtest — response-field gating (RISKIEST → isolated PR)
The single endpoint `POST /api/strategies/{id}/backtest` returns one
`BacktestResponse` bundling FREE-basic + PREMIUM-advanced. Do NOT 402 it (that
would kill free basic backtest).

- **When NOT entitled (flag ON + plan not active):** null out the PREMIUM
  sections; leave the BASIC result untouched and the HTTP 200 intact.
- **Field split (confirm exact boundary with product before build):**
  - BASIC (always returned): the core backtest result (PnL, win rate, trade
    count, basic equity/trade list).
  - PREMIUM (→ `None` when not entitled): `reliability`, `health_card`, `truth`,
    `regime`, `deviation`, `trade_quality`, `diagnosis`. (Open question to
    confirm: is the equity-curve chart basic or premium?)
- These fields are already `Optional`/`| None` in the response model, so nulling
  them is contract-safe; frontend must render an upgrade placeholder where a
  premium panel's data is `None` (coordinate with §8).
- **Why isolated:** it's response-shaping (not a clean dep swap), it's the only
  endpoint where a wrong split breaks a FREE feature, and it needs the frontend
  to handle null panels. Its own PR = small blast radius, independent review,
  independent revert.

## 7. Admin set-plan endpoint (testing + provisioning)
- **Decision: add a small admin-gated endpoint** —
  `PUT /api/admin/users/{user_id}/plan`, behind `get_current_admin`/`require_admin`,
  setting ONLY `plan_status` / `active_plan_id` / `plan_expires_at`.
  - Validates the `plan_status` vocabulary and the `active_plan_id` FK; writes an
    audit-log row; **does NOT touch** `role` / `is_admin` / `live_trading_enabled`.
- **Why an endpoint (not just psql):** (a) needed to provision an `active` test
  user to verify the paywall *before* Razorpay exists; (b) it's the interim
  comp/support provisioning path until the Razorpay webhook lands, and remains a
  useful admin override after; (c) mirrors the existing `toggle_active` /
  `toggle_admin` admin pattern, so it's small and consistent.
- **Fallback:** manual psql (`UPDATE users SET plan_status=…, active_plan_id=…,
  plan_expires_at=…`) unblocks testing immediately and is the break-glass path if
  we choose not to build the endpoint. Document it in `ADMIN_PROVISIONING.md`
  either way.
- Isolated, tiny PR; can land right after the foundation so QA can flip test
  users without psql.

## 8. Frontend upgrade-wall component (UX-only)
- A `PaywallGate` / `UpgradeWall` component + an "Upgrade" CTA → `/pricing`.
- **Reactive, not proactive:** walls trigger on the **backend signals** — a
  `402 PLAN_REQUIRED` response, or a `None` premium section in the backtest
  payload — NOT proactively on `plan_status` alone. This guarantees the frontend
  never locks anyone out while the flag is OFF (flag OFF ⇒ backend returns 200 /
  full sections ⇒ no wall). `plan_status` from `/me` (§5) is used only for
  *labeling* (current plan, CTA copy).
- Backend remains the single source of truth; this layer is cosmetic.

## 9. Tests (MANDATORY)
Backend matrix (per gated endpoint + the dep unit):
1. **Lockout guard (critical):** `plan_status='none'` user passes ALL free
   endpoints (strategies list/detail, marketplace browse, basic-backtest core
   fields present) — under flag ON *and* OFF.
2. **Flag OFF ⇒ everyone sees all:** `none`/`active`/`expired` all get 200 on
   premium endpoints and full backtest sections. (current behavior preserved)
3. **active + non-expired ⇒ premium granted:** 200 + advanced sections present.
4. **none ⇒ premium blocked:** 402 `PLAN_REQUIRED`; backtest advanced = null,
   basic present.
5. **expired-treated-free:** `plan_status='active'` but `plan_expires_at` in past
   ⇒ premium blocked / advanced null (NOT a lockout of free).
6. **cancelled ⇒ premium blocked** (same as none).
7. **Independence:** the dep never changes `role`/`live_trading_enabled`;
   asserts billing ⟂ RBAC.
8. **Admin set-plan:** sets only plan fields, rejects bad status vocab, validates
   FK, audit-logs, leaves `role`/`is_admin`/`live_trading` untouched.
9. **`/me` shape:** returns `plan_status` + tier + expiry.
10. **Sacred-path regression:** webhook/live_orders/kill_switch endpoints have no
    plan dep (assert they don't import/use `require_active_plan`); existing
    suites stay green; ruff/format clean on touched files; no new pytest-baseline
    failures.

## 10. PR split, sequencing, deploy
All backend PRs land with `PAYWALL_ENFORCED=OFF` ⇒ each is a behavior-neutral,
independently revertable cutover. No migration (B2 columns already live).

| PR | Scope | Risk | Depends on |
|----|-------|------|-----------|
| **B3.0 Foundation** | `PAYWALL_ENFORCED` flag + `entitlements.py` `require_active_plan` (wired to nothing) + `UserResponse` plan fields (§5) + dep unit tests | Low (inert) | — |
| **B3.1 Admin set-plan** | `PUT /api/admin/users/{id}/plan` (§7) + tests | Low | B3.0 |
| **B3.2 Gate clean endpoints** | dep swap on the 3 surfaces (§4) + tests incl. lockout guard | Med | B3.0, (B3.1 for QA) |
| **B3.3 Backtest field-gating** | response nulling (§6) + tests; **isolated** | **High** | B3.0 |
| **B3.4 Frontend walls** | `PaywallGate`, reactive on 402/null (§8) | Low (UX) | B3.0 deployed (for `/me` fields) |

**Sequencing:** B3.0 → B3.1 → B3.2 → B3.3, then B3.4 once `/me` fields are in
prod. B3.1 before B3.2/B3.3 so QA can provision an `active` test user (or use
manual psql to start earlier).

**Per-module deploy:** each backend PR is a standard `release-cutover-N`
(build → no migration → recreate → verify per `DEPLOY.md` §6). Because the flag
is OFF, every deploy is a no-op for users; verify only that nothing regressed
(sacred BSE `89423ecc` untouched, free + premium endpoints still 200).

**Go-live flip (separate, after B4–6 can mint `active`):**
1. In staging/canary: set a test user `active` (B3.1), flip `PAYWALL_ENFORCED=ON`,
   run the full §9 matrix live (free user keeps free; active gets premium; expired
   falls back to free).
2. Flip ON in prod (env + recreate). Watch for any wrongful 402s on free users.
3. **Kill-switch:** if anything locks free users out, flip OFF (fail-open
   everyone) immediately and diagnose.

**Sacred path:** untouched in every module. No change to webhook/live_orders/
kill_switch/brokers/executor; BSE `89423ecc` / cutover-15 stack unaffected.

## Open questions for sign-off
- §3: confirm `402` (vs `403` + `code`) is acceptable through your edge/CDN.
- §6: confirm the exact BASIC vs PREMIUM field boundary (esp. equity curve).
- §4: is `POST .../ledger/verify` premium, or should verify stay free?
- §7: admin set-plan endpoint — build it, or manual-psql only for now?
- §1: env flag (recreate to toggle) acceptable, or do you want a runtime
  (Redis/DB) kill-switch?
