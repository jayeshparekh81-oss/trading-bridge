# BLOCKERS — Phase 2 Templates Part 2 (indicator-commission backlog)

**Branch:** `feat/phase-2-templates-part-2`
**Date:** 2026-05-17
**Sibling doc:** `docs/PHASE_2_TEMPLATES_PART_2.md`

---

## Open questions for founder review

### Q1. Indicator commission — approve the 5-template unlock?

The 5 remaining inactive equity templates can't ship until 5 indicators
are implemented. Estimated **5 dev-days total** for all 5, sequenced
lightest-first:

| Template | Indicator | Effort | Notes |
|---|---|---:|---|
| `kama-adaptive-trend` | `kama` | 0.5 day | One TA-Lib call (`talib.KAMA`) + param validation; ta-lib already vendored |
| `alma-slope` | `alma` | 0.5 day | ~15-line Gaussian-weighted formula, pure-Python, no new dep |
| `pivot-reversal-strategy` | `pivot_swing` | 0.5 day | Thin wrapper around existing `swing_high` + `swing_low` |
| `heikin-ashi-smooth-trend` | `heikin_ashi` | 1 day | Candle transform; multi-output dispatch (`ha_open`, `ha_high`, `ha_low`, `ha_close`) |
| `renko-trend` | `renko` | 3 days | Variable-cadence chart transform; tooling work beyond a normal indicator function |

**Decision needed:** approve commission, in what order, and whether the
3-day `renko` work is in scope for the current sprint or deferred.

Recommendation: approve items 1-3 (1.5 days) for immediate unlock of
3 templates; defer items 4-5 to Phase 3 of templates work.

### Q2. `pandas-ta` dependency for ALMA?

ALMA can ship in two ways:

- **(a)** ~15 lines pure-Python implementing the Gaussian-weighted
  formula directly. No new dependency.
- **(b)** Add `pandas-ta` to `pyproject.toml`. ALMA is one call:
  `pandas_ta.alma(close, length, offset, sigma)`. Plus `pandas-ta`
  gives the team ~120 other prebuilt indicators for future commissions.

The repo currently has no `pandas-ta` dependency (only `ta-lib`).
Adding it would be a meaningful surface-area expansion.

Recommendation: **(a)**. The pure-Python implementation is small
enough that the dependency cost isn't worth it. Future indicators
that genuinely need pandas-ta can be evaluated case-by-case.

### Q3. Where should the new indicators land?

Existing structure:
```
backend/app/strategy_engine/indicators/
    _pack5_active.py
    _pack10_active.py
    ...
    _pack18_active.py
    _phase9_coming_soon.py
    calculations/
        <one .py per indicator with calculation_function set>
```

`renko`, `heikin_ashi`, `alma`, `kama` currently appear in the registry
via the `_phase9_coming_soon.py` block. Promoting them means:
1. Implementing `calculation_function` in
   `app/strategy_engine/indicators/calculations/{renko,heikin_ashi,alma,kama}.py`
2. Adding the dispatch branch in
   `app/strategy_engine/backtest/indicator_runner.py` (1492 LOC — Pack
   18+ section seems the right home)
3. Flipping the registry entry's `status` from `COMING_SOON` to `ACTIVE`

`pivot_swing` is a new indicator entirely — adds to `_pack18_active.py`
or a new `_pack19_active.py`, plus the calculations/ file, plus the
dispatch branch.

Recommendation: each indicator commission lands as a single PR adding
calc file + dispatch branch + registry promotion + 96%+ test
coverage. Don't batch — easier to revert one if a numeric bug surfaces.

### Q4. Will the existing 165-branch dispatch in `indicator_runner.py` accept 5 new branches without breaking?

The dispatch is a flat `if cfg.type == "X":` table. Each new indicator
adds one branch. The function is already 1492 LOC; 5 more branches is
~5 more if-blocks of ~5-15 lines each.

No structural risk — every existing pack added 10-15 branches via the
same pattern. The Week-2-prep audit doc
(`docs/EXISTING_BACKTEST_ENGINE_AUDIT.md`) confirms this dispatch is
intentionally flat for inspection clarity.

Decision needed: none — flagged so founder is aware that
`indicator_runner.py` continues to grow.

### Q5. Are there other phase-2 inactives I missed?

Audit (this branch, 2026-05-17, on origin/main HEAD `b90e356` ancestor):

```
TOTAL templates:        113
active equity:           45
inactive equity:          5
options pending:         63
```

The 5 inactives are listed in Q1. **No other inactive equity
templates exist.** The original Queue II Task 2 spec ("20 inactive")
was written before the recent 20-template activation push landed on
main. This branch is now a status-report + indicator-commission
backlog, not a config-design pass.

---

## Verification needed by Jayesh — the 45-active discrepancy

The Queue II Task 2 spec assumed ~15 active + ~35 inactive equity
templates (the Queue I Task 2 state on 2026-05-17 morning). The
current state of `origin/main` is **45 active + 5 inactive**. That's
30 net-new active equity templates landing on main in the gap
between Queue I and Queue II. Need to confirm which of three
hypotheses is right, because each implies different follow-up work:

### Hypothesis A — Queue I `feat/phase-2-template-configs` was merged

Queue I Task 2 produced `feat/phase-2-template-configs` with 15
proposed configs (`docs/PHASE_2_TEMPLATE_CONFIGS.md` +
`backend/data/phase_2_template_configs.json`). Founder approved
those configs verbatim, merged them into
`strategy_templates_seed.json`, and the seed loader pushed them
active on EC2.

Evidence for A:
- The 15 slugs proposed in Queue I (parabolic-sar-reversal,
  stochastic-oscillator, engulfing-candle-reversal,
  hammer-hanging-man-pattern, doji-reversal, donchian-channel-breakout,
  triple-ema-crossover, adx-strong-trend-filter,
  williams-pct-r-reversal, cci-momentum, pivot-point-bounce,
  bollinger-pct-b-extreme, chandelier-exit-trail,
  volume-spike-price-confirm, mfi-overbought-oversold) — check git
  log on `backend/data/strategy_templates_seed.json` for these slugs
  arriving as a batch.
- This would explain ~15 of the 30 activations.

Evidence against:
- The recent commits visible on origin/main include one-by-one
  activations: `templates(active): donchian-channel-breakout`,
  `templates(active): doji-reversal`, `templates(active):
  hammer-hanging-man-pattern`, `templates(active):
  engulfing-candle-reversal`, etc. That's the granular pattern of
  individual reviews, NOT a batch merge of Queue I's PR.
- Queue I's `feat/phase-2-template-configs` would have merged as
  ONE commit, but git log shows ~25+ separate `templates(active):`
  commits.

### Hypothesis B — Independent seed-update push

Someone (Jayesh? a parallel CC session?) ran a separate per-template
activation push on main, working from a different list — possibly
informed by Queue I's audit but not by its proposed configs verbatim.
That would explain the granular commit pattern.

Evidence for B:
- 25+ individual `templates(active):` commits visible in `git log`
  between Queue I cut and Queue II cut.
- Some of the activated slugs (`squeeze-momentum`, `fibonacci-
  retracement-entry`, `inside-bar-breakout`, `obv-divergence`,
  `range-trading-sr`, `camarilla-pivots-intraday`) were specifically
  in Queue I Task 2's NOT-picked list ("requires non-trivial
  indicator work"). Their activation implies the indicators got
  commissioned somewhere.
- Some of the activated slugs (`squeeze-momentum`, `inside-bar-
  breakout`) reference indicators I flagged as NOT-existing in
  Queue I's BLOCKERS — meaning either those indicators DID get
  commissioned, or the configs are using approximated alternatives.

Evidence against:
- None strong. Hypothesis B is the most likely.

### Hypothesis C — Counting error

I counted the seed file wrong. Maybe `is_active=True` doesn't mean
what I assume, or `requires_options_builder` overlap inflated my
"active equity" bucket.

Evidence for C:
- None. The Python snippet I ran was unambiguous:
  `is_active==True and not requires_options_builder → active_equity`.
- The 5 inactive slugs visible at `is_active==False and not
  options_pending` are all consistent with what I'd expect to be
  blocked on indicator commission.

Evidence against:
- The bucket math sums to 113 (45 + 5 + 63 = 113) — matches the
  documented template count exactly. No silent overlap.

### Recommendation

Hypothesis B is the most likely. Three concrete follow-ups regardless
of which hypothesis turns out true:

1. **Audit which configs activated.** Read each of the ~25 `templates(active):`
   commit diffs to see what `config_json` was filled in. Compare against
   Queue I Task 2's proposed configs — was Queue I's work cherry-picked,
   adapted, or ignored?

2. **Verify the indicators behind newly-active templates work.** The
   ones that surprised me (`squeeze-momentum`, `obv-divergence`) had
   indicators flagged as missing in Queue I's BLOCKERS. Either:
   (a) the indicators were commissioned (verify by checking
   `INDICATOR_REGISTRY[name].status` and `calculation_function != None`)
   (b) the configs use a workaround that the customer-visible config
   won't match (verify by reading the activated config_json)

3. **Decide if Queue I's proposed configs need to be revisited.** If
   the activated configs are the same as Queue I's proposals → done,
   close that branch. If they're different → which won? Was Queue I's
   work superseded by founder-curated configs, or did a parallel
   session miss Queue I's improvements?

### Q6. Should `phase_2_part_2_template_configs.json` be empty?

The file ships with `"proposals": []` because there's nothing to
propose without working indicators. Alternative: ship "draft" configs
that reference the not-yet-implemented indicators with a `"draft": true`
flag so they're not picked up by the validator. The argument for is
"founder can review the proposed entry/exit conditions before the
indicator lands"; the argument against is "configs that reference
non-existent indicators will rot if the indicator implementation
changes its parameter shape."

Recommendation: **keep empty**. Once the indicators ship and their
parameter signatures are locked, design the configs against the real
signatures. Draft-before-implementation invites churn.

---

## What this branch ships

```
docs/PHASE_2_TEMPLATES_PART_2.md                       full status + commission analysis
backend/data/phase_2_part_2_template_configs.json      empty-proposals file with status note
BLOCKERS_PHASE_2_PART_2.md                             this file
```

NOT touched: `backend/data/strategy_templates_seed.json`. No source files. No indicators added or modified. No tests added or modified.

## What needs to happen post-review

1. Founder confirms the 5-template gap is the complete remaining set
   (Q5).
2. Founder picks commission scope: items 1-3 of Q1 (recommended), 1-5
   (full clear), or zero (defer to Phase 3 entirely).
3. Each approved indicator gets its own implementation branch.
4. As each indicator ships ACTIVE, a follow-up `phase_2_part_2_*`
   config PR proposes the matching template's `config_json` against
   the real indicator signature.
5. Once configs are approved, the founder merges them into
   `strategy_templates_seed.json` and re-runs the seed loader on EC2.
