# ADMIN PROVISIONING — runbook / audit log

Manual admin-privilege grants/revocations on the **production** database.
Append one line per change (newest at the bottom). Each entry: date — who (email + id) — what — how — why.

The `users` table has **two** admin mechanisms (keep them in sync when granting):
- `is_admin = true` → frontend M1 route guard + `app/api/admin.py` endpoints (users, audit, announcements, kill-switch-events, system/broker-health).
- `role = 'admin'` → `app/api/admin_indicators.py` endpoints (indicator queue / overrides).

## Log

- 2026-06-15 — jayeshparekh81@gmail.com (id 46a5...022) granted is_admin=true + role=admin on prod, manual UPDATE, reason: HHH admin go-live.
