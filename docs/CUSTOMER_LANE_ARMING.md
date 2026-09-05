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

| # | blocker | how to verify it has cleared |
|---|---|---|
| 1 | **Dhan partner credentials** issued to TRADETRI | `DHAN_PARTNER_ID` and `DHAN_PARTNER_SECRET` present in the server environment (never in git), and `DhanPartnerAuthProvider().credentials_available` returns `True` |
| 2 | **Dedicated egress IP** purchased, and whitelisted **by the customer in their own Dhan account** | the customer's `customer_broker_link.assigned_static_ip` and `proxy_url` are populated, and no other customer holds either (`build_lane` refuses a shared identity with `EgressNotExclusive`) |
| 3 | **Calendar mount applied** | `docker exec trading_bridge_celery_worker ls -l /opt/tradetri/holidays.yaml` succeeds — see `docs/CUSTOMER_LANE_CALENDAR_IN_CONTAINER.md` |
| 4 | **CALL rung resolved or accepted** | either a voice transport now exists, or `CUSTOMER_LANE_ACCEPT_UNWIRED_RUNGS=1` is set as a deliberate decision — see §1a |
| 5 | **Email or Telegram can actually deliver** | see §1b — today neither can |

### 1a. The CALL rung has no transport

There is **no voice/telephony capability anywhere in this estate** (H1 audit, adversarially
re-checked). `users.phone` is stored and read by no sender. The CALL rung is wired to
`UnavailableChannel`, which **refuses** and records `outcome=UNAVAILABLE`. It will never
quietly become a message — a customer told a call is coming, who gets a Telegram instead,
has been lied to.

Two honest options, and no third:

- **Provide a transport.** Requires choosing a vendor (none is integrated), and in India a
  voice/SMS sender also needs DLT registration. This is a project, not a config change.
- **Accept the rung as unwired.** Set `CUSTOMER_LANE_ACCEPT_UNWIRED_RUNGS=1`. Preflight then
  arms, the CALL rung is skipped loudly and logged as `UNAVAILABLE`. **If you take this
  option, do not describe a phone call to customers anywhere** — not in onboarding, not in
  the app, not in the ladder copy.

### 1b. Neither message transport can deliver today

Measured against the running production container:

| transport | code | credentials | can deliver today |
|---|---|---|---|
| email (AWS SES) | REAL | `aws_access_key_id` **EMPTY**, `aws_secret_access_key` **EMPTY** | **no** |
| telegram | REAL | bot token SET, but `telegram_enabled=False` and **0 of 12 users** have a `telegram_chat_id` | **no** |

Email is the shorter path: 12 of 12 users already have an email address, so it needs
credentials only. Telegram additionally needs every customer to start a chat with the bot.

**Until one of these is fixed, arming the ladder produces `FAILED:` outcomes, not messages.**

---

## 2. Deploy and migration

1. Merge the branch (founder), build the image, deploy by your normal process.
2. Apply migration `047_customer_lane`.
   **Receipt:** `alembic current` reports `047_customer_lane`, and
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

**The 7-day IP lock and the once-per-week IP change limit are OPERATIONAL PROCEDURE, not
enforced by code.** The columns `ip_whitelisted_at` and `ip_lock_until` exist on
`customer_broker_link` and **nothing reads them**. If these limits matter, either enforce
them in code before go-live or track them manually and knowingly.

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
- The CALL rung is unwired and customers have been told a call will come.
- Neither email nor Telegram can deliver (§1b) — the ladder would log `FAILED:` and nobody
  would be reminded of anything.
- `preflight.check()` does not return `ready=True`.
- The calendar's coverage does not extend past the day you are arming (it currently ends
  **2026-12-31**).
- You cannot watch the screen for the whole session.
- It is a Friday, an expiry day, or the last hour before a long weekend.
