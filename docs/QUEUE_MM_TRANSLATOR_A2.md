# Queue MM — Translator A2 → Sub-Output Synonym Resolution (ARCHITECTURE)

**Status:** Phase A (design). Re-scoped from the original "alias-key" brief (which
was based on a wrong root-cause model — see §1) to a **sub-output synonym
resolution layer**. Branch `feat/translator-a2-synonym-resolution` off
`main@6bf7f26`. Implementation (Phase B+) is gated on founder sign-off of the
registry structure in §3.

---

## 1. Why the original alias-key fix was wrong (recap)
The 4 `FAIL_VALIDATION` templates contain **no dotted keys**. They fail the
StrategyJSON **referential-integrity** validator (`schema/strategy.py:364-376`)
because conditions reference **bare sub-output ids** that aren't declared in
`indicators[]`:

| Template | Declares | Undeclared ids referenced |
|---|---|---|
| macd-trend-signal | `macd_12_26_9` | `macd_line`, `signal_line`, `macd_histogram` |
| rsi-macd-confluence | `rsi_14`, `macd_12_26_9` | `macd_line`, `signal_line` |
| bb-rsi-oversold | `bb_20_2`, `rsi_14` | `bb_lower`, `bb_middle` |
| orb-15min | `orb_15` | `orb_15_high` |

The runner emits sub-outputs only for `macd`+`bollinger_bands` under short
suffixes (`signal`, `lower`, …), and ORB emits none. So the referenced names
resolve to nothing. The fix is to teach the translator+engine the mapping from
prose sub-output names → (parent indicator, output), declare them, and emit them.

## 2. Design overview (3 touch points, all additive)
```
 template config_json
        │ parse_conditions  (unchanged grammar; _IND_ID already matches these)
        ▼
 referenced ids: {macd_line, signal_line, bb_lower, orb_15_high, ...}
        │ NEW: resolve_sub_output(token, declared_parents)        [translator]
        ▼
 auto-declare IndicatorConfig(id=token, type=parent, params=…, output=key)
        │ StrategyJSON referential integrity now passes
        ▼
 indicator_runner: for cfg.output set → store extras[output] under cfg.id  [engine]
        │ ORB promoted to emit {high, low} band series
        ▼
 simulator values_at(series_by_id) finds macd_line / signal_line / orb_15_high
```

Touch points:
1. **Schema** `schema/strategy.py` — add optional `output: str | None` to
   `IndicatorConfig` (frozen+extra=forbid → declared optional field is safe,
   backward-compatible; existing rows have `output=None`).
2. **Translator** new module `translator/sub_outputs.py` (the registry, §3) +
   `parser.py` auto-declaration step (alongside the existing close/open/high/low
   pseudo-indicator step at `parser.py:196-224`).
3. **Engine** `backtest/indicator_runner.py` — when `cfg.output` is set, store the
   selected sub-series under `cfg.id`; **ORB band helper** in
   `indicators/calculations/opening_range_breakout.py` (new function, existing
   `opening_range_breakout` untouched).

## 3. Registry structure (THE THING TO SIGN OFF) — `translator/sub_outputs.py`
Two resolution styles, because the seed templates name sub-outputs two ways:

```python
# Style A — fixed semantic synonyms. Token carries NO params; binds to the
# single declared parent indicator of the given registry type.
#   token            -> (parent registry type, runner output key)
_FIXED_SUBOUTPUT_SYNONYMS: dict[str, tuple[str, str]] = {
    "macd_line":      ("macd",            "macd"),
    "signal_line":    ("macd",            "signal"),
    "macd_histogram": ("macd",            "histogram"),
    "bb_upper":       ("bollinger_bands", "upper"),
    "bb_middle":      ("bollinger_bands", "middle"),
    "bb_lower":       ("bollinger_bands", "lower"),
}

# Style B — parametrized "<parent_id>_<suffix>" (token embeds params, e.g.
# orb_15_high = parent orb_15 + output 'high'). parent_id is parsed by the
# existing parse_indicator_id(); suffix must be in the type's output set.
_SUFFIX_SUBOUTPUTS: dict[str, frozenset[str]] = {
    "opening_range_breakout": frozenset({"high", "low"}),
}

@dataclass(frozen=True)
class ResolvedSubOutput:
    sub_id: str        # referenced token  e.g. "signal_line" / "orb_15_high"
    parent_type: str   # registry type     e.g. "macd" / "opening_range_breakout"
    params: dict       # parent params     e.g. {fast:12,slow:26,signal:9} / {minutes:15}
    output: str        # runner output key e.g. "signal" / "high"

def resolve_sub_output(
    token: str, declared: list[IndicatorConfig]
) -> ResolvedSubOutput | None:
    # A: fixed synonym → bind to the one declared parent of matching type
    if token in _FIXED_SUBOUTPUT_SYNONYMS:
        ptype, output = _FIXED_SUBOUTPUT_SYNONYMS[token]
        parents = [c for c in declared if c.type == ptype]
        if len(parents) == 1:
            return ResolvedSubOutput(token, ptype, dict(parents[0].params), output)
        return None  # 0 = no parent declared; >1 = ambiguous → leave unresolved
    # B: <parent_id>_<suffix>
    for ptype, suffixes in _SUFFIX_SUBOUTPUTS.items():
        for suf in suffixes:
            if token.endswith("_" + suf):
                parent_id = token[: -(len(suf) + 1)]
                try:
                    cfg = parse_indicator_id(parent_id)
                except UnknownIndicatorError:
                    continue
                if cfg.type == ptype:
                    return ResolvedSubOutput(token, ptype, dict(cfg.params), suf)
    return None
```

Covers all 6 undeclared ids across the 4 templates. `bb_upper`/`orb_15_low`
included for forward-compat (no current template uses them, cheap to support).

## 4. Auto-declaration logic (`parser.py`)
After parsing entry+exit conditions and before assembly, extend the existing
referenced-id walk (`parser.py:205-208`):
```python
for ref in sorted(referenced_ids - declared_ids - PSEUDO_IDS):
    resolved = resolve_sub_output(ref, indicators)
    if resolved is not None:
        indicators.append(IndicatorConfig(
            id=resolved.sub_id, type=resolved.parent_type,
            params=resolved.params, output=resolved.output))
    # else: leave undeclared → same FAIL_VALIDATION as today (correct for
    #       genuinely unknown ids; none of the 4 targets hit this branch)
```
Ordering: run the sub-output pass BEFORE the close/open/high/low pseudo pass so a
token like `orb_15_high` is claimed by sub-output resolution, not mistaken for the
`high` pseudo (it won't be — pseudo only matches the bare words, but order is
defensive).

## 5. ORB multi-output promotion
`opening_range_breakout.py`: ADD `opening_range_levels(highs, lows, closes,
timestamps, range_minutes) -> tuple[list[float|None], list[float|None]]` returning
the per-bar opening-range high & low (forward-filled after the OR window each
session day; `None` before completion — mirrors the existing signal calc's day
grouping). The existing `opening_range_breakout` signal function is **untouched**.
`indicator_runner.py` ORB branch (`:675-681`) changes from `return fn(...), {}` to
`return signal, {"high": hi, "low": lo}`; add `"opening_range_breakout"` to
`_MULTI_OUTPUT_INDICATORS` if it gates emission (TBC in Phase C — currently the
`if extras:` check at `:86` is what actually drives emission).

## 6. Engine output-selection (`indicator_runner.py` main loop `:80-95`)
```python
primary, extras = _compute_one(cfg, params, candles)
if getattr(cfg, "output", None):
    series_by_id[cfg.id] = extras[cfg.output] or [None]*n   # sub-output config
else:
    series_by_id[cfg.id] = primary or [None]*n              # UNCHANGED path
    if extras: ...emit dotted keys as today...              # UNCHANGED path
```
**Additive guarantee:** `cfg.output is None` for every existing indicator →
identical behavior. Regression test asserts rsi_14 / ema_9 / sma_20 series are
byte-identical pre/post change.

## 7. Phasing & tests
- **A** registry + doc (this) → SIGN-OFF GATE.
- **B** schema `output` field + `sub_outputs.py` + `parser.py` integration.
  Tests: `test_sub_outputs.py` (resolution table), `test_parser.py` additions.
- **C** engine: ORB band helper + runner output-selection. Tests: ORB band emit,
  single-output regression (rsi/ema/sma identical).
- **D** 4 target templates: translate → validate → synthetic backtest (trades>0, 0 errors).
- **E** regression: 8 PASS templates still PASS; `test_pine_mapper_options.py` green;
  `pytest tests/strategy_engine/` green.

## 8. SACRED / risk
Untouched: BSE LTD `89423ecc` path, `brokers/*`, `webhook/*`, `kill_switch`,
`strategy_executor`, `direct_exit`, `migrations`. **Live-trading risk: ZERO** —
all edits are in the offline translator + backtest + schema layers; the runner
change is additive (new `output` branch only). No `is_paper` logic touched.
Files to be modified: `schema/strategy.py`, `translator/{sub_outputs(new),parser}.py`,
`backtest/indicator_runner.py`, `indicators/calculations/opening_range_breakout.py`,
+ tests + this doc. Coverage target: 8 → 12.

## 9. Results (Phases B–E) — DONE
**Coverage 8 → 12.** All 4 targets translate → validate → synthetic backtest with
trades (deterministic 720×5-min sine harness): macd-trend-signal=17, rsi-macd-confluence=23,
bb-rsi-oversold=9, orb-15min=18.

Extra fix found during impl (in scope, additive): `parse_indicator_id` emitted
template-shorthand param names (`std`, `minutes`) that `validate_indicator_params`
rejects; corrected to the registry names (`std_dev`, `range_minutes`) in
`field_mappers._INDICATOR_PARAM_SCHEMA`. Latent because bb/orb never reached the
engine before (they were FAIL_VALIDATION). macd already aligned.

Files changed (diff vs main):
| File | Δ | What |
|---|---|---|
| `schema/strategy.py` | +15/-4 | optional `IndicatorConfig.output` + validator allows None |
| `translator/sub_outputs.py` | +new ~95 | synonym registry + `resolve_sub_output` |
| `translator/parser.py` | +29 | sub-output auto-declaration pass |
| `translator/field_mappers.py` | +9/-3 | bb/orb param names → registry (std_dev/range_minutes) |
| `backtest/indicator_runner.py` | +33 | additive output-selection branch; ORB→multi-output |
| `indicators/calculations/opening_range_breakout.py` | +58 | additive `opening_range_levels` band helper |
| tests (4 files) | +new+edits | sub_outputs/runner/pack8/parser |

Regression evidence:
- **8 PASS templates trade-by-trade IDENTICAL pre/post** (engine backtested old-vs-new
  via git-stash; `diff` empty across all 8). Translation also byte-identical to the
  committed `translated/<slug>.json`.
- **Single-output indicators (rsi/ema/sma) unchanged** — `output is None` path is
  byte-identical; unit-asserted (no extra keys, no warning).
- **`test_pine_mapper_options.py` green** (48 passed) — parallel options work intact.
- **Full `tests/strategy_engine/` introduces ZERO new failures**: 11 pre-existing
  pollution failures (compliance/indicator_admin/registry) exist on `main` identically;
  the lone A2-touched test (`test_pack8…[opening_range_breakout…]`) was updated to
  assert ORB's new, intended multi-output contract (+ band sub-ids).
- **strategy_executor audit (live path): ZERO risk** — no live executor imports
  `precompute_indicators`/`values_at`/the backtest module, so new sub-output keys never
  reach the live order path. SACRED files untouched; `is_paper` untouched.
