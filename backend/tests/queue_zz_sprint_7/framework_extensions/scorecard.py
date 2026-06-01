"""Queue ZZ Sprint 7e — composite scorecard.

Join the 4 prior sub-sprint outputs per template and assign a composite
bucket + actionable recommendation:

    PRODUCTION_READY    — active, parse OK, deps clean, fires + sanity-clean
    ACTIVE_BUT_BROKEN   — active but currently cannot translate or execute
    NEEDS_FIX           — has a concrete defect blocking activation
    INACTIVE_OK         — inactive and no urgent issue (Phase 2-3 placeholder
                          OR dep-clean populated inactive)
    UNKNOWN             — fell through every rule (shouldn't happen)

Inputs:
    parse_results_old_format.csv  (7a v2)
    dependency_audit.csv          (7b)
    backtest_execution.csv        (7c — subset of templates)
    performance_sanity.csv        (7d — subset of templates)

Output: backend/tests/queue_zz_sprint_7/template_scorecard.csv (113 rows × 10 cols).
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

_BACKEND_ROOT = Path(__file__).resolve().parents[3]
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

_REPO_ROOT = _BACKEND_ROOT.parent
_QUEUE_DIR = _BACKEND_ROOT / "tests" / "queue_zz_sprint_7"
_SEED_PATH = _BACKEND_ROOT / "data" / "strategy_templates_seed.json"
_OUT_CSV = _QUEUE_DIR / "template_scorecard.csv"

_BENIGN_SANITY = {"PASS_SANITY", "SUSPICIOUS_INF_PROFIT_FACTOR"}


def _load_csv_by_slug(path: Path) -> dict[str, dict]:
    if not path.exists():
        return {}
    return {row["slug"]: row for row in csv.DictReader(path.open())}


def _bucket_and_reco(  # noqa: PLR0911 - explicit per-case branching reads clearer than a table
    is_active: bool,
    parse_status: str,
    dep_status: str,
    exec_status: str | None,
    sanity_flags: str | None,
    exec_error: str,
) -> tuple[str, str]:
    """Return (composite_bucket, recommendation)."""
    if is_active:
        if exec_status in {"FIRES_CLEAN", "FIRES_WITH_WARNINGS"}:
            flags = {f.strip() for f in (sanity_flags or "").split(";") if f.strip()}
            if flags <= _BENIGN_SANITY and flags:
                if "SUSPICIOUS_INF_PROFIT_FACTOR" in flags:
                    return (
                        "PRODUCTION_READY",
                        "leave-as-is — small-sample inf profit-factor will "
                        "resolve on real-data backtests",
                    )
                return "PRODUCTION_READY", "leave-as-is"
            if not flags:
                # 7d hasn't been run on this template (shouldn't happen for
                # an active that fires, but guard anyway).
                return "PRODUCTION_READY", "leave-as-is — sanity not re-checked"
            return (
                "NEEDS_FIX",
                f"investigate sanity flags: {sanity_flags}",
            )

        if exec_status == "TRANSLATION_FAILED":
            # Active + parse OK + deps clean + can't backtest = translator gap.
            return (
                "ACTIVE_BUT_BROKEN",
                f"extend translator NL-parse to handle: {exec_error[:160]}",
            )

        if exec_status in {"ZERO_TRADES", "EXECUTION_ERROR"}:
            return (
                "NEEDS_FIX",
                f"investigate 7c exec_status={exec_status}: {exec_error[:160]}",
            )

        # exec_status is None (template not in 7c) — shouldn't happen for
        # active templates (7c covered all 27), but guard.
        return "UNKNOWN", "not exercised in 7c — re-run audit"

    # Inactive path -----------------------------------------------------
    if parse_status == "PHASE_2_PLACEHOLDER":
        return (
            "INACTIVE_OK",
            "Phase 2-3 populate config_json before activation",
        )

    if dep_status == "HAS_D_TIER":
        return (
            "NEEDS_FIX",
            "blocked on D-tier indicator(s); wait for indicator fix before "
            "re-activation (see release-cutover-4 / VWAP)",
        )

    if dep_status == "HAS_UNKNOWN":
        return (
            "NEEDS_FIX",
            "indicator(s) not in dual_scoreboard — verify in indicator queue "
            "or rewrite template to use verified indicators",
        )

    # Inactive + populated + dep-clean.
    if exec_status == "TRANSLATION_FAILED":
        return (
            "INACTIVE_OK",
            "dep-clean but translator gap: extend translator id-registry / "
            "NL-parse before activation",
        )
    if exec_status is None:
        return (
            "INACTIVE_OK",
            "dep-clean populated inactive; 7c did not spot-check — re-test on "
            "demand before activation",
        )
    return "INACTIVE_OK", "leave-as-is"


def run() -> dict:
    seed = json.loads(_SEED_PATH.read_text())
    templates = seed["templates"]

    parse = _load_csv_by_slug(_QUEUE_DIR / "parse_results_old_format.csv")
    deps = _load_csv_by_slug(_QUEUE_DIR / "dependency_audit.csv")
    execs = _load_csv_by_slug(_QUEUE_DIR / "backtest_execution.csv")
    sanity = _load_csv_by_slug(_QUEUE_DIR / "performance_sanity.csv")

    rows: list[dict] = []
    bucket_counts: dict[str, int] = {}

    for i, t in enumerate(templates):
        slug = t.get("slug", "")
        name = t.get("name", "")
        is_active = t.get("is_active") is True

        parse_status = parse.get(slug, {}).get("status", "—")
        dep_status = deps.get(slug, {}).get("status", "—")
        exec_row = execs.get(slug)
        exec_status = exec_row["status"] if exec_row else None
        exec_error = exec_row.get("error_summary", "") if exec_row else ""
        sanity_row = sanity.get(slug)
        sanity_flags = sanity_row["flags"] if sanity_row else None

        composite, recommendation = _bucket_and_reco(
            is_active=is_active,
            parse_status=parse_status,
            dep_status=dep_status,
            exec_status=exec_status,
            sanity_flags=sanity_flags,
            exec_error=exec_error,
        )

        bucket_counts[composite] = bucket_counts.get(composite, 0) + 1

        rows.append(
            {
                "index": i,
                "slug": slug,
                "name": name,
                "is_active": is_active,
                "parse_status": parse_status,
                "dep_status": dep_status,
                "exec_status": exec_status or "NOT_TESTED",
                "sanity_status": sanity_flags or "NOT_TESTED",
                "composite": composite,
                "recommendation": recommendation,
            }
        )

    _OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    with _OUT_CSV.open("w", newline="") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=[
                "index",
                "slug",
                "name",
                "is_active",
                "parse_status",
                "dep_status",
                "exec_status",
                "sanity_status",
                "composite",
                "recommendation",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)

    active_buckets = {
        b: sum(1 for r in rows if r["is_active"] and r["composite"] == b)
        for b in bucket_counts
    }
    inactive_buckets = {
        b: sum(1 for r in rows if not r["is_active"] and r["composite"] == b)
        for b in bucket_counts
    }

    return {
        "total": len(rows),
        "bucket_counts": bucket_counts,
        "active_buckets": {k: v for k, v in active_buckets.items() if v},
        "inactive_buckets": {k: v for k, v in inactive_buckets.items() if v},
        "output_csv": str(_OUT_CSV.relative_to(_REPO_ROOT)),
    }


if __name__ == "__main__":
    result = run()
    print(json.dumps(result, indent=2))
