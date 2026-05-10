"""Locked Hinglish + English message templates per issue type.

Templates are static strings with named placeholders so the wording
stays uniform across the codebase. Each helper returns a tuple of
``(message, hinglish_message)`` matching the
:class:`DataQualityIssue` field pair.
"""

from __future__ import annotations

from datetime import datetime


def missing_candle_messages(timestamp: datetime) -> tuple[str, str]:
    iso = timestamp.isoformat()
    return (
        f"Missing candle expected near {iso} — backtest will not be reliable.",
        f"Candle missing hai timestamp {iso} pe. Backtest reliable nahi hoga.",
    )


def duplicate_candle_messages(timestamp: datetime) -> tuple[str, str]:
    iso = timestamp.isoformat()
    return (
        f"Duplicate candle at {iso}.",
        f"Duplicate candle mila timestamp {iso} pe.",
    )


def invalid_ohlc_messages(
    candle_index: int, *, high: float, low: float
) -> tuple[str, str]:
    return (
        f"Invalid OHLC at index {candle_index}: high {high} < low {low}.",
        f"Invalid OHLC at index {candle_index}: high {high} < low {low}",
    )


def invalid_ohlc_oc_messages(
    candle_index: int, *, label: str, value: float, low: float, high: float
) -> tuple[str, str]:
    """``open`` or ``close`` outside the [low, high] band."""
    return (
        (
            f"Invalid OHLC at index {candle_index}: {label} {value} outside "
            f"[low={low}, high={high}]."
        ),
        (
            f"Invalid OHLC at index {candle_index}: {label} {value} "
            f"low {low} aur high {high} ke bahar hai."
        ),
    )


def zero_volume_messages(percent: float) -> tuple[str, str]:
    pct_str = f"{percent * 100:.1f}"
    return (
        (
            f"Volume is zero on {pct_str}% of candles — possible liquidity issue."
        ),
        (
            f"Volume zero hai {pct_str}% candles mein. Liquidity issue ho sakta hai."
        ),
    )


def time_gap_messages(timestamp: datetime) -> tuple[str, str]:
    iso = timestamp.isoformat()
    return (
        f"Time gap detected near {iso} — market closed or data missing.",
        f"Time gap detected {iso} pe. Market closed ya data missing.",
    )


def timezone_mismatch_messages(distinct_count: int) -> tuple[str, str]:
    return (
        (
            f"Candle stream mixes {distinct_count} different timezones — "
            "expected single IST offset."
        ),
        (
            f"Candles ka timezone mix ho raha hai ({distinct_count} different). "
            "IST mein hone chahiye."
        ),
    )


def out_of_order_messages(candle_index: int) -> tuple[str, str]:
    return (
        f"Candle at index {candle_index} is not in chronological order.",
        f"Candles sequence mein nahi hain (index {candle_index}).",
    )


# ─── Summary templates (locked) ────────────────────────────────────────


def summary_for(can_backtest: bool, quality_score: float) -> str:
    """Hinglish report summary keyed off the can_backtest gate and the
    raw quality score band."""
    if not can_backtest:
        return "Data quality bahut kharab hai. Backtest skip karo, data fix karo."
    if quality_score >= 90:
        return "Data quality excellent. Backtest run kar sakte ho."
    if quality_score >= 70:
        return "Data quality theek hai. Kuch warnings hain - dekh lo."
    return "Data quality concerning hai. Results reliable nahi honge."


__all__ = [
    "duplicate_candle_messages",
    "invalid_ohlc_messages",
    "invalid_ohlc_oc_messages",
    "missing_candle_messages",
    "out_of_order_messages",
    "summary_for",
    "time_gap_messages",
    "timezone_mismatch_messages",
    "zero_volume_messages",
]
