# Customer lane — arming runbook

**One document for go-live day. Follow it in order. Each step has a receipt; do not
start a step until the previous receipt exists.**

Status language is exact and is used deliberately throughout:

| word | means |
|---|---|
| **built** | code exists |
| **landed** | committed on the branch |
| **armed** | a flag is on in a real environment |
| **live** | it has actually done its job with real money or a real customer |

Nothing in the customer lane is **live**. Everything below is **landed**.

---

## 0. State of the branch at the time of writing

- Branch `feat/customer-lane-full`, not merged, not pushed, not deployed.
- Migration `047_customer_lane` is **not applied to production** (verified: 0 customer-lane
  tables in the prod database).
- Every arming flag defaults OFF.
- 125 customer-lane tests pass; the full suite has zero new failures vs base.

---

## 1. Blockers — none of the rest may start until every one is cleared

| # | blocker | blocked on | how to verify it has cleared |
|---|---|---|---|
| 1 | **Dhan partner credentials** issued to TRADETRI | **Dhan** | `DHAN_PARTNER_ID` and `DHAN_PARTNER_SECRET` present in the server environment (never in git), and `DhanPartnerAuthProvider().credentials_available` returns `True` |
| 2 | **Dedicated egress IP** purchased, and whitelisted **by the customer in their own Dhan account** | **founder (purchase) + customer (whitelist)** | the customer's `assigned_static_ip` and `proxy_url` are populated, and no other customer holds either (`build_lane` refuses with `EgressNotExclusive`) |
| 3 | **AWS SES credentials** supplied | **founder** | with `CUSTOMER_LANE_CHANNELS_LIVE=1`, `preflight.check()` returns `ready=True` instead of `transport_credentials_missing` |
| 4 | **Calendar mount applied** | **founder** (needs a container recreate) | `docker exec trading_bridge_celery_worker ls -l /opt/tradetri/holidays.yaml` succeeds — see `docs/CUSTOMER_LANE_CALENDAR_IN_CONTAINER.md` |
| 5 | ~~CALL rung~~ **CLEARED by decision (run J)** | — | unwired by default; nothing to do. See §1a |
| 6 | **Merge, build, deploy** | **founder** | the branch is not merged, not pushed, not deployed |

Everything else in this document is downstream of these six.

### 1a. The CALL rung is unwired — decided, not pending

**Founder decision (run J): no voice transport will be built now.** A vendor plus
Indian DLT registration is its own project and is not worth blocking on while there
is no partner credential, no egress IP and no customer.

**The ladder delivers THREE rungs: R1 07:45, R2 08:32, RED 09:07.**

This is the documented default state — `CUSTOMER_LANE_UNWIRED_RUNGS` defaults to
`CALL`, so nothing needs setting by hand on go-live day. CALL still runs and still
records `outcome=UNAVAILABLE`, so the gap stays visible in the notification log
rather than disappearing because it is expected. It can never degrade into a
message.

Acceptance is **per-rung**: if a *different* rung loses its transport, preflight
still refuses, because nobody decided about that one.

🔴 **Because CALL is unwired, no customer may be told a phone call is coming** — not
in onboarding, not in the app, not in the ladder copy, not in marketing. The repo
was swept for this in run J; the one offending string (`"Calling you — …"` in the
CALL rung's own message) was removed, and a test now guards against it returning.

To add voice later: write a NEW `Channel` class, register it as `CHANNELS["voice"]`,
and drop `CALL` from `CUSTOMER_LANE_UNWIRED_RUNGS`. Do not refactor
`UnavailableChannel` — it stays for the next rung that loses a transport.

### 1b. Email is the first transport — it needs credentials

**Founder decision (run J): email first.** All 12 users already have an address, so
it needs credentials only; Telegram additionally requires every customer to start a
bot chat. Telegram stays selectable via `CUSTOMER_LANE_PRIMARY_TRANSPORT=telegram`.

Measured against the running production container:

| transport | code | credentials | can deliver today |
|---|---|---|---|
| email (AWS SES) | REAL | `aws_access_key_id` **EMPTY**, `aws_secret_access_key` **EMPTY** (`aws_ses_region`, `from_email` SET) | **no** |
| telegram | REAL | bot token SET, but `telegram_enabled=False` and **0 of 12 users** have a `telegram_chat_id` | **no** |

**The credentials are yours to supply at arming time. They are never stored in git,
and no placeholder has been committed anywhere.**

Preflight checks them at **arm time**, not send time — discovering an empty AWS key
at 07:45 on a live morning is the failure being prevented. The check applies only
when `CUSTOMER_LANE_CHANNELS_LIVE=1`; a disarmed lane needs no credentials.

**Receipt:**
```bash
docker exec trading_bridge_celery_worker python -c \
  "from app.domains.customer_lane import preflight; print(preflight.check())"
```
Expect `ready=True`. While credentials are absent you get
`transport_credentials_missing` naming exactly which settings are empty.

## 2. Deploy and migration

1. Merge the branch (founder), build the image, deploy by your normal process.
2. Apply migrations `047_customer_lane` and `048_customer_ip_change_clock`.
   **Receipt:** `alembic current` reports `048_customer_ip_change_clock`, and
   `SELECT count(*) FROM information_schema.tables WHERE table_name LIKE 'customer_%'`
   returns the three new tables.
   047 is additive — 3 `create_table`, 6 `create_index`, **0 destructive operations**.
3. Apply the calendar mount (§1 blocker 3) and set `CUSTOMER_LANE_HOLIDAYS_FILE`.
   **Receipt:** `preflight.check()` inside the worker no longer reports
   `calendar_unavailable`.

---

## 3. Flag order — one at a time, observe a full session between each

Egress verification and the exclusivity guard come on **before** anything that can place an
order. That ordering is not negotiable.

| # | flag | turns on | receipt before the next step | rollback |
|---|---|---|---|---|
| 1 | `CUSTOMER_LANE_STATUS_API_ENABLED` | read-only status endpoints | `/api/customer-lane/board` returns; **no existing route changed** | unset, restart |
| 2 | `CUSTOMER_LANE_CHANNELS_LIVE` | channels may actually deliver | a test customer receives one real message | unset |
| 3 | `CUSTOMER_LANE_LADDER_ENABLED` | the ladder runs | `customer_notification_log` shows the expected rungs, once each | unset |
| 4 | `CUSTOMER_LANE_BEAT_ENABLED` | the ladder runs on schedule | rungs fire at 07:45 / 08:32 / 08:57 / 09:07 IST | unset, restart beat |
| 5 | `CUSTOMER_LANE_EGRESS_VERIFY_ENABLED` | egress probe | observed IP **equals** `assigned_static_ip` | unset |
| 6 | `CUSTOMER_LANE_ORDER_ENABLED` | **REAL ORDERS. LAST. ONE CUSTOMER.** | §4 | unset, then `CUSTOMER_LANE_KILL_ALL=1` |

`CUSTOMER_LANE_REQUIRE_VERIFIED_EGRESS` stays **true** throughout. It makes an unverified
egress a refusal rather than a warning. Turning it off defeats the point of step 5.

**Step 6 is the only irreversible one.** Not on a Friday, not on an expiry day, not when you
cannot watch the screen.

---

## 4. The first real proving order

Carried forward from `docs/CUSTOMER_LANE_RUNBOOK.md` §3 step 8 — smallest possible size,
one customer, watched. Record all of:

- **POST → 202** time
- **202 → broker acknowledgement** time
- **observed egress IP** (must equal `assigned_static_ip`)
- the broker's own **`createTime`**
- on failure, **the full error body**, verbatim

This settles the two things that cannot be settled any other way:

1. **whether Dhan accepts an order from a hosted/datacenter IP at all** — currently unknown;
2. **the proxy's added latency** — currently unmeasured.

If the egress IP does not match, **STOP**. Do not continue to a second order.

---

## 5. The first real customer

1. Customer signs up and completes onboarding.
2. Assign a dedicated egress IP. `build_lane` refuses if any other customer holds the same
   IP or proxy — this is enforced in code (`EgressNotExclusive`).
3. The customer whitelists that IP **in their own Dhan account**. We cannot do this for them.
4. Issue a connect link. It is single-use, same-day, and only its SHA-256 hash is stored.
5. Customer taps it and authorises on Dhan's own page. **We never see their password, PIN or
   TOTP.**
6. **Receipt:** the board shows them `FULL_DAY`, and `customer_broker_link.status` is
   `CONNECTED`.

**The 7-day IP lock and the once-per-week change limit are now ENFORCED IN CODE**
(run J — this corrects the earlier note that called them manual procedure).
`app/domains/customer_lane/ip_lock.py::change_static_ip` is the only write path to
`assigned_static_ip`, and it refuses before mutating anything.

They are **two different clocks** and are modelled separately:

| rule | clock | source |
|---|---|---|
| Dhan holds a whitelisted IP for 7 days | `ip_whitelisted_at` (+ `ip_lock_until`) | broker |
| the exchange allows one change per **calendar week** | `last_ip_change_at` | exchange |

A refusal tells you **when** the change becomes possible. It **fails closed**: an
assigned IP with no whitelist timestamp, or no change history, is refused rather
than allowed. The calendar week is computed in **IST, starting Monday** — the box
runs UTC, and 23:00 UTC Sunday is already Monday in IST.

Migration `048_customer_ip_change_clock` adds `last_ip_change_at` (additive: one
nullable column) and must be applied along with 047.

---

## 6. Abort conditions — stop immediately, roll back

- Observed egress IP ≠ `assigned_static_ip`.
- An order appears at the broker under the wrong client id.
- A customer sees another customer's data on the board.
- A raw token appears in any log or any database column.
- The founder's BSE strategy state changed and you did not change it.
- Disk crosses 90%.
- Any rung reports `UNAVAILABLE` that you expected to be wired.

**Rollback at any stage:**
```bash
export CUSTOMER_LANE_KILL_ALL=1
```
The kill is read fresh at every act, so it takes effect at the next order without waiting
for a restart. Migration 047 is additive; leaving the tables in place is the safer choice.

---

## 7. Do NOT proceed if

- Any blocker in §1 is unverified — **including "I think it's fine".**
- The CALL rung is unwired **and** customers have been told a call will come.
- AWS SES credentials are absent (`preflight.check()` reports `transport_credentials_missing`).
- Neither email nor Telegram can deliver (§1b) — the ladder would log `FAILED:` and nobody
  would be reminded of anything.
- `preflight.check()` does not return `ready=True`.
- The calendar's coverage does not extend past the day you are arming (it currently ends
  **2026-12-31**).
- You cannot watch the screen for the whole session.
- It is a Friday, an expiry day, or the last hour before a long weekend.
