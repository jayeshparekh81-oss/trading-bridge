# Pine Script Importer

> Status: Production-ready (active mappings expand commit-over-commit)
> Phase 7 baseline: Commit `72de0be`
> Batch 1 expansion: Commit `b33d205`
> Pack 2 dispatch follow-up: Commit `f7d3827`
> Last updated: 2026-05-09

## Overview

The Pine Script importer takes a Pine v5 source string, recognises
a curated subset of `ta.*` calls + `strategy.entry` / `.exit`
hooks, and emits a fully-populated `StrategyJSON` the rest of the
TRADETRI engine can backtest, validate, and execute. The
conversion is **purely textual + structural** — no `eval`, no
`exec`, no `compile`. An AST-inspection test
(`test_no_dynamic_code_execution`) pins that property as
load-bearing.

## Why It Exists

TradingView is where most Indian retail algo traders live today.
Asking them to rewrite a working Pine strategy in TRADETRI's
builder would be a non-starter. The importer:

- Recognises 31 standard Pine indicators today (Pack 2-4 mapped).
- Translates entry / exit conditions into the `EntryRules` /
  `ExitRules` shape.
- Surfaces unsupported calls as **non-blocking notes** so the
  user can review and either rewrite that bit or wait for the
  next mapping batch.
- Is license-aware — Pine scripts marked `// @license=*` other
  than open-source-compatible licenses get flagged for review
  rather than silently imported.

## Public API

```python
from app.strategy_engine.pine_import import convert_pine_to_strategy

result = convert_pine_to_strategy(source_string)

# Success path:
# result["success"] is True
# result["strategy"] is a StrategyJSON dict
# result["explanation"] — Hinglish summary of what got mapped
# result["notes"] — list of "x mapped to y" / "x is coming-soon" hints
# result["license_status"] — "open_source" | "needs_review"
#
# Failure path:
# result["success"] is False
# result["partial"] — dict with whatever did convert (may be None)
# result["converted"] — count of mapped calls
# result["unsupported"] — list of un-recognised symbols
# result["message"] — Hinglish failure summary
```

REST endpoint: `POST /api/strategies/pine-import` (body:
`{"source": "..."}`).

Source: `app/strategy_engine/pine_import/`.

## Conversion Algorithm

```
source string
    ↓ validate_source — license + safety
    ↓ parse_source    — regex-extract supported subset
    ↓ map_program     — build StrategyJSON-shaped dict
    ↓ StrategyJSON.model_validate — final schema check
    → ConversionResult
```

1. **`validate_source`** rejects:
   - Non-Pine input (no `//@version=` header).
   - Restrictive license headers.
   - Suspicious patterns that look like attempts to bypass the
     no-eval guarantee.
2. **`parse_source`** is regex-based — no Pine grammar parser. It
   walks line-by-line and extracts:
   - `ta.<func>(args)` indicator calls (gated by
     `SUPPORTED_TA_INDICATORS` in `parser.py`).
   - `strategy.entry(...)` / `strategy.exit(...)` hooks.
   - `crossover` / `crossunder` boolean expressions.
3. **`map_program`** walks the parsed list and emits a
   `StrategyJSON`-shaped dict. Active Pine names get a real
   indicator dict; coming-soon names get a note + are dropped
   from the strategy (the schema validator would reject an
   indicator without a calc function).
4. **Final schema validation** — `StrategyJSON.model_validate`
   enforces every Phase 1 invariant (unique indicator IDs, at
   least one exit primitive, etc.).

## Supported Pine Names (Active + Coming-Soon)

The parser's `SUPPORTED_TA_INDICATORS` set in
`backend/app/strategy_engine/pine_import/parser.py` is the
authoritative list. As of Pack 4 (commit `fe5533a`):

### Active (mapped to real indicator dicts)

| Pine call | Maps to | Pack |
|---|---|---|
| `ta.ema` / `ta.sma` / `ta.rsi` / `ta.macd` / `ta.bb` / `ta.atr` / `ta.vwap` / `ta.highest` / `ta.lowest` | their direct registry equivalents | Phase 7 |
| `ta.wma` | `wma` | Phase 7 |
| `ta.adx` | `adx` | Phase 7 |
| `ta.cmf` | `cmf` | Phase 7 |
| `ta.trix` | `trix` | Phase 7 |
| `ta.aroon` | `aroon` | Phase 7 |
| `ta.obv` | `obv` | Phase 7 |
| `ta.vwma` / `ta.supertrend` / `ta.psar` / `ta.dema` / `ta.tema` / `ta.hma` | Pack 2 actives | Pack 2 follow-up |
| `ta.cci` / `ta.mfi` / `ta.williams_r` / `ta.stoch` / `ta.roc` | Pack 2 actives | Pack 2 follow-up |
| `ta.donchian` / `ta.keltner` | `donchian_channel` / `keltner_channel` | Pack 2 follow-up |
| `ta.rma` | `smma` (Wilder's) | Pack 2 follow-up (new) |
| `ta.cmo` | `chande_momentum` | Pack 2 follow-up (new) |
| `ta.pivothigh` / `ta.pivotlow` | `swing_high` / `swing_low` | Pack 4 |
| `ta.stdev` / `ta.variance` / `ta.correlation` | `std_dev` / `variance` / `correlation_coefficient` | Pack 4 |
| `ta.percentrank` / `ta.percentile_nearest_rank` / `ta.median` | `percentile_rank` / `percentile_nearest` / `median_value` | Pack 5 |

### Coming-soon (recognised but emits a note)

| Pine call | Maps to | Status |
|---|---|---|
| `ta.stoch_rsi` | `stoch_rsi` | Pending Pack 6 |
| `ta.mom` | `momentum` | Pending Pack 6 |
| `ta.heikinashi` | `heikin_ashi` | Pending Pack 6 |

When a coming-soon Pine call is found, the importer emits a note
but does NOT add the indicator to the strategy. The frontend
shows the note inline so the user knows what's pending.

## License-Aware Handling

Pine scripts often carry a license header:

```pine
//@version=5
//@license=MIT
strategy("My breakout system", ...)
```

The importer reads the header and tags the result:

- **Open-source-compatible** licenses (MIT, BSD, Apache, MPL,
  Unlicense, public-domain) → `license_status: "open_source"`.
  Importer proceeds without warning.
- **Restrictive or unknown** licenses → `license_status:
  "needs_review"`. Importer still produces a strategy but the
  frontend surfaces a yellow banner asking the user to confirm
  they have the right to use the script.
- **No license header** → treated as `needs_review`. Defensive
  default; users can attest to provenance to dismiss.

The list of recognised licenses lives in
`pine_import/validator.py`.

## User Flow

1. User pastes Pine source into the import dialog at
   `/strategies/import-pine`.
2. Frontend POSTs to `/api/strategies/pine-import`.
3. Backend returns the conversion result + notes.
4. UI shows three tabs:
   - **Strategy Preview** — the converted `StrategyJSON`
     pre-filled into a read-only Expert builder view.
   - **Notes** — coming-soon hints, license review, partial-fail
     reasons.
   - **Original Pine** — the source the user pasted, for
     reference.
5. User reviews + clicks "Save as Strategy".
6. Backend writes the strategy through the Phase 5 CRUD endpoint.

## Coming-Soon Warnings

A user pasting a Pine script that uses `ta.heikinashi` (still
coming-soon) gets:

- The strategy converts successfully without that indicator.
- The notes tab shows: `"ta.heikinashi matches the heikin_ashi
  indicator, currently coming_soon in TRADETRI's registry —
  preserved as a note. Re-run the import after the indicator
  ships."`
- The user can either delete the corresponding entry condition
  or wait for the next pack.

## Edge Cases & Limitations

- **No nested function calls.** A Pine line like
  `len = ta.ema(close, 20) > ta.sma(close, 50)` is not parsed —
  the importer recognises top-level `ta.<func>(...)` calls only.
  Nested expressions surface as unsupported.
- **No Pine functions / variables.** User-defined functions and
  reassigned variables aren't followed. The importer is a
  flat-call recogniser, not a Pine interpreter.
- **No multi-timeframe.** `request.security(...)` is rejected —
  the engine doesn't have multi-timeframe data plumbing yet.
- **No Pine v4 / v3.** Only `//@version=5` is supported. Earlier
  versions get a "please upgrade" message.

## Testing

- `tests/strategy_engine/pine_import/test_no_dynamic_code_execution.py`
  — AST-inspects the package to verify no `eval` / `exec` /
  `compile` ever ships. Don't loosen this.
- `tests/strategy_engine/pine_import/test_mappings_batch1.py` —
  per-Pine-call mapping cases.
- `tests/strategy_engine/pine_import/test_pack2_active_mappings.py`
  — the 13 Pack 2-promoted mappings + 2 brand-new ones (rma,
  cmo).
- `tests/strategy_engine/pine_import/test_license_aware.py` —
  open-source vs needs-review classification matrix.

## Future Work

- **Multi-timeframe support.** Plumb `request.security(...)` once
  the engine grows multi-timeframe data feeds.
- **Pine v6** when TradingView ships it.
- **AST-based parser** (replacing the regex parser) for nested
  expressions + user-defined functions. Big effort, would unlock
  ~80% more real-world Pine scripts.
- **Reverse importer** — TRADETRI strategy → Pine source so users
  can take their builder-built strategy and paper-trade it on
  TradingView. Symmetric story to the current one-way path.

## References

- Module source: `backend/app/strategy_engine/pine_import/`
- API endpoint: `backend/app/strategy_engine/api/pine_import.py`
- Frontend integration: `frontend/src/app/(dashboard)/strategies/import-pine/page.tsx`
- Tests: `backend/tests/strategy_engine/pine_import/`
- Sister doc: [`/docs/strategy-truth-engine.md`](./strategy-truth-engine.md)
