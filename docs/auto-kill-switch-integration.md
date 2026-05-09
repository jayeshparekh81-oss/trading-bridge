# Auto Kill Switch — Integration Guide

> Status: Production-ready (Phase 1-12 untouched)
> Originally introduced: Phase 4
> Live-orders integration: Commit `9c5b811` (SafetyChain)
> Audit wrapper wiring: Commit `7bf2a10`
> Last updated: 2026-05-09

## Overview

The Auto Kill Switch is the platform's last line of defence. It
watches every user's realized + unrealized PnL against their
configured daily-loss cap, and when the cap is breached it:

1. Cancels every pending order on every connected broker (in
   parallel).
2. Squares off every open position on every connected broker (in
   parallel).
3. Persists a `KillSwitchEvent` row + an `AuditLog` row.
4. Flips the user's Redis tripped-flag so downstream webhooks
   reject new orders until an explicit reset.
5. Notifies the user via Telegram + email.

The orchestration logic is `app.services.kill_switch_service.KillSwitchService`.
Phase 8B-2 (commit `9c5b811`) added a SafetyChain that consults
the kill-switch state as the **first** of seven safety gates
before placing any new live order — so a tripped kill switch
makes the live-order path fail closed even if a downstream check
were to misbehave.

## Why It Exists

Algo trading without a circuit breaker is malpractice. Every
deploy at TRADETRI assumes:

- **A user's algorithm can have a bad day.** Strategies don't
  know they're losing money — only the platform sees the
  cumulative damage and can act.
- **Bugs are inevitable.** A regime shift, a broker glitch, a
  silently-broken strategy — the kill switch is the safety
  net that contains the blast radius without requiring the
  user to be at their laptop.

Every path that mutates a user's exposure passes through the
kill-switch service or the SafetyChain that consults it.

## Public API — KillSwitchService

```python
from app.services.kill_switch_service import KillSwitchService

service = KillSwitchService(db, redis_client)

# Trip detection on every PnL update.
result = await service.evaluate_and_trip_if_breached(
    user_id=user.id,
    realized_pnl=realized,
    unrealized_pnl=unrealized,
)
# result.tripped → bool
# result.reason  → "daily_loss_breach" | "manual" | None
# result.broker_results → per-broker square-off outcome

# Manual trip (user clicked "Stop Everything" in the UI).
await service.manual_trip(user_id=user.id, reason="user_initiated")

# Manual reset (user explicitly acknowledges + resumes).
await service.reset(user_id=user.id, reason="user_acknowledged")
```

Source: `app/services/kill_switch_service.py`.

## SafetyChain Integration (Phase 8B-2)

Live orders go through a 7-check chain in
`app.strategy_engine.live_orders.safety_chain`. The chain runs
checks in **locked order** — kill-switch first.

```
1. auto_kill_switch     ← consults the kill-switch service's tripped flag.
2. paper_sessions       ← strategy-maturity gate (≥7 completed sessions).
3. trust_score          ← backtest reliability floor.
4. truth_score          ← fake-backtest detection floor.
5. live_trading_enabled ← per-user opt-in.
6. broker_connection    ← at least one broker linked.
7. risk_engine_precheck ← deferred (fail-open, see safety_checks).
```

Re-ordering is load-bearing. The kill switch goes first because
"an incident in progress" must never reach a downstream gate that
might leak information about the user's strategy state. The
ordering is pinned by a test:

```
backend/tests/strategy_engine/live_orders/test_safety_chain.py::
  test_safety_check_order_is_locked
```

## Trip Conditions

| Trigger | Source | Notes |
|---|---|---|
| Daily-loss-cap breach | `KillSwitchService.evaluate_and_trip_if_breached` | Watches realized + unrealized PnL on every fill / tick. |
| Manual user trip | `manual_trip()` | "Stop Everything" UI button. |
| Manual admin trip | `admin_trip()` | Admin tooling for incident response. |
| Deviation-driven trip | DEFERRED | The Deviation Monitor's `auto_kill_switch_signal` is read-only today; wiring it is a future phase with its own trip reason + audit trail. |

## Reset Workflow

A tripped kill switch stays tripped until the user explicitly
acknowledges. The reset flow:

1. User opens the Kill Switch detail page.
2. UI surfaces the trip reason + the audit-log row that
   recorded it.
3. User clicks "Acknowledge & resume" + types a confirmation
   string.
4. Backend calls `KillSwitchService.reset()` which:
   - Clears the Redis tripped-flag.
   - Writes an `AuditLog` row with the user's acknowledgement.
   - Re-enables the SafetyChain's `auto_kill_switch` check
     (returns "ok").

The audit row is the audit trail — kill-switch trips and
resets are append-only history.

## Audit Log Integration

Every trip + reset writes an `AuditLog` row. Commit `7bf2a10`
wired the audit wrapper around the kill-switch service so:

- Trip events have severity `critical`.
- Reset events have severity `info` and reference the trip event by id.
- Both events are user-visible in the user's audit dashboard.
- Admin-trip events also flag the admin user that initiated.

See [`/docs/audit-logs.md`](./audit-logs.md) for the audit
schema + retention details.

## Partial-Failure Policy

A real-world incident: broker A's `square_off_all` raises while
broker B's succeeds. The service:

1. Records both results in `KillSwitchResult.broker_results`.
2. Continues — broker B must not be penalised for broker A's failure.
3. The Celery retry task picks up broker A's failure and retries.
4. The Redis tripped flag stays set — no new orders go out
   regardless of which broker is misbehaving.

Source: `kill_switch_service.py` docstring.

## Notifications

Tripped events fire both Telegram and email notifications. The
templates live at:

- `app/templates/notifications/telegram/kill_switch_triggered.txt`
- `app/templates/notifications/email/kill_switch_triggered.html`

Both render the trip reason + a link to the kill-switch detail
page. The Hinglish copy is calibrated to be alarming without
inducing panic — "Aapka kill switch trip ho gaya — abhi
acknowledge karna padega."

## Edge Cases & Limitations

- **Service-restart safety.** The Redis tripped-flag survives a
  backend restart. If Redis itself goes down the SafetyChain's
  kill-switch check fails closed — better-safe-than-sorry.
- **Multi-broker race.** Broker fills land asynchronously; a fill
  arriving milliseconds after the kill-switch trips can sneak
  through. The service idempotently re-fires square-off on every
  evaluation tick to catch these.
- **PnL freshness.** Realized PnL comes from broker reconciliation
  (lag: seconds). Unrealized PnL comes from live-tick mark-to-market.
  In practice the service has fresh-enough data that breaches are
  caught within a few ticks.

## Configuration

| Env var | Behaviour |
|---|---|
| `DEFAULT_MAX_DAILY_LOSS_INR` | Default cap for new users (₹10 000 in dev / production templates). |
| `DEFAULT_MAX_DAILY_TRADES` | Default daily-trade cap. |

Per-user overrides live in the `KillSwitchConfig` table — set
via the user's settings page.

## Testing

- `tests/services/test_kill_switch_service.py` — trip /
  reset / partial-failure / Redis-down matrix.
- `tests/strategy_engine/live_orders/test_safety_chain.py` —
  kill-switch-first ordering pinned.
- `tests/integration/test_kill_switch_full_flow.py` — webhook
  → trip → square-off → audit row → notification end-to-end.

## Future Work

- **Wire the Deviation Monitor's `auto_kill_switch_signal`.**
  Add a dedicated trip type with its own audit reason and
  (optionally) reset workflow that requires the user to
  re-confirm the strategy before resuming.
- **Per-strategy kill switch.** Today the kill switch is per-user.
  A per-strategy variant would let a multi-strategy user pause
  one bad performer without taking down the rest.
- **Telegram-driven manual trip.** Today the user has to be in
  the dashboard to manual-trip; a Telegram bot command would
  let users hit the brake from their phone in 15 seconds.

## References

- Service source: `backend/app/services/kill_switch_service.py`
- SafetyChain source: `backend/app/strategy_engine/live_orders/safety_chain.py`
- Frontend integration: `frontend/src/app/(dashboard)/kill-switch/page.tsx`
- Tests: `backend/tests/services/test_kill_switch_service.py`,
  `backend/tests/strategy_engine/live_orders/`
- Sister doc: [`/docs/audit-logs.md`](./audit-logs.md)
- Sister doc: [`/docs/deviation-monitor.md`](./deviation-monitor.md)
