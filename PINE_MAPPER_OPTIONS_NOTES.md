# Pine mapper — options support (Phase 2B)

**Branch:** `feat/pine-mapper-options` (built on `feat/scrip-master-options-parser` @ `7b26aee`)
**Files:** `backend/app/services/pine_mapper.py`, `backend/app/schemas/pine_webhook.py`, `backend/tests/services/test_pine_mapper_options.py`
**Date:** 2026-05-23

> **Branch base note.** The task header said "off main (HEAD 3f8dd65)" but
> also "Builds on feat/scrip-master-options-parser (7b26aee) — ScripMeta".
> Those conflict: `ScripMeta` only exists in 2A. Since scope #4 requires a
> ScripMeta lookup, this branch was cut from `7b26aee` (the 2A branch HEAD)
> so the parser changes are available to consume. No `dhan.py` changes were
> made — 2A's `_ScripMaster._meta` is consumed read-only.

---

## Critical semantic — Options are NRML carry-forward ONLY

Options positions are **multi-day**. MIS/INTRADAY product types are
auto-squared-off by the broker at ~15:15–15:30 IST, which would silently
liquidate an open options position. **MIS/INTRADAY are therefore forbidden
for options.** This is enforced in two places (defence in depth):

1. **Schema** — `OptionsConfig._must_be_nrml` rejects anything that isn't
   `NRML`/`MARGIN` (and `_must_carry_forward` requires `carry_forward=true`)
   at parse time, raising `ValueError` → translated to `PineMapperError`.
2. **Order boundary** — `_enforce_nrml(config)` re-checks immediately
   before `OrderRequest` construction, guarding against a config object
   mutated after parse.

The built `OrderRequest` **always** sets `product_type=ProductType.MARGIN`
— the enum member whose documented meaning is *"NRML / overnight margin
(F&O carry-forward)"* (`schemas/broker.py:66`). There is no separate
`NRML` enum member; `MARGIN` **is** NRML.

---

## 1. Options signal payload schema (`PineAlertPayload`)

`backend/app/schemas/pine_webhook.py` — raw Pine v4.8.1 alert body,
`extra="allow"` (tolerates the ~17 indicator keys). Phase 2B adds two
**optional** fields, so existing futures alerts that omit them still
validate:

| Field | Type | Purpose |
|-------|------|---------|
| `spot_price` | `Decimal \| None` (≥0) | Underlying spot for strike resolution. Falls back to `price` when absent. |
| `signal_direction` | `LONG_ENTRY \| SHORT_ENTRY \| EXIT \| None` | Normalised direction; overrides the legacy `type` field when present. |

The normalised `StrategyWebhookPayload` (post-mapping shape consumed by the
webhook handler) was **not** changed → the live BSE LTD futures path is
untouched.

## 2. Strategy options config schema (`OptionsConfig`)

Lives on `Strategy.strategy_json` under the `"options"` key (or, if the
config carries an options marker key, at the top level of `strategy_json`).
There is **no `instrument_type` column** on the `Strategy` model and no
migration was added; detection reads `strategy_json` with a forward-compat
`getattr(strategy, "instrument_type", ...)` fallback.

```jsonc
{
  "instrument_type": "options",
  "options": {
    "option_type": "auto",              // auto | CE_only | PE_only
    "strike_selection": {"method": "ATM", "offset": 0},  // ATM | OTM_OFFSET | ITM_OFFSET
    "expiry": "current_week",           // current_week | next_week | current_month
    "premium_budget_per_lot": 18000,
    "product_type": "NRML",             // MUST be NRML/MARGIN — MIS/INTRADAY rejected
    "carry_forward": true,              // MUST be true
    "expiry_day_force_close": true,
    "no_intraday_squareoff": true,
    "strike_step": 100                  // optional override; default 100 (see below)
  }
}
```

Validation: `product_type ∈ {NRML, MARGIN}` (case-insensitive, normalised to
`"NRML"`); `MIS`/`INTRADAY`/`CNC`/`DELIVERY` → `PineMapperError`.
`carry_forward` must be `true`.

## 3. Public API added to `pine_mapper.py`

| Function | Returns | Notes |
|----------|---------|-------|
| `is_options_strategy(strategy)` | `bool` | instrument_type attr → strategy_json.instrument_type → options block |
| `parse_options_config(strategy)` | `OptionsConfig` | NRML violations → `PineMapperError` |
| `resolve_atm_strike(spot, step=100)` | `Decimal` | half-up rounding to nearest step |
| `resolve_strike(spot, opt_type, method, offset, step)` | `Decimal` | ATM / OTM_OFFSET / ITM_OFFSET |
| `resolve_options_expiry(ref, type, weekday=3, holidays=None)` | `date` | current_week / next_week / current_month |
| `resolve_option_type(direction, config)` | `"CE"`/`"PE"` | auto: LONG→CE, SHORT→PE |
| `map_pine_to_option_order(payload, strategy, *, spot_price, reference_date, scrip_master)` | `OrderRequest` | full build; product_type ALWAYS MARGIN/NRML |
| `PineMapperError(PineMappingError)` | — | subclass → existing webhook `except PineMappingError` still catches it |

`map_to_tradetri_payload` (the existing futures/dict flow) is **unchanged**.

---

## 4. Strike step assumption for BSE LTD — ⚠️ FLAG FOR VERIFICATION

`_DEFAULT_STRIKE_STEP = Decimal("100")`. **This is an assumption** — verify
against the live BSE LTD options contract spec (BSE Ltd trades on NSE F&O)
before Phase 3 live wiring. It is overridable per-strategy via
`OptionsConfig.strike_step`, so a correction needs no code change once
verified.

Likewise `_WEEKLY_EXPIRY_WEEKDAY = 3` (Thursday) follows the task's stated
"current_week = next Thursday for BSE LTD weekly" convention. NSE has
revised weekly-expiry weekdays for some instruments in recent years and
single-stock options are conventionally **monthly** (last Thursday) — so
the weekly-Thursday assumption is also **flagged for verification**. The
weekday is a parameter on `resolve_options_expiry`, so it is trivially
adjustable.

## 5. Holiday handling

No holiday calendar ships in the codebase today (consistent with
`futures_resolver.py`, which computes "last Thursday" purely from the
calendar with a documented caveat). `resolve_options_expiry` accepts an
optional `holidays: set[date]`; when the computed expiry lands on a holiday
it shifts to the **previous** day (mirrors NSE's "previous working day"
rule). **By default no holiday set is passed**, so expiry is calendar-only
— acceptable for the immediate window, to be wired to a published calendar
in a later phase.

## 6. Expiry-day force close

`OptionsConfig.expiry_day_force_close` (default `true`) and
`no_intraday_squareoff` (default `true`) are **carried on the config and
validated, but not yet acted upon** by the mapper — they are inputs for the
Phase 3 executor/position-loop, which owns position lifecycle. They are
documented here so the contract is explicit:

> Options carry forward overnight under NRML. They are **not** intraday
> squared-off. They are force-closed only on **expiry day** (so a worthless
> or deep-ITM contract doesn't go to physical settlement / auto-exercise).

---

## 7. Downstream integration notes (Phase 3 — OUT OF SCOPE here)

- **Executor is frozen** and still **hard-codes `Exchange.NFO`**. The
  mapper derives the exchange from the matched `ScripMeta.segment`
  (`NSE_FNO→NFO`, `BSE_FNO→BFO`), but until the executor consumes the built
  `OrderRequest`, that mapping is not exercised in production. Wiring
  `map_pine_to_option_order` into the executor is Phase 3.
- **Symbol resolution** scans `_ScripMaster._meta` for a row matching
  `(option_type, strike, expiry, underlying-root substring)` — a read-only
  consumption of 2A. It depends on the scrip master being loaded and on the
  Dhan options-symbol format that 2A parses; the exact live symbol string
  was not verifiable here.
- **No DB INSERT** of a BSE LTD Options strategy row (separate phase).
- **No real broker order placement, no Greeks, no options-chain feed.**
- `premium_budget_per_lot` is parsed/validated but **not yet used** to size
  or cap the order — qty is `entry_lots * lot_size`. Budget-based sizing is
  a Phase 3 concern (needs a live premium quote).

---

## 8. Tests

`backend/tests/services/test_pine_mapper_options.py` — **48 passed**
(parametrized cases expand the methods). No DB / broker / HTTP; a
`_FakeScripMaster` provides Phase 2A `ScripMeta` rows.

Coverage: ATM strike (5 spots + default), zero-step guard, OTM/ITM offset
(CE & PE), expiry (current_week / on-Thursday / next_week / current_month /
month-roll / holiday-shift / unknown), option_type (auto LONG→CE, auto
SHORT→PE, CE_only, PE_only), config validation (NRML ok, MARGIN alias,
MIS/INTRADAY/CNC/carry_forward=false rejected, no-options-block rejected),
strategy detection (4 paths + None), and end-to-end order build (CE/PE,
product_type==MARGIN always, qty=entry_lots*lot_size, exchange NFO, spot
fallback to price, spot kwarg override, OTM contract match, missing-spot
raise, unknown-contract raise, EXIT/non-options/MIS rejection, explicit
signal_direction override, error-subclass invariant).

### Run

```bash
cd backend
.venv/bin/python -m pytest tests/services/test_pine_mapper_options.py -v
# regression:
.venv/bin/python -m pytest tests/test_pine_mapper.py tests/test_pine_qty_interpretation.py -v
```

### Results

- New options tests: **48 passed**.
- Regression — `test_pine_mapper.py` + `test_pine_qty_interpretation.py`:
  **18 passed**.
- `mypy` on both changed source files: **clean**.
- `ruff`: only one **pre-existing** finding (`pine_mapper.py` `# noqa:
  BLE001` in the untouched `_try_lookup_lot_size`, present on `7b26aee`);
  zero new findings.
- The DB-backed webhook tests error with `SQLiteTypeCompiler … visit_JSONB`
  — a **pre-existing** SQLite-test-engine limitation, reproduced identically
  on the clean `7b26aee` parent. Unrelated to this change (no models /
  migrations touched).

---

## Frozen-file compliance

No changes to `strategy_executor.py`, `direct_exit.py`,
`kill_switch_service.py`, `reconciliation_loop.py`, or the `dhan.py`
adapter. No DB migrations. The only edits are additive: a new schema
module, additive functions in `pine_mapper.py`, the docstring fix, and a
new test file. The live BSE LTD futures path (`map_to_tradetri_payload`)
is behaviourally unchanged.
