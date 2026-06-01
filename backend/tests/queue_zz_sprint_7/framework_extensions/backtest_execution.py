"""Queue ZZ Sprint 7c — observation-only backtest execution audit.

For each target template, translate its seed-format ``config_json`` to
``StrategyJSON`` via the existing ``translate_template`` shim (the same
path the user-clone flow uses) and feed the result to ``run_backtest``
against the deterministic 720-bar synthetic candle series used by the
HTTP endpoint when the caller doesn't supply candles.

Per founder direction (Queue ZZ Sprint 7 prompt):
    - All 27 ACTIVE templates run end-to-end.
    - 10 inactive (with populated config_json) spot-check.
    - PHASE_2_PLACEHOLDER templates are not invoked.
    - No template math/logic edits. Capture only.

Buckets:
    FIRES_CLEAN          — trades > 0 and warnings == 0
    FIRES_WITH_WARNINGS  — trades > 0 and warnings > 0
    ZERO_TRADES          — translation + backtest succeeded but total_trades == 0
    EXECUTION_ERROR      — run_backtest raised (or precompute_indicators failed)
    TRANSLATION_FAILED   — translate_template raised TranslationError

Output: backend/tests/queue_zz_sprint_7/backtest_execution.csv
"""

from __future__ import annotations

import csv
import json
import os
import sys
import time
import traceback
from pathlib import Path

_BACKEND_ROOT = Path(__file__).resolve().parents[3]
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

# Test-only env required by app.core.config / security on import.
os.environ.setdefault("ENCRYPTION_KEY", "TZNZeqzMl_RWXVukYW1Cl9JLn2hHIxOmQYx3FW6S_uA=")
os.environ.setdefault("JWT_SECRET", "x" * 32)
os.environ.setdefault("ENVIRONMENT", "test")

from app.strategy_engine.api.backtest import _synthetic_candles  # noqa: E402
from app.strategy_engine.backtest.runner import (  # noqa: E402
    BacktestInput,
    BacktestResult,
    run_backtest,
)
from app.strategy_engine.translator.errors import TranslationError  # noqa: E402
from app.strategy_engine.translator.parser import translate_template  # noqa: E402

_REPO_ROOT = _BACKEND_ROOT.parent
_SEED_PATH = _BACKEND_ROOT / "data" / "strategy_templates_seed.json"
_OUT_CSV = _BACKEND_ROOT / "tests" / "queue_zz_sprint_7" / "backtest_execution.csv"

_SYNTH_BARS = 720


def _bucket(trade_count: int, warning_count: int) -> str:
    if trade_count == 0:
        return "ZERO_TRADES"
    return "FIRES_WITH_WARNINGS" if warning_count > 0 else "FIRES_CLEAN"


def _run_one(template: dict, candles) -> dict:
    """Run translate + backtest for one template. Captures status + metrics."""
    slug = template.get("slug", "")
    name = template.get("name", "")
    is_active = bool(template.get("is_active", False))

    t0 = time.perf_counter()
    try:
        strategy_json = translate_template(template)
    except TranslationError as exc:
        return {
            "slug": slug,
            "name": name,
            "is_active": is_active,
            "status": "TRANSLATION_FAILED",
            "trade_count": "",
            "total_pnl": "",
            "win_rate": "",
            "warning_count": "",
            "runtime_ms": round((time.perf_counter() - t0) * 1000, 2),
            "error_summary": f"{type(exc).__name__}: {exc}".replace("\n", " "),
        }
    except Exception as exc:  # noqa: BLE001 - we want every reason captured
        return {
            "slug": slug,
            "name": name,
            "is_active": is_active,
            "status": "TRANSLATION_FAILED",
            "trade_count": "",
            "total_pnl": "",
            "win_rate": "",
            "warning_count": "",
            "runtime_ms": round((time.perf_counter() - t0) * 1000, 2),
            "error_summary": f"unexpected {type(exc).__name__}: {exc}".replace("\n", " "),
        }

    try:
        payload = BacktestInput(candles=candles, strategy=strategy_json)
        result: BacktestResult = run_backtest(payload)
    except Exception as exc:  # noqa: BLE001
        return {
            "slug": slug,
            "name": name,
            "is_active": is_active,
            "status": "EXECUTION_ERROR",
            "trade_count": "",
            "total_pnl": "",
            "win_rate": "",
            "warning_count": "",
            "runtime_ms": round((time.perf_counter() - t0) * 1000, 2),
            "error_summary": (
                f"{type(exc).__name__}: {exc} | "
                f"tb_tail={traceback.format_exc().splitlines()[-1]}"
            ).replace("\n", " "),
        }

    runtime_ms = round((time.perf_counter() - t0) * 1000, 2)
    warning_count = len(result.warnings or [])
    status = _bucket(result.total_trades, warning_count)
    return {
        "slug": slug,
        "name": name,
        "is_active": is_active,
        "status": status,
        "trade_count": result.total_trades,
        "total_pnl": round(result.total_pnl, 2),
        "win_rate": round(result.win_rate, 4),
        "warning_count": warning_count,
        "runtime_ms": runtime_ms,
        "error_summary": (
            "; ".join(result.warnings[:3]).replace("\n", " ")
            + (f" (+{warning_count - 3} more)" if warning_count > 3 else "")
            if warning_count
            else ""
        ),
    }


def _select_targets(templates: list[dict]) -> tuple[list[int], list[int]]:
    """Return (active_indices, first_10_populated_inactive_indices)."""
    active = [i for i, t in enumerate(templates) if t.get("is_active") is True]
    inactive_pop = [
        i
        for i, t in enumerate(templates)
        if t.get("is_active") is False
        and isinstance(t.get("config_json"), dict)
        and t.get("config_json")
    ]
    return active, inactive_pop[:10]


def run() -> dict:
    with _SEED_PATH.open() as fh:
        seed = json.load(fh)
    templates = seed["templates"]

    active_idx, inactive_idx = _select_targets(templates)
    targets = active_idx + inactive_idx

    candles = _synthetic_candles(_SYNTH_BARS)

    rows: list[dict] = []
    for i in targets:
        t = templates[i]
        out = _run_one(t, candles)
        out["index"] = i
        rows.append(out)

    _OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    with _OUT_CSV.open("w", newline="") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=[
                "index",
                "slug",
                "name",
                "is_active",
                "status",
                "trade_count",
                "total_pnl",
                "win_rate",
                "warning_count",
                "runtime_ms",
                "error_summary",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)

    # Roll-up.
    from collections import Counter

    by_status_active = Counter(r["status"] for r in rows if r["is_active"])
    by_status_inactive = Counter(r["status"] for r in rows if not r["is_active"])

    return {
        "synthetic_bars": _SYNTH_BARS,
        "active_total": len(active_idx),
        "inactive_spot_checked": len(inactive_idx),
        "active_buckets": dict(by_status_active),
        "inactive_buckets": dict(by_status_inactive),
        "active_fires_clean": by_status_active.get("FIRES_CLEAN", 0),
        "active_fires_with_warnings": by_status_active.get("FIRES_WITH_WARNINGS", 0),
        "active_zero_trades": by_status_active.get("ZERO_TRADES", 0),
        "active_execution_errors": by_status_active.get("EXECUTION_ERROR", 0),
        "active_translation_failed": by_status_active.get("TRANSLATION_FAILED", 0),
        "output_csv": str(_OUT_CSV.relative_to(_REPO_ROOT)),
    }


if __name__ == "__main__":
    result = run()
    print(json.dumps(result, indent=2))
