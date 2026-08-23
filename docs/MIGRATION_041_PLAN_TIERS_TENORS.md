# Migration 041 — Plan tiers + tenors (SPEC ONLY, NOT BUILT)

**Status:** deferred by founder decision. A migration is a deploy hard-stop, and
deploy is gated on BSE being solid + market-closed. This document is the
ready-to-execute plan for when that gate opens.

**Not in this document:** the OPTIONS honesty note. That shipped separately as
frontend-only work (`OptionsMetricsNote` + `mentionsOptions`, sourced from
`lib/risk-labels.ts`) and needs no migration. It already fires automatically the
moment a tier starts advertising options — i.e. the moment this migration lands.

---

## Why a migration is unavoidable

`subscription_plans` is a real table created **and seeded** by
`backend/migrations/versions/031_subscription_plans.py`. Prod's alembic head is
**040**, so 031 has already run and those three rows exist in production.

Two independent blockers:

1. **No tenor columns.** The model has exactly `price_monthly_inr` and
   `price_yearly_inr`. There is nowhere to put 3-month or 6-month prices.
2. **Tier content is seeded data.** The old caps live in each row's
   `feature_limits` JSON. Editing the `_SEED` literal in 031 changes **nothing**
   on prod, because 031 has already run — a trap worth naming explicitly,
   because it looks like a one-line copy change and silently has zero effect.

The frontend is **not** a second source: `lib/billing/plans.ts` is types-only and
both surfaces consume `GET /api/pricing/plans`. Changing frontend copy alone
would change nothing a customer is actually sold.

---

## (a) Schema — two new tenor columns

```python
op.add_column("subscription_plans", sa.Column(
    "price_quarterly_inr", sa.Numeric(10, 2), nullable=False,
    server_default="0"))
op.add_column("subscription_plans", sa.Column(
    "price_halfyearly_inr", sa.Numeric(10, 2), nullable=False,
    server_default="0"))
```

Additive and non-breaking: existing readers ignore them, and `server_default`
means no rewrite of existing rows is required before the UPDATE below.

**Rejected alternative — tenors inside `feature_limits` JSON.** It avoids the
schema change but puts *prices* inside a field the API returns as an opaque
render blob. Money belongs in typed, queryable columns; billing logic should
never have to reach into a display field.

Model change (`app/db/models/subscription_plan.py`): two `Mapped[Decimal]`
columns mirroring the existing pair. API + `PricingPlan` type gain the two
fields.

---

## (b) Data UPDATE — real structure, replacing the display-only caps

The old `feature_limits` carried marketing caps (`brokers: 1/3/6`,
`strategies: 5/50/200`). Those are **replaced**, not supplemented — leaving both
would put two contradictory claims on the same card.

The differentiator is now **SEGMENT + STRATEGY COUNT**.

| Tier | Strategies | Segments | Direction | Support |
|---|---|---|---|---|
| Starter | 1 | CASH | Long only (cash cannot short) | Email |
| Pro | 3 | CASH + OPTIONS | Long + Short | Priority |
| Premium | All | CASH + OPTIONS + FUTURES | Long + Short | Direct founder |

### Price ladder (per month, by tenor)

Monthly = list. 3-month ≈ −7%, 6-month ≈ −13%, yearly = −20%.

| Tier | Monthly | 3-month | 6-month | Yearly |
|---|---|---|---|---|
| Starter | ₹999 | ₹929 | ₹869 | ₹799 |
| Pro | ₹2,499 | ₹2,324 | ₹2,174 | ₹1,999 |
| Premium | ₹4,999 | ₹4,649 | ₹4,349 | ₹3,999 |

✅ **Monthly and yearly already match the 031 seed exactly** (999/799,
2499/1999, 4999/3999). Only the two new tenors are new money.

### New `feature_limits` shape

```jsonc
{
  "popular": false,
  "strategies": 1,              // number, or "all" for Premium
  "segments": ["CASH"],         // CASH | OPTIONS | FUTURES
  "directions": ["long"],       // long | short
  "killSwitch": true,
  "support": "Email",
  "bullets": [
    "1 strategy",
    "CASH only",
    "Long only",
    "Kill Switch",
    "Email support"
  ]
}
```

`brokers` and the old `strategies` caps are **removed**. Any frontend
feature-comparison row keyed on `brokers` must be removed in the same change, or
the table will render an empty column.

### The UPDATE itself

Write it as an explicit per-tier `op.execute(...)` keyed on `tier`
(`starter`/`pro`/`premium`), not a blanket rewrite — so a hand-edited prod row
cannot be silently clobbered by an assumption about its current contents.

**Downgrade:** restore the 031 `feature_limits` verbatim and drop the two
columns. Keep the old blob inline in the migration so the downgrade is real
rather than aspirational.

⚠️ **Pre-flight before running:** `SELECT tier, feature_limits FROM
subscription_plans` on prod and confirm the rows still match the 031 seed. If
anything was hand-edited since, the UPDATE must be reconciled first.

---

## (c) 🔴 The `razorpay_plan_id` problem — solve BEFORE checkout, not at it

`SubscriptionPlan.razorpay_plan_id` is a **single nullable `String(64)`** — one
id per tier. But Razorpay issues a plan id **per (tier, billing interval)**, so
the new structure needs **4 tenors × 3 tiers = 12 plan ids** and there are only
3 slots.

Today this is invisible: the column is NULL everywhere and Razorpay keys are
empty in prod. It becomes a hard blocker the first time real billing is switched
on — which is exactly the wrong moment to discover it.

### Recommended fix — a child table

```python
op.create_table(
    "subscription_plan_prices",
    sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
    sa.Column("plan_id", sa.Uuid(as_uuid=True),
              sa.ForeignKey("subscription_plans.id", ondelete="CASCADE"),
              nullable=False, index=True),
    # monthly | quarterly | halfyearly | yearly
    sa.Column("tenor", sa.String(16), nullable=False),
    sa.Column("price_per_month_inr", sa.Numeric(10, 2), nullable=False),
    sa.Column("razorpay_plan_id", sa.String(64), nullable=True),
    sa.UniqueConstraint("plan_id", "tenor", name="uq_plan_tenor"),
)
```

**Why this over the two columns in (a):** one row per sellable thing, so each
tenor carries its **own** Razorpay id, and a fifth tenor later is a row rather
than a migration. The unique constraint makes a duplicate tenor impossible.

**Trade-off, stated plainly:** this is a bigger change than (a) and requires the
pricing API and both frontend surfaces to read a price *list* instead of two
scalar fields.

### Decision to make before building

- **Option 1 — (a) now, child table later.** Fastest to ship; means a *second*
  migration before real billing, and the 12-id problem stays unsolved.
- **Option 2 — child table now (recommended).** One migration, solves tenors and
  the Razorpay id together. Founder's stated intent — *"solve it once, before
  checkout, not at it"* — points here.

If Option 2 is taken, the two columns in (a) are unnecessary: prices live in
`subscription_plan_prices` and `price_monthly_inr` / `price_yearly_inr` become
legacy (keep them populated for one release so nothing breaks mid-deploy, then
drop them in a later migration).

---

## Frontend follow-on (same change, no migration of its own)

- Tenor selector: monthly / 3-month / 6-month / yearly (the pricing page has a
  monthly↔yearly toggle today — it becomes a 4-way control).
- Show the discount per tenor (−7% / −13% / −20%) and the total billed amount.
- Replace the broker/strategy-cap comparison rows with segment + strategy count.
- `OptionsMetricsNote` will start rendering **by itself** on Pro and Premium
  once `segments`/bullets mention OPTIONS — already built and tested.

---

## Checklist for the gated deploy

- [ ] Founder picks Option 1 or Option 2 in (c)
- [ ] `SELECT tier, feature_limits FROM subscription_plans` pre-flight on prod
- [ ] Migration written with a real, tested downgrade
- [ ] Migration tested against the postgres_test harness (JSONB — SQLite will
      not exercise the JSON column faithfully)
- [ ] Frontend updated in the same release (comparison rows keyed on `brokers`
      MUST go, or the table renders an empty column)
- [ ] Verify `OptionsMetricsNote` renders on Pro + Premium after the data change
- [ ] Deploy hard-stop before migration, per CLAUDE.md
