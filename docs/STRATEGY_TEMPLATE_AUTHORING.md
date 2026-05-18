# Strategy Template Authoring Guide

This guide walks through adding a new strategy template to TradeTri. We ship 50+ templates today; the bar for a new one is HIGH because customers clone these expecting realistic, working setups. Half-baked templates erode trust faster than missing ones.

## What a strategy template actually is

A template on TradeTri has FIVE pieces, all required:

1. **The strategy logic** — Python file defining entry/exit rules in `backend/app/templates/<slug>.py`.
2. **The config metadata** — JSON/YAML describing parameters, default values, and validation rules.
3. **The explainer content** — TypeScript file at `frontend/src/lib/strategies/explainers/<slug>.ts` with what-it-does, best/worst conditions, common mistakes, realistic returns, example trade, follow-up strategies (EN + Hinglish).
4. **The backtest data** — at least 3 months of historical paper-trading results on the templates that the strategy is calibrated for (NIFTY F&O daily, BANKNIFTY weekly, etc.).
5. **The registry entry** — both backend and frontend registries include the new slug.

## Step 1: Pick the slug + decide the scope

Slug rules:

- Kebab-case: `ema-crossover-9-21`, `bb-mean-reversion`, `rsi-oversold-bounce`.
- Be specific: include parameters if they're the strategy's defining trait (`ema-crossover-9-21` not just `ema-crossover`).
- Don't reuse. Slugs are forever.

Scope rules:

- One trading idea per template. Don't combine three filters into one "ultimate" template.
- The template's logic must fit in a 1-paragraph mental model. If you can't explain it in a paragraph, split it.
- Decide BEFORE coding: is this a trend, mean-reversion, breakout, or filter overlay? That determines the realistic-returns calibration you'll need.

## Step 2: Write the strategy logic

Create `backend/app/templates/<slug>.py`:

```python
"""EMA Crossover 9/21 — beginner-friendly trend-following template.

Long when EMA(9) crosses above EMA(21).
Exit when EMA(9) crosses below EMA(21).
Optional: ADX > 20 filter to skip chop.
"""
from __future__ import annotations

import pandas as pd

from app.templates._base import StrategyTemplate, Signal, SignalType


class EmaCrossover921(StrategyTemplate):
    slug = "ema-crossover-9-21"
    name = "EMA Crossover 9/21"
    timeframe = "1d"
    instruments = ("NIFTY", "BANKNIFTY", "F&O_STOCKS")

    @property
    def parameters(self) -> dict:
        return {
            "fast_period": {"type": "int", "default": 9, "min": 5, "max": 20},
            "slow_period": {"type": "int", "default": 21, "min": 10, "max": 50},
            "adx_filter_min": {"type": "int", "default": 20, "min": 0, "max": 50},
        }

    def generate_signals(
        self, df: pd.DataFrame, params: dict | None = None,
    ) -> list[Signal]:
        p = {**self.parameter_defaults, **(params or {})}
        fast = df["close"].ewm(span=p["fast_period"], adjust=False).mean()
        slow = df["close"].ewm(span=p["slow_period"], adjust=False).mean()
        cross_up = (fast > slow) & (fast.shift(1) <= slow.shift(1))
        cross_down = (fast < slow) & (fast.shift(1) >= slow.shift(1))

        adx = self._compute_adx(df, period=14)
        in_trend = adx >= p["adx_filter_min"]

        signals = []
        for idx in df.index:
            if cross_up.get(idx) and in_trend.get(idx):
                signals.append(Signal(idx, SignalType.LONG_ENTRY, df.at[idx, "close"]))
            elif cross_down.get(idx):
                signals.append(Signal(idx, SignalType.LONG_EXIT, df.at[idx, "close"]))
        return signals
```

Rules:

- **Pure-function `generate_signals`** — takes a DataFrame, returns a list of Signal objects.
- **No I/O.** No broker calls. No Redis. The strategy is deterministic, period.
- **Declare `parameters`** with type, default, min, max. The UI exposes these as form fields.
- **Subclass `StrategyTemplate`** for registry auto-discovery.

## Step 3: Calibrate realistic returns

This step matters more than any other. Customers compare templates and choose based on these numbers. Lying or pumping = trust collapse.

Run the strategy on at least 3 months of paper data:

```bash
cd backend
python -m scripts.backtest_template --slug ema-crossover-9-21 \
  --instruments NIFTY,BANKNIFTY,RELIANCE,HDFCBANK \
  --start 2025-01-01 --end 2025-04-30 \
  --capital 100000 --risk-per-trade 0.01
```

Capture:

- Win rate (NOT inflated; raw signal count)
- Avg R:R (winners' avg gain divided by losers' avg loss)
- Max drawdown
- Sharpe
- Total trades
- Monthly P&L distribution

Use these numbers — and ONLY these numbers — when writing the explainer's `realistic_returns` field.

Examples of LYING that we will reject:

- "Average monthly returns 20-30%" — vastly overstates real performance. Most templates deliver 2-7% paper monthly.
- "85% win rate" — only true on cherry-picked instruments + dates.
- "Backtest-proven profitable" — backtests are not guarantees; this phrasing implies one.

Examples of HONEST framing:

- "50-58% win rate, R:R 1:1.7. Monthly paper at 1% risk: 2-5%."
- "Without ADX filter, returns turn negative in choppy months."
- "Fires only on gap days (8-12 setups per month)."

## Step 4: Write the explainer content

Create `frontend/src/lib/strategies/explainers/<slug>.ts` following the pattern in `frontend/src/lib/strategies/explainers/_types.ts`.

Required fields:

- `slug` — matches the backend slug exactly.
- `what_it_does` — 2 paragraphs EN explaining the strategy logic in plain English.
- `what_it_does_hi` — same in Hinglish bhai-tone.
- `best_market_conditions` — one sentence on when this works.
- `worst_market_conditions` — one sentence on when it fails.
- `common_mistakes` — array of 3-5 strings.
- `realistic_returns` — honest numbers from your backtest.
- `example_trade` — { symbol, entry, exit, pnl } with realistic detail.
- `follow_up_strategies` — array of 3 related slugs.
- `difficulty_score` — 1 (beginner) to 5 (advanced).
- `capital_efficiency_score` — 1 to 5.

See `frontend/src/lib/strategies/explainers/rsi-oversold-bounce.ts` as the canonical example.

## Step 5: Register both ways

Backend (`backend/app/templates/__init__.py`):

```python
from app.templates.ema_crossover_9_21 import EmaCrossover921

STRATEGIES = {
    EmaCrossover921.slug: EmaCrossover921,
}
```

Frontend (`frontend/src/lib/strategies/explainers/index.ts`):

```ts
import { EMA_CROSSOVER_9_21 } from "./ema-crossover-9-21";

const EXPLAINERS_MAP: Record<string, StrategyExplainer> = {
  "ema-crossover-9-21": EMA_CROSSOVER_9_21,
};
```

## Step 6: Write tests

Backend test (`backend/tests/templates/test_ema_crossover_9_21.py`):

```python
def test_ema_crossover_signals_basic():
    df = generate_trending_data(rows=200)
    strategy = EmaCrossover921()
    signals = strategy.generate_signals(df)
    # In a clean trend, we expect at least one long entry
    assert any(s.type == SignalType.LONG_ENTRY for s in signals)

def test_ema_crossover_adx_filter_blocks_chop():
    df = generate_choppy_data(rows=200)
    strategy = EmaCrossover921()
    signals = strategy.generate_signals(df, params={"adx_filter_min": 25})
    # Chop data should produce few or no entries
    long_entries = [s for s in signals if s.type == SignalType.LONG_ENTRY]
    assert len(long_entries) <= 3

def test_ema_crossover_parameters_validate():
    strategy = EmaCrossover921()
    assert strategy.parameters["fast_period"]["default"] == 9
    assert strategy.parameters["slow_period"]["default"] == 21
```

Frontend test: the registry test in `frontend/tests/strategies/explainers-registry.test.ts` already pins shape; just bump the expected count when you add a slug.

## Step 7: Verify end-to-end

```bash
# Backend
cd backend && pytest tests/strategies/test_ema_crossover_9_21.py

# Frontend
cd frontend && npx vitest run tests/strategies

# Run the actual UI flow
cd frontend && npm run dev
# Open http://localhost:3000/strategies
# Confirm new template appears in the list
# Click it → detail page shows all explainer content
# Click "Clone to my account" → settings form appears with the parameters
# Save and Start Paper Trade → confirm a paper run starts
```

## Quality checklist before opening the PR

- [ ] Backend logic is deterministic and has no I/O
- [ ] Parameters are declared with sensible min/max ranges
- [ ] At least 3 months of backtest data informs the realistic_returns
- [ ] EN + Hinglish content reads naturally (NOT machine-translation feel)
- [ ] Common mistakes list is specific, not generic ("don't overtrade" is generic; "don't widen the stop on an open trade" is specific)
- [ ] Example trade uses a real symbol and realistic numbers
- [ ] Difficulty + capital efficiency scores reflect actual usage
- [ ] Registry entries added on both backend and frontend
- [ ] Backend + frontend tests added
- [ ] Dev-server smoke test passed manually

## What we will NOT accept

- Strategies with backtest-pumped returns (anything above 10% paper monthly average without compelling evidence).
- Strategies that claim to work "in all market conditions" — no strategy does.
- Strategies that introduce a hidden parameter not declared in `parameters` dict.
- Strategies that read external state (APIs, databases) during signal generation.
- Strategies without Hinglish content.
- Strategies without an `example_trade` with specific numbers.

## Related docs

- [ARCHITECTURE_OVERVIEW](ARCHITECTURE_OVERVIEW.md)
- [CONTRIBUTING](CONTRIBUTING.md)
- [INDICATOR_AUTHORING_GUIDE](INDICATOR_AUTHORING_GUIDE.md)
- [STRATEGY_TEMPLATES_CATALOG.md](STRATEGY_TEMPLATES_CATALOG.md) — historical catalog
- [TEMPLATES_IMPLEMENTATION_ROADMAP.md](TEMPLATES_IMPLEMENTATION_ROADMAP.md) — current template roadmap
