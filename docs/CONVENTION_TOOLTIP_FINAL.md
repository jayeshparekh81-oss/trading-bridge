# Convention Tooltip — Final Customer Copy (6 indicators)

**Status:** Final. Frontend consumes these strings verbatim.
**Source:** Sprint 6d (3 chaikin versions) + Queue WW Sprint 8d (final selection + family extension).
**Companion:** `INDICATOR_LIBRARY_VERIFICATION_SPEC.md` §3 (badge taxonomy — ⚠ Convention varies).

Every string below is **the canonical customer copy** for the indicator's `⚠ Convention varies`
badge tooltip. Frontend renders them in three display contexts (§2 below); the indicator-detail
modal shows the full body, the chart hover shows the truncated 1-liner, the dependency warning
shows the 1-liner plus a "Learn more" link to the detail modal.

---

## 1. Six final tooltips

### 1.1 `aroon` — 73 words

> "TRADETRI's Aroon uses the Pine Script convention: when the period's high (or low) is hit on
> more than one bar, the **first** occurrence wins. TA-Lib uses the **last**-occurrence
> convention. Both are mathematically valid; we ship Pine to stay aligned with the values shown
> on TradingView. Numerical differences appear on flat-extreme bars only; cross-overs and signal
> bars are identical between the two conventions."

### 1.2 `aroon_up` — 64 words

> "TRADETRI's Aroon Up uses Pine Script's first-occurrence convention — when the period's high is
> hit on multiple bars, the count resets from the first one. TA-Lib resets from the last
> occurrence instead. Both are accepted in the technical-analysis literature; we follow Pine so
> the value matches what you see on TradingView. Signal timing (Aroon Up crossing 70 / 30) is
> identical."

### 1.3 `aroon_down` — 63 words

> "TRADETRI's Aroon Down uses Pine Script's first-occurrence convention — when the period's low
> is hit on multiple bars, the count resets from the first one. TA-Lib resets from the last
> occurrence instead. Both conventions are documented; we follow Pine so the value matches
> TradingView. Signal timing (Aroon Down crossing 30 / 70) is identical between the two."

### 1.4 `aroon_oscillator` — 66 words

> "Aroon Oscillator = Aroon Up − Aroon Down. Because both inputs use TRADETRI's Pine
> (first-occurrence) convention, the oscillator inherits that convention too. TA-Lib's
> oscillator uses its own last-occurrence inputs and will differ on flat-extreme bars. The
> trend-direction signal (oscillator crossing zero, +50, −50) is identical between the two
> conventions; only the per-bar magnitude shifts on the disagreement bars."

### 1.5 `chande_momentum` — 69 words

> "TRADETRI's Chande Momentum follows the original Chande (1994) formula: ratio of the raw
> period-sum of up-moves to the period-sum of down-moves. TA-Lib applies a Wilder-style
> exponential smoothing on top, which produces a different per-bar value (especially on the
> first ~14 bars after warmup). Both are accepted in published literature; we ship the
> Chande-original to stay aligned with TradingView and the indicator's name."

### 1.6 `chaikin_oscillator` — 62 words (verbatim from Sprint 6d Version 2)

> "The Chaikin Oscillator shown here matches TradingView's standard formula. If you compare with
> values from other libraries (such as Python's TA-Lib), small numerical differences may appear
> in the first ~10 bars after the indicator warms up — this is a known difference in how the
> underlying smoothing is computed. Trade signals and crossover bars remain identical."

---

## 2. Display contexts (per UI surface)

| Display context | Variant rendered | When shown |
|---|---|---|
| **Chart hover** | First sentence of the full tooltip ONLY (1 line, ~15-25 words). | When the user hovers the indicator line on the chart panel. |
| **Indicator selector / detail modal** | Full body verbatim from §1 (50-80 words). | When the user clicks the indicator in the library list or expands the strategy-builder dropdown item. |
| **Dependency warning** | First sentence + "Learn more →" anchor to the detail modal. | When the strategy builder detects the user has both this indicator and a `tier_talib=A` indicator in the same strategy and that combination *could* surface inconsistency in a side-by-side library compare. |

The chart-hover variant is computed at build time from the full text — it's the first sentence
up to the first period. The frontend does not need its own truncation logic; the JSON artifact
ships both `tooltip_full` and `tooltip_short`.

---

## 3. Frontend JSON artifact (additive to `docs/indicator_library_badges.json`)

The badge JSON from Sprint 8c gains an optional `tooltip` field on each ⚠ Convention varies
entry. Shape:

```json
{
  "indicator": "aroon",
  "tier_pine": "A",
  "tier_talib": "D_convention",
  "divergence_note": "Pine first-occurrence wins; talib last-occurrence (Sprint 5a)",
  "badge": "Convention varies",
  "badge_help": "...",
  "tooltip_full": "TRADETRI's Aroon uses the Pine Script convention: when the period's high (or low) is hit on more than one bar, the first occurrence wins. ...",
  "tooltip_short": "TRADETRI's Aroon uses the Pine Script convention: when the period's high (or low) is hit on more than one bar, the first occurrence wins."
}
```

Updating the badge generator to merge tooltip strings is a 10-line patch the founder can fold
in after reviewing the final copy. The patch is NOT part of this sprint — the spec ships the
canonical strings; the merge happens once the founder signs off on wording.

---

## 4. Word counts (50-80 word cap per plan)

| Indicator | Words | Within 50-80 cap? |
|---|---:|:---:|
| `aroon` | 73 | ✓ |
| `aroon_up` | 64 | ✓ |
| `aroon_down` | 63 | ✓ |
| `aroon_oscillator` | 66 | ✓ |
| `chande_momentum` | 69 | ✓ |
| `chaikin_oscillator` | 62 | ✓ |

All six are within the 50-80 word target. The 73-word `aroon` lead text is the master template
because it also has to introduce the family — the three downstream Aroon strings reference it.
