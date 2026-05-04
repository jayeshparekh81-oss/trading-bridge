"""Strategy engine — no-code AI-assisted trading strategy stack.

This package is **additive** to the existing TRADETRI execution engine:
``app/services/strategy_executor.py`` and friends remain the live broker
path and are not modified by anything inside this package. The strategy
engine builds a parallel system for user-built strategies that go through
schema → indicators → engines → backtest → reliability → builder UI →
advisor → Pine source-code import → paper/live execution bridge.

Phase 1 ships:
    * :mod:`app.strategy_engine.schema` — Pydantic models for the
      Strategy JSON contract and indicator metadata.
    * :mod:`app.strategy_engine.indicators` — registry + 10 pure-Python
      indicator calculations (EMA, SMA, WMA, RSI, MACD, Bollinger, ATR,
      VWAP, OBV, Volume SMA).

Later phases (2-10) live alongside under sibling sub-packages.
"""

from __future__ import annotations

__all__: list[str] = []
