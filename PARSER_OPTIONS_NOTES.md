# Scrip-master parser — options column retention

**Audit Critical #1** — `backend/app/brokers/dhan.py`
**Branch:** `feat/scrip-master-options-parser` (off `main` @ `3f8dd65`)
**Date:** 2026-05-23

---

## Problem

`_ScripMaster._parse` (Dhan scrip-master CSV ingest) extracted only
`SEM_SMST_SECURITY_ID`, `SEM_TRADING_SYMBOL`, the exchange/segment columns,
and `SEM_LOT_UNITS`. It **silently dropped** `SEM_OPTION_TYPE`,
`SEM_STRIKE_PRICE`, and `SEM_EXPIRY_DATE` — the data is in the CSV but was
discarded at parse time.

Those three columns are the data anchor for every options feature
downstream. Until they are retained, no strike/expiry-aware logic is
possible (per `OPTIONS_AUDIT_2026_05_21.md` §"BLOCKERS, ranked", item 1).

## What changed

Only **one production file** was touched: `backend/app/brokers/dhan.py`.
Plus tests. No DB migrations, no Docker, no changes to
`strategy_executor.py`, `direct_exit.py`, `kill_switch_service.py`, or
`pine_mapper.py`.

### 1. New `ScripMeta` dataclass

A frozen, slotted dataclass carrying the full parsed row:

```python
@dataclass(frozen=True, slots=True)
class ScripMeta:
    security_id: str
    symbol: str
    segment: str
    instrument: str            # SEM_INSTRUMENT_NAME (FUTSTK/OPTIDX/EQUITY/…)
    lot_size: int | None = None
    option_type: str | None = None     # "CE" | "PE" | None
    strike_price: Decimal | None = None
    expiry_date: date | None = None
```

`frozen=True` means cached metadata cannot be mutated by callers.

### 2. `_ScripMaster` now builds `self._meta: dict[str, ScripMeta]`

Keyed by `security_id`, populated in the same parse loop as the existing
dicts. The pre-existing lookup structures (`_by_symbol`, `_by_id`,
`_lot_sizes`) are computed **byte-for-byte identically** — `_meta` is a
strict superset, added alongside. The existing lookup remains the hot path.

### 3. Parse helpers

- `_parse_strike(raw) -> Decimal | None` — float-string → `Decimal`;
  empty / zero / unparseable → `None`.
- `_parse_expiry(raw) -> date | None` — tolerant of Dhan's format drift
  (`YYYY-MM-DD`, `YYYY-MM-DD HH:MM:SS`, `DD-MMM-YYYY`, `DD/MM/YYYY`); empty
  / unparseable → `None`, never raises.

### 4. Accessors / classification helpers on `_ScripMaster`

- `meta(security_id) -> ScripMeta | None`
- `is_option_symbol(security_id) -> bool` — driven by `SEM_OPTION_TYPE`
  ∈ {CE, PE}.
- `is_future_symbol(security_id) -> bool` — driven by `SEM_INSTRUMENT_NAME`
  starting with `FUT` (FUTSTK / FUTIDX / FUTCUR / FUTCOM).

---

## Design decisions (and why)

### The option triplet is gated on a valid CE/PE option type

For a row to carry `strike_price` / `expiry_date`, its `SEM_OPTION_TYPE`
must be `CE` or `PE`. Futures and equity rows keep all three triplet fields
`None`.

- **Why:** the task requires the triplet to "default `None` for futures",
  and `CE`/`PE` is the canonical option discriminator Dhan emits. Gating on
  it keeps futures/equity metadata identical to the pre-options world →
  zero regression risk to the live BSE LTD futures path.

### Futures expiry is deliberately NOT stored

Real Dhan futures rows *do* carry a `SEM_EXPIRY_DATE`, but because the row
is not an option, we drop it (triplet stays `None`).

- **Why:** futures rollover is already handled symbol-side by
  `app/services/futures_resolver.py` (last-Thursday computation), not via
  scrip-master expiry. Storing futures expiry here would add a second,
  unused source of truth and was explicitly out of scope ("default `None`
  for futures"). If a future feature needs scrip-master futures expiry,
  flip the gate — the column is already read.

### Zero / empty strike → `None`

A `0`/`0.000000`/empty strike is meaningless for an option leg, so it
collapses to `None`. This also means a malformed option row degrades
gracefully rather than reporting a nonsense `Decimal("0")` strike.

### `strike_price` is `Decimal`, not `float`

Consistent with the rest of the Dhan adapter (`_money` → `Decimal`).
Avoids binary-float drift on strike comparisons downstream.

### Parse never aborts on a bad row

`_parse_strike` / `_parse_expiry` swallow malformed values → `None`,
mirroring the existing `lot_units` `try/except`. One corrupt row in a
~hundreds-of-thousands-row master must never break ingestion.

---

## Resolved ambiguity — `scrip` parameter of the classifier helpers

The spec said `is_option_symbol(scrip)` / `is_future_symbol(scrip)` without
defining `scrip`. **I interpreted `scrip` as the `security_id`** — the
primary key used everywhere else in `_ScripMaster` (`reverse`, `lot_size`,
`meta`). This keeps the classifier API consistent with the rest of the
class: resolve a symbol → `security_id` via `lookup()`, then classify by id.

> If the intended argument was the *trading symbol string* instead, the
> helpers are a one-line change (look up `security_id` first). Flag it on
> review and I'll adjust — it does not affect the parser or stored data.

---

## What is explicitly NOT changed (regression safety)

- BSE LTD Futures strategy `89423ecc` execution path — untouched.
- `_by_symbol` / `_by_id` / `_lot_sizes` construction — identical output.
- No `OrderRequest` / position-model / schema changes (see audit §"NEXT
  DECISIONS" — those are separate, larger tasks).
- No DB migration.
- Pre-existing `ruff` (I001 import order, SIM102) and `mypy` findings in
  `dhan.py` were left as-is; this change introduces **zero** new lint or
  type errors (verified against `HEAD`).

---

## Tests

`backend/tests/brokers/test_dhan_scrip_master.py` — inline-CSV unit tests,
no HTTP / DB / Docker:

| Area | Test |
|------|------|
| CE parsed | `test_ce_option_row_retains_triplet` |
| PE parsed | `test_pe_option_row_retains_triplet` |
| option_type normalisation | `test_option_type_lowercase_is_normalised` |
| option_type validation | `test_invalid_option_type_collapses_to_none` |
| graceful bad expiry | `test_option_row_with_malformed_expiry_keeps_option` |
| **futures regression** | `test_future_row_has_no_option_triplet` |
| **futures regression** | `test_future_lookup_and_lot_size_unchanged` |
| equity classification | `test_equity_row_is_neither_option_nor_future` |
| mixed master | `test_mixed_master_keeps_each_kind_separate` |
| strike numeric (Decimal) | `test_strike_is_decimal_not_float` |
| fractional strike | `test_fractional_strike_preserved` |
| strike helper matrix | `test_parse_strike_helper` (6 cases) |
| expiry format end-to-end | `test_iso_date_parsed_end_to_end` |
| expiry helper matrix | `test_parse_expiry_helper` (6 cases) |
| unknown id | `test_unknown_security_id_classifies_as_neither` |
| FUTIDX classification | `test_futidx_classified_as_future` |
| immutability | `test_scripmeta_is_immutable` |

### Run

```bash
cd backend
.venv/bin/python -m pytest tests/brokers/test_dhan_scrip_master.py -v
```

### Results

- New tests: **27 passed** (parametrized cases expand the 17 methods).
- Regression — existing `tests/test_dhan_broker.py`: **57 passed**
  (includes `TestScripMasterSegmentParsing`).
- `mypy app/brokers/dhan.py`: same 2 pre-existing errors as `HEAD`, no new.
- `ruff`: no new findings attributable to this change.

---

## Downstream — still required for actual options support

This change retains the data; it does **not** make the system trade
options. Per `OPTIONS_AUDIT_2026_05_21.md`, the remaining blockers (each a
separate task) are at minimum:

1. `OrderRequest` schema — add `option_type` / `strike` / `expiry` (audit §2).
2. `strategy_position` model — instrument metadata (audit §5).
3. Strike / expiry selector (ATM/OTM — needs a chain feed).
4. Options-symbol builder + options expiry rollover.
5. `strategy_executor.py` options branches.
6. Webhook / pine_mapper option_type handling.

`ScripMeta` is the foundation those layers read from.
