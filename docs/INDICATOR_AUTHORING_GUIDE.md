# Indicator Authoring Guide

This guide is for engineers adding new technical indicators to Trading Bridge. We support 70+ indicators today; adding one more should be mechanical, not adventurous. This guide makes it so.

## What an indicator actually is in our codebase

An indicator on TradeTri has FOUR pieces, and you need all four to ship a new one cleanly:

1. **The calculation** — pure-Python function in `backend/app/strategy_engine/indicators/<slug>.py` that takes OHLCV data and returns indicator values.
2. **The audit log integration** — the calculation must emit a deterministic audit log entry so users can verify the math (Glass Box).
3. **The content** — educational TypeScript file at `frontend/src/lib/indicators/content/<slug>.ts` with EN + Hinglish descriptions, use cases, signals, pitfalls, Indian context.
4. **The registry entry** — both backend and frontend registries import and register the new slug.

Skipping any of these four ships an incomplete feature. The Phase F audit specifically calls out: "every indicator must be auditable end-to-end, from formula to UI." That's why the guide is structured this way.

## Step 1: Pick the slug

- Use kebab-case: `mass-index`, `coppock-curve`, `comparative-relative-strength`.
- Match the canonical name from a reputable reference (Murphy, Pring, the indicator's original paper).
- Don't abbreviate unless the abbreviation is widely recognized (RSI yes, RVI maybe, AdjEMA no).
- Never reuse a slug. Slugs are forever — they're part of URLs, bookmarks, and audit log keys.

## Step 2: Write the backend calculation

Create `backend/app/strategy_engine/indicators/<slug>.py`:

```python
"""Mass Index — volatility-expansion reversal detector.

Reference: Donald Dorsey, Stocks & Commodities V13:9 (1995).
"""
from __future__ import annotations

import pandas as pd

from app.strategy_engine.indicators._base import Indicator, AuditEntry


class MassIndex(Indicator):
    slug = "mass-index"
    name = "Mass Index"
    default_period = 25
    inputs = ("high", "low")

    def compute(self, df: pd.DataFrame, period: int = 25) -> pd.Series:
        """Compute Mass Index over `df`.

        Args:
            df: DataFrame with 'high', 'low' columns.
            period: Sum window length (Dorsey's default: 25).

        Returns:
            Series of Mass Index values, indexed like df.
        """
        rng = df["high"] - df["low"]
        ema1 = rng.ewm(span=9, adjust=False).mean()
        ema2 = ema1.ewm(span=9, adjust=False).mean()
        ratio = ema1 / ema2
        return ratio.rolling(window=period).sum()

    def audit(self, df: pd.DataFrame, period: int = 25) -> AuditEntry:
        """Emit a verifiable audit entry for the last bar's computation."""
        return AuditEntry(
            indicator=self.slug,
            formula_version="dorsey_1995",
            inputs={
                "high_last_25": df["high"].tail(25).tolist(),
                "low_last_25": df["low"].tail(25).tolist(),
            },
            params={"period": period, "smooth_period": 9},
            timestamp=df.index[-1],
        )
```

Rules:

- **Pure function**. No I/O, no broker calls, no Redis.
- **Deterministic**. Same input → same output, every time.
- **Pandas Series output**. Indexed identically to the input DataFrame.
- **Subclass `Indicator`** for registry auto-discovery.
- **Implement both `compute` and `audit`**. The audit is what makes Glass Box honest.

## Step 3: Add tests

Create `backend/tests/indicators/test_<slug>.py`:

```python
import pandas as pd
import pytest

from app.strategy_engine.indicators.mass_index import MassIndex


def make_df(rows: int = 100) -> pd.DataFrame:
    """Generate deterministic test OHLCV data."""
    import numpy as np
    rng = np.random.default_rng(42)
    close = 100 + np.cumsum(rng.normal(0, 1, rows))
    return pd.DataFrame({
        "open": close + rng.normal(0, 0.5, rows),
        "high": close + np.abs(rng.normal(0.5, 0.5, rows)),
        "low": close - np.abs(rng.normal(0.5, 0.5, rows)),
        "close": close,
        "volume": rng.integers(1000, 100000, rows),
    })


def test_mass_index_basic_shape():
    ind = MassIndex()
    df = make_df(100)
    out = ind.compute(df)
    assert len(out) == 100
    assert out.iloc[:24].isna().all()  # first 24 bars unfillable
    assert not out.iloc[25:].isna().any()


def test_mass_index_deterministic():
    """Same input → same output (Glass Box requirement)."""
    ind = MassIndex()
    df = make_df(100)
    out1 = ind.compute(df)
    out2 = ind.compute(df.copy())
    pd.testing.assert_series_equal(out1, out2)


def test_mass_index_audit_entry():
    ind = MassIndex()
    df = make_df(100)
    audit = ind.audit(df)
    assert audit.indicator == "mass-index"
    assert audit.formula_version == "dorsey_1995"
    assert len(audit.inputs["high_last_25"]) == 25


def test_mass_index_reversal_bulge():
    """A volatility spike should push MI above 27 (Dorsey's reversal threshold)."""
    df = make_df(100)
    df.loc[df.index[-10:], "high"] += 20  # inject volatility expansion
    out = MassIndex().compute(df)
    assert out.iloc[-1] > 27
```

Rules:

- **Deterministic test data**. Seed the RNG explicitly.
- **Test both correctness AND audit shape**.
- **At least one test that exercises the indicator's CHARACTERISTIC behavior** (e.g., reversal bulge for Mass Index).
- **Don't mock; use real Pandas DataFrames.**

## Step 4: Register on the backend

Add to `backend/app/strategy_engine/indicators/__init__.py`:

```python
from app.strategy_engine.indicators.mass_index import MassIndex
# ... other imports

INDICATORS = {
    # ... existing
    MassIndex.slug: MassIndex,
}
```

## Step 5: Write the frontend content

Create `frontend/src/lib/indicators/content/<slug>.ts` following the pattern from existing indicators (see `frontend/src/lib/indicators/content/rsi.ts` as the canonical example).

Required fields:

- `slug` — must match the backend slug exactly.
- `name` — display name including spelled-out version: `"Mass Index"`.
- `category` — one of `momentum | trend | volatility | volume | rate | pattern | advanced`.
- `complexity` — `beginner | intermediate | advanced`.
- `one_liner_en` / `one_liner_hi` — tooltip-length summary.
- `description_en` / `description_hi` — 3-4 paragraphs separated by `\n\n`.
- `formula_explanation` — plain-English math; no LaTeX, no code.
- `default_period`, `period_range`, `common_periods` — period semantics.
- `use_cases` — array of 2-4 scenario/what_to_do/why objects.
- `common_signals` — array of 2-5 signal/condition/action objects.
- `pitfalls` — array of 3-5 string pitfalls.
- `works_well_with` / `works_poorly_with` — kebab-case slug lists.
- `example_strategies` — free-text strategy names.
- `indian_context` — NIFTY/BANKNIFTY/F&O specifics. **Required**, not optional.

Bilingual rules (enforced by tests):

- `description_hi` and `one_liner_hi` must be in **Roman-script Hinglish**, NOT Devanagari. Test will reject Devanagari characters.
- Content should be informally conversational, not formal: "Aapka data" not "आपका डेटा".
- The Hinglish must read naturally to a Hindi speaker — no machine-translation feel.

## Step 6: Register on the frontend

Add to `frontend/src/lib/indicators/registry.ts`:

```ts
import { MASS_INDEX } from "./content/mass-index";

export const INDICATORS: Readonly<Record<string, IndicatorContent>> = {
  // ... existing
  "mass-index": MASS_INDEX,
};
```

## Step 7: Verify the structural test passes

Run the existing wave-3 registry test (or create a new wave test for your batch):

```bash
cd frontend
npx vitest run tests/indicators/wave-3-registry.test.ts
```

The test enforces:

- Slug present in registry
- ≥500 chars EN/HI description
- ≥3 paragraphs in description_en
- No Devanagari in HI text (Hinglish enforced)
- ≥2 use cases, ≥3 pitfalls
- `indian_context` ≥ 150 chars
- `works_well_with` references kebab-case

## Step 8: Verify end-to-end

```bash
# Backend
cd backend
pytest tests/indicators/test_mass_index.py

# Frontend
cd frontend
npx vitest run tests/indicators
npm run typecheck

# End-to-end: dev server + click on the indicator in the chart
npm run dev
# Open http://localhost:3000/indicators/mass-index
# Confirm: title, description, signals all render
# Click an indicator value on a chart — audit log entry shows the formula and inputs
```

## What to do when the math is hard

Some indicators (Ichimoku, Hilbert Transform, Schaff Trend Cycle) have non-trivial math. Don't try to derive from memory.

- Cite the original paper or canonical reference in a comment.
- Compare your implementation against pandas-ta or TA-Lib output on the same data — they're your sanity check.
- Test on real NIFTY/BANKNIFTY data in addition to synthetic data.
- If a precise period/parameter is debated in references, document your choice and why.

## What we will NOT accept

- Indicators without an audit log entry (violates Glass Box principle).
- Indicators without Hinglish content (we're India-first).
- Indicators without an `indian_context` section.
- Indicators that depend on volume data without a fallback for index futures (hedging volume distortion is documented behavior).
- Indicators implemented as "the formula I remember" without a citation.

## Related docs

- [ARCHITECTURE_OVERVIEW](ARCHITECTURE_OVERVIEW.md) — system context
- [CONTRIBUTING](CONTRIBUTING.md) — general code rules
- [indicator-registry.md](indicator-registry.md) — historical Phase F audit notes
