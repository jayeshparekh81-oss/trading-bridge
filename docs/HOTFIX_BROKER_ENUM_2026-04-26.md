> **SUPERSEDED — 2026-05-04**
>
> This planned hotfix was NOT executed. Investigation on 2026-05-04 revealed:
> 1. The actual root cause was different from what's documented below.
> 2. The real fix had already shipped in commit `5de7128` (2026-04-24) — frontend
>    lowercase normalization + backend validation + migration 002.
> 3. `BrokerName` is `StrEnum` (not plain Enum), which changes SAEnum behavior
>    such that the `values_callable` workaround documented below was unnecessary.
> 4. Production has been stable since 2026-04-26. `/api/users/me/brokers` works.
>
> Keeping this document for historical context — it shows the (incorrect)
> diagnosis from a 21+ hour day. Actual fix lives in commit 5de7128.
>
> **Do not execute the plan below.**

---

[original content continues...]

# Hotfix: Broker enum case mismatch (planned for 2026-04-26)

**Status:** PLANNED — do NOT execute tonight (2026-04-25). Author was awake 21+ hours when this was scoped; fresh-eyes review tomorrow morning before any change lands.

**Severity:** P1 — `/api/users/me/brokers` is 500-ing for any user with a real `broker_credentials` row. Latent in 6 other tables.

**Customer impact tonight:** acceptable. Frontend shows the honest "Couldn't load brokers" banner (Layer 1 fix from commit `83d9d6b` shipped earlier today). No customer trades blocked because the brokers list is read-only on this page; the order-execution path uses the same model so live trading would also break — but no real customer trades are happening tonight.

---

## 1. Problem summary

`GET /api/users/me/brokers` raises:

```
LookupError: 'fyers' is not among the defined enum values.
Enum name: broker_name_enum.
Possible values: FYERS, DHAN, SHOONYA, ZERODHA, UPSTOX, ANGELONE
```

The DB column holds **lowercase** values (`'fyers'`, `'dhan'`, …). SQLAlchemy is validating against **uppercase NAMES** (`FYERS`, `DHAN`, …) on row hydration. Mismatch → `LookupError` at every fetch.

`/trades/stats` accidentally still works only because the `trades` table has no rows for the test user yet. The same crash will happen on `/trades`, `/audit_logs`, `/webhooks`, `/algomitra/messages`, etc., as soon as those tables get real data.

---

## 2. Root cause

`backend/app/db/models/broker_credential.py:38`:

```python
broker_name: Mapped[BrokerName] = mapped_column(
    SAEnum(BrokerName, name="broker_name_enum", native_enum=False),
    nullable=False,
)
```

When SQLAlchemy is given an enum class and `native_enum=False`, the **default `values_callable` returns the enum's NAMES, not its VALUES**. So:

- `BrokerName.FYERS = "fyers"` → name `"FYERS"`, value `"fyers"`
- SAEnum emits CHECK / validates against `["FYERS", "DHAN", "SHOONYA", ...]`
- Migration 001 created the column constraint with the *string list* `["fyers", "dhan", ...]` — the lowercase strings

So the column constraint is lowercase but the SQLAlchemy hydrator's allow-list is uppercase — they were written by different paths and have always been misaligned. It only surfaces now because:

1. Migration 002 (`fix_broker_name_case`) explicitly LOWERed all data (so any historical uppercase rows became lowercase).
2. The frontend POST started sending lowercase (commit `5de7128`).
3. With lowercase data + uppercase-expecting hydrator, every read crashes.

The fix is one parameter on `SAEnum`:

```python
SAEnum(BrokerName, name="broker_name_enum", native_enum=False,
       values_callable=lambda obj: [e.value for e in obj])
```

This makes SQLAlchemy validate against the enum's **VALUES** (lowercase), matching the DB.

This same flaw is present in **7 model column definitions**. List in §6.

---

## 3. Current DB state (verified 2026-04-25 evening)

```
SELECT id, broker_name, is_active, created_at FROM broker_credentials;
→ 5 rows for the founder's user_id
   - 4 rows: broker_name = 'fyers' (lowercase), is_active = true
   - 1 row: broker_name = 'FYERS' (uppercase), is_active = true
   - All created on 2026-04-24 (yesterday, debug session)

\dT broker_name_enum
→ "broker_name_enum" does not exist as a Postgres type
   (Migration 002 dropped the type; column is now plain VARCHAR with a CHECK)
```

Implication:
- Multiple duplicates from yesterday's debug attempts. Cleanup needed regardless of the code fix.
- The lone uppercase row predates `5de7128` (the lowercase normalisation commit). It was missed by migration 002 because 002 ran **before** that row was inserted.
- No native Postgres ENUM type exists, only a CHECK constraint. So data fixes are simple `UPDATE` statements; no enum-type ALTER required.

---

## 4. Recommended path: hotfix branch (Path A)

We chose this over Path B (full main pull) because main carries Phase 1B AlgoMitra backend code (`anthropic` SDK import, migrations 003 + 004) that EC2 hasn't ingested yet. Pulling main now would crash backend at import time without `pip install anthropic` + `alembic upgrade head`. The enum fix should not require that risk.

**Branch shape:**

- Base: `5de7128` (the commit currently deployed on EC2, per yesterday's "Backend AWS NOT updated" decision)
- Patch: `values_callable` added to all 7 SAEnum sites
- Branch name: `hotfix/enum-values-callable`
- Push to origin so EC2 can `git fetch && git checkout hotfix/enum-values-callable`

**Why not just edit the file in place on EC2?** Optionally fine, but a branch leaves a clean audit trail and lets us merge the same fix into main later when AlgoMitra activates.

---

## 5. SQL cleanup (run BEFORE the code deploy)

Goal: leave exactly one `is_active = true` Fyers row per user; archive the rest.

```sql
-- Step 1. Normalise the lone uppercase row.
-- (Migration 002 missed it because the row was inserted after 002 ran.)
UPDATE broker_credentials
SET broker_name = LOWER(broker_name)
WHERE broker_name <> LOWER(broker_name);

-- Step 2. Keep only the most recent active credential per (user_id, broker_name);
-- deactivate the older duplicates so the user sees a single Fyers card.
-- We deactivate rather than DELETE — preserves audit history.
WITH ranked AS (
  SELECT
    id,
    ROW_NUMBER() OVER (
      PARTITION BY user_id, broker_name
      ORDER BY created_at DESC
    ) AS rn
  FROM broker_credentials
  WHERE is_active = true
)
UPDATE broker_credentials
SET is_active = false
WHERE id IN (SELECT id FROM ranked WHERE rn > 1);

-- Verify: should show exactly 1 active row per (user_id, broker_name).
SELECT user_id, broker_name, COUNT(*) FILTER (WHERE is_active) AS active_count
FROM broker_credentials
GROUP BY user_id, broker_name
ORDER BY user_id, broker_name;
```

Run inside `docker compose exec postgres psql -U trading_bridge -d trading_bridge`.

**Both steps are idempotent.** Re-running is safe.

---

## 6. Code changes — 7 sites

Add `values_callable=lambda obj: [e.value for e in obj]` to every `SAEnum(...)` call. The pattern is identical in each file; the type name changes.

### 6.1 `backend/app/db/models/broker_credential.py:38`

```python
broker_name: Mapped[BrokerName] = mapped_column(
    SAEnum(
        BrokerName,
        name="broker_name_enum",
        native_enum=False,
        values_callable=lambda obj: [e.value for e in obj],
    ),
    nullable=False,
)
```

### 6.2 `backend/app/db/models/trade.py:73,77,81,88` — 4 sites

```python
side: Mapped[OrderSide] = mapped_column(
    SAEnum(OrderSide, name="order_side_enum", native_enum=False,
           values_callable=lambda obj: [e.value for e in obj]),
    nullable=False,
)
order_type: Mapped[OrderType] = mapped_column(
    SAEnum(OrderType, name="order_type_enum", native_enum=False,
           values_callable=lambda obj: [e.value for e in obj]),
    nullable=False,
)
product_type: Mapped[ProductType] = mapped_column(
    SAEnum(ProductType, name="product_type_enum", native_enum=False,
           values_callable=lambda obj: [e.value for e in obj]),
    nullable=False,
)
status: Mapped[TradeStatus] = mapped_column(
    SAEnum(TradeStatus, name="trade_status_enum", native_enum=False,
           values_callable=lambda obj: [e.value for e in obj]),
    nullable=False,
)
```

### 6.3 `backend/app/db/models/algomitra_message.py:50` *(only present in commits ≥ `067a77c`; not in `5de7128`)*

If hotfix branches off `5de7128`, this file does not exist on the branch — skip. When AlgoMitra activates later, ensure the same fix is applied there before deploy.

### 6.4 `backend/app/db/models/webhook_event.py:35`

```python
processing_status: Mapped[ProcessingStatus] = mapped_column(
    SAEnum(ProcessingStatus, name="processing_status_enum", native_enum=False,
           values_callable=lambda obj: [e.value for e in obj]),
    nullable=False,
)
```

### 6.5 `backend/app/db/models/audit_log.py:42`

```python
actor: Mapped[ActorType] = mapped_column(
    SAEnum(ActorType, name="actor_type_enum", native_enum=False,
           values_callable=lambda obj: [e.value for e in obj]),
    nullable=False,
)
```

**Total LOC changed:** 7 column definitions, ~14 lines (one extra parameter line per call). No new imports, no logic changes, no migration.

---

## 7. Branch creation steps (do on local machine first)

```bash
cd /Users/jayeshparekh/projects/trading-bridge
git fetch origin
git checkout -b hotfix/enum-values-callable 5de7128

# Apply the 6 file edits (broker_credential, trade, webhook_event, audit_log + 2
# more if branch is later than 5de7128 — confirm what's present on the branch).

# Verify locally
cd backend && python3 -m py_compile app/db/models/broker_credential.py \
                                  app/db/models/trade.py \
                                  app/db/models/webhook_event.py \
                                  app/db/models/audit_log.py
cd ..

git add backend/app/db/models/
git commit -m "fix(db): add values_callable to SAEnum columns — fixes lowercase enum hydration"
git push -u origin hotfix/enum-values-callable
```

---

## 8. EC2 deploy steps (after SQL cleanup)

```bash
ssh ubuntu@43.205.195.227
cd /path/to/trading-bridge

# 1. Pull the hotfix branch.
git fetch origin
git checkout hotfix/enum-values-callable
git pull --ff-only

# 2. Restart backend (no pip install needed; no migration needed).
docker compose restart backend

# 3. Verify backend is healthy.
curl -s http://localhost:8000/health
# → {"status":"ok"}
```

**No `pip install`. No `alembic upgrade`. No env var changes.** Only a code pull + container restart.

---

## 9. Verification

```bash
# From EC2 — local probe
curl -s http://localhost:8000/health
curl -s http://localhost:8000/api/users/me/brokers \
     -H "Authorization: Bearer <test-token>"
# → expect a JSON list, not a 500
```

From browser:
1. Open `https://tradetri.com/brokers` (logged in).
2. The "Couldn't load brokers" banner should be **gone**.
3. Real Fyers card visible with the actual `created_at` ("Connected ~Xh ago").
4. Open devtools → Network → confirm `/api/users/me/brokers` returns `200`, not `500`.

---

## 10. Rollback plan

If the deploy makes things worse:

```bash
ssh ubuntu@43.205.195.227
cd /path/to/trading-bridge
git checkout 5de7128
docker compose restart backend
```

The SQL cleanup (§5) is data-safe to leave in place even if the code rolls back — it only deactivates duplicate rows; nothing is destroyed.

---

## 11. Out of scope tomorrow

Do **not** mix any of these into the hotfix:

- Phase 1B AlgoMitra deploy (still parked behind `ANTHROPIC_API_KEY` decision).
- Backend `last_used_at` column for real "last sync" timestamp on the brokers page (Layer 2 of yesterday's plan).
- Premium waitlist backend (Path C from the reconnect-banner task — also parked).
- Any frontend changes.

Each of those has its own activation gate. Don't bundle.

---

## 12. Tomorrow morning checklist (Sunday 2026-04-26 ~9 AM IST)

- [ ] Review this document with fresh eyes.
- [ ] Re-run the DB query from §3 to confirm state hasn't drifted overnight.
- [ ] Create `hotfix/enum-values-callable` branch off `5de7128` (§7).
- [ ] Apply 6 file edits (§6, skipping 6.3).
- [ ] Local `py_compile` to catch syntax errors before push.
- [ ] Push branch.
- [ ] SSH EC2.
- [ ] Run SQL cleanup (§5).
- [ ] `git checkout hotfix/enum-values-callable && docker compose restart backend`.
- [ ] Curl `/health`, then `/api/users/me/brokers` with auth.
- [ ] Browser test on `tradetri.com/brokers` (logged in).
- [ ] If green → customer outreach.
- [ ] If red → rollback per §10, regroup.

---

*Document author: Claude Code session, 2026-04-25 evening (IST). Founder approved scope before sleep; nothing was executed tonight.*
