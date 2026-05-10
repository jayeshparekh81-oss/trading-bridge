# Indicator Registry

> Status: Production-ready (catalogue grows commit-over-commit)
> Phase 9 baseline: Commit `543c898`
> Pack 2: Commit `511f591` + dispatch follow-up `f7d3827`
> Pack 3: Commit `fd96326`
> Pack 4: Commit `fe5533a`
> Pack 5: Commit `f893c78`
> Last updated: 2026-05-09

## Overview

The Indicator Registry is the single source of truth for what
indicators TRADETRI knows about. Every `IndicatorMetadata` row
carries an id, name, category, status (`active` /
`coming_soon` / `experimental`), difficulty (`BEGINNER` /
`INTERMEDIATE` / `EXPERT`), Pine aliases, the `calculation_function`
that resolves to a Python callable, and the input / output spec
the builder UI renders.

Phase 9 shipped 105 catalogue entries (10 base + 10 Phase 9
actives + 85 coming-soon stubs). Packs 2-5 progressively
promoted coming-soon stubs and added net-new ids. As of Pack 5:

- **Total registry size: 136 entries.**
- **Active indicators: 71** (usable by the backtest engine).
- **Coming-soon: ~65** (catalogue-visible, no calculation yet).

## Why It Exists

Every other strategy-engine subsystem (backtest dispatch, Pine
importer, frontend builder UI, indicator versioning, marketplace
performance snapshots) needs to agree on what indicators exist
and what their shape is. A central registry:

- Makes "is this indicator usable today?" a single boolean
  query (`status is IndicatorStatus.ACTIVE`).
- Lets the Phase 1-12 indicator-versioning seeder iterate every
  registry id once and stamp v1.0.0 records — adding a new
  indicator is purely catalogue + calculation work; the version
  trail comes free.
- Surfaces coming-soon entries in the builder UI so users plan
  strategies that reference indicators we haven't shipped yet,
  with explicit "wait for it" copy.

## Public API

```python
from app.strategy_engine.indicators import INDICATOR_REGISTRY
from app.strategy_engine.indicators.registry import (
    get_active_indicators,
    get_beginner_recommended_indicators,
    get_calculation_function,
    get_indicator_by_id,
    get_indicators_by_category,
    list_categories,
    validate_indicator_params,
)

# Catalogue browse.
all_meta: dict[str, IndicatorMetadata] = INDICATOR_REGISTRY
active: list[IndicatorMetadata] = get_active_indicators()  # 71 today.

# Single lookup (None if missing).
ema_meta = get_indicator_by_id("ema")

# Param validation against the indicator's InputSpec.
validated = validate_indicator_params("ema", {"period": 20})

# Resolve to a callable for the backtest dispatcher.
fn = get_calculation_function("ema")
```

Source: `backend/app/strategy_engine/indicators/registry.py`.

## Status Flags

| Status | Meaning | What changes |
|---|---|---|
| `ACTIVE` | Calculation function is shipped + tested + dispatch-wired. | Backtest engine + Pine importer + builder UI all treat it as a real indicator. |
| `COMING_SOON` | Catalogue entry only — no `calculation_function`, no dispatch. | Builder UI shows it in the picker with a "wait for it" hint; Pine importer recognises the name and emits a coming-soon note. |
| `EXPERIMENTAL` | Reserved. No live indicator uses this status today. | Future use: shipped calculation but flagged as unstable; opt-in via feature flag. |

A coming-soon → active promotion (the Pack 2 / 4 pattern):

1. Implement the calculation function under `calculations/<id>.py`.
2. Add a row to a new `_pack{N}_active.py` with `status=ACTIVE`
   + `calculation_function=<id>`.
3. Splat `*PACK{N}_ACTIVE_INDICATORS` at the **end** of the
   registry's dict-comp tuple — same-id coming-soon stubs get
   overridden by Python dict-comp later-wins semantics.
4. Wire the dispatch branch in `backtest/indicator_runner.py`.
5. Optionally wire the Pine importer mapping (only if a real
   `ta.*` Pine name maps to it — don't invent calls).

## Difficulty Tiers

| Tier | Beginner builder | Intermediate builder | Expert builder |
|---|---|---|---|
| `BEGINNER` | ✅ visible | ✅ visible | ✅ visible |
| `INTERMEDIATE` | hidden | ✅ visible | ✅ visible |
| `EXPERT` | hidden | hidden | ✅ visible |

The exact set of `BEGINNER` ids is locked by
`tests/strategy_engine/test_registry.py::test_beginner_recommended_subset`
to `{ema, sma, rsi, volume_sma}`. **This lock is load-bearing** —
adding a new beginner indicator requires updating the test
deliberately. Pack 2's ROC was demoted from `BEGINNER` to
`INTERMEDIATE` to avoid silently breaking that contract.

## Adding a New Indicator (Pack 6+ Contributor Guide)

1. **Pick the id**: snake_case, doesn't collide with any existing
   id (active OR coming-soon).
2. **Write the calculation**: `calculations/<id>.py`. Pure stdlib,
   `Sequence[float]` inputs, `list[float | None]` outputs. Empty
   input → `[]`. Insufficient data → `[]` or warm-up `None`s.
3. **Write the metadata**: append to a new `_pack{N}_active.py`
   tuple. Include InputSpec entries for every param, sensible
   defaults, Hinglish `ai_explanation`.
4. **Wire dispatch**: `backtest/indicator_runner.py::_compute_one`
   gets a new branch.
5. **Wire Pine importer** (optional, only if real `ta.*` name).
6. **Write tests**: per-pack test file
   `tests/strategy_engine/test_pack{N}_indicators.py` with at
   least: known-input/known-output, empty input, registry
   promotion check, dispatch integration test.
7. **Loosen any count locks** that need it (`>= N` not `== N` —
   see `test_seed_populates_every_runtime_indicator_at_v1` for
   the prior pattern).

## Indicator Versioning Integration

Every registry id gets a `IndicatorVersionRecord` at module
import via `app.strategy_engine.indicator_versioning.seed`. The
seeder iterates `INDICATOR_REGISTRY.keys()` and stamps every id
with `version=1.0.0`, `formula_version=f1`, `created_at=initial`,
`deprecated=False`. Adding a new indicator → adds a registry
entry → seeder picks it up next process boot.

The backtest pipeline uses
`indicator_versioning.capture_manifest()` to pin which version of
each indicator ran for a given backtest, so a future formula
change (`f1 → f2`) doesn't silently change historical results.

See [`/docs/strategy-truth-engine.md`](./strategy-truth-engine.md)
for how indicator versions feed into the truth-engine's manifest.

## Pine Importer Mapping Table

The Pine importer's `_COMING_SOON_PINE_TO_REGISTRY` dict + the
per-name active branches in `pine_import/mapper.py` are kept in
sync with the registry status as packs ship. The full mapping
table lives in [`/docs/pine-importer.md`](./pine-importer.md).

Lesson learned (Pack 2 follow-up commit `f7d3827`): the parser's
`SUPPORTED_TA_INDICATORS` set + the mapper's branch table BOTH
need the new Pine name in lockstep, otherwise the parser drops
the call before the mapper sees it. Pack 4+ commits ship both
in the same change.

## Configuration

No env vars. Indicator registration is code-only. The
`feature_flags` module's `INDICATORS_BACKTEST_ENABLED` flag
(see [`/docs/feature-flags.md`](./feature-flags.md)) gates the
whole backtest path; per-indicator gating is not a thing today.

## Edge Cases & Limitations

- **Coming-soon stubs are inert.** `get_calculation_function`
  raises on a coming-soon id. The backtest engine + Pine
  importer never accidentally pick one up.
- **Status changes via splat order.** Promoting a coming-soon to
  active works because the `PACK{N}_ACTIVE_INDICATORS` tuple is
  splat AFTER `PHASE9_COMING_SOON_INDICATORS` in the registry's
  dict comprehension. Don't reverse the splat order.
- **No per-instrument variants.** A "RSI optimised for NIFTY"
  isn't a separate registry id today. Per-instrument calibration
  is a v1.1 enhancement.
- **The `calculation_function` is BOTH the module name AND the
  function name.** A new indicator named `frob` requires a
  `calculations/frob.py` that exposes a callable named `frob`.
  This 1:1 mapping is enforced by `get_calculation_function`'s
  dynamic import.

## Testing

- `tests/strategy_engine/test_registry.py` — every active id
  has a resolvable calculation function + the 10 Phase 1 +
  10 Phase 9 actives are present + the locked beginner subset.
- `tests/strategy_engine/test_coming_soon_indicators.py` — for
  every coming-soon id, `get_calculation_function` raises with
  the `coming_soon` reason in the message + no coming-soon
  entry has a non-None `calculation_function`.
- `tests/strategy_engine/test_pack{2,3,4,5}_indicators.py` —
  per-pack: `_PACK{N}_IDS` set membership + active count
  delta + dispatch integration + Pine mapping (where applicable).
- `tests/strategy_engine/indicator_versioning/test_indicator_versioning.py`
  — seeder iterates the full registry; loose `>= 105` lock so
  future packs don't have to edit this file.

## Future Work

- **Pack 6+** — additional indicator mass (target: 230+).
- **Per-instrument variants** for indicators where instrument
  characteristics meaningfully change ideal parameters (BANKNIFTY's
  natural ATR is bigger than NIFTY's).
- **Custom user indicators** — a future feature lets the user
  upload a Python snippet (sandboxed) that the registry accepts
  as `EXPERIMENTAL`. Far horizon; opens a security/audit can.
- **Indicator deprecation flow** — flip a registry entry to
  `deprecated=True`, surface a warning on every backtest that
  uses it, lock new strategies from referencing it. Today every
  indicator is `deprecated=False`.

## References

- Module source: `backend/app/strategy_engine/indicators/`
- Schema: `backend/app/strategy_engine/schema/indicator.py`
- Calculation modules: `backend/app/strategy_engine/indicators/calculations/`
- Tests: `backend/tests/strategy_engine/test_registry.py`,
  `test_pack{2,3,4,5}_indicators.py`
- Sister doc: [`/docs/pine-importer.md`](./pine-importer.md)
- Sister doc: [`/docs/strategy-truth-engine.md`](./strategy-truth-engine.md)
- Sister doc: [`/docs/feature-flags.md`](./feature-flags.md)
