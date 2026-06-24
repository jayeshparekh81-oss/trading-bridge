"""Tests for the read-only /api/showcase router (app/api/showcase_api.py).

Covers: endpoint shapes, NET basis served (not raw), per-direction slice caveats,
the honest empty live state, that the live endpoint NEVER fabricates P&L, and a
static assertion that the router has NO write / DB-mutation / trading-module path.
"""
from __future__ import annotations

import asyncio
import json

import pytest
from fastapi import HTTPException

from app.api import showcase_api as api


def _doc():
    return api._load_doc()


# ── fake read-only session (returns a fixed reconciled count) ───────────────
class _FakeResult:
    def __init__(self, n):
        self._n = n

    def scalar_one(self):
        return self._n


class _FakeSession:
    def __init__(self, n=0):
        self._n = n

    async def execute(self, *a, **k):
        return _FakeResult(self._n)


# ── GET /api/showcase (list) ────────────────────────────────────────────────
def test_list_three_strategies_with_net_headline():
    res = asyncio.run(api.list_showcase())
    strats = {s["key"]: s for s in res["strategies"]}
    assert set(strats) == {"bse", "cdsl", "angelone"}
    assert strats["bse"]["live_status"]["track_type"] == "LIVE_REAL"
    assert strats["cdsl"]["live_status"]["track_type"] == "LIVE_NO_TRADES"
    assert strats["angelone"]["live_status"]["track_type"] == "PAPER"
    for s in strats.values():
        assert s["basis"] == "net"
        assert set(s["headline_net"]) == {
            "win_rate_pct", "avg_pct_per_trade", "profit_factor", "max_drawdown_pct", "trades",
        }
    assert res["meta"]["slippage_excluded"] is True


def test_list_serves_net_not_raw():
    res = asyncio.run(api.list_showcase())
    bse = next(s for s in res["strategies"] if s["key"] == "bse")
    doc_bse = next(s for s in _doc()["strategies"] if s["key"] == "bse")
    net_avg = doc_bse["backtest"]["net"]["aggregate"]["all"]["avg_pct_per_trade"]
    raw_avg = doc_bse["backtest"]["raw"]["aggregate"]["all"]["avg_pct_per_trade"]
    assert bse["headline_net"]["avg_pct_per_trade"] == net_avg
    assert bse["headline_net"]["avg_pct_per_trade"] != raw_avg  # NET, not RAW


# ── GET /api/showcase/{key} (detail) ────────────────────────────────────────
def test_detail_net_structure_and_slice_caveats():
    d = asyncio.run(api.showcase_detail("bse"))
    bt = d["backtest"]
    assert bt["basis"] == "net"
    assert set(bt["aggregate"]) == {"all", "long", "short"}
    # long/short slices carry the slice flag + caveat
    assert bt["aggregate"]["long"]["slice_of_full_system"] is True
    assert "caveat" in bt["aggregate"]["long"]
    assert "slice_of_full_system" not in bt["aggregate"]["all"]
    assert bt["by_year"] and bt["by_month"]
    # served detail is NET
    doc_bse = next(s for s in _doc()["strategies"] if s["key"] == "bse")
    assert bt["aggregate"]["all"] == doc_bse["backtest"]["net"]["aggregate"]["all"]
    # global meta: caveats + cost model + slippage
    assert d["meta"]["slippage_excluded"] is True
    assert d["meta"]["cost_model"]["rates_asof"]
    assert d["meta"]["cost_model"]["estimated"] is True


def test_detail_unknown_key_404():
    with pytest.raises(HTTPException) as exc:
        asyncio.run(api.showcase_detail("nifty"))
    assert exc.value.status_code == 404


# ── GET /api/showcase/{key}/live (honest, never fabricated) ─────────────────
def test_live_zero_reconciled_is_tracking_active():
    res = asyncio.run(api.showcase_live("bse", session=_FakeSession(0)))
    assert res["status"] == "tracking_active"
    assert res["reconciled_trades"] == 0
    assert "no trades reconciled" in res["note"].lower()


def test_live_paper_strategy_reports_no_live():
    res = asyncio.run(api.showcase_live("angelone", session=_FakeSession(0)))
    assert res["status"] == "paper_no_live"
    assert res["reconciled_trades"] == 0


def test_live_never_fabricates_pnl_even_with_reconciled_count():
    res = asyncio.run(api.showcase_live("bse", session=_FakeSession(7)))
    assert res["reconciled_trades"] == 7
    blob = json.dumps(res).lower()
    assert "pnl" not in blob and "₹" not in blob and "profit" not in blob


def test_build_live_record_pure_never_fabricates():
    for tt, n in [("PAPER", 0), ("LIVE_REAL", 0), ("LIVE_NO_TRADES", 0), ("LIVE_REAL", 12)]:
        rec = api.build_live_record(tt, n)
        blob = json.dumps(rec).lower()
        assert "pnl" not in blob and "profit" not in blob
        assert isinstance(rec["reconciled_trades"], int)


# ── READ-ONLY guarantee: no write / DB-mutation / trading-module path ───────
def test_router_has_no_write_or_trading_path():
    with open(api.__file__) as f:
        src = f.read()
    forbidden = [
        "INSERT", "UPDATE ", "DELETE ", ".commit(", "session.add", ".flush(",
        "strategy_executor", "direct_exit", "strategy_webhook", "kill_switch",
        "order_router", "place_order", "place_strategy_orders", "app.brokers",
    ]
    hits = [tok for tok in forbidden if tok in src]
    assert hits == [], f"router contains forbidden write/trading tokens: {hits}"


def test_router_prefix_is_showcase():
    assert api.router.prefix == "/api/showcase"


# ── M3.5: detail passes through the non-compounded NET chart series ─────────
def test_detail_includes_noncompounded_series():
    d = asyncio.run(api.showcase_detail("bse"))
    ser = d["backtest"]["series"]
    assert set(ser) == {"all", "long", "short"}
    blk = ser["all"]
    assert blk["basis"] == "non_compounded_fixed_size_net_pct"
    assert set(blk) == {"basis", "equity_curve_noncompounded", "drawdown_curve", "monthly_returns_grid"}
    eq, dd = blk["equity_curve_noncompounded"], blk["drawdown_curve"]
    assert len(eq) == d["backtest"]["aggregate"]["all"]["trades"]   # one point per trade
    assert all(p["v"] <= 0 for p in dd)                              # underwater
    # drawdown min equals the served NET aggregate max-drawdown
    assert abs(min(p["v"] for p in dd) - d["backtest"]["aggregate"]["all"]["max_drawdown_pct"]) <= 0.01
