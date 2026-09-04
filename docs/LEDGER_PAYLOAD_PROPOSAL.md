# Transparency Ledger — re-pointing the snapshot payload at real positions

**Status: PROPOSAL. No snapshot has been taken. No code in this document is built.**
Founder's rule that governs every choice below: *publish NOTHING rather than a
zero — an empty ledger is honest, a zero ledger is a permanent lie on a
hash-chained record.*

---

## 1. Audit — what the payload does today, and why it must not run

`gather_performance_payload` (`backend/app/strategy_engine/ledger/snapshots.py:102`)
builds every number the ledger publishes from two sources:

| field | source today | value it would publish for the BSE listing |
|---|---|---|
| `cumulative_pnl_inr`, `win_rate`, `max_drawdown_pct` | completed `paper_sessions` for the strategy | **0 / 0 / 0** — the live strategy has 0 completed paper sessions |
| `live_trades_count` | `count(*)` of the legacy **`trades`** table | **0** — the strategy engine never writes that table (0 rows on prod) |
| `paper_trades_count` | sum over paper sessions | 0 |
| `total_trades` | paper + live | **0** |

The strategy behind that listing has **49 real owner executions and 12 closed
positions**. A snapshot today would publish "0 trades, ₹0 P&L" as sequence #1
of an append-only chain (`ledger_snapshots` is "never UPDATEd or DELETEd" by
design; `verify` walks the chain and flags any change as tampering). There is
no correction path short of deleting the chain out-of-band — which the
verification API would then report as tampering.

Side-effect-wise the trigger is clean: `create_daily_snapshot` inserts one
`LedgerSnapshot` + one `LedgerAttestation`, calls no broker, writes no strategy
or position row, is idempotent per UTC day (`UNIQUE(listing_id, snapshot_date)`
→ 409). The trigger is `POST /marketplace/listings/{id}/ledger/snapshot/now`,
creator-only with an ownership check, reachable from
`creator-dashboard-card.tsx:63`. It is **not scheduled** — nothing in celery
beat. The endpoint's own docstring names beat as "Phase 4".

**Root cause is the same one the CSV export had**: the code reads the dead
`Trade` table. The ledger's live figures must come from `strategy_positions`,
priced by the P&L reconciler.

---

## 2. What the reconciler can and cannot give the ledger

The reconciler (`backend/app/domains/pnl_reconciler/service.py`) reconstructs
each **closed** position's round trip from `action_history` events and the
REAL broker fills in `strategy_executions.broker_response`, and returns per
trip: `gross_pnl`, an itemised estimated `costs` breakdown, `net_pnl`, and a
`complete` flag with `flags` explaining any gap. It is **pure and read-only
by default** (`reconcile_strategy(session, strategy_id, write=False)`), which is
exactly the shape the payload needs.

Prod, BSE strategy `89423ecc`, as of 2026-09-03 (read-only export, recomputed
locally with the de-dup fix in cutover-21):

| | count | notes |
|---|---|---|
| closed positions | 12 | |
| `final_pnl` already set | 1 | `bf70e28c`, exit_reason `paper_test_cleanup_20260524`, **final_pnl = ₹0.00** — a cleanup row, not a trade |
| `final_pnl` NULL | 11 | closed 2026-05-19 → 2026-08-31 |
| **complete** (reconciler can price them) | **7** | exits: direct_sl ×5, direct_exit ×2 |
| incomplete | 5 | close-qty mismatch ×2, entry fill missing ×1, no close legs ×2 (`manual_exit_dhan_jun5`, `manual_founder_close`, two `phantom_cleanup_*`) |
| net P&L, 7 complete trips | ₹−329,981.97 | gross ₹−325,392.19 − est. costs ₹4,589.78 |

So the reconciler can price **7 of 12** today. The other 5 cannot be priced
from platform data at all — their exits happened on Dhan's own app, or they
were phantom/cleanup rows. They are not "pending"; they are permanently
unknown to the platform.

The single non-NULL `final_pnl` is a **stored zero on a non-trade**. Under the
founder's rule it must never be summed into anything the ledger publishes.

---

## 3. Proposal

### 3.1 Source of truth for live figures

Replace the `Trade`-table count and the paper-session aggregates with a
read-only reconciler pass over the listing's strategy:

```
trips = reconcile_strategy(db, listing.strategy_id, write=False).trips
priced   = [t for t in trips if t.complete and t.net_pnl is not None]
unpriced = [t for t in trips if not t.complete]
```

Derived from `priced` **only**:

| ledger field | definition |
|---|---|
| `live_trades_count` | `len(priced)` |
| `cumulative_pnl_inr` | `sum(t.net_pnl for t in priced)` — **NET of estimated costs**, never gross |
| `win_rate` | `len([t for t in priced if t.net_pnl > 0]) / len(priced)` |
| `max_drawdown_pct` | peak-to-trough on the cumulative `net_pnl` series ordered by `closed_at` |
| `paper_trades_count` | 0 for a live strategy (see 3.4) |
| `total_trades` | `live_trades_count + paper_trades_count` |

Two new fields the row must carry so the number is honest about its own
coverage (schema change — see 3.6):

| field | definition |
|---|---|
| `unpriced_positions` | `len(unpriced)` — closed positions the platform could **not** price |
| `pnl_basis` | literal `"reconciled_net_estimated_costs"` — the costs are a published-rate **estimate**, not contract-note actuals, and the ledger must say so |

### 3.2 `final_pnl` NULL — do not read it, do not write it

The payload **never reads `strategy_positions.final_pnl`**. It recomputes from
fills every time via the reconciler. Reasons:

* 11 of 12 are NULL, and the only non-NULL is a stored zero on a cleanup row.
  Reading the column today would either publish nothing or publish that zero.
* Whether to *write* `final_pnl` is the `pnl_reconciler_write` decision, which
  stays the founder's. The ledger must not depend on it, and must not become
  the reason to flip it.
* Recomputing is deterministic: same fills → same net → same `data_hash`.
  The chain does not need `final_pnl` to be stable.

When the write flag is eventually turned on, nothing here changes — the
reconciler's output is the same number either way. That is the point: the
ledger and `final_pnl` would agree by construction, not by copying.

### 3.3 Incomplete data — publish nothing, not zero

Three distinct situations, three distinct behaviours:

| situation | behaviour |
|---|---|
| **No priced trips at all** (`len(priced) == 0`) | **Refuse to snapshot.** Raise a typed `NothingToPublishError`; the endpoint returns **422** with a plain reason; nothing is inserted. The UI keeps showing "no snapshot yet". An empty ledger is honest. |
| **Some priced, some unpriced** (today: 7 / 5) | Snapshot the 7, and publish `unpriced_positions = 5` in the same row so the coverage gap is *on the chain*, not hidden. The panel renders "7 of 12 closed positions priced". |
| **Reconciler raises / DB error mid-payload** | Propagate; no partial row. `create_daily_snapshot` already commits only at the end. |

Two invariants, enforced in code and by test:

* A `cumulative_pnl_inr` of exactly `0` with `live_trades_count == 0` is
  **never written**. It is the refuse case above.
* `paper_trades_count` is **never** summed into `total_trades` for a listing
  whose strategy is live (`is_paper = false`). Paper sessions from before
  go-live are not the live record.

### 3.4 Paper listings

For a paper strategy (`is_paper = true`) the existing paper-session
aggregation is the right source and stays as is, **with the same refuse rule**:
zero completed sessions → no snapshot. Nothing in this proposal touches paper
logic beyond that guard.

### 3.5 The daily beat — wait

**Do not schedule until the payload has produced a correct snapshot on real
data at least once, by manual trigger, and the founder has read it.**

Order of operations:

1. Build the re-pointed payload + tests (fixture = the real BSE rows, pinned
   to the numbers in §2).
2. Add a **dry-run** to the trigger endpoint: `POST …/snapshot/now?dry_run=true`
   returns the payload the snapshot *would* write, inserts nothing. Creator-only
   like the real trigger.
3. Founder runs the dry-run against the BSE listing and compares to §2.
4. Founder takes the first real snapshot manually (sequence #1).
5. Only then: beat, `crontab(hour=10, minute=45, day_of_week="1-5")` UTC
   = **16:15 IST weekdays**, after the 15:30 close and after the 16:00 IST
   `reconcile_recent_pnl` log-only pass, one snapshot per listing per day.
   The trigger's own 409-on-duplicate makes a beat + manual overlap harmless.

Cadence reasoning: the numbers only change when a position closes, positions
close during market hours, and a daily post-close row is what the panel's
"days since publish" and drawdown series assume. Weekly would leave the chain
stale for most of its life; intraday would chain noise.

### 3.6 Schema

Two additive nullable columns on `ledger_snapshots` (`unpriced_positions
INTEGER`, `pnl_basis VARCHAR(48)`), plus the same two on `LedgerSnapshotRead`.
Data-only for existing rows: there are **none** (0 snapshots on prod), so the
downgrade is a plain column drop with nothing to restore. Same discipline as
041–043: pre-flight, proven on a throwaway Postgres, founder's go.

`data_hash` is computed over the payload dict, so the two new fields become
part of the hash from sequence #1. There is no chain to migrate.

### 3.7 What this does NOT do

* Does not touch `pnl_reconciler_write`, `final_pnl`, or any strategy or
  position row.
* Does not take a snapshot. Does not schedule one.
* Does not change the hash or chain algorithm.
* Does not change how paper listings are aggregated.
* Does not touch the sacred paths (no webhook, executor, exit, broker, or
  fan-out code).

---

## 4. Decisions needed from the founder before any of §3 is built

1. **Net vs gross on the public record.** This proposes NET of *estimated*
   costs, labelled as such via `pnl_basis`. The alternative is gross with a
   separate costs column. Net is what a customer's account actually moved by;
   gross is what is provable from fills alone.
2. **The 5 unpriced positions.** Publish the count (proposed), or omit the
   listing from the ledger until every closed position can be priced (which
   for the two manual-Dhan exits is never).
3. **The `bf70e28c` cleanup row** (`final_pnl = 0.00`, paper test). It is
   excluded from everything here by the `complete` filter (its trip has no
   close legs), but it is a stored zero in a column that may one day be read.
   Leave it, NULL it, or delete the row — your call; not touched here.
4. **Go / no-go on the dry-run endpoint** (§3.5 step 2) as the first build.
