# Queue Z — Phase 1 SUMMARY (Template Validation)

**Session date:** 2026-05-19 evening → night
**Branch:** `chore/template-validation-sprint`
**Unvalidated templates evaluated:** 17 (not the mission's predicted 14 — see `00_UNVALIDATED_LIST.md` for the +3 arithmetic correction)

## Per-template verdict — all 17 the same

| Slug | Verdict | Reason | Indicators dispatched? |
|------|---------|--------|------------------------|
| adx-strong-trend-filter | **BLOCKED** | Template `config_json` is prose, not `StrategyJSON` — Queue Y STRUCTURAL_BLOCKER | ✓ |
| aroon-crossover | **BLOCKED** | same | ✓ |
| camarilla-pivots-intraday | **BLOCKED** | same | ✓ |
| cci-momentum | **BLOCKED** | same | ✓ |
| cmf-confirmation | **BLOCKED** | same | ✓ |
| doji-reversal | **BLOCKED** | same | ✓ |
| donchian-channel-breakout | **BLOCKED** | same | ✓ |
| engulfing-candle-reversal | **BLOCKED** | same | ✓ |
| hull-ma-trend | **BLOCKED** | same | ✓ |
| ichimoku-cloud-crossover | **BLOCKED** | same | ✓ |
| inside-bar-breakout | **BLOCKED** | same | ✓ |
| macd-divergence | **BLOCKED** | same | ✓ |
| mfi-overbought-oversold | **BLOCKED** | same | ✓ |
| obv-divergence | **BLOCKED** | same | ✓ |
| rsi-divergence | **BLOCKED** | same | ✓ |
| triple-ema-crossover | **BLOCKED** | same | ✓ |
| williams-pct-r-reversal | **BLOCKED** | same | ✓ |

## Counts

| Verdict | Count | Recommended action |
|---------|-------|--------------------|
| PASS | 0 | — |
| WARN | 0 | — |
| FAIL | 0 | — |
| MISSING_INDICATOR | **0** | Engine indicator dispatch is at 230/230 parity. No commissioning gap. |
| **BLOCKED (structural)** | **17** | Deactivate in seed pending template→`StrategyJSON` translator (Path B from Queue Y), OR wait for translator (Path A). |

The BLOCKED verdict applies equally to the 12 "Phase 1 original active" templates — they share the same prose `config_json` shape. The 17-template scope is what Queue Y/Z were chartered to evaluate; the same fix would apply to all 29 currently-active equity templates.

## Indicator dispatch health (Phase 2 input)

- 16 unique indicator types referenced by the 17 templates.
- 16/16 present in `indicator_runner.py` dispatch table.
- See `MISSING_INDICATORS.md` for per-template breakdown.

## Recommended seed action

Same as Queue Y's recommendation: apply `proposed_deactivation_patch.json`
(deactivate the 17 batch-activated templates pending translator). NOT
applied here — founder review required.

Cleaner alternative once Jayesh decides:
- **Path A — Build the translator first.** Then re-run this validation harness with the translator in place. Expect the 17 to land somewhere on the PASS/WARN/FAIL spectrum based on actual backtest results. Estimated translator build: 3-5 days.
- **Path B — Deactivate the 17 in seed, ship anyway.** Customer gallery shows 12 (unvalidated but UI-tested) Phase 1 templates. Router mount proceeds with reduced template surface.
- **Path C — Document the gap, ship as-is.** Customers clone a template → get a half-empty Strategy row → must manually re-author. Existing gap; would persist post-router-mount.

Queue Y already recommended **Path B for ship safety + Path A in parallel.** Queue Z's static-analysis findings reinforce that recommendation: there's no quick path to validating templates via dispatch-wiring tweaks; the gap is genuinely the translator.

## What changed between Queue Y and Queue Z

- Queue Y stopped at Phase 1 (structural-blocker discovery) and produced 4 artefacts.
- Queue Z added the **static-analysis MISSING_INDICATORS finding** (zero gaps) and **PRIORITY_LIST.md** (51 COMING_SOON candidates sorted by commission complexity).
- No code changes in Queue Z. No seed file touched.
