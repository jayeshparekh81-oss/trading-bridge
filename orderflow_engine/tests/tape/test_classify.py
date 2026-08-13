"""Tests for the Lee-Ready aggressor classifier (Module R3)."""

from __future__ import annotations

from tape.classify import BUY, SELL, classify_trade


def test_quote_rule_lift_offer_is_buy():
    assert classify_trade(101.0, bid=99.0, ask=101.0, prev_price=100.0, prev_side=SELL) == BUY


def test_quote_rule_hit_bid_is_sell():
    assert classify_trade(99.0, bid=99.0, ask=101.0, prev_price=100.0, prev_side=BUY) == SELL


def test_inside_spread_above_mid_is_buy():
    assert classify_trade(100.6, bid=100.0, ask=101.0, prev_price=100.0, prev_side=SELL) == BUY


def test_inside_spread_below_mid_is_sell():
    assert classify_trade(100.4, bid=100.0, ask=101.0, prev_price=100.6, prev_side=BUY) == SELL


def test_at_mid_falls_back_to_tick_rule():
    # at mid (100.5): uptick vs prev 100.0 -> BUY
    assert classify_trade(100.5, bid=100.0, ask=101.0, prev_price=100.0, prev_side=SELL) == BUY
    # at mid: downtick vs prev 101.0 -> SELL
    assert classify_trade(100.5, bid=100.0, ask=101.0, prev_price=101.0, prev_side=BUY) == SELL
    # at mid, zero tick -> carry previous side
    assert classify_trade(100.5, bid=100.0, ask=101.0, prev_price=100.5, prev_side=SELL) == SELL


def test_no_quote_uses_tick_rule():
    assert classify_trade(100.0, bid=None, ask=None, prev_price=99.0, prev_side=SELL) == BUY
    assert classify_trade(100.0, bid=None, ask=None, prev_price=101.0, prev_side=BUY) == SELL


def test_method_tick_rule_ignores_quote():
    # even though price >= ask (would be BUY on quote rule), tick_rule uses prev
    assert classify_trade(101.0, bid=99.0, ask=101.0, prev_price=102.0, prev_side=BUY,
                          method="tick_rule") == SELL
