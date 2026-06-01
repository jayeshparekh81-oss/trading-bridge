"""Queue ZZ Sprint 7a v2 — parse audit against the OLD seed-format schema.

The seed JSON's populated ``config_json`` blocks all share one structural
shape — the format the live ``strategy_executor`` reads today (the same
format BSE-LTD runs on Dhan with real money). 7a v1 validated against
``StrategyJSON`` (Phase-1-shipped forward schema, zero overlap), which
correctly returned 0/113 PARSE_OK. v2 validates against the OLD format
directly so the chain can anchor on the format production actually uses.

Bucketing (founder direction, 2026-06-01):

    PARSE_OK             — every populated field conforms to the OLD shape.
    PHASE_2_PLACEHOLDER  — config_json == {} or absent. By design per seed
                           _meta. Not counted in failure totals.
    VALIDATION_ERROR     — populated, but a field is wrong type / shape /
                           constraint violation.
    SCHEMA_DRIFT         — populated, carries fields the OLD schema doesn't
                           accept (should be 0 if the OLD format is faithful;
                           a non-zero count means a third schema is sneaking in).

Output: backend/tests/queue_zz_sprint_7/parse_results_old_format.csv
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path
from typing import Literal

_BACKEND_ROOT = Path(__file__).resolve().parents[3]
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator  # noqa: E402

_REPO_ROOT = _BACKEND_ROOT.parent
_SEED_PATH = _BACKEND_ROOT / "data" / "strategy_templates_seed.json"
_OUT_CSV = _BACKEND_ROOT / "tests" / "queue_zz_sprint_7" / "parse_results_old_format.csv"


# ─── OLD-format Pydantic models ──────────────────────────────────────────────
# Mirrors the populated config_json shape observed across all 45 populated
# templates (35 long-only + 10 long-short, no other variants). Conditions
# are NL strings — the live executor parses them at runtime. Validation
# here is structural only: required keys + types + non-empty strings.


class _ConditionBlock(BaseModel):
    model_config = ConfigDict(extra="forbid")
    condition: str = Field(..., min_length=1)


class _PositionSizing(BaseModel):
    model_config = ConfigDict(extra="forbid")
    method: Literal["fixed_amount"]
    amount_inr: int = Field(..., gt=0)


class _TradingHours(BaseModel):
    model_config = ConfigDict(extra="forbid")
    start: str = Field(..., pattern=r"^\d{2}:\d{2}$")
    end: str = Field(..., pattern=r"^\d{2}:\d{2}$")


class OldFormatConfig(BaseModel):
    """The live-executor template format (as serialized in seed config_json)."""

    model_config = ConfigDict(extra="forbid")

    indicators: list[str] = Field(..., min_length=1)
    entry_long: _ConditionBlock
    exit_long: _ConditionBlock
    entry_short: _ConditionBlock | None = None
    exit_short: _ConditionBlock | None = None
    stop_loss_pct: float = Field(..., gt=0)
    take_profit_pct: float = Field(..., gt=0)
    position_sizing: _PositionSizing
    max_open_positions: int = Field(..., ge=1)
    trading_hours: _TradingHours

    @field_validator("indicators")
    @classmethod
    def _indicators_non_empty_strings(cls, v: list[str]) -> list[str]:
        for i, item in enumerate(v):
            if not isinstance(item, str) or not item.strip():
                raise ValueError(f"indicators[{i}] must be a non-empty string")
        return v


# ─── Bucketing ───────────────────────────────────────────────────────────────


def _classify(cfg: dict | None, exc: ValidationError | None) -> tuple[str, str]:
    if cfg is None or cfg == {}:
        return "PHASE_2_PLACEHOLDER", "empty config_json (Phase 2-3, by design)"
    if exc is None:
        return "PARSE_OK", ""

    errors = exc.errors()
    error_types = {e["type"] for e in errors}

    if "extra_forbidden" in error_types:
        unknown = sorted(
            {".".join(str(p) for p in e["loc"]) for e in errors if e["type"] == "extra_forbidden"}
        )
        summary = f"extra fields rejected: {unknown[:5]}"
        if len(unknown) > 5:
            summary += f" (+{len(unknown) - 5} more)"
        return "SCHEMA_DRIFT", summary

    first = errors[0]
    loc = ".".join(str(p) for p in first["loc"])
    summary = f"{first['type']} @ {loc}: {first['msg']}"
    if len(errors) > 1:
        summary += f" (+{len(errors) - 1} more)"
    return "VALIDATION_ERROR", summary


def run() -> dict:
    with _SEED_PATH.open() as fh:
        seed = json.load(fh)
    templates = seed["templates"]

    rows: list[dict] = []
    counters = {
        "PARSE_OK": 0,
        "PHASE_2_PLACEHOLDER": 0,
        "VALIDATION_ERROR": 0,
        "SCHEMA_DRIFT": 0,
    }

    for i, t in enumerate(templates):
        cfg = t.get("config_json", {})
        slug = t.get("slug", "")
        name = t.get("name", "")
        is_active = bool(t.get("is_active", False))

        if not isinstance(cfg, dict):
            status, summary = "VALIDATION_ERROR", f"config_json is {type(cfg).__name__}, not dict"
        elif cfg == {}:
            status, summary = _classify(cfg, None)
        else:
            try:
                OldFormatConfig.model_validate(cfg)
                status, summary = _classify(cfg, None)
            except ValidationError as exc:
                status, summary = _classify(cfg, exc)

        counters[status] += 1
        rows.append(
            {
                "index": i,
                "slug": slug,
                "name": name,
                "is_active": is_active,
                "status": status,
                "error_summary": summary.replace("\n", " ").replace("\r", " "),
            }
        )

    _OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    with _OUT_CSV.open("w", newline="") as fh:
        writer = csv.DictWriter(
            fh, fieldnames=["index", "slug", "name", "is_active", "status", "error_summary"]
        )
        writer.writeheader()
        writer.writerows(rows)

    populated_total = sum(1 for r in rows if r["status"] != "PHASE_2_PLACEHOLDER")
    failures = sum(
        1 for r in rows if r["status"] in {"VALIDATION_ERROR", "SCHEMA_DRIFT"}
    )

    return {
        "total": len(rows),
        "counters": counters,
        "populated_total": populated_total,
        "failures_excl_placeholders": failures,
        "failure_rate_excl_placeholders": (
            round(100.0 * failures / populated_total, 1) if populated_total else 0.0
        ),
        "active_total": sum(1 for r in rows if r["is_active"]),
        "active_parse_ok": sum(1 for r in rows if r["is_active"] and r["status"] == "PARSE_OK"),
        "output_csv": str(_OUT_CSV.relative_to(_REPO_ROOT)),
    }


if __name__ == "__main__":
    result = run()
    print(json.dumps(result, indent=2))
