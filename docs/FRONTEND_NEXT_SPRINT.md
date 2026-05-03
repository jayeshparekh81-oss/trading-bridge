# Frontend — next sprint queue (post-Monday)

Sun 2026-05-03 evening sprint shipped 4 Tier-1 pages wired to real
backend (Kill Switch, Live Positions, Trade History, Overview). The
following pages are still on `mock-data` and were intentionally
deferred per the "ZERO half-working features" mandate.

## Deferred Tier-1 pages

### Strategies management (`src/app/(dashboard)/strategies/page.tsx`)
- **Backend:** `GET/POST/PUT/DELETE /api/users/me/strategies` already
  exist (full CRUD).
- **Why deferred:** Strategy config rarely changes day-to-day. Today's
  strategy works for Monday. The edit modal needs careful UX: which
  fields are safe to mutate (entry_lots / partial_profit_lots /
  ai_validation_enabled / is_active) vs. which require migration-aware
  thinking (exit_strategy_type — flipping to internal mid-position is
  unsafe). Webhook URL display needs copy-to-clipboard with shadcn
  popover. Estimated 90-120 min for proper wire + UX.
- **Scope when ported:**
  * List card per strategy with status toggle + edit + (soft-)delete.
  * Modal form with Pydantic-shape validation matching backend.
  * Disable destructive ops while a position is open for the strategy
    (read `/strategies/positions?strategy_id=...`).
  * Copy webhook URL button with token reveal/hide.

### Webhooks read-only (`src/app/(dashboard)/webhooks/page.tsx`)
- **Backend:** `GET /api/users/me/webhooks` exists. No "recent triggers
  log" endpoint exists; would need to build from `strategy_signals`
  joined to webhook_token.
- **Why deferred:** The webhook URL is already in
  `docs/MONDAY_LIVE_FIRSTRUN.md`. UI version would mostly duplicate
  that. Recent-triggers log requires a new endpoint
  (`GET /api/users/me/webhooks/{token_id}/recent`). Estimated 60-90 min.
- **Scope when ported:**
  * Per-token: URL with copy button, status, last triggered, total
    triggers (today / 7d / all).
  * Recent 20 hits: timestamp, IP, signal_id, action, processed status.
  * TradingView setup card with Pine alert config screenshots.

### Alerts (Telegram + email config) (`src/app/(dashboard)/alerts/page.tsx`)
- **Backend missing:** No alert-preferences model or endpoint. User
  table has no per-event toggle columns. Building this requires:
  * Migration 009 — `user_alert_preferences` table OR JSON column on
    `users` row.
  * Pydantic schemas for read + update.
  * `GET/PUT /api/users/me/alert_preferences`.
  * Wire into existing alert call-sites (executor / direct_exit /
    kill_switch_service / reconciliation_loop) to honour the prefs.
- **Why deferred:** Telegram alerts ALREADY fire end-to-end for entry,
  partial, exit, SL_HIT, errors, kill-switch trip. Reconciliation drift
  spam is gated by env (`RECONCILIATION_TELEGRAM_ENABLED=false`). User
  has zero broken Telegram experience today. UI to toggle individual
  events is "nice to have" not "Monday-blocking". Estimated 3-4 hours
  end-to-end including migration + tests.
- **Scope when ported:**
  * Telegram: status, chat_id display, test alert button, disconnect.
  * Per-event toggles for: order placed, filled, partial, exit, SL_HIT,
    AI rejection, critical errors, kill-switch trip, reconciliation
    drift (default off).
  * Email channel (lower priority — Telegram is primary).

## Pages now showing ComingSoon placeholder

Customer-facing routes that render the shared `ComingSoon` component
(no mock data leakage). All routes still exist; only the page content
is a placeholder until properly wired:

- `/strategies`
- `/webhooks`
- `/alerts`
- `/settings`
- `/analytics`
- `/admin/*` (system-health, users, audit, kill-switch-events,
  announcements)

**`/brokers` is fully wired** — earlier mention of brokers as "still
mock" in this doc was a documentation error. Brokers page connects
to `/api/users/me/brokers` end-to-end (Fyers OAuth, Dhan PAT,
reconnect, remove). Not a defer item.

## Backend gaps for next sprint

- `GET /api/users/me/alert_preferences` + `PUT` (alerts page).
- `GET /api/users/me/webhooks/{token_id}/recent` — log of recent hits
  for the webhooks page.
- `GET /api/users/me/system-health` (or expose `/api/admin/system-health`
  for the user themselves) for the System Health page.
- Aggregation endpoint for `/analytics`: P&L curve, win-rate over time,
  per-strategy breakdown.

## Frontend tech debt to address

- `src/lib/use-api.ts` doesn't surface `setData` for optimistic updates;
  add it before building strategies page (POST creates strategy →
  optimistically prepend to list, rollback on error).
- ESLint config doesn't enforce no-`any`; tighten before this becomes a
  habit.
- Mobile nav (`MobileDrawer`) overlaps with sticky header on small
  viewports — visual polish.

## Sprint sizing estimate

| Item | Estimated effort |
|---|---|
| Strategies page | 90-120 min |
| Webhooks page (incl. recent-hits endpoint) | 90-120 min |
| Alerts page (incl. backend migration + endpoint) | 3-4 hours |
| System Health page | 60 min |
| Analytics page | 4-6 hours (aggregation + charts) |
| Settings page | 90 min |
| Frontend tech debt cleanup | 60-90 min |
| **Total realistic next sprint** | 14-20 hours |

Recommended split: Strategies + Webhooks + Alerts = one tight 8-hour
day. System Health + Settings = another 3-4 hour session. Analytics
gets its own day with proper requirements before a line of code.
