# Queue Z — Phase 1 Output: MISSING_INDICATORS.md

**Status:** ✅ ZERO missing indicators across all 17 unvalidated templates.
**Method:** Static analysis (Queue Y's structural blocker prevents direct backtest invocation).
**Implication:** Phase 2 hard-stop triggered — "Phase 1 finds ZERO missing indicators → SKIP Phase 2 entirely."

---

## Method

Engine-side blocker discovered in Queue Y (`docs/TEMPLATE_VALIDATION/STRUCTURAL_BLOCKER.md`):
template `config_json` stores prose conditions like
`"close > 20-bar donchian upper band (new 20-bar high) AND adx_14 > 20"`,
not engine-callable `StrategyJSON`. Feeding any template into the engine
yields a 16-error Pydantic `ValidationError` *before* reaching the
indicator dispatch table.

Static-analysis substitute used here:
1. Read every `config_json.indicators[*]` entry across the 17 unvalidated templates → 16 unique indicator instance IDs (e.g. `ema_9`, `donchian_channel_20`).
2. Strip trailing numeric suffix to recover the registry **type** (e.g. `ema`, `donchian_channel`).
3. Compare against the dispatch table parsed out of `backend/app/strategy_engine/backtest/indicator_runner.py` — captured BOTH dispatch forms (`cfg.type == "X"` AND `cfg.type in ("X", "Y", ...)`).

## Result

| Metric | Count |
|--------|-------|
| Unique indicator types referenced by the 17 templates | 16 |
| Already in dispatch table | **16** |
| Missing from dispatch table | **0** |

### All 16 referenced types — every one is dispatched
`adx`, `aroon_down`, `aroon_up`, `camarilla_pivots`, `cci`, `cmf`,
`donchian_channel`, `ema`, `hull_ma`, `ichimoku`, `macd`, `mfi`, `obv`,
`rsi`, `vwap`, `williams_r`.

### Per-template indicator coverage (all ✓)

| Slug | Indicators (id → type) | Coverage |
|------|------------------------|----------|
| adx-strong-trend-filter | adx_14→adx, ema_9→ema, ema_21→ema | ✓ |
| aroon-crossover | aroon_up_14→aroon_up, aroon_down_14→aroon_down | ✓ |
| camarilla-pivots-intraday | camarilla_pivots, vwap | ✓ |
| cci-momentum | cci_20→cci, ema_50→ema | ✓ |
| cmf-confirmation | cmf_20→cmf, ema_20→ema, ema_50→ema | ✓ |
| doji-reversal | ema_50→ema, rsi_14→rsi | ✓ |
| donchian-channel-breakout | donchian_channel_20, donchian_channel_10, adx_14 | ✓ |
| engulfing-candle-reversal | ema_50→ema, rsi_14→rsi | ✓ |
| hull-ma-trend | hull_ma_21→hull_ma | ✓ |
| ichimoku-cloud-crossover | ichimoku_9_26_52→ichimoku | ✓ |
| inside-bar-breakout | ema_20→ema | ✓ |
| macd-divergence | macd_12_26_9→macd | ✓ |
| mfi-overbought-oversold | mfi_14→mfi, ema_50→ema | ✓ |
| obv-divergence | obv, ema_50→ema | ✓ |
| rsi-divergence | rsi_14→rsi | ✓ |
| triple-ema-crossover | ema_8, ema_21, ema_55 (all →ema) | ✓ |
| williams-pct-r-reversal | williams_r_14→williams_r, ema_50→ema | ✓ |

## Indicator dispatch table — overall health

- `INDICATOR_REGISTRY` ACTIVE entries: 230
- `indicator_runner.py` dispatched types: 230
- Registered-active ↔ dispatched parity: **1:1**, zero orphans on either side.
- Calculation files on disk: 229 (perfect overlap with registry's 229 named `calculation_function` fields).

The indicator engine is in a clean state — every ACTIVE registry entry has an implementation file and a dispatch entry. There is no commissioning gap to close.

## Why the templates still fail validation

The structural blocker (Queue Y) — template `config_json` shape doesn't match `StrategyJSON` — is the actual reason none of the 17 templates can be backtest-validated. It's not an indicator commissioning issue. Fixing it requires the template→StrategyJSON translator layer that `clone_service.py` cites as "Phase 7-8 backtest-engine concern" but which has not been written.

A second-order observation: the 51 `IndicatorStatus.COMING_SOON` registry entries all have `calculation_function=None` — no implementation hook. Those are inventory placeholders, not "missing dispatch wiring." See `PRIORITY_LIST.md` for the full COMING_SOON inventory.
