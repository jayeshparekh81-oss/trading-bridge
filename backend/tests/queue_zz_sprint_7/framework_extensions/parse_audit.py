"""Queue ZZ Sprint 7a — parse-validation audit of strategy_templates_seed.json.

For each of the 113 templates, extract ``config_json`` and attempt
construction via :class:`app.strategy_engine.schema.strategy.StrategyJSON`
(which has ``extra="forbid"``). Bucket the outcome:

    PARSE_OK         — StrategyJSON(...) constructed without error.
    MISSING_FIELDS   — every reported error is a missing required field
                       (the well-documented "empty config_json={}" case
                       for inactive Phase 2-3 placeholders).
    SCHEMA_DRIFT     — at least one reported error is ``extra_forbidden``
                       (template carries a field the schema doesn't know).
    VALIDATION_ERROR — anything else: type mismatch, enum value out of
                       range, constraint violation, validator failure.

Output: backend/tests/queue_zz_sprint_7/parse_results.csv (113 rows × 6 cols).

Invoke from repo root:

    python -m backend.tests.queue_zz_sprint_7.framework_extensions.parse_audit

or:

    python backend/tests/queue_zz_sprint_7/framework_extensions/parse_audit.py
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

_BACKEND_ROOT = Path(__file__).resolve().parents[3]
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from pydantic import ValidationError

from app.strategy_engine.schema.strategy import StrategyJSON  # noqa: E402

_REPO_ROOT = _BACKEND_ROOT.parent
_SEED_PATH = _BACKEND_ROOT / "data" / "strategy_templates_seed.json"
_OUT_CSV = _BACKEND_ROOT / "tests" / "queue_zz_sprint_7" / "parse_results.csv"


def _classify(template: dict, exc: ValidationError | None) -> tuple[str, str]:
    """Return (status, error_summary) for one template."""
    if exc is None:
        return "PARSE_OK", ""

    errors = exc.errors()
    error_types = {e["type"] for e in errors}

    if "extra_forbidden" in error_types:
        unknown_fields = sorted(
            {".".join(str(p) for p in e["loc"]) for e in errors if e["type"] == "extra_forbidden"}
        )
        summary = f"extra fields rejected: {unknown_fields[:5]}"
        if len(unknown_fields) > 5:
            summary += f" (+{len(unknown_fields) - 5} more)"
        return "SCHEMA_DRIFT", summary

    only_missing = error_types <= {"missing"}
    if only_missing:
        missing_fields = sorted(
            {".".join(str(p) for p in e["loc"]) for e in errors if e["type"] == "missing"}
        )
        # The 86 inactive placeholders ship with config_json={} so the
        # set of missing fields is exactly the StrategyJSON top-level
        # required set; flag that distinctly for the report.
        cfg = template.get("config_json")
        if cfg == {} or cfg is None:
            return "MISSING_FIELDS", "empty config_json (Phase 2-3 placeholder)"
        summary = f"missing: {missing_fields[:5]}"
        if len(missing_fields) > 5:
            summary += f" (+{len(missing_fields) - 5} more)"
        return "MISSING_FIELDS", summary

    # Mixed / type / value / validator errors.
    first = errors[0]
    loc = ".".join(str(p) for p in first["loc"])
    msg = first["msg"]
    summary = f"{first['type']} @ {loc}: {msg}"
    if len(errors) > 1:
        summary += f" (+{len(errors) - 1} more)"
    return "VALIDATION_ERROR", summary


def run() -> dict:
    with _SEED_PATH.open() as fh:
        seed = json.load(fh)
    templates = seed["templates"]

    rows: list[dict] = []
    counters = {"PARSE_OK": 0, "MISSING_FIELDS": 0, "SCHEMA_DRIFT": 0, "VALIDATION_ERROR": 0}

    for i, t in enumerate(templates):
        config = t.get("config_json", {})
        slug = t.get("slug", "")
        name = t.get("name", "")
        is_active = bool(t.get("is_active", False))

        if not isinstance(config, dict):
            status, summary = "VALIDATION_ERROR", f"config_json is {type(config).__name__}, not dict"
        else:
            try:
                StrategyJSON.model_validate(config)
                status, summary = _classify(t, None)
            except ValidationError as exc:
                status, summary = _classify(t, exc)

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

    return {
        "total": len(rows),
        "counters": counters,
        "active_total": sum(1 for r in rows if r["is_active"]),
        "active_parse_ok": sum(1 for r in rows if r["is_active"] and r["status"] == "PARSE_OK"),
        "active_failures": sum(1 for r in rows if r["is_active"] and r["status"] != "PARSE_OK"),
        "inactive_total": sum(1 for r in rows if not r["is_active"]),
        "inactive_empty_config": sum(
            1
            for r in rows
            if not r["is_active"]
            and r["status"] == "MISSING_FIELDS"
            and "empty config_json" in r["error_summary"]
        ),
        "output_csv": str(_OUT_CSV.relative_to(_REPO_ROOT)),
    }


if __name__ == "__main__":
    result = run()
    print(json.dumps(result, indent=2))
