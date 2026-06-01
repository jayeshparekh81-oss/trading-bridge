# Queue WW Sprint 8d — chaikin + Aroon tooltip final specs

**Branch:** `docs/sprint-8d-tooltip-final-spec` (off `main@85d09ea`)
**Date:** 2026-06-02
**Time used:** ~15 min (cap 30 min)
**Verdict:** **PASS.** 6 final tooltips written (50-80 words each), all within plan's word-count band. 3 display contexts (chart hover, detail modal, dependency warning) specified. Optional JSON-artifact merge shape documented for Sprint 8c's badge artifact.

---

## 1. Headline

| Item | Value |
|---|---|
| Indicators covered | 6 (matches the ⚠ Convention varies bucket from Sprint 8c) |
| Final tooltip per indicator | 1 each (the 50-80 word version) |
| Tooltips within cap | 6 / 6 (all in 50-80 word band) |
| Display contexts specified | 3 (chart hover, detail modal, dependency warning) |
| Doc | `docs/CONVENTION_TOOLTIP_FINAL.md` |
| Sources reused | Sprint 6d Version 2 (chaikin verbatim) + Sprint 6d Sprint 5a notes (aroon family) + Sprint 5c notes (chande) |
| Seed JSON / sacred-zone touches | 0 |

---

## 2. Per-indicator word counts

| Indicator | Words | Pine convention summary |
|---|---:|---|
| `aroon` | 73 | First-occurrence of period extreme wins (TA-Lib uses last-occurrence) |
| `aroon_up` | 64 | Same first-vs-last convention |
| `aroon_down` | 63 | Same first-vs-last convention |
| `aroon_oscillator` | 66 | Inherits Aroon Up − Aroon Down convention |
| `chande_momentum` | 69 | Original Chande raw period-sum (TA-Lib applies Wilder smoothing) |
| `chaikin_oscillator` | 62 | Pine independent-EMA seeding (TA-Lib uses aligned internal seeding) |

---

## 3. Display-context decisions

| Context | What's shown | Why |
|---|---|---|
| Chart hover | First sentence only (~15-25 words) | Hover real-estate is tight; the first sentence carries the "we use Pine convention" headline |
| Indicator detail modal | Full 50-80 word body | The full-context surface — customers evaluating the indicator deliberately |
| Dependency warning | First sentence + "Learn more →" link | Strategy builder surfaces this only when a Convention-varies indicator is combined with a side-by-side talib-reference indicator in the same strategy |

---

## 4. Reuse from prior sprints

- **`chaikin_oscillator`** — copy is verbatim from Sprint 6d Version 2 (62 words). Sprint 6d shipped 3 versions and explicitly recommended V2 for the chart panel; this sprint canonicalises that recommendation as the single final form.
- **Aroon family (4 indicators)** — convention split is from Sprint 5a's first-vs-last-occurrence finding (TRADETRI uses Pine first-occurrence). Each indicator gets its own tooltip because their use cases differ slightly (Up vs Down vs the Oscillator composite); the four bodies share a near-identical convention-explanation paragraph with indicator-specific signal-impact tails.
- **`chande_momentum`** — convention split is from Sprint 5c's raw-sum-vs-Wilder-smoothing finding. New copy written this sprint.

---

## 5. Founder review checklist for tomorrow

1. **Voice check (CRITICAL)** — the six bodies all use a similar "TRADETRI's X uses Pine; TA-Lib uses Y; both are valid; signals are identical" pattern. Confirm this is the customer-facing voice you want (some founders want "TradingView-equivalent" front-loaded; others want the technical reason first). Small wording tweaks won't change the spec shape.

2. **JSON-artifact merge** — Sprint 8c's `docs/indicator_library_badges.json` currently has no `tooltip_full` / `tooltip_short` fields. Doc §3 shows the shape; the frontend can read either the markdown directly or merge the strings into the JSON. If the JSON is the canonical source for the frontend, sign off on the merge and Sprint 8c's `generate_badges.py` gains a 10-line patch.

3. **"TRADETRI" vs "Tradetri" vs no brand at all** — the chaikin Sprint 6d V2 says "The Chaikin Oscillator shown here matches TradingView's standard formula" without using "TRADETRI". The other 5 lead with "TRADETRI's Aroon uses…". Pick a unified voice (or accept the asymmetry — chaikin V2 was reviewed and approved in Sprint 6d, so changing it just for symmetry may not be worth it).

4. **Whether to surface in the chart hover at all** — the chart hover already shows the indicator value at the cursor. Adding a ⚠ tooltip when hovering an indicator line may be visual noise. Consider showing ⚠ ONLY in the indicator-selector (where the customer is *about* to select) and in the strategy-builder dependency warning (where they've already selected, and the system noticed the combination). The chart hover would then show value-only as today. Lighter-touch.

5. **Localisation** — these are English-only. If a Hindi/Hinglish customer voice is on the roadmap, schedule a separate localisation sprint; the spec already supports it (just add `tooltip_full_hi` etc. to the JSON).
