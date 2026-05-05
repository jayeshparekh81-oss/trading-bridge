"""Map a parsed :class:`PineProgram` to a Tradetri StrategyJSON dict.

The mapper turns the AST into the JSON shape the
:class:`~app.strategy_engine.schema.strategy.StrategyJSON` validator
accepts. It does **not** call the validator itself — that is the
:mod:`converter`'s responsibility, which fails the whole conversion
loudly if anything in the produced dict is malformed.

Indicator mapping table (``ta.<func>`` → registry id + params)::

    ta.ema(src, len)              → {"type": "ema", params={period, source}}
    ta.sma(src, len)              → {"type": "sma", params={period, source}}
    ta.rsi(src, len)              → {"type": "rsi", params={period, source}}
    ta.macd(src, fast, slow, sig) → {"type": "macd", params={...}}
    ta.bb(src, len, mult)         → {"type": "bollinger_bands", params={...}}
    ta.atr(len)                   → {"type": "atr", params={period}}
    ta.vwap(src)                  → {"type": "vwap", params={}}

``ta.highest`` / ``ta.lowest`` map to the upcoming Donchian channel
indicator that ships as ``coming_soon`` in Phase 9 — the importer
records them as unsupported with a clear note rather than silently
dropping them.

Default exit block: ``targetPercent=2``, ``stopLossPercent=1``,
``reverseSignalExit`` set to True when the source has both an entry
and a corresponding ``strategy.close`` triggered by the inverse cross.
"""

from __future__ import annotations

import re
from typing import Any

from app.strategy_engine.pine_import.parser import (
    SUPPORTED_TA_INDICATORS,
    CrossCall,
    EntryDirection,
    IndicatorCall,
    PineProgram,
)

_IDENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]*$")
_VALID_PRICE_SOURCES: frozenset[str] = frozenset(
    {"open", "high", "low", "close", "volume", "hl2", "hlc3", "ohlc4"}
)


# ─── Indicator construction ────────────────────────────────────────────


def _coerce_period(value: str | int | float, default: int) -> int:
    """Numeric arg → int period; identifier → default with a note."""
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    return default


def _coerce_source(value: str | int | float, default: str = "close") -> str:
    """Identifier arg that names a price source → that source; else default."""
    if isinstance(value, str) and value in _VALID_PRICE_SOURCES:
        return value
    return default


def _slugify(name: str) -> str:
    """Pine variable name → registry-safe id (lower-snake-case, alphanumerics)."""
    cleaned = re.sub(r"[^A-Za-z0-9_]", "_", name).lower().strip("_")
    if not cleaned:
        cleaned = "indicator"
    if not cleaned[0].isalpha() and cleaned[0] != "_":
        cleaned = f"x_{cleaned}"
    return cleaned


def _build_indicator(call: IndicatorCall) -> tuple[dict[str, Any], list[str]]:
    """Return ``(indicator_dict, partial_notes)`` for one parsed call."""
    notes: list[str] = []
    args = call.args
    indicator_id = _slugify(call.var_name)

    if call.func == "ema":
        period = _coerce_period(args[1], default=20) if len(args) >= 2 else 20
        source = _coerce_source(args[0]) if len(args) >= 1 else "close"
        return (
            {
                "id": indicator_id,
                "type": "ema",
                "params": {"period": period, "source": source},
            },
            notes,
        )

    if call.func == "sma":
        period = _coerce_period(args[1], default=20) if len(args) >= 2 else 20
        source = _coerce_source(args[0]) if len(args) >= 1 else "close"
        return (
            {
                "id": indicator_id,
                "type": "sma",
                "params": {"period": period, "source": source},
            },
            notes,
        )

    if call.func == "rsi":
        period = _coerce_period(args[1], default=14) if len(args) >= 2 else 14
        source = _coerce_source(args[0]) if len(args) >= 1 else "close"
        return (
            {
                "id": indicator_id,
                "type": "rsi",
                "params": {"period": period, "source": source},
            },
            notes,
        )

    if call.func == "macd":
        source = _coerce_source(args[0]) if len(args) >= 1 else "close"
        fast = _coerce_period(args[1], default=12) if len(args) >= 2 else 12
        slow = _coerce_period(args[2], default=26) if len(args) >= 3 else 26
        signal = _coerce_period(args[3], default=9) if len(args) >= 4 else 9
        return (
            {
                "id": indicator_id,
                "type": "macd",
                "params": {
                    "source": source,
                    "fast_period": fast,
                    "slow_period": slow,
                    "signal_period": signal,
                },
            },
            notes,
        )

    if call.func == "bb":
        source = _coerce_source(args[0]) if len(args) >= 1 else "close"
        period = _coerce_period(args[1], default=20) if len(args) >= 2 else 20
        std_dev_arg = args[2] if len(args) >= 3 else 2.0
        std_dev = (
            float(std_dev_arg) if isinstance(std_dev_arg, (int, float)) else 2.0
        )
        return (
            {
                "id": indicator_id,
                "type": "bollinger_bands",
                "params": {
                    "period": period,
                    "std_dev": std_dev,
                    "source": source,
                },
            },
            notes,
        )

    if call.func == "atr":
        period = _coerce_period(args[0], default=14) if len(args) >= 1 else 14
        return (
            {
                "id": indicator_id,
                "type": "atr",
                "params": {"period": period},
            },
            notes,
        )

    if call.func == "vwap":
        return (
            {"id": indicator_id, "type": "vwap", "params": {}},
            notes,
        )

    if call.func in {"highest", "lowest"}:
        notes.append(
            f"ta.{call.func} maps to the Donchian channel indicator "
            "(coming_soon in Phase 9) — preserved as a note for review."
        )
        return ({}, notes)

    # Should not happen — parser only emits supported funcs into IndicatorCall.
    notes.append(f"Unhandled ta.{call.func}")  # pragma: no cover
    return ({}, notes)


# ─── Cross condition mapping ───────────────────────────────────────────


def _cross_to_condition(
    cross: CrossCall,
    indicator_var_to_id: dict[str, str],
) -> tuple[dict[str, Any] | None, list[str]]:
    """Build an :class:`IndicatorCondition` dict for the cross.

    Both operands must resolve to a known indicator id (i.e. a Pine
    variable that mapped to a recognised ``ta.*`` indicator). When one
    operand isn't bound to an indicator (e.g. ``ta.crossover(close, 50)``
    or a literal level), the cross is dropped with an explanatory note.
    """
    notes: list[str] = []
    left = indicator_var_to_id.get(cross.left)
    right = indicator_var_to_id.get(cross.right)
    if left is None or right is None:
        notes.append(
            f"ta.{cross.kind.value}({cross.left}, {cross.right}) — operand is "
            "not a recognised indicator; condition dropped from the import."
        )
        return None, notes
    return (
        {
            "type": "indicator",
            "left": left,
            "op": cross.kind.value,
            "right": right,
        },
        notes,
    )


# ─── Top-level mapper ──────────────────────────────────────────────────


def map_program(program: PineProgram) -> tuple[dict[str, Any], list[str]]:
    """Return ``(strategy_dict, notes)`` from a parsed program.

    ``strategy_dict`` is StrategyJSON-shaped but **not yet validated** —
    the converter calls ``StrategyJSON.model_validate`` to enforce the
    schema.
    """
    notes: list[str] = []
    indicator_dicts: list[dict[str, Any]] = []
    indicator_var_to_id: dict[str, str] = {}

    for call in program.indicators:
        ind, ind_notes = _build_indicator(call)
        notes.extend(ind_notes)
        if ind:
            indicator_dicts.append(ind)
            indicator_var_to_id[call.var_name] = ind["id"]

    # Build a map from cross-variable → IndicatorCondition.
    cross_conditions: dict[str, dict[str, Any]] = {}
    for cross in program.crosses:
        cond, cross_notes = _cross_to_condition(cross, indicator_var_to_id)
        notes.extend(cross_notes)
        if cond is not None:
            cross_conditions[cross.var_name] = cond

    # Pick the entry trigger: first strategy.entry that has a known cross
    # gating it, falling back to the first cross in the file.
    entry_conditions: list[dict[str, Any]] = []
    side: str = "BUY"
    for entry in program.entries:
        if entry.triggered_by and entry.triggered_by in cross_conditions:
            entry_conditions = [cross_conditions[entry.triggered_by]]
            side = "BUY" if entry.direction is EntryDirection.LONG else "SELL"
            break
    if not entry_conditions and cross_conditions:
        first_var = next(iter(cross_conditions))
        entry_conditions = [cross_conditions[first_var]]
        notes.append(
            "No strategy.entry() gated by a cross condition was found — "
            f"using the first cross ({first_var}) as the entry signal."
        )

    if not entry_conditions:
        # Worst-case fallback: a price > 0 condition so the schema accepts
        # the strategy. The converter flags this as partial.
        entry_conditions = [{"type": "price", "op": ">", "value": 0.0}]
        notes.append(
            "No entry condition could be reconstructed from the source — "
            "inserted a placeholder price > 0 condition."
        )

    # Reverse-signal exit when an opposite-direction cross drives a close.
    reverse_signal_exit = False
    for close in program.closes:
        if close.triggered_by and close.triggered_by in cross_conditions:
            reverse_signal_exit = True
            break

    exit_block: dict[str, Any] = {
        "targetPercent": 2.0,
        "stopLossPercent": 1.0,
    }
    if reverse_signal_exit:
        exit_block["reverseSignalExit"] = True

    strategy: dict[str, Any] = {
        "id": "imported_pine",
        "name": "Imported Pine Strategy",
        "mode": "intermediate",
        "version": 1,
        "indicators": indicator_dicts,
        "entry": {
            "side": side,
            "operator": "AND",
            "conditions": entry_conditions,
        },
        "exit": exit_block,
        "risk": {},
        "execution": {
            "mode": "backtest",
            "orderType": "MARKET",
            "productType": "INTRADAY",
        },
    }

    if program.unsupported_calls:
        for label in program.unsupported_calls:
            notes.append(f"Unsupported in importer: {label}")

    return strategy, notes


__all__ = ["SUPPORTED_TA_INDICATORS", "map_program"]
