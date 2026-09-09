# ADR 0003 — The record begins 1 September 2026, and it begins in exactly one place

- **Status:** Accepted
- **Date:** 2026-09-09
- **Supersedes nothing.** Extends ADR 0001's one-source-per-fact rule to the
  backend for this one constant.
- **Decider:** Jayesh Parekh (founder). The BSE python and CDSL only began
  running properly in September; he wants the record to start there without
  losing anything.

## Context

The platform had been counting everything it had ever done. That included an
April-to-August period of manual interference, a phantom position, three
strategies that have not traded since July, and a realised P&L of
**−195,830.51** accumulated while the system was being brought up.

He asked for a **tracking cut-off at 2026-09-01 00:00 IST** (= 2026-08-31
18:30 UTC): everything before it archived and hidden from what the platform
counts and shows; everything from it onward is the record.

The census, taken before deciding:

| | today | after the cut |
| --- | --- | --- |
| positions (all) | 34 | 3 |
| positions still open/partial | 1 | **1** |
| executions (real broker orders) | 115 | 13 |
| signals | 117 | 6 |
| priced round trips (/analytics) | 8 | **0** |
| strategies with any visible position | 5 | 1 |
| net realised P&L (live) | −195,830.51 | **0.00** |

Straddlers — a position opened before and closed after the line — were
**zero**, so the boundary is clean today.

He approved knowing the record starts at **zero closed trades**, not a small
number, and that CDSL (last traded 24 July) and ANGELONE would show nothing.

## Decision

### 1. NOTHING IS DELETED, and nothing is even written

The cut-off is a **setting**, not a column: `settings.tracking_epoch`, read
only through `app/core/tracking_epoch.py`. Pre-cut rows are untouched. They are
real broker orders held for tax and audit, and the archive must remain
**priceable** — the P&L reconciler still reaches it.

A column was rejected. `opened_at` already holds the fact, so a flag would
duplicate it and could drift — and always in the flattering direction: a row
inserted later with a pre-cut date would take `server_default false` and enter
the published record silently. Backfilling one would also mean writing to real
broker-order history, and "reversible by changing one value" would stop being
literally true. The precedent is the founder's own
`pnl_reconciler_lookback_hours`, whose docstring already calls itself "the SOLE
boundary that excludes pre-existing manual-era trips".

The default lives in `config.py`, in git — not only in `.env`. A restore from a
database dump must reproduce the **definition** of the record, not just its rows.

### 2. THE ANCHOR RULE — one column per table, decided once

```
strategy_positions   → opened_at      a trade belongs to when it was ENTERED
strategy_executions  → placed_at      an order belongs to when it was SENT
strategy_signals     → received_at    a signal belongs to when it ARRIVED
trade_markers        → timestamp_utc
```

This exists because straddlers are zero **today**. `opened_at` and `closed_at`
therefore agree, and will keep agreeing right up until the first position spans
a future cut-off. On that day this rule decides, not the instinct of whoever is
holding the keyboard. Callers ask for a predicate **by table**
(`positions_in_record()`); no call site spells a column itself.

### 3. THE CUT-OFF NEVER TOUCHES THE EXECUTION PATH

`app/core/tracking_epoch.py` may not be imported by — nor may
`settings.tracking_epoch` be read by — `strategy_executor`, `direct_exit`,
`position_manager`, `position_lookup`, `order_service`,
`futures_expiry_backstop`, `kill_switch_service`, `marketplace_fanout`, the
position or reconciliation loops, or the webhooks.

Not style. Concretely:

- **the kill switch** — a filtered select leaves a real open Dhan position the
  brake silently skips, and the endpoint still answers success, because it
  reports what it closed rather than what it should have;
- **the reconciliation loop** — recreates the phantom-BUY-800 blindness on an
  age axis: a live broker leg, no visible DB counterpart, `db_only` empty;
- **`position_lookup`** — would not even error. The webhook logs
  `exit_no_open_position` and returns success on purpose, to stop TradingView
  retry storms, so an expiry-day exit would simply never happen.

**And not the P&L reconciler.** Its `since` is a different fact with a similar
name — its own docstring calls it "the GOING-FORWARD boundary". Wiring the
epoch in would stop it pricing new trips and make the archive unpriceable,
which defeats the reason the archive is kept.

`tests/integration/test_tracking_epoch_isolation.py` pins all of this, and pins
it the way ADR 0001 §7 demands: every guard test runs its query twice — once as
the code really is, once with the filter **injected** — and asserts the first
finds the pre-cut position and the second does not. The sensitivity proof runs
on every pass. Injecting the filter into `kill_switch_service.py` was verified
to turn the suite red.

### 4. THE ARCHIVE IS DISCLOSED, NEVER DENIED

Every affected surface says so, with the date coming **from the server**
(`GET /api/system/mode` → `tracking_epoch`), never hardcoded — the same
discipline the paper banner was fixed for:

> Record 1 Sept 2026 se — usse pehle ka data archive mein hai.

A strategy with no post-cut trades shows an honest empty state and is **never
hidden**: *"Is strategy ne 1 Sept ke baad abhi tak koi trade nahi kiya."* A
strategy vanishing would be its own lie, and ADR 0001 §4 requires the empty
state anyway.

### 5. THE LEDGER RECORDS ITS OWN WINDOW

`ledger_snapshots` is append-only and hash-chained: once sequence #1 exists its
numbers cannot be corrected without breaking verification. Migration **047**
adds a nullable `tracking_epoch` column so each chained row records which window
it covers — otherwise a later change to the epoch silently changes what every
historical row *means* while the chain still asserts the old value.

It is deliberately **not** inside `data_hash`: adding a field to the hashed
payload would invalidate verification for every existing row.

Taken **before snapshot #1**, while the table holds zero rows. That timing is
the whole reason it is a schema addition and not an edit to an immutable
record.

## Consequences

- `/analytics` shows **0 priced round trips** and ₹0 realised. That is the
  truth about the record's first days, not a bug. It stays 0 until one clean
  bot round trip completes with no manual fills on the same contract.
- CDSL and ANGELONE render empty states until they trade again.
- The −195,830.51 is archived, not deleted, and remains priceable.
- Moving the epoch is one line. Moving it **after** snapshot #1 is not — the
  chain will hold numbers computed under the old window, which is exactly why
  047 stamps the window on the row.
- Every new reporting surface must remember the filter. There is no shared base
  query to enforce it, and deliberately so: a global default filter is the one
  implementation that would leak into the execution path.

## Alternatives rejected

**A column (`archived` / `tracking_epoch` on rows).** Duplicates a fact
`opened_at` already holds, requires writing to real broker-order history,
fails in the flattering direction on later inserts, and makes reversal a second
write. It would also have been the first migration ever to write to
`strategy_positions`.

**Deleting the pre-cut rows.** Never considered. They are a tax and audit
record; the founder's standing rule is that his data is archived, never deleted.

**A global/default query filter** (SQLAlchemy `with_loader_criteria`, a query
event, or a filter on the model). It would apply the boundary in one place —
and that place would include the kill switch.
