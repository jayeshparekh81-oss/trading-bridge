# BLOCKERS — Template Activation Audit

**Branch:** `docs/template-activation-audit-batch-1`
**Date:** 2026-05-18
**Sibling docs:**
  - `docs/TEMPLATE_ACTIVATION_AUDIT.md` (per-template status table)
  - `docs/proposed_seed_patch.json` (proposed deactivation list — NOT applied)
  - `scripts/audit_template_activation.py` (regenerator)

---

## TL;DR

45 active equity templates audited. **16 are flagged as not
runtime-safe** — they reference indicators that aren't registered
under their resolvable name OR aren't in the backtest dispatch table.

The remaining 29 are runtime-safe.

The auditor uses a **name-normalisation pass** to bridge config-time
informal names (`ema_9`) to registry type ids (`ema`). After
normalisation, 16 templates still fail.

**Per spec, this branch does NOT modify the seed file.** The
proposed-deactivation patch ships as a JSON artifact for founder
review.

---

## The 16 unsafe templates

Per the audit, these template `config_json.indicators` lists reference
names that don't resolve to a runtime-callable indicator:

```
pdh-pdl-breakout
banknifty-weekly-equity
premarket-gap
heikin-ashi-trend
keltner-channel-bounce
parabolic-sar-reversal
stochastic-oscillator
psar-ema-combo
pivot-point-bounce
fibonacci-retracement-entry
range-trading-sr
hammer-hanging-man-pattern
chandelier-exit-trail
volume-spike-price-confirm
bollinger-pct-b-extreme
squeeze-momentum
```

---

## Founder-review items

### Q1. Indicator-naming-drift policy

The audit revealed that template configs use 3+ different naming
conventions for the SAME indicator:

| Config-time | Registry id | Calculation file |
|---|---|---|
| `ema_9`, `ema_20`, `ema_50` | `ema` | `ema.py` |
| `bb_20_2` | `bollinger_bands` | `bollinger_bands.py` |
| `stochastic_14_3_3` | `stochastic` | `stochastic.py` |
| `psar` | `parabolic_sar` | `parabolic_sar.py` |
| `williams_pct_r` | `williams_r` | `williams_r.py` |
| `engulfing_pattern` | `bullish_engulfing` | `bullish_engulfing.py` |

The auditor's `_normalise_indicator_name` function has a
hand-curated alias map for the known drift cases. Even after
normalisation, 16 templates remain unsafe — meaning they reference
indicators that genuinely don't map.

**Decision needed:** schedule a `chore/template-indicator-naming-canonicalisation`
sprint that rewrites every `config_json.indicators` in the live seed
to use canonical registry ids. Single-source-of-truth eliminates the
drift class entirely.

Recommendation: yes, ship in a single coordinated PR + re-run seed
loader on EC2.

### Q2. The 16 unsafe templates — deactivate or commission?

Two paths per unsafe template:

- **Deactivate** (recommended for templates blocked on indicators
  that don't exist in registry at all): flip `is_active=False` until
  the indicator is commissioned.

- **Commission the missing indicator** (recommended when the
  indicator IS implemented but missing from the dispatch table OR
  using a non-canonical name):
  - `heikin-ashi-trend` → `heikin_ashi` was commissioned in Queue III
    Task 1 + dispatched in Queue IV Task 3 → should be SAFE now;
    needs config update to use canonical name
  - `fibonacci-retracement-entry` → `fibonacci_retracement` same as above
  - `parabolic-sar-reversal` → `parabolic_sar` registered + dispatched;
    config likely uses `psar` short form

Recommendation: **batch decision per-template**. The audit table in
`docs/TEMPLATE_ACTIVATION_AUDIT.md` shows the specific failure cause
per indicator per template.

### Q3. The proposed seed patch is conservative

`docs/proposed_seed_patch.json` lists all 16 unsafe slugs. Applying
it without per-template review would deactivate templates that just
need a config rename (not actual indicator commission).

**Decision needed:** apply the patch wholesale (conservative; minor
customer-visible disruption) OR per-template review + commission as
needed.

Recommendation: per-template review. The audit output makes this
quick — each row tells you exactly which indicator failed.

### Q4. Auto-correction script

A follow-up sprint could ship `scripts/canonicalize_template_indicators.py`
that:
1. Reads the seed file
2. For each `config_json.indicators` name, normalises via the same
   alias map the auditor uses
3. Writes the corrected seed back

That would fix Q1 in one sprint. Out of scope here per spec.

---

## Files this branch ships

```
scripts/audit_template_activation.py         the auditor (regenerator)
docs/TEMPLATE_ACTIVATION_AUDIT.md            per-template status table
docs/proposed_seed_patch.json                proposed deactivation list (NOT applied)
BLOCKERS_TEMPLATE_ACTIVATION_AUDIT.md        this file
```

NOT touched:
- The live `backend/data/strategy_templates_seed.json`
- Any template config_json
- Any source code

## Hard constraints honoured

- ✅ DO NOT modify the live seed file
- ✅ DO NOT modify any template configs
- ✅ Audit doc + proposed patch only

## How to regenerate

```sh
python3 scripts/audit_template_activation.py
# Writes docs/TEMPLATE_ACTIVATION_AUDIT.md + docs/proposed_seed_patch.json
```

Run after:
- Any change to the seed file
- Any new indicator commission
- Any change to the dispatch table
- Adding a new entry to `_normalise_indicator_name` aliases (if a
  drift case is discovered)
