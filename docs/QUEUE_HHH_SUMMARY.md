# Queue HHH — Coming-Soon page buildout summary

**Date:** 2026-06-13 (overnight chain after gate (d) + Queue FFF merges)
**Branches:** 10 feature branches pushed to origin; **none merged to main**. Founder reviews + clicks merge in the morning.
**Origin base for every branch:** `62f84f3` (current `origin/main`).

🔴 **No deploys, no main pushes, no Vercel pushes.** Every change lives on its own feature branch awaiting visual review.

---

## Status legend
| ✅ COMPLETE | Fully wired to real backend, tested, no important gaps. |
| 🟡 SCAFFOLDED | Wired end-to-end but with explicit scope notes / future-sprint flags shown inline on the page. |

---

## M1 — Admin auth guard

**Branch:** `feat/hhh-admin-auth-guard` · **HEAD:** `35e5b2f` · **Status:** ✅ COMPLETE

### What changed
- New file: `frontend/src/app/(dashboard)/admin/layout.tsx` (~57 LOC).
- Wraps every `/admin/*` route with a `useAuth()`-based client-side guard.
- isLoading → DashboardSkeleton · `!isAuthenticated` → redirect `/login` · `!user.is_admin` → toast (Hinglish) + redirect `/`.

### Design note (important context)
Founder's brief said `frontend/src/middleware.ts`. That doesn't work in this codebase because the JWT is stored in `localStorage` (`lib/api.ts`), not cookies — Next.js middleware runs at the edge and **cannot read localStorage**. A cookie-mirror would require touching the login/logout flow, outside the additive-only contract for M1. **The layout-guard achieves the same UX goal** (block customers from seeing admin pages). Backend `require_admin` dependency on every `/api/admin/*` endpoint remains the actual security boundary.

### Morning visual-check
1. Log in as a NON-admin user.
2. Navigate to `/admin` (or any `/admin/*`).
3. Expected: brief skeleton flash → Hinglish toast "Yeh page sirf admins ke liye hai." → redirect to `/`.
4. Log in as an admin (`is_admin=true`). Navigate to `/admin/users`. Expected: page renders normally.

### Backend added
None.

### Production-ready?
**Yes**, for the UX layer. Defense in depth: pair with the backend 403s that already exist.

---

## M2 — /webhooks (customer-facing, TOP priority)

**Branch:** `feat/hhh-webhooks` · **HEAD:** `f74a785` · **Status:** ✅ COMPLETE

### What changed
- Replaced the Coming-Soon placeholder at `(dashboard)/webhooks/page.tsx` (~387 LOC).
- Wired to existing `GET/POST/DELETE /api/users/me/webhooks` — no new backend.
- Features: empty-state with CTA; list cards (label · status · id-prefix · created · last_used); Create dialog with label input; **one-time success modal** with prominent AlertTriangle banner and per-field Copy buttons for the webhook URL + token + HMAC secret; Revoke button per active webhook with browser confirm; TradingView setup hint card.
- Style matches `/brokers` verbatim (GlassmorphismCard + GlowButton + framer-motion stagger + sonner toast).

### Morning visual-check
1. Log in. Go to `/webhooks`. Empty state should show: "No webhooks yet" + CTA.
2. Click "Create webhook". Optional label (e.g. "Test alert"). Click Generate.
3. **CRITICAL UX:** the success modal must appear with the webhook URL, token, and HMAC secret. Click Copy on each — sonner toast confirms. Click "I've saved these".
4. Card now appears in list. Click Revoke → confirm → toast → card now shows "Revoked" badge.
5. **DO NOT** test create/revoke against production tokens — use the dev DB.

### Backend added
None.

### Production-ready?
**Yes**, for what's built. **Future-sprint flag** inline on the page: "Recent-hits audit panel is shipping in a future sprint." (the original Coming-Soon's reason).

---

## M3 — /admin/users

**Branch:** `feat/hhh-admin-users` · **HEAD:** `ccbd9dd` · **Status:** 🟡 SCAFFOLDED (read-only by intent)

### What changed
- Replaced the placeholder at `(dashboard)/admin/users/page.tsx` (~181 LOC).
- Wired to `GET /api/admin/users` (existing). Server-side search (email/name), 50-per-page pagination.
- Table columns: user (name + email) · status badge · role badge · joined relativeTime.

### Morning visual-check
1. Log in as admin. Go to `/admin/users`.
2. Expected: table populated with all platform users (paginated). Search by partial email or name.
3. Activate/role mutations are NOT in this build — the page is read-only by intent.

### Backend added
None.

### Production-ready?
**Yes for read-only.** Activation/deactivation/role mutations exist server-side (`PUT /admin/users/{id}/activate`, `/admin/{id}/admin`) but are NOT exposed in the UI here — deliberate scope limit to keep the page safe to click around. Adding those mutations is the natural next iteration.

---

## M4 — /admin/announcements

**Branch:** `feat/hhh-admin-announcements` · **HEAD:** `412e688` · **Status:** ✅ COMPLETE

### What changed
- Replaced the placeholder at `(dashboard)/admin/announcements/page.tsx` (~173 LOC).
- Wired to `POST /api/admin/announcements`.
- Textarea with 500-char counter (amber at 80%, red at 100%). Confirmation modal shows the exact preview before send. Sonner toast on success/failure. Last-send result surfaced inline.

### Morning visual-check
1. Log in as admin. Go to `/admin/announcements`.
2. Type a test message (e.g. "Test broadcast — please ignore"). Counter should update.
3. Click "Send to all active users". Confirmation modal opens.
4. **WARNING:** clicking "Confirm send" fires real notifications to every active user. Use only in dev.

### Backend added
None.

### Production-ready?
**Yes**, with the destructive-action warning. The dialog gives a clear preview + cancel path.

---

## M5 — /admin/audit

**Branch:** `feat/hhh-admin-audit` · **HEAD:** `522577f` · **Status:** ✅ COMPLETE

### What changed
- Replaced the placeholder at `(dashboard)/admin/audit/page.tsx` (~209 LOC).
- Wired to `GET /api/admin/audit-logs`.
- Two filter inputs (action token + user UUID), 50/page pagination. Tone-coded Action badge for common values (login / logout / kill_switch_trip / config_change / broker_connect); unknown actions get neutral tone. Truncates long resource_id and user_id to 8/12 chars with ellipsis.

### Morning visual-check
1. Log in as admin. Go to `/admin/audit`.
2. Table shows recent audit entries.
3. Try filter: type `login` in the Action filter. Type a user UUID in the User filter. List narrows.

### Backend added
None.

### Production-ready?
**Yes** for inspection. Doesn't support exporting/CSV — natural future iteration.

---

## M6 — /admin/kill-switch-events

**Branch:** `feat/hhh-admin-kill-switch-events` · **HEAD:** `fa5c586` · **Status:** ✅ COMPLETE

### What changed
- Replaced the placeholder (~205 LOC).
- Wired to `GET /api/admin/kill-switch-events`.
- Summary chips: events on this page · still-active count · all-time total. Per-row P&L formatting with `en-IN` locale (₹ + sign + comma grouping). Active-trip rows get a subtle loss-tone background and "Still tripped" badge; reset rows show "Reset N ago" badge.

### Morning visual-check
1. Log in as admin. Go to `/admin/kill-switch-events`.
2. If any kill-switch trips exist in dev DB, they should display with proper P&L formatting.
3. The summary chips (still-active, total) should update with the data.

### Backend added
None.

### Production-ready?
**Yes**. Operations-side admin view is fully wired.

---

## M7 — /admin home

**Branch:** `feat/hhh-admin-home` · **HEAD:** `732e04b` · **Status:** ✅ COMPLETE

### What changed
- Replaced the placeholder at `(dashboard)/admin/page.tsx` (~201 LOC).
- Wired to `GET /api/admin/system-health` for the 4 snapshot cards (active_users · orders_today · failed_today · error_rate_pct). Error-rate goes loss-tone when >5%; failed_today goes loss-tone when >0.
- Tool cards link to all 6 admin subpages: users · announcements · audit · kill-switch-events · indicators · compliance. Hover reveals an ArrowUpRight affordance.

### Morning visual-check
1. Log in as admin. Go to `/admin`.
2. Snapshot cards populate with real counts.
3. Click each tool card — should navigate to the respective subpage.

### Backend added
None.

### Production-ready?
**Yes**.

---

## M8 — /settings

**Branch:** `feat/hhh-settings` · **HEAD:** `79db7fc` · **Status:** 🟡 SCAFFOLDED (scope clearly flagged)

### What changed
- Replaced the placeholder at `(dashboard)/settings/page.tsx` (~296 LOC).
- Wired to `GET /api/auth/me` + `PUT /api/users/me` (both existing — `UpdateProfileRequest` already accepts `full_name`, `phone`, `telegram_chat_id`, `notification_prefs`).
- Sections: Account (read-only: email · role badge · joined) · Profile (editable: full_name · phone with tel input + 32-char limit) · Notifications (email toggle · telegram toggle · chat ID).
- Sticky save bar; only enables when dirty; sonner toast on success.

### Morning visual-check
1. Log in. Go to `/settings`.
2. Account section displays your email + role + joined date.
3. Edit full_name or phone — Save button enables.
4. Click Save — toast confirms; refresh page — values persist.
5. Toggle telegram switch, paste a fake chat ID, save. Same flow.

### Backend added
None.

### Production-ready?
**Yes for what's built.** Explicit out-of-scope flagged on the page footer: "Password change · 2FA · timezone — coming in a later sprint" — those need new backend work.

---

## M9 — /analytics

**Branch:** `feat/hhh-analytics` · **HEAD:** `7ee3fda` · **Status:** 🟡 SCAFFOLDED (limited window honest)

### What changed
- Replaced the placeholder (~319 LOC).
- Wired to existing `GET /me/trades/stats` (summary) + `GET /me/trades?limit=100` (recent trades).
- 6 summary cards: total trades · total P&L · win rate · avg P&L · best · worst (rupees formatted with sign tones).
- Equity curve (SVG sparkline, no chart lib): client-cumulated from last 100 trades. Loss-tone line if final value <0.
- Top-symbols distribution: grouped bars with count + tone-coded P&L per symbol.
- **Honest scope note** rendered on the page itself: full-history daily aggregation needs a new backend endpoint, flagged as next sprint.

### Morning visual-check
1. Log in. Go to `/analytics`.
2. Summary cards populate with your trade stats.
3. Equity curve renders if you have ≥1 trade.
4. Top-symbols section shows top 8 by trade count.

### Backend added
None.

### Production-ready?
**Honest framing.** Summary cards = real stats from full history. Equity curve + symbol distribution = computed from last 100 trades only (page banner says so). Full-history daily aggregation needs `/me/trades/daily` endpoint — explicitly next sprint. Drawdown / Sharpe / per-strategy comparison / date-range filters likewise.

---

## M10 — /alerts (LARGEST module: backend + frontend)

**Branch:** `feat/hhh-alerts` · **HEAD:** `4ffebba` · **Status:** 🟡 SCAFFOLDED (storage only — engine deferred)

### 🛑 BRUTAL HONESTY
**Alerts are STORED but NOT YET EVALUATED/FIRED.** The background tick consumer + notification fanout is a SEPARATE sprint and explicitly out of scope. The page renders a prominent amber AlertTriangle banner at the top saying so. Customers WILL NOT be misled about whether alerts will wake them at 03:00 IST.

### What changed (backend, all NEW additive files)
- `backend/app/db/models/alert.py` — Alert ORM model (~100 LOC)
- `backend/migrations/versions/031_alerts.py` — net-new table, no ALTER. **Applied to LOCAL dev DB (head moved 030 → 031). NOT applied to EC2 prod.**
- `backend/app/api/alerts.py` — router at `/api/alerts` with GET (list) · POST (create) · DELETE (delete). Auth-gated. Pydantic v2.
- `backend/app/main.py` — 2 additive lines: import + `include_router(alerts_router)`. NO existing endpoint logic changed.
- `backend/tests/api/test_alerts.py` — 4 ORM tests (create happy / invalid condition_kind CHECK / per-user isolation / FK CASCADE on user drop). Module-level Postgres skipif (matches existing pattern). 4/4 pass locally.

### What changed (frontend)
- `(dashboard)/alerts/page.tsx` (~330 LOC). List + create dialog + delete confirm + AlertTriangle banner.

### Morning visual-check
1. Log in. Go to `/alerts`.
2. **Verify the amber banner is prominent** — it should be the first thing you see.
3. Empty state shows. Click "New alert".
4. Fill: label "Nifty above 25k" · symbol "NIFTY" (auto-upper) · condition "Price above" · threshold "25000". Save.
5. Alert appears in list. Click Delete → confirm → toast.
6. Open backend dev DB: `SELECT * FROM alerts;` — verify rows created/deleted correctly.

### Production-ready?
**Storage layer is yes.** Evaluation engine is no — that's the explicit next sprint. The honesty banner on the page is the load-bearing UX choice.

### EC2 deploy posture
🛑 **Migration 031 NOT applied on EC2 prod.** When this branch eventually merges, a separate founder-gated `alembic upgrade head` on EC2 dev/staging/prod is required before the page works there.

---

## Aggregate stats

| Metric | Count |
|---|---|
| Branches pushed | 10 |
| Modules ✅ COMPLETE | 6 (M1, M2, M4, M5, M6, M7) |
| Modules 🟡 SCAFFOLDED (with honest scope notes) | 4 (M3 read-only, M8 settings, M9 analytics, M10 alerts-storage) |
| Backend changes | M10 only (new model + new migration + new router + 2 lines in main.py + tests) |
| Migrations added | 1 (031_alerts) — applied locally, NOT on EC2 |
| Total LOC added | ~2,800 across all 10 modules |
| `npm run build` passes | ✅ on every module |
| ruff check + format clean | ✅ on M10 backend files |
| Sacred-zone touches | NONE (no dhan.py / fyers.py / executor / kill_switch / broker_credential / is_paper / strategies migration / webhook handlers) |

## Hard-stops respected

✅ No merge to main · ✅ No PR auto-merge · ✅ No Vercel deploy · ✅ No push to main · ✅ No sacred-zone touch · ✅ Backend additions are ALL new additive files (one main.py line is the only existing-file edit, restricted to a router import + include — no existing endpoint logic touched) · ✅ Migration 031 is additive net-new table only · ✅ No new deps (verified via `package.json` unchanged) · ✅ No new design tokens · ✅ No `any` / `@ts-ignore` · ✅ Module-by-module, each on own branch, per-module commit + branch push

## Morning workflow recommendation

1. Visual-check M1 first (auth guard) — confirm admin-only redirect works as a non-admin.
2. M2 (webhooks) is the customer-facing TOP-priority — give this extra time. Test the one-time-secret modal carefully.
3. M3-M7 admin pages — sweep through each from the M7 admin home hub.
4. M8 (settings) — verify profile edit + save + persist.
5. M9 (analytics) — confirm the scope-banner is visible; sanity-check the equity curve direction.
6. M10 (alerts) — **the amber honesty banner is the most important visual element.** If it's missing or unclear, that's a blocker — alerts must not appear to "just work".
7. Decide merge order. Suggested: M1 first (security prereq), then M2 (high-value customer page), then admin cluster (M3-M7), then M8/M9, finally M10 (which also needs the 031 migration on EC2 separately).

— end of summary —
