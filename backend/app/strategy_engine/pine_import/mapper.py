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
from collections.abc import Sequence
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

#: Pine TA function name → registry indicator id for indicators
#: whose calculation function isn't shipped yet. Matching one of
#: these emits a note (same shape as ``highest``/``lowest``) so the
#: import surfaces what's pending without dropping it silently.
#:
#: Pack 2 (commit 511f591) promoted 13 of the original Batch 1
#: coming-soon mappings to ACTIVE; their handlers now sit in the
#: "Pack 2 ACTIVE mappings" block below and emit real indicator
#: dicts. Pack 18 promoted ``mom`` to ACTIVE
#: (-> ``momentum_oscillator``). Two entries remain coming-soon:
#: ``stoch_rsi`` and ``heikinashi``.
_COMING_SOON_PINE_TO_REGISTRY: dict[str, str] = {
    "stoch_rsi": "stoch_rsi",
    "heikinashi": "heikin_ashi",
}


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


def _pivot_left_right(args: Sequence[Any]) -> tuple[int, int]:
    """Read ``(left, right)`` from a ``ta.pivothigh`` / ``ta.pivotlow``
    call. Pine's most-common 2-arg form is handled here; defaults are
    (5, 5) when args are missing."""
    left = _coerce_period(args[0], default=5) if len(args) >= 1 else 5
    right = _coerce_period(args[1], default=5) if len(args) >= 2 else 5
    return (left, right)


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

    # ─── Batch 1 ACTIVE mappings — produce real indicator dicts. ─────

    if call.func == "wma":
        period = _coerce_period(args[1], default=20) if len(args) >= 2 else 20
        source = _coerce_source(args[0]) if len(args) >= 1 else "close"
        return (
            {
                "id": indicator_id,
                "type": "wma",
                "params": {"period": period, "source": source},
            },
            notes,
        )

    if call.func == "adx":
        # Pine ``ta.adx(len)`` returns a single ADX line. Registry's
        # ADX takes period only.
        period = _coerce_period(args[0], default=14) if len(args) >= 1 else 14
        return (
            {
                "id": indicator_id,
                "type": "adx",
                "params": {"period": period},
            },
            notes,
        )

    if call.func == "cmf":
        period = _coerce_period(args[0], default=20) if len(args) >= 1 else 20
        return (
            {
                "id": indicator_id,
                "type": "cmf",
                "params": {"period": period},
            },
            notes,
        )

    if call.func == "trix":
        # Pine ``ta.trix(src, len)`` order. Registry takes (period, source).
        period = _coerce_period(args[1], default=15) if len(args) >= 2 else 15
        source = _coerce_source(args[0]) if len(args) >= 1 else "close"
        return (
            {
                "id": indicator_id,
                "type": "trix",
                "params": {"period": period, "source": source},
            },
            notes,
        )

    if call.func == "aroon":
        period = _coerce_period(args[0], default=25) if len(args) >= 1 else 25
        return (
            {
                "id": indicator_id,
                "type": "aroon",
                "params": {"period": period},
            },
            notes,
        )

    if call.func == "obv":
        # On-balance volume is parameter-less in Pine and the registry.
        return (
            {"id": indicator_id, "type": "obv", "params": {}},
            notes,
        )

    # ─── Pack 2 ACTIVE mappings (commit 511f591). ────────────────────────
    #
    # These all used to live in ``_COMING_SOON_PINE_TO_REGISTRY`` and
    # produced "currently coming_soon" notes; Pack 2 shipped real
    # calculation functions for them, so the importer now emits a
    # populated indicator dict instead.

    if call.func == "vwma":
        # ta.vwma(source, length).
        source = _coerce_source(args[0]) if len(args) >= 1 else "close"
        period = _coerce_period(args[1], default=20) if len(args) >= 2 else 20
        return (
            {
                "id": indicator_id,
                "type": "vwma",
                "params": {"period": period, "source": source},
            },
            notes,
        )

    if call.func == "rma":
        # ta.rma(source, length) — Wilder's smoothed MA / SMMA.
        source = _coerce_source(args[0]) if len(args) >= 1 else "close"
        period = _coerce_period(args[1], default=20) if len(args) >= 2 else 20
        return (
            {
                "id": indicator_id,
                "type": "smma",
                "params": {"period": period, "source": source},
            },
            notes,
        )

    if call.func == "dema":
        # ta.dema(source, length).
        source = _coerce_source(args[0]) if len(args) >= 1 else "close"
        period = _coerce_period(args[1], default=20) if len(args) >= 2 else 20
        return (
            {
                "id": indicator_id,
                "type": "dema",
                "params": {"period": period, "source": source},
            },
            notes,
        )

    if call.func == "tema":
        # ta.tema(source, length).
        source = _coerce_source(args[0]) if len(args) >= 1 else "close"
        period = _coerce_period(args[1], default=20) if len(args) >= 2 else 20
        return (
            {
                "id": indicator_id,
                "type": "tema",
                "params": {"period": period, "source": source},
            },
            notes,
        )

    if call.func == "hma":
        # ta.hma(source, length).
        source = _coerce_source(args[0]) if len(args) >= 1 else "close"
        period = _coerce_period(args[1], default=20) if len(args) >= 2 else 20
        return (
            {
                "id": indicator_id,
                "type": "hull_ma",
                "params": {"period": period, "source": source},
            },
            notes,
        )

    if call.func == "supertrend":
        # ta.supertrend(factor, atrPeriod). The Pine signature
        # passes the multiplier first and the ATR period second —
        # opposite of the registry's (period, multiplier) order.
        multiplier_arg = args[0] if len(args) >= 1 else 3.0
        multiplier = (
            float(multiplier_arg)
            if isinstance(multiplier_arg, (int, float))
            else 3.0
        )
        period = _coerce_period(args[1], default=10) if len(args) >= 2 else 10
        return (
            {
                "id": indicator_id,
                "type": "supertrend",
                "params": {"period": period, "multiplier": multiplier},
            },
            notes,
        )

    if call.func == "psar":
        # ta.psar(start, increment, max). Registry takes
        # (step, max_step); we map increment -> step, max -> max_step
        # (Pine's ``start`` is the initial AF, identical to ``increment``
        # in nearly every published preset).
        increment = args[1] if len(args) >= 2 else 0.02
        max_arg = args[2] if len(args) >= 3 else 0.2
        step = float(increment) if isinstance(increment, (int, float)) else 0.02
        max_step = float(max_arg) if isinstance(max_arg, (int, float)) else 0.2
        return (
            {
                "id": indicator_id,
                "type": "parabolic_sar",
                "params": {"step": step, "max_step": max_step},
            },
            notes,
        )

    if call.func == "cci":
        # ta.cci(source, length). Source is ignored — registry's CCI
        # uses the typical price (HLC/3) by definition.
        period = _coerce_period(args[1], default=20) if len(args) >= 2 else 20
        return (
            {
                "id": indicator_id,
                "type": "cci",
                "params": {"period": period},
            },
            notes,
        )

    if call.func == "mfi":
        # ta.mfi(source, length). Source is ignored — registry's MFI
        # uses HLC/3 + volume by definition.
        period = _coerce_period(args[1], default=14) if len(args) >= 2 else 14
        return (
            {
                "id": indicator_id,
                "type": "mfi",
                "params": {"period": period},
            },
            notes,
        )

    if call.func == "williams_r":
        # ta.williams_r(source, high, low, length) — the importer
        # accepts the 4-arg form used in TRADETRI's existing tests.
        # Length lands at args[3]; source/high/low are absorbed by
        # the registry calc internally.
        period = _coerce_period(args[3], default=14) if len(args) >= 4 else 14
        return (
            {
                "id": indicator_id,
                "type": "williams_r",
                "params": {"period": period},
            },
            notes,
        )

    if call.func == "cmo":
        # ta.cmo(source, length).
        source = _coerce_source(args[0]) if len(args) >= 1 else "close"
        period = _coerce_period(args[1], default=9) if len(args) >= 2 else 9
        return (
            {
                "id": indicator_id,
                "type": "chande_momentum",
                "params": {"period": period, "source": source},
            },
            notes,
        )

    if call.func == "stoch":
        # ta.stoch(close, high, low, length). Registry stochastic
        # additionally takes a ``d_period`` smoothing window which
        # Pine doesn't surface; default to 3 (the standard %D).
        period = _coerce_period(args[3], default=14) if len(args) >= 4 else 14
        return (
            {
                "id": indicator_id,
                "type": "stochastic",
                "params": {"k_period": period, "d_period": 3},
            },
            notes,
        )

    if call.func == "roc":
        # ta.roc(source, length).
        source = _coerce_source(args[0]) if len(args) >= 1 else "close"
        period = _coerce_period(args[1], default=9) if len(args) >= 2 else 9
        return (
            {
                "id": indicator_id,
                "type": "roc",
                "params": {"period": period, "source": source},
            },
            notes,
        )

    if call.func == "donchian":
        # ta.donchian(length).
        period = _coerce_period(args[0], default=20) if len(args) >= 1 else 20
        return (
            {
                "id": indicator_id,
                "type": "donchian_channel",
                "params": {"period": period},
            },
            notes,
        )

    if call.func == "keltner":
        # ta.keltner(source, length, multiplier). Source is absorbed
        # by the registry calc (Keltner uses EMA of close + ATR).
        period = _coerce_period(args[1], default=20) if len(args) >= 2 else 20
        mult_arg = args[2] if len(args) >= 3 else 2.0
        multiplier = (
            float(mult_arg) if isinstance(mult_arg, (int, float)) else 2.0
        )
        return (
            {
                "id": indicator_id,
                "type": "keltner_channel",
                "params": {"period": period, "multiplier": multiplier},
            },
            notes,
        )

    # ─── Pack 4 ACTIVE mappings — real Pine ta.* names. ──────────────────

    if call.func == "pivothigh":
        # ta.pivothigh(left, right) — both ints. Source overload
        # (ta.pivothigh(source, left, right)) accepted by shifting.
        left, right = _pivot_left_right(args)
        return (
            {
                "id": indicator_id,
                "type": "swing_high",
                "params": {"left_bars": left, "right_bars": right},
            },
            notes,
        )

    if call.func == "pivotlow":
        left, right = _pivot_left_right(args)
        return (
            {
                "id": indicator_id,
                "type": "swing_low",
                "params": {"left_bars": left, "right_bars": right},
            },
            notes,
        )

    if call.func == "stdev":
        # ta.stdev(source, length).
        source = _coerce_source(args[0]) if len(args) >= 1 else "close"
        period = _coerce_period(args[1], default=20) if len(args) >= 2 else 20
        return (
            {
                "id": indicator_id,
                "type": "std_dev",
                "params": {"period": period, "source": source},
            },
            notes,
        )

    if call.func == "variance":
        # ta.variance(source, length, biased=true). The ``biased``
        # arg is dropped — registry uses population variance to
        # match Pine's default.
        source = _coerce_source(args[0]) if len(args) >= 1 else "close"
        period = _coerce_period(args[1], default=20) if len(args) >= 2 else 20
        return (
            {
                "id": indicator_id,
                "type": "variance",
                "params": {"period": period, "source": source},
            },
            notes,
        )

    if call.func == "correlation":
        # ta.correlation(source_a, source_b, length).
        source_a = _coerce_source(args[0]) if len(args) >= 1 else "close"
        source_b = _coerce_source(args[1], default="open") if len(args) >= 2 else "open"
        period = _coerce_period(args[2], default=20) if len(args) >= 3 else 20
        return (
            {
                "id": indicator_id,
                "type": "correlation_coefficient",
                "params": {
                    "period": period,
                    "source_a": source_a,
                    "source_b": source_b,
                },
            },
            notes,
        )

    # ─── Pack 5 ACTIVE mappings — real Pine ta.* names. ──────────────────

    if call.func == "percentrank":
        # ta.percentrank(source, length).
        source = _coerce_source(args[0]) if len(args) >= 1 else "close"
        period = _coerce_period(args[1], default=100) if len(args) >= 2 else 100
        return (
            {
                "id": indicator_id,
                "type": "percentile_rank",
                "params": {"period": period, "source": source},
            },
            notes,
        )

    if call.func == "percentile_nearest_rank":
        # ta.percentile_nearest_rank(source, length, percentage).
        source = _coerce_source(args[0]) if len(args) >= 1 else "close"
        period = _coerce_period(args[1], default=100) if len(args) >= 2 else 100
        pct_arg = args[2] if len(args) >= 3 else 50.0
        percentage = (
            float(pct_arg) if isinstance(pct_arg, (int, float)) else 50.0
        )
        return (
            {
                "id": indicator_id,
                "type": "percentile_nearest",
                "params": {
                    "period": period,
                    "percentage": percentage,
                    "source": source,
                },
            },
            notes,
        )

    if call.func == "median":
        # ta.median(source, length).
        source = _coerce_source(args[0]) if len(args) >= 1 else "close"
        period = _coerce_period(args[1], default=20) if len(args) >= 2 else 20
        return (
            {
                "id": indicator_id,
                "type": "median_value",
                "params": {"period": period, "source": source},
            },
            notes,
        )

    # ─── Pack 6 ACTIVE mappings — real Pine ta.* names. ──────────────────

    if call.func == "accdist":
        # ta.accdist() — no params; cumulative A/D Line.
        return (
            {
                "id": indicator_id,
                "type": "accumulation_distribution",
                "params": {},
            },
            notes,
        )

    if call.func == "ao":
        # ta.ao() — no required params in Pine; Pack 6 defaults
        # 5 / 34 match Bill Williams' originals.
        return (
            {
                "id": indicator_id,
                "type": "awesome_oscillator",
                "params": {"fast": 5, "slow": 34},
            },
            notes,
        )

    # ─── Pack 9 ACTIVE mappings — rewires of stale donchian-coming_soon notes.
    # The donchian_channel indicator went active in an earlier pack but
    # the ``highest`` / ``lowest`` Pine wirings were never updated.
    # Pack 9's ``price_channel_high`` / ``price_channel_low`` are the
    # correct one-line projections for Pine's ``ta.highest(high, len)``
    # and ``ta.lowest(low, len)``.

    if call.func == "highest":
        period = _coerce_period(args[1], default=20) if len(args) >= 2 else 20
        return (
            {
                "id": indicator_id,
                "type": "price_channel_high",
                "params": {"period": period},
            },
            notes,
        )

    if call.func == "lowest":
        period = _coerce_period(args[1], default=20) if len(args) >= 2 else 20
        return (
            {
                "id": indicator_id,
                "type": "price_channel_low",
                "params": {"period": period},
            },
            notes,
        )

    # ─── Pack 10 ACTIVE mappings — real Pine ta.* names. ────────────────

    if call.func == "tsi":
        # ta.tsi(source, short, long) — note Pine's argument
        # order: short comes BEFORE long. Our calc takes
        # ``(closes, long, short)`` keyword-clear.
        short_p = _coerce_period(args[1], default=13) if len(args) >= 2 else 13
        long_p = _coerce_period(args[2], default=25) if len(args) >= 3 else 25
        return (
            {
                "id": indicator_id,
                "type": "true_strength_index",
                "params": {"long": long_p, "short": short_p},
            },
            notes,
        )

    if call.func == "ppo":
        # ta.ppo(fast, slow, signal).
        fast = _coerce_period(args[0], default=12) if len(args) >= 1 else 12
        slow = _coerce_period(args[1], default=26) if len(args) >= 2 else 26
        signal = _coerce_period(args[2], default=9) if len(args) >= 3 else 9
        return (
            {
                "id": indicator_id,
                "type": "percent_price_oscillator",
                "params": {"fast": fast, "slow": slow, "signal": signal},
            },
            notes,
        )

    # ─── Pack 7 ACTIVE mappings — real Pine ta.* names. ──────────────────

    if call.func == "vortex":
        # ta.vortex(length) returns ``[VI+, VI-]`` in Pine. Our
        # parser doesn't unpack tuples, so we map to the positive
        # line and surface a note pointing the user at the negative-
        # line config they'd add separately.
        period = _coerce_period(args[0], default=14) if len(args) >= 1 else 14
        notes.append(
            "ta.vortex returns [VI+, VI-]; mapped to the "
            "``vortex_positive`` line. Add a separate "
            "``vortex_negative`` indicator config if you need "
            "both for crossover signals."
        )
        return (
            {
                "id": indicator_id,
                "type": "vortex_positive",
                "params": {"period": period},
            },
            notes,
        )

    # ─── Pack 18 ACTIVE mappings — real Pine ta.* names. ────────────────

    if call.func == "mom":
        # ta.mom(source, length) → momentum_oscillator. Source is
        # accepted in Pine but our momentum_oscillator dispatch
        # operates on close (matches Pine's default usage); record
        # a note if a non-close source is requested.
        source = _coerce_source(args[0]) if len(args) >= 1 else "close"
        period = _coerce_period(args[1], default=10) if len(args) >= 2 else 10
        if source != "close":
            notes.append(
                f"ta.mom called with source={source!r}; "
                "momentum_oscillator currently uses close - "
                "non-close sources will be ignored."
            )
        return (
            {
                "id": indicator_id,
                "type": "momentum_oscillator",
                "params": {"period": period},
            },
            notes,
        )

    # ─── Remaining COMING_SOON mappings — recognise + note + skip. ───
    #
    # These Pine functions match a registry entry whose calculation
    # function isn't yet shipped. We surface the import attempt as a
    # note (same shape as ``highest``/``lowest``) so the user sees
    # what's pending; the indicator isn't emitted into the strategy
    # so the schema validator doesn't reject the import.
    if call.func in _COMING_SOON_PINE_TO_REGISTRY:
        registry_id = _COMING_SOON_PINE_TO_REGISTRY[call.func]
        notes.append(
            f"ta.{call.func} matches the ``{registry_id}`` indicator, "
            "currently coming_soon in TRADETRI's registry — preserved "
            "as a note. Re-run the import after the indicator ships."
        )
        return ({}, notes)

    # ``ta.highest`` / ``ta.lowest`` are handled by the Pack 9
    # mappings above — they map to ``price_channel_high`` /
    # ``price_channel_low`` actives. The previous "donchian
    # coming_soon" note is gone (donchian became active and the
    # rewire is now correct).

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
