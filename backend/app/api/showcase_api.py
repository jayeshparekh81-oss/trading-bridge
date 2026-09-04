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
    fabricates live P&L. Also carries ``listing_id``: the published marketplace
    listing for this strategy, so the public card can offer Subscribe without
    the frontend hardcoding an id. ``None`` when no published listing exists.

⚠️ THE MASK. s1/s2/s3 exist to hide WHICH strategy is which on a public page.
Nothing here may name the instrument. ``_LIVE_STRATEGY``'s uuid prefixes are
server-only and are never returned. ``listing_id`` IS returned and therefore
makes "s1 ↔ that listing" public — which is safe only while the listing's own
copy is masked too (title "Strategy S1", generic description, no instrument
tags). The mask holds on both surfaces or it holds on neither.
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

# Public code -> live strategy UUID prefix. The prefix is used ONLY for the
# internal reconciled-trades SQL join and is NEVER returned to the client; the
# outward-facing key is the anonymised code (s1/s2/s3). None = no live
# deployment (paper). Do not surface the real instrument identity here.
_LIVE_STRATEGY: dict[str, str | None] = {
    "s1": "89423ecc",
    "s2": "0252e82c",
    "s3": None,
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


#: Founder's wording (2026-09-04) for the live record while the Python-live
#: period is unverified. No count, no P&L, no zero.
VERIFICATION_PERIOD_NOTE = (
    "Live execution is in a verification period — live results are not yet published."
)


def build_live_record(
    track_type: str,
    reconciled_count: int = 0,
    human_interfered_count: int = 0,
    *,
    published: bool = False,
) -> dict[str, Any]:
    """Honest live record. NEVER fabricates P&L — only integer counts + a note.

    PAPER (no live deployment) is reported as such. A LIVE strategy reports the
    verification-period state (``published=False``, the founder's gate
    ``showcase_live_record_published``): a plain sentence, no count, no P&L,
    no zero — nothing about live execution is published until the founder
    declares the live period 100%. Only with ``published=True`` do the
    reconciled-real-trade count and the human-interfered count
    (cutover-26 — closed real trades the founder's exit rule refused to price)
    appear, the 0-case as 'tracking_active'.
    """
    if track_type == "PAPER":
        return {
            "status": "paper_no_live",
            "reconciled_trades": 0,
            "human_interfered_trades": 0,
            "note": "Paper / backtest-only — not deployed live; no real-money record exists.",
        }
    if not published:
        return {"status": "verification_period", "note": VERIFICATION_PERIOD_NOTE}
    interfered_note = (
        f" {human_interfered_count} closed trade(s) are human-interfered — not attributable: "
        "excluded by rule, not zeroed."
        if human_interfered_count > 0
        else ""
    )
    if reconciled_count <= 0:
        return {
            "status": "tracking_active",
            "reconciled_trades": 0,
            "human_interfered_trades": max(human_interfered_count, 0),
            "note": "Live tracking active — no trades reconciled/published yet" + interfered_note,
        }
    return {
        "status": "tracking_active",
        "reconciled_trades": reconciled_count,
        "human_interfered_trades": max(human_interfered_count, 0),
        "note": (
            f"{reconciled_count} live trade(s) reconciled — verified per-trade results "
            "are pending publication; no P&L is shown until reviewed." + interfered_note
        ),
    }


# ─────────────── read-only DB access (SELECT only; raw text()) ──────────────
async def _readonly_session():
    # lazy import so this module stays import-light and pulls no DB stack at import
    from app.db.session import get_session
    async for s in get_session():
        yield s


async def _count_reconciled_real_trades(session, uuid_prefix: str) -> int:
    """READ-ONLY count of genuinely RECONCILED REAL trades for the LIVE
    (is_paper=false) strategy — the public live-record number.

    A position is counted ONLY when ALL of these hold:
      * the strategy is live (``s.is_paper = false``), AND
      * the position has a reconciled P&L (``p.final_pnl IS NOT NULL``) carrying
        a PRICED attribution tag (``bot_only`` / ``account_flat`` — the founder's
        exit rule, cutover-26; the same predicate the ledger snapshot uses), AND
      * the position has a REAL broker fill — an execution on its entry signal
        whose ``broker_order_id`` is a real id, NOT a paper simulation.

    The real-vs-paper marker is the ``broker_order_id``: paper (simulated) fills
    are tagged ``'PAPER-...'`` (and carry ``broker_response.raw.paper_mode = true``
    / ``"paper-mode simulated fill"``), whereas real broker fills carry the
    broker's own id. Excluding ``LIKE 'PAPER-%'`` is the fix for the credibility
    bug where a STALE PAPER position (``PAPER-…`` order id, manually-closed
    ``final_pnl=0``) was counted as a "live reconciled" trade purely because the
    strategy's CURRENT ``is_paper`` flag is now false. A real-but-not-yet-
    reconciled position (real id, ``final_pnl IS NULL``) is correctly NOT counted
    here — the honest 0-state shows "tracking active, none reconciled yet".

    Raw SELECT — never the Strategy model; reads only, mutates nothing.
    ``CAST(... AS TEXT)`` is the portable equivalent of ``::text`` (identical on
    Postgres; also runs on the sqlite test engine)."""
    from sqlalchemy import text
    row = (await session.execute(
        text(
            "SELECT count(*) FROM strategy_positions p "
            "JOIN strategies s ON p.strategy_id = s.id "
            "WHERE CAST(s.id AS TEXT) LIKE :p "
            "AND s.is_paper = false "
            "AND p.final_pnl IS NOT NULL "
            # Same predicate as the ledger (cutover-26): a value counts ONLY with a
            # priced attribution tag — never a pre-rule value, never a
            # human-interfered row that still carries a stale number.
            "AND p.pnl_attribution IN ('bot_only', 'account_flat') "
            "AND EXISTS ("
            "  SELECT 1 FROM strategy_executions e "
            "  WHERE e.signal_id = p.signal_id "
            "    AND e.broker_order_id IS NOT NULL "
            "    AND e.broker_order_id NOT LIKE 'PAPER-%'"
            ")"
        ),
        {"p": f"{uuid_prefix}%"},
    )).scalar_one()
    return int(row or 0)


async def _count_human_interfered_real_trades(session: Any, uuid_prefix: str) -> int:
    """READ-ONLY count of closed REAL positions the founder's exit rule
    (2026-09-04) tagged ``human_interfered``: NULL ``final_pnl`` by rule — the
    founder's manual fills on the same contract made the bot's exit a guess.

    Same real-fill predicate as :func:`_count_reconciled_real_trades`, so a
    paper/phantom row can never be counted as an interfered real trade. Raw
    SELECT, reads only."""
    from sqlalchemy import text
    row = (await session.execute(
        text(
            "SELECT count(*) FROM strategy_positions p "
            "JOIN strategies s ON p.strategy_id = s.id "
            "WHERE CAST(s.id AS TEXT) LIKE :p "
            "AND s.is_paper = false "
            "AND p.status = 'closed' "
            "AND p.pnl_attribution = 'human_interfered' "
            "AND EXISTS ("
            "  SELECT 1 FROM strategy_executions e "
            "  WHERE e.signal_id = p.signal_id "
            "    AND e.broker_order_id IS NOT NULL "
            "    AND e.broker_order_id NOT LIKE 'PAPER-%'"
            ")"
        ),
        {"p": f"{uuid_prefix}%"},
    )).scalar_one()
    return int(row or 0)


async def _published_listing_id(session, uuid_prefix: str) -> str | None:
    """READ-ONLY lookup of the PUBLISHED marketplace listing for this strategy.

    Exists so the public showcase card can offer a Subscribe path without the
    frontend hardcoding a listing id. Returns ``None`` when no published
    listing exists — the card then shows no Subscribe control at all, never a
    dead or disabled one.

    ⚠️ MASKING. Returning this id makes the pairing "s1 ↔ this listing" PUBLIC:
    it lands in the HTML of a page anyone can read. That is safe ONLY while the
    listing's own copy is masked (title "Strategy S1", generic description, no
    instrument tags). If a listing for this strategy is ever titled with the
    real instrument, this endpoint is the thing that breaks the mask — the id
    itself is opaque, the listing's copy is not. See the note in
    ``build_live_record``'s module docstring and the deploy checklist.

    Ordered by ``published_at`` so a duplicate listing (nothing in the schema
    forbids two) resolves deterministically to the OLDEST published one rather
    than flapping between rows.

    Raw SELECT — reads only, mutates nothing; imports no executor / broker /
    webhook / kill-switch module, consistent with this router's contract.
    """
    from sqlalchemy import text
    row = (await session.execute(
        text(
            "SELECT CAST(l.id AS TEXT) FROM marketplace_listings l "
            "WHERE CAST(l.strategy_id AS TEXT) LIKE :p "
            "AND l.status = 'published' "
            "ORDER BY l.published_at ASC NULLS LAST "
            "LIMIT 1"
        ),
        {"p": f"{uuid_prefix}%"},
    )).scalar_one_or_none()
    return str(row) if row else None


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
            # non-compounded NET chart series {all,long,short} (M3.5) — passthrough
            "series": bt["net"].get("series"),
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
    # Founder gate (2026-09-04): while the live record is unpublished, no
    # count query runs at all — the response carries the verification-period
    # sentence and nothing numeric. Lazy import keeps the router import-light.
    from app.core.config import get_settings

    published = bool(get_settings().showcase_live_record_published)
    reconciled = 0
    interfered = 0
    listing_id: str | None = None
    if prefix is not None:
        if published:
            reconciled = await _count_reconciled_real_trades(session, prefix)
            interfered = await _count_human_interfered_real_trades(session, prefix)
        # ADDITIVE + optional. Carried on THIS endpoint because it is the only
        # one that already holds a session — ``list_showcase`` and
        # ``showcase_detail`` stay pure loaders with no DB access at all, which
        # is the property that makes this router cheap and safe.
        listing_id = await _published_listing_id(session, prefix)
    return {
        "key": key,
        **build_live_record(track_type, reconciled, interfered, published=published),
        "listing_id": listing_id,
    }


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
