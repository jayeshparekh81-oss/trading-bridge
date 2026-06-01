# Queue ZZ Sprint 7a — Strategy-template parse audit

**Branch:** `verify/sprint-7a-template-parse`
**Date:** 2026-06-01
**Time used:** ~25 min (cap 1.5 hr)
**Verdict:** **STRATEGIC FINDING — schema mismatch.** Sub-sprint mechanically complete; framework correct; result requires founder direction before 7b–7e continue.

---

## Headline

| Bucket | Count | % |
|---|---|---|
| **PARSE_OK** | **0** | **0.0%** |
| MISSING_FIELDS | 68 | 60.2% |
| SCHEMA_DRIFT | 45 | 39.8% |
| VALIDATION_ERROR | 0 | 0.0% |
| **Total** | **113** | 100.0% |

> Both Hard-stop #4 ( >50% failures = framework issue likely ) and #8 ( strategic decision required ) fired. Investigation: **not** a script bug — see §3.

---

## 1. Method

For each of the 113 entries in `backend/data/strategy_templates_seed.json`, pull `config_json` and attempt construction via `app.strategy_engine.schema.strategy.StrategyJSON` (`extra="forbid"`, `frozen=True`). Bucket the outcome:

- **PARSE_OK** — `StrategyJSON(**cfg)` succeeded.
- **MISSING_FIELDS** — every reported error is `type="missing"`. Sub-flagged when `config_json == {}` (the documented Phase 2-3 placeholder case).
- **SCHEMA_DRIFT** — at least one `type="extra_forbidden"` error: the template carries a top-level field the schema doesn't accept.
- **VALIDATION_ERROR** — anything else (type mismatch, enum value, validator failure).

Framework: `backend/tests/queue_zz_sprint_7/framework_extensions/parse_audit.py`
Output: `backend/tests/queue_zz_sprint_7/parse_results.csv` (113 rows × 6 cols).

---

## 2. Breakdown by active status

| | active=true (27) | active=false (86) | Total (113) |
|---|---|---|---|
| PARSE_OK | 0 | 0 | 0 |
| MISSING_FIELDS — empty config_json | 0 | 68 | 68 |
| SCHEMA_DRIFT — old-format populated config_json | 27 | 18 | 45 |
| VALIDATION_ERROR | 0 | 0 | 0 |

Math: 27 active + 18 populated-inactive + 68 empty-inactive = **113** ✓

---

## 3. Root cause — two coexisting schemas

The 45 SCHEMA_DRIFT templates do not have malformed configs. They have **well-formed configs in a different schema** than `StrategyJSON`.

### 3a. Field-set comparison

| Required by `StrategyJSON` | Present in populated seed `config_json` |
|---|---|
| `id` | — |
| `name` | — |
| `mode` | — |
| `entry` (`EntryRules`) | — |
| `exit` (`ExitRules`) | — |
| `execution` (`ExecutionConfig`) | — |
| `indicators` (optional) | `indicators` ✓ (only overlapping field) |
| `risk` (optional) | — |
| `version` (optional) | — |

| Present in populated seed `config_json` | In `StrategyJSON`? |
|---|---|
| `entry_long` (45/45 populated templates) | ❌ rejected as extra |
| `exit_long` (45/45) | ❌ rejected as extra |
| `entry_short` (10/45) | ❌ rejected as extra |
| `exit_short` (10/45) | ❌ rejected as extra |
| `position_sizing` (45/45) | ❌ rejected as extra |
| `stop_loss_pct` (45/45) | ❌ rejected as extra |
| `take_profit_pct` (45/45) | ❌ rejected as extra |
| `trading_hours` (45/45) | ❌ rejected as extra |
| `max_open_positions` (45/45) | ❌ rejected as extra |

**Zero overlap on required fields.** The two shapes are not "compatible-with-extras"; they're entirely different serializations.

### 3b. Why this is by design (for now)

Quoting `backend/app/strategy_engine/schema/strategy.py:1-14`:
> "Phase 1 ships only the schema. Downstream phases lean on Pydantic to catch malformed strategies at the boundary so engine code never has to guard against missing fields."

And `_meta` in the seed JSON:
> "Phase 1 spec — 15 active equity + 35 inactive equity + 63 inactive options = 113 total"
> "Inactive entries (is_active=false) ship with empty config_json={}; populating their configs is Phase 2-3 work."

→ **`StrategyJSON` is forward-looking. The seed JSON is the format the current production `strategy_executor` reads.** The OLD format is what's running on Dhan today (including BSE-LTD). The migration from OLD-format → StrategyJSON has not happened yet — it's part of "Phase 2 entry/exit/risk engines" per the schema docstring.

### 3c. Confirmation — production is live on OLD format

- `is_active=true` count: **27** (15 equity + 12 others; matches `_meta` claim of "15 active equity").
- All 27 carry populated OLD-format `config_json`.
- The founder-protected BSE-LTD strategy (`89423ecc`) is among the 27 — and is **LIVE REAL MONEY on Dhan** per CLAUDE.md. So this format is unambiguously authoritative for the current executor.

---

## 4. The 68 MISSING_FIELDS (empty placeholders)

68 inactive templates have `config_json == {}`. Per the seed `_meta` note, this is by design: their configs are scheduled for Phase 2-3 population. Validating them against any schema today is a category error — they don't have configs yet. Confirmed via `parse_results.csv` filter: every MISSING_FIELDS row has `is_active=False` AND `error_summary == "empty config_json (Phase 2-3 placeholder)"`.

These 68 are not failures. They're not-yet-authored.

---

## 5. The 18 populated-inactive SCHEMA_DRIFT templates

18 inactive templates have **populated** `config_json` in the OLD format. They presumably exist because they were authored ahead of activation, awaiting either founder approval, options builder (Phase 7-8), or other unblockers (BLOCKERS_TEMPLATES.md per `_meta`). Same root cause as the 27 actives.

---

## 6. Hard-stops fired

| # | Hard-stop | Fired? | Disposition |
|---|---|---|---|
| 1 | Sub-sprint time cap reached | No | ~25 min vs 1.5-hr cap |
| 2 | Total elapsed >10 hr | No | Queue-start |
| 3 | Sacred-zone path write | No | All writes confined to `backend/tests/queue_zz_sprint_7/` and `docs/QUEUE_ZZ_*` |
| 4 | >50% template failures | **YES** | Investigated — not a script bug; finding is real (§3) |
| 5 | Seed JSON modification attempted | No | Read-only; zero writes to `backend/data/strategy_templates_seed.json` |
| 6 | Template math/logic edit attempted | No | No template files modified |
| 7 | Wanted to merge to main | No | Branch-only |
| 8 | **Strategic decision required** | **YES** | This report. Options in §7. |
| 9 | Backtest API unreachable | N/A | Not invoked in 7a |

---

## 7. Strategic options for the rest of the chain (founder decision)

**The chain as originally scoped assumes `StrategyJSON` is the canonical template format. It isn't (yet). All four downstream sub-sprints depend on this choice:**

### Option A — Re-target validation to the OLD format (recommended)
- **7a re-run** *(quick)*: write a sibling schema or duck-typed validator for the OLD seed format (`entry_long / entry_short / exit_long / exit_short / position_sizing / stop_loss_pct / take_profit_pct / trading_hours / max_open_positions / indicators`). Re-bucket all 45 populated templates: PARSE_OK / drift-from-OLD-format / VALIDATION_ERROR.
- **7b** *(unblocked)*: extract `config_json.indicators` references in the OLD shape, cross-ref against Sprint 6e's `dual_scoreboard.csv`. Largely schema-agnostic at the indicator-name level — minimal re-work.
- **7c** *(needs the real loader)*: find and invoke whatever `strategy_executor` uses today to read the OLD format and run a backtest. Source the existing `strategy_engine/api/backtest.py` and `backend/migrations/versions/028_add_backtest_runs.py` pointers.
- **7d/7e**: as designed.
- **Founder cost**: chain proceeds; 7a's framework is re-pointed (10-15 min) rather than rewritten.

### Option B — Park 7a as "schema gap discovered", skip 7c, do 7b/7d/7e light-touch
- 7b: indicator dep audit (schema-agnostic enough on `indicators_used` field) — proceeds.
- Skip 7c (backtest exec) until OLD-format support is built into the queue framework, OR until the OLD→StrategyJSON migration ships.
- 7d/7e become a thinner scorecard with parse-status + indicator-dep status only; no execution/performance dimensions.
- **Founder cost**: less coverage, but lower risk of getting tangled in OLD-format internals.

### Option C — Pause the queue, address the schema gap first
- Treat this finding as the trigger for a separate "OLD → StrategyJSON migration" workstream.
- Queue ZZ resumes after migration; templates would then PARSE_OK against `StrategyJSON`.
- **Founder cost**: longest path; depends on Phase 2 timeline.

**Recommendation: Option A.** The findings 7b–7e want to surface (indicator coverage, backtest behavior, performance sanity) are independent of which schema we validate against. Re-pointing the validator is small. Option C trades immediate observability for a larger initiative the queue wasn't scoped to drive.

---

## 8. Deliverables (this sub-sprint)

- `backend/tests/queue_zz_sprint_7/framework_extensions/__init__.py`
- `backend/tests/queue_zz_sprint_7/framework_extensions/parse_audit.py`
- `backend/tests/queue_zz_sprint_7/parse_results.csv` (113 rows)
- `docs/QUEUE_ZZ_SPRINT_7A_REPORT.md` (this file)

No changes to seed JSON. No changes to schema. No changes to sacred zone. No changes outside `backend/tests/queue_zz_sprint_7/` and `docs/QUEUE_ZZ_*.md`.

---

## 9. Awaiting founder direction

Per Hard-stop #8: 7a is checkpointed and the branch will be committed + pushed. **The chain pauses here** until founder picks Option A / B / C above. 7b is mostly independent of the schema choice; with founder OK, it can start immediately under Option A or B framing.

---

# Sprint 7a v2 — OLD-format validator + re-run

**Founder direction received 2026-06-01:** Option A — re-target Sprint 7 to OLD format. Build sibling validator. Re-categorize PHASE_2_PLACEHOLDER separately and exclude it from failure totals.

## 10. v2 method — `OldFormatConfig` sibling validator

Built `backend/tests/queue_zz_sprint_7/framework_extensions/old_format_audit.py`. The validator is a Pydantic model (`extra="forbid"`) that mirrors the live-executor template format observed across the 45 populated templates:

```python
class OldFormatConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    indicators: list[str] = Field(..., min_length=1)
    entry_long: _ConditionBlock              # {"condition": "<NL string>"}
    exit_long: _ConditionBlock
    entry_short: _ConditionBlock | None = None
    exit_short: _ConditionBlock | None = None
    stop_loss_pct: float = Field(..., gt=0)
    take_profit_pct: float = Field(..., gt=0)
    position_sizing: _PositionSizing         # method:"fixed_amount", amount_inr:int>0
    max_open_positions: int = Field(..., ge=1)
    trading_hours: _TradingHours             # start/end "HH:MM"
```

Two distinct field-set combos observed across 45 populated templates (validator covers both):
- **35 long-only**: 8 fields — no `entry_short`/`exit_short`
- **10 long-short**: 10 fields — all present
- 0 other combos. 0 outliers. Conditions are NL strings (the live executor parses them).
- `position_sizing.method` is `fixed_amount` in 100% of cases. No other method observed → modeled as `Literal["fixed_amount"]`. If/when `percent_equity` or others ship, the validator will surface them as VALIDATION_ERROR — surface that's exactly the right behavior.

## 11. v2 categorization (founder-specified)

| Bucket | Definition |
|---|---|
| **PARSE_OK** | every populated field conforms to OLD shape |
| **PHASE_2_PLACEHOLDER** | `config_json == {}` or absent — **not** counted in failure totals |
| **VALIDATION_ERROR** | populated, but field is wrong type / shape / constraint |
| **SCHEMA_DRIFT** | populated, carries fields the OLD schema doesn't accept (should be 0; non-zero would mean a third schema is sneaking in) |

## 12. v2 results

| Bucket | Count | % (of 113) |
|---|---|---|
| **PARSE_OK** | **45** | 39.8% |
| PHASE_2_PLACEHOLDER | 68 | 60.2% |
| VALIDATION_ERROR | 0 | 0.0% |
| SCHEMA_DRIFT | 0 | 0.0% |
| **Total** | 113 | 100.0% |

**Failure rate excluding placeholders: 0.0%** (0 failures / 45 populated). Below the 50% hard-stop threshold — chain may continue.

### Breakdown by active status

| | active=true (27) | active=false (86) | Total |
|---|---|---|---|
| PARSE_OK | **27** | 18 | 45 |
| PHASE_2_PLACEHOLDER | 0 | 68 | 68 |
| VALIDATION_ERROR | 0 | 0 | 0 |
| SCHEMA_DRIFT | 0 | 0 | 0 |

→ **100% of active templates parse cleanly against the OLD schema.** Exactly as the founder predicted (45 PARSE_OK / 68 placeholders).

The 0 SCHEMA_DRIFT result is itself a finding: the OLD format is faithfully homogeneous across all 45 populated templates. No outliers, no in-flight migration partials, no rogue fields. The seed JSON is internally consistent w.r.t. its own (OLD) schema.

## 13. v2 deliverables

- `backend/tests/queue_zz_sprint_7/framework_extensions/old_format_audit.py` (new, ~150 LOC)
- `backend/tests/queue_zz_sprint_7/parse_results_old_format.csv` (113 rows)
- Appended sections 10-14 to `docs/QUEUE_ZZ_SPRINT_7A_REPORT.md`

The v1 NEW-format validator (`parse_audit.py`, `parse_results.csv`) is retained as-is for posterity — it remains the canonical artifact for the eventual OLD → StrategyJSON migration check.

## 14. Hard-stops re-evaluated against v2 result

| # | Hard-stop | v2 status |
|---|---|---|
| 4 | >50% failures | **Cleared** — 0% failures excluding placeholders |
| 8 | Strategic decision required | **Resolved** — founder picked Option A |

## 15. v2 conclusion + handoff to 7b

Sub-sprint 7a is **complete**. The OLD format is the canonical anchor for the rest of the chain. Sprint 7b proceeds with these inputs:

- 45 templates have populated, structurally valid OLD-format configs → eligible for indicator-dependency cross-reference
- 27 active templates have populated OLD-format configs → eligible for 7c backtest execution
- 68 PHASE_2_PLACEHOLDER templates carry no `indicators` to cross-reference — 7b excludes them
- The 92-indicator verified tier map from Sprint 6e's `dual_scoreboard.csv` is the reference set
- New 7b bucket per founder direction: `INDIRECT_DEPENDENCY` for indicators that don't map cleanly to the verified 92 (composite names like `macd_12_26_9` vs base `macd` etc.) — distinct from `HAS_UNKNOWN`

Time used (7a v1 + v2): ~45 min of 1.5 hr cap. Remaining budget for 7a is unused.
