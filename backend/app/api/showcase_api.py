"""Read-only ``/api/showcase`` API — serves the showcase NET artifact.

Single source of truth = ``backend/scripts/showcase_metrics.py`` output
(``showcase_backtest.json``). This router NEVER recomputes metrics and NEVER
writes. It imports NO executor / broker / webhook / kill-switch / trading
module and has NO write path of any kind. The only DB access is a read-only
``SELECT count(*)`` for the honest live-record endpoint (raw text(), never the
sacred Strategy model).

Endpoints (all GET, all read-only):
  * ``GET /api/showcase``           — list 3 strategies + NET headline metrics.
  * ``GET /api/showcase/{key}``     — full NET detail (aggregate + by_year +
    by_month + by_direction {all,long,short}) + caveats + cost-model meta.
  * ``GET /api/showcase/{key}/live``— honest reconciled-real-trade count; never
    fabricates live P&L.
"""
from __future__ import annotations

import json
import os
from typing import Any

from fastapi import APIRouter, Depends, HTTPException

router = APIRouter(prefix="/api/showcase", tags=["showcase"])

_JSON_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..", "scripts", "showcase_backtest.json"
)

# key -> live strategy UUID prefix. None = no live deployment (paper). Public ids.
_LIVE_STRATEGY: dict[str, str | None] = {
    "bse": "89423ecc",
    "cdsl": "0252e82c",
    "angelone": None,
}

_HEADLINE_KEYS = (
    "win_rate_pct", "avg_pct_per_trade", "profit_factor", "max_drawdown_pct", "trades",
)


# ───────────────────────── pure loaders (no DB) ────────────────────────────
def _load_doc() -> dict[str, Any]:
    with open(_JSON_PATH) as f:
        return json.load(f)


def _find(doc: dict[str, Any], key: str) -> dict[str, Any]:
    for s in doc.get("strategies", []):
        if s["key"] == key:
            return s
    raise KeyError(key)


def _net_aggregate_all(s: dict[str, Any]) -> dict[str, Any]:
    return s["backtest"]["net"]["aggregate"]["all"]


def build_live_record(track_type: str, reconciled_count: int) -> dict[str, Any]:
    """Honest live record. NEVER fabricates P&L — only an integer count + note.

    PAPER (no live deployment) is reported as such; otherwise we report the
    reconciled-real-trade count, and the 0-case as 'tracking_active'.
    """
    if track_type == "PAPER":
        return {
            "status": "paper_no_live",
            "reconciled_trades": 0,
            "note": "Paper / backtest-only — not deployed live; no real-money record exists.",
        }
    if reconciled_count <= 0:
        return {
            "status": "tracking_active",
            "reconciled_trades": 0,
            "note": "Live tracking active — no trades reconciled/published yet",
        }
    return {
        "status": "tracking_active",
        "reconciled_trades": reconciled_count,
        "note": (
            f"{reconciled_count} live trade(s) reconciled — verified per-trade results "
            "are pending publication; no P&L is shown until reviewed."
        ),
    }


# ─────────────── read-only DB access (SELECT only; raw text()) ──────────────
async def _readonly_session():
    # lazy import so this module stays import-light and pulls no DB stack at import
    from app.db.session import get_session
    async for s in get_session():
        yield s


async def _count_reconciled_real_trades(session, uuid_prefix: str) -> int:
    """READ-ONLY count of reconciled (final_pnl populated) positions for the
    LIVE (is_paper=false) strategy. Raw SELECT — never the Strategy model."""
    from sqlalchemy import text
    row = (await session.execute(
        text(
            "SELECT count(*) FROM strategy_positions p "
            "JOIN strategies s ON p.strategy_id = s.id "
            "WHERE s.id::text LIKE :p AND s.is_paper = false "
            "AND p.final_pnl IS NOT NULL"
        ),
        {"p": f"{uuid_prefix}%"},
    )).scalar_one()
    return int(row or 0)


# ───────────────────────────────── endpoints ───────────────────────────────
@router.get("")
async def list_showcase() -> dict[str, Any]:
    try:
        doc = _load_doc()
    except FileNotFoundError:
        raise HTTPException(status_code=503, detail="showcase artifact not built")
    out = []
    for s in doc["strategies"]:
        agg = _net_aggregate_all(s)
        out.append({
            "key": s["key"],
            "instrument": s["instrument"],
            "name": s["display_name"],
            "live_status": s["live_status"],
            "basis": "net",
            "disclaimer": s["backtest"]["disclaimer"],
            "headline_net": {k: agg.get(k) for k in _HEADLINE_KEYS},
        })
    return {"strategies": out, "meta": _public_meta(doc)}


@router.get("/{key}")
async def showcase_detail(key: str) -> dict[str, Any]:
    try:
        doc = _load_doc()
        s = _find(doc, key)
    except FileNotFoundError:
        raise HTTPException(status_code=503, detail="showcase artifact not built")
    except KeyError:
        raise HTTPException(status_code=404, detail=f"unknown strategy key: {key}")
    bt = s["backtest"]
    return {
        "key": s["key"],
        "instrument": s["instrument"],
        "name": s["display_name"],
        "live_status": s["live_status"],
        "backtest": {
            "track_type": bt["track_type"],
            "label": bt["label"],
            "disclaimer": bt["disclaimer"],
            "strategy_version": bt["strategy_version"],
            "in_sample_range": bt["in_sample_range"],
            "basis": "net",
            # NET block only: aggregate + by_year + by_month, each {all, long, short};
            # long/short slices already carry slice_of_full_system + caveat.
            "aggregate": bt["net"]["aggregate"],
            "by_year": bt["net"]["by_year"],
            "by_month": bt["net"]["by_month"],
        },
        "cost_delta": bt.get("cost_delta"),
        "meta": _public_meta(doc),
    }


@router.get("/{key}/live")
async def showcase_live(key: str, session=Depends(_readonly_session)) -> dict[str, Any]:
    if key not in _LIVE_STRATEGY:
        raise HTTPException(status_code=404, detail=f"unknown strategy key: {key}")
    try:
        s = _find(_load_doc(), key)
        track_type = s["live_status"]["track_type"]
    except (FileNotFoundError, KeyError):
        track_type = "PAPER" if _LIVE_STRATEGY[key] is None else "LIVE_REAL"
    prefix = _LIVE_STRATEGY[key]
    reconciled = 0
    if prefix is not None:
        reconciled = await _count_reconciled_real_trades(session, prefix)
    return {"key": key, **build_live_record(track_type, reconciled)}


def _public_meta(doc: dict[str, Any]) -> dict[str, Any]:
    """Global honesty meta surfaced to the client (caveats + cost-model)."""
    m = doc.get("meta", {})
    return {
        "strategy_version": m.get("strategy_version"),
        "basis": "net",
        "caveats": m.get("caveats", []),
        "slice_caveat": m.get("slice_caveat"),
        "slippage_excluded": True,
        "cost_model": m.get("cost_model", {}),
    }
