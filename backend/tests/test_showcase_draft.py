"""Tests for the DRAFT showcase read logic (app/api/showcase_draft.py).

Covers the HONEST summarisation: paper has no live deployment; a thin live record
(positions present but final_pnl mostly NULL because the reconciler is log-only)
reports counts honestly and WITHHOLDS metrics — never fabricates. Also checks the
static backtest payload shape + that no compounded/INR artifacts leak.

These exercise the pure read logic only — they never touch a live DB.
"""
from __future__ import annotations

import json

import pytest

from app.api import showcase_draft as sd

LIVE = ("LIVE_REAL", "Live (real money)", "disc")
FWD = ("FORWARD_TEST", "Forward test", "disc")
PAPER = ("PAPER", "Paper", "disc")


def test_paper_has_no_live_deployment():
    rec = sd.build_live_record("angelone", PAPER, None, [])
    assert rec["track_type"] == "PAPER"
    assert rec["has_live_deployment"] is False
    assert rec["metrics"] is None
    assert rec["confirmed_reconciled_count"] == 0
    assert "no live real-money deployment" in rec["caveat"].lower()


def test_empty_live_record_is_honest():
    rec = sd.build_live_record("bse", LIVE, {"is_active": True, "is_paper": False}, [])
    assert rec["has_live_deployment"] is True
    assert rec["data_completeness"] == "empty"
    assert rec["positions_recorded"] == 0
    assert rec["metrics"] is None


def test_thin_live_record_withholds_metrics_and_counts_honestly():
    # BSE-like: 7 closed positions, final_pnl all NULL (reconciler log-only)
    positions = [{"status": "closed", "final_pnl": None} for _ in range(7)]
    rec = sd.build_live_record("bse", LIVE, {"is_active": True, "is_paper": False}, positions)
    assert rec["positions_recorded"] == 7
    assert rec["closed_positions"] == 7
    assert rec["open_positions"] == 0
    assert rec["confirmed_reconciled_count"] == 0          # nothing reconciled
    assert rec["data_completeness"] == "thin"
    assert rec["metrics"] is None                          # NOT fabricated
    assert "withheld" in rec["caveat"].lower()
    assert "0 with reconciled" in rec["caveat"]


def test_some_reconciled_but_below_threshold_still_withholds():
    positions = [{"status": "closed", "final_pnl": (1.0 if i < 5 else None)} for i in range(20)]
    rec = sd.build_live_record("cdsl", FWD, {"is_active": True, "is_paper": False}, positions,
                               sufficient_reconciled=30)
    assert rec["confirmed_reconciled_count"] == 5
    assert rec["data_completeness"] == "thin"
    assert rec["metrics"] is None


def test_sufficient_count_still_does_not_fabricate_metrics():
    # Even with enough reconciled rows, we do NOT invent per-trade % tonight.
    positions = [{"status": "closed", "final_pnl": 1.0} for _ in range(40)]
    rec = sd.build_live_record("bse", LIVE, {"is_active": True, "is_paper": False}, positions,
                               sufficient_reconciled=30)
    assert rec["confirmed_reconciled_count"] == 40
    assert rec["data_completeness"] == "sufficient"
    assert rec["metrics"] is None          # honest: live metric source is an open question


def test_open_vs_closed_split():
    positions = [{"status": "closed", "final_pnl": None},
                 {"status": "open", "final_pnl": None},
                 {"status": "closed", "final_pnl": None}]
    rec = sd.build_live_record("bse", LIVE, {"is_active": True, "is_paper": False}, positions)
    assert rec["closed_positions"] == 2
    assert rec["open_positions"] == 1


def test_backtest_payload_shape_and_labels():
    doc = sd.load_backtest_doc()
    p = sd.build_backtest_payload(doc, "bse")
    assert p["instrument"] == "BSE"
    assert p["backtest"]["track_type"] == "BACKTEST_IN_SAMPLE"
    assert p["live_status_label"]["track_type"] == "LIVE_REAL"
    m = p["backtest"]["metrics"]
    assert m["closed_trades"] == 1149
    assert 0 < m["win_rate_pct"] <= 100
    # non-compounded series present, labelled, not a compounded total
    cs = p["backtest"]["cumulative_series"]
    assert "non_compounded" in cs["basis"]
    assert isinstance(cs["cum_net_pct"], list) and len(cs["cum_net_pct"]) == 1149


def test_backtest_payload_has_no_inr_or_compounded_artifacts():
    doc = sd.load_backtest_doc()
    p = sd.build_backtest_payload(doc, "cdsl")
    blob = json.dumps(p)
    # no rupee symbol, no per-trade INR pnl key, no compounded-total key
    assert "₹" not in blob
    for k in ("pnl_inr", "qty", "size_value", "compounded_total", "cumulative_pct\":"):
        assert k not in blob.lower().replace(" ", "")


def test_unknown_key_raises():
    with pytest.raises(KeyError):
        sd.build_backtest_payload(sd.load_backtest_doc(), "nifty")


def test_state_map_matches_spec():
    assert sd.LIVE_STATE["bse"][1][0] == "LIVE_REAL"
    assert sd.LIVE_STATE["cdsl"][1][0] == "FORWARD_TEST"
    assert sd.LIVE_STATE["angelone"][0] is None        # no live deployment
    assert sd.LIVE_STATE["angelone"][1][0] == "PAPER"
