"""Tick aggressor classification (Module R3).

Determines whether a trade was buyer- or seller-initiated. The Dhan FULL packet
carries no explicit aggressor flag, so we use the Lee-Ready algorithm against the
packet's OWN top-of-book quote (bid_price_1 / ask_price_1, contemporaneous — no
quote-lag) with a tick-rule fallback:

    price >= ask                      -> BUY  (aggressor lifted the offer)
    price <= bid                      -> SELL (aggressor hit the bid)
    bid < price < ask, price > mid    -> BUY
    bid < price < ask, price < mid    -> SELL
    price == mid  (or no quote)       -> tick rule:
        price > prev_price -> BUY;  price < prev_price -> SELL;  else prev_side

ACCURACY ASSUMPTION: quote+tick classification is ~80-90% accurate vs true
order-level aggressor (Lee & Ready 1991; degrades for illiquid names and at the
mid). Exact aggressor is unknowable without order-level data. This is a knob:
classify.method = lee_ready | tick_rule. To be VALIDATED against real data Monday.
"""

from __future__ import annotations

from typing import Optional

BUY = 1
SELL = -1


def _tick_rule(price: float, prev_price: Optional[float], prev_side: int) -> int:
    if prev_price is None:
        return prev_side or BUY   # no history: default BUY (documented bias, rare)
    if price > prev_price:
        return BUY
    if price < prev_price:
        return SELL
    return prev_side or BUY        # zero tick -> carry previous classification


def classify_trade(price: float, bid: Optional[float], ask: Optional[float],
                   prev_price: Optional[float], prev_side: int,
                   method: str = "lee_ready") -> int:
    """Return BUY (+1) or SELL (-1) for a trade at ``price``.

    ``bid``/``ask`` are the contemporaneous top-of-book (may be None). ``prev_price``
    / ``prev_side`` carry tick-rule state for the same instrument.
    """
    if method == "tick_rule" or bid is None or ask is None or bid <= 0 or ask <= 0:
        return _tick_rule(price, prev_price, prev_side)
    # Lee-Ready quote rule
    if price >= ask:
        return BUY
    if price <= bid:
        return SELL
    mid = (bid + ask) / 2.0
    if price > mid:
        return BUY
    if price < mid:
        return SELL
    return _tick_rule(price, prev_price, prev_side)   # at mid -> tick rule
