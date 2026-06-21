"""DRAFT — read-only showcase API.  **NOT WIRED. DO NOT ENABLE / DEPLOY.**

This router is deliberately NOT registered in ``app.main`` (main.py includes
routers explicitly by name; this one is omitted on purpose), so importing this
module has zero effect on the running app. It exists for review only.

What it would serve (all GET, all read-only):
  * ``GET /api/showcase/backtest/{key}`` — the static, size-independent backtest
    object from ``backend/scripts/showcase_backtest.json`` (in-sample labelled).
  * ``GET /api/showcase/live/{key}`` — an HONEST live/forward/paper record built
    from a READ-ONLY SELECT on existing tables. The reconciler runs log-only, so
    ``strategy_positions.final_pnl`` is mostly NULL → the record reports
    "N recorded ≈ 0 reconciled" rather than fabricating metrics.

Guardrails honoured: read-only (SELECT only, raw text() — never imports/mutates
the sacred strategy model or execution path), no writes, no migration, no flag
flips. The live-strategy UUIDs are public ids, not secrets.
"""
from __future__ import annotations

import json
import os
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException

router = APIRouter(prefix="/api/showcase", tags=["showcase-DRAFT (not wired)"])

# key -> (live strategy UUID prefix | None, 4-state live label tuple)
#   BSE = live-real, CDSL = forward-test, ANGELONE = paper (no live deployment).
LIVE_STATE: dict[str, tuple[Optional[str], tuple[str, str, str]]] = {
    "bse": ("89423ecc", ("LIVE_REAL", "Live (real money)",
                          "Live real-money results. Past performance is not a guarantee.")),
    "cdsl": ("0252e82c", ("FORWARD_TEST", "Forward test (out-of-sample)",
                          "Forward test — out-of-sample, limited sample, not a track record.")),
    "angelone": (None, ("PAPER", "Paper (simulated)",
                        "Paper / simulated — no real money traded; backtest-only candidate.")),
}

_JSON_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "scripts", "showcase_backtest.json")

# threshold of RECONCILED (NET-P&L-bearing) trips before any live metric is shown
SUFFICIENT_RECONCILED = 30


# ───────────────────────── pure logic (no DB — fully testable) ─────────────

def load_backtest_doc(path: str | None = None) -> dict[str, Any]:
    with open(path or _JSON_PATH) as f:
        return json.load(f)


def build_backtest_payload(doc: dict[str, Any], key: str) -> dict[str, Any]:
    """Return the per-strategy backtest object + its live-status label. Raises
    KeyError if the key is unknown."""
    for s in doc.get("strategies", []):
        if s["key"] == key:
            return {
                "key": s["key"],
                "instrument": s["instrument"],
                "display_name": s["display_name"],
                "backtest": s["backtest"],         # already in-sample labelled
                "live_status_label": s["live_status"],
                "global_caveats": doc.get("meta", {}).get("caveats", []),
            }
    raise KeyError(key)


def build_live_record(
    key: str,
    live_state: tuple[str, str, str],
    strategy_meta: Optional[dict[str, Any]],
    positions: list[dict[str, Any]],
    *,
    sufficient_reconciled: int = SUFFICIENT_RECONCILED,
) -> dict[str, Any]:
    """Build an HONEST live/forward/paper record. Never fabricates metrics.

    ``strategy_meta`` is None when there is no live deployment (paper). Otherwise
    a dict with id/name/is_active/is_paper. ``positions`` is a read-only snapshot
    of dicts with status/final_pnl. Per-trade metrics are WITHHELD (None) until
    there are >= ``sufficient_reconciled`` positions carrying a reconciled
    final_pnl — they are never invented from unreconciled data.
    """
    track_type, label, disclaimer = live_state
    base = {"key": key, "track_type": track_type, "label": label, "disclaimer": disclaimer}

    if strategy_meta is None:
        return {
            **base,
            "has_live_deployment": False,
            "data_completeness": "none",
            "confirmed_reconciled_count": 0,
            "positions_recorded": 0,
            "closed_positions": 0,
            "open_positions": 0,
            "metrics": None,
            "caveat": "No live real-money deployment — paper / backtest-only candidate.",
        }

    closed = sum(1 for p in positions if str(p.get("status", "")).lower().startswith("clos"))
    confirmed = sum(1 for p in positions if p.get("final_pnl") is not None)
    if not positions:
        completeness = "empty"
    elif confirmed < sufficient_reconciled:
        completeness = "thin"
    else:
        completeness = "sufficient"

    # Honest stance: even when position COUNT is sufficient, per-trade NET %
    # requires reconciled final_pnl. The reconciler is log-only, so we do NOT
    # fabricate live metrics here. Left None; see design open-question on source.
    metrics = None

    caveat = (
        f"Live tracking: {len(positions)} position(s) recorded, {confirmed} with reconciled "
        f"NET P&L (reconciler is log-only, so final_pnl is largely NULL). Per-trade metrics "
        f"are WITHHELD until sufficient reconciled data — not fabricated."
    )
    return {
        **base,
        "has_live_deployment": True,
        "strategy_active": bool(strategy_meta.get("is_active")),
        "strategy_is_paper": bool(strategy_meta.get("is_paper")),
        "data_completeness": completeness,
        "confirmed_reconciled_count": confirmed,
        "positions_recorded": len(positions),
        "closed_positions": closed,
        "open_positions": len(positions) - closed,
        "metrics": metrics,
        "caveat": caveat,
    }


# ───────────────────── read-only DB access (raw SELECT; not unit-tested) ───
# Raw text() SELECTs — never import/mutate the sacred Strategy model or touch
# the execution path. SELECT only.

async def _fetch_strategy_meta(session, uuid_prefix: str) -> Optional[dict[str, Any]]:
    from sqlalchemy import text  # local import keeps this module light
    row = (await session.execute(
        text("SELECT id::text AS id, name, is_active, is_paper FROM strategies "
             "WHERE id::text LIKE :p ORDER BY created_at LIMIT 1"),
        {"p": f"{uuid_prefix}%"},
    )).mappings().first()
    return dict(row) if row else None


async def _fetch_positions(session, uuid_prefix: str) -> list[dict[str, Any]]:
    from sqlalchemy import text
    rows = (await session.execute(
        text("SELECT status, final_pnl, opened_at, closed_at FROM strategy_positions "
             "WHERE strategy_id::text LIKE :p ORDER BY opened_at"),
        {"p": f"{uuid_prefix}%"},
    )).mappings().all()
    return [dict(r) for r in rows]


async def _readonly_session():
    # lazy import so importing this DRAFT module never pulls in the DB stack
    from app.db.session import get_session
    async for s in get_session():
        yield s


# ───────────────────────────────── endpoints (DRAFT) ──────────────────────

@router.get("/backtest/{key}")
async def get_backtest(key: str) -> dict[str, Any]:
    try:
        return build_backtest_payload(load_backtest_doc(), key)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"unknown strategy key: {key}")
    except FileNotFoundError:
        raise HTTPException(status_code=503, detail="showcase backtest artifact not built")


@router.get("/live/{key}")
async def get_live(key: str, session=Depends(_readonly_session)) -> dict[str, Any]:
    if key not in LIVE_STATE:
        raise HTTPException(status_code=404, detail=f"unknown strategy key: {key}")
    prefix, live_state = LIVE_STATE[key]
    if prefix is None:  # paper, no live deployment
        return build_live_record(key, live_state, None, [])
    meta = await _fetch_strategy_meta(session, prefix)
    positions = await _fetch_positions(session, prefix) if meta else []
    return build_live_record(key, live_state, meta, positions)
