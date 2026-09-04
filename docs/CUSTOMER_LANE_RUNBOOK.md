# CUSTOMER LANE — LIVE PROVING RUNBOOK

**STATUS: PENDING. NOT EXECUTED. FOUNDER-GATED.**

Nothing in this runbook has been run. It was written in the build session; every
step below is unproven against a real broker. The build session could not execute
it, for reasons stated in §0.

---

## §0 — Why this could not be executed in the build run

| Blocker | Detail |
|---|---|
| No partner credentials | TRADETRI has no Dhan partner ID/secret. `DhanPartnerAuthProvider` raises `PartnerCredentialsMissing` by design rather than guessing an endpoint. |
| No live customers | None exist and none could be onboarded in the build run. |
| No dedicated egress | No per-customer proxy or static IP has been provisioned. `build_lane` fails closed without one. |
| Order lane disarmed | `CUSTOMER_LANE_ORDER_ENABLED=false`, and `_transmit` is unimplemented. |
| No deploy | The branch is not merged, not built, not deployed. |

Each is a hard blocker on its own. All five are open.

---

## §1 — Preconditions (ALL must be true before step 1)

1. Founder has read this file end to end and said go.
2. Dhan partner credentials exist and are in the server environment, not in git.
3. At least one dedicated egress IP is provisioned and whitelisted with the broker.
4. `customer_broker_link.proxy_url` and `assigned_static_ip` are populated for the
   test customer.
5. The test customer is a **real account the founder controls**, funded with the
   smallest amount that can transact. Not a stranger's account.
6. Disk on the EC2 box is below 85%. (It has been 90%+ historically.)
7. `alembic current` shows `047_customer_lane`.
8. The BSE live strategy's state is recorded before you start: open position, level
   file, `stop_state.json`, `own_fills.json`. **You are proving you did not disturb it.**

## §2 — Order of arming (never skip, never reorder)

Arm ONE flag at a time. After each, observe for one full session before the next.

| # | Flag | What it turns on | Rollback |
|---|---|---|---|
| 1 | `CUSTOMER_LANE_STATUS_API_ENABLED` | Read-only status endpoints | unset, restart |
| 2 | `CUSTOMER_LANE_LADDER_ENABLED` | Reminder ladder, still log-only channels | unset |
| 3 | *(real channel provider)* | Messages actually leave the box | swap provider back to stub |
| 4 | `CUSTOMER_LANE_BEAT_ENABLED` | Ladder runs on schedule | unset, restart beat |
| 5 | `CUSTOMER_LANE_EGRESS_VERIFY_ENABLED` | Egress probe (needs `_observe_public_ip` built) | unset |
| 6 | `CUSTOMER_LANE_ORDER_ENABLED` | **REAL ORDERS. LAST. ONE CUSTOMER.** | unset, then `CUSTOMER_LANE_KILL_ALL=1` |

**Step 6 is the only irreversible one.** Do not arm it on a Friday, on an expiry
day, or when you cannot watch the screen.

## §3 — The proving sequence

1. **Status only.** Arm flag 1. Load `/api/customer-lane/board`. Confirm the test
   customer shows `NOT_TODAY`. Confirm no existing route changed.
2. **Connect.** Issue a link. Confirm the DB stores a hash, never the raw token:
   `SELECT token_hash FROM customer_connect_link ORDER BY created_at DESC LIMIT 1;`
   Tap it. Confirm status flips to `CONNECTED` and the board shows `FULL_DAY`.
3. **Single use.** Tap the same link again. It must refuse with `already_consumed`.
4. **Ladder, silent.** Arm flag 2 with the customer already connected. Confirm
   `customer_notification_log` stays EMPTY — a connected customer is asked nothing.
5. **Ladder, loud.** Disconnect. Run the rungs. Confirm R1, R2, CALL, RED land once
   each, and that RED names the consequence.
6. **Cancel rule.** Reconnect between R1 and R2. Confirm R2 never fires.
7. **Egress.** Arm flag 5. Confirm the observed IP equals `assigned_static_ip`.
   **If it does not match, STOP. Do not continue to step 8.**
8. **One order, smallest size.** Arm flag 6 for ONE customer. Place the smallest
   possible order. Confirm at the broker that it arrived from the customer's own IP
   and under their own token.
9. **Kill.** Set `CUSTOMER_LANE_KILL_ALL=1` mid-session. Confirm the next order
   refuses. Confirm the founder's BSE strategy is STILL RUNNING and untouched.
10. **Compare §1.8.** Position, level file, stop state, own fills — all unchanged.

## §4 — Abort conditions (any one → stop, roll back, report)

- Egress IP does not match the expected IP.
- An order appears at the broker under the wrong client id.
- Any customer sees another customer's data on the board.
- A raw token appears in any log or any DB column.
- The BSE strategy's state changed and you did not change it.
- Disk crosses 90%.

## §5 — Rollback

```
unset CUSTOMER_LANE_ORDER_ENABLED
export CUSTOMER_LANE_KILL_ALL=1
```

Then restart the worker. The kill is read fresh at every act, so it takes effect at
the next order without waiting for a restart. Migration 047 is additive; it creates
three new tables and alters nothing, so it does not need to be reversed to make the
lane inert. Leaving the tables in place is the safer choice.

## §6 — What this runbook does NOT prove

- Partner token lifetime. **NOT MEASURED.** The 24h default is a guess.
- Behaviour at 25+ customers against a real broker's rate limits.
- What the broker does when a customer revokes consent mid-session.
- ~~Holiday handling: no exchange holiday list exists in this repo.~~ **CORRECTED
  2026-09-05 — that was wrong.** `orderflow_engine/holidays.yaml` was git-tracked in
  this repo the whole time (16 NSE 2026 dates; the tick/depth recorders, the daily
  pulse and the morning watchdog already run on it). The ladder now reads that same
  file via `app/domains/customer_lane/calendar.py` and refuses loudly past its
  coverage. See `docs/HOLIDAY_CALENDAR_REFRESH.md`.
