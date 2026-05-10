"""Phase 8C — Data Quality validator tests.

Pure-function coverage for the read-only candle validator. Each test
constructs a small candle list (the ``Candle`` model enforces the
OHLC invariant on init, so the invalid-OHLC test uses
``model_construct`` to bypass validation and feed the validator the
same kind of malformed bar a corrupted upstream feed would).
"""

from __future__ import annotations

import ast
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path

import pytest

from app.strategy_engine.data_quality import (
    DataQualityReport,
    validate_candles,
)
from app.strategy_engine.data_quality.constants import (
    MAX_MISSING_PERCENT,
    QUALITY_FLOOR_FOR_BACKTEST,
)
from app.strategy_engine.schema.ohlcv import Candle

# ─── Builders ──────────────────────────────────────────────────────────


_BASE_TS = datetime(2026, 1, 1, 9, 30, tzinfo=UTC)


def _clean_candles(n: int = 30, *, timeframe_minutes: int = 5) -> list[Candle]:
    """``n`` evenly-spaced, well-formed candles with non-zero volume."""
    return [
        Candle(
            timestamp=_BASE_TS + timedelta(minutes=timeframe_minutes * i),
            open=100.0,
            high=101.0,
            low=99.0,
            close=100.5,
            volume=1_000.0,
        )
        for i in range(n)
    ]


# ─── 1. Clean candles → score 100, no issues ───────────────────────────


def test_clean_candles_score_100_no_issues() -> None:
    report = validate_candles(_clean_candles(30), expected_timeframe_minutes=5)
    assert isinstance(report, DataQualityReport)
    assert report.is_valid is True
    assert report.can_backtest is True
    assert report.quality_score == 100.0
    assert report.issues == ()
    assert report.total_candles == 30
    assert "excellent" in report.summary_hinglish


# ─── 2. Missing candle gap → critical + score drop ─────────────────────


def test_missing_candle_gap_emits_critical_and_lowers_score() -> None:
    """A 30-min hole in a 5-min stream is well above 2x the timeframe
    so the validator must classify it as ``missing_candle`` critical
    (not just a ``time_gap`` warning)."""
    base = _clean_candles(10)
    # Drop indexes 4..6 → leaves a 25-minute hole between bar 3 and 7.
    sliced = base[:4] + base[7:]
    report = validate_candles(sliced, expected_timeframe_minutes=5)
    missing = [i for i in report.issues if i.issue_type == "missing_candle"]
    assert len(missing) == 1
    assert missing[0].severity == "critical"
    assert report.quality_score < 100.0
    assert report.is_valid is False  # any critical issue flips this


# ─── 3. Duplicate timestamp → critical ─────────────────────────────────


def test_duplicate_timestamp_emits_critical_issue() -> None:
    candles = _clean_candles(5)
    # Re-add candle[2] so its timestamp appears twice in a row.
    duplicate = [*candles[:3], candles[2], *candles[3:]]
    report = validate_candles(duplicate, expected_timeframe_minutes=5)
    dups = [i for i in report.issues if i.issue_type == "duplicate_candle"]
    assert len(dups) == 1
    assert dups[0].severity == "critical"
    # The duplicate is reported at the second occurrence index (3).
    assert dups[0].candle_index == 3
    assert report.is_valid is False


# ─── 4. Invalid OHLC → critical + can_backtest=False ──────────────────


def test_invalid_ohlc_blocks_backtest() -> None:
    """``high < low`` is impossible in the real world. We construct
    one such bar via ``model_construct`` (bypasses Pydantic validation)
    so the validator sees a corrupted-feed-style row."""
    good = _clean_candles(5)
    bad = Candle.model_construct(
        timestamp=_BASE_TS + timedelta(minutes=25),  # next slot after 5 good
        open=100.0,
        high=98.0,  # high < low → invariant break
        low=101.0,
        close=99.0,
        volume=1_000.0,
    )
    report = validate_candles([*good, bad], expected_timeframe_minutes=5)
    invalid = [i for i in report.issues if i.issue_type == "invalid_ohlc"]
    assert len(invalid) == 1
    assert invalid[0].severity == "critical"
    assert invalid[0].candle_index == 5
    assert report.can_backtest is False


# ─── 5. Out-of-order timestamps → critical + can_backtest=False ───────


def test_out_of_order_blocks_backtest() -> None:
    candles = _clean_candles(6)
    # Swap last two so candles[5].timestamp < candles[4].timestamp.
    candles[4], candles[5] = candles[5], candles[4]
    report = validate_candles(candles, expected_timeframe_minutes=5)
    out_of_order = [i for i in report.issues if i.issue_type == "out_of_order"]
    assert out_of_order, "expected at least one out_of_order issue"
    assert all(i.severity == "critical" for i in out_of_order)
    assert report.can_backtest is False


# ─── 6. Zero volume on >5% candles → warning ──────────────────────────


def test_zero_volume_above_threshold_emits_warning() -> None:
    """10 candles with 1 zero-volume bar = 10% — above the 5% threshold."""
    candles = _clean_candles(10)
    candles[5] = Candle(
        timestamp=candles[5].timestamp,
        open=candles[5].open,
        high=candles[5].high,
        low=candles[5].low,
        close=candles[5].close,
        volume=0.0,
    )
    report = validate_candles(candles, expected_timeframe_minutes=5)
    zero_vol = [i for i in report.issues if i.issue_type == "zero_volume"]
    assert len(zero_vol) == 1
    assert zero_vol[0].severity == "warning"
    assert "Liquidity" in zero_vol[0].hinglish_message


# ─── 7. Mixed timezone → warning ──────────────────────────────────────


def test_mixed_timezone_emits_warning() -> None:
    """Same offset, different tzinfo objects (UTC vs +05:30) → warning."""
    ist = timezone(timedelta(hours=5, minutes=30))
    base_utc = _BASE_TS
    candles = [
        Candle(
            timestamp=base_utc + timedelta(minutes=5 * i),
            open=100.0, high=101.0, low=99.0, close=100.5, volume=1_000.0,
        )
        for i in range(3)
    ]
    candles += [
        Candle(
            timestamp=base_utc.astimezone(ist) + timedelta(minutes=5 * (3 + i)),
            open=100.0, high=101.0, low=99.0, close=100.5, volume=1_000.0,
        )
        for i in range(3)
    ]
    report = validate_candles(candles, expected_timeframe_minutes=5)
    tz_issues = [i for i in report.issues if i.issue_type == "timezone_mismatch"]
    assert len(tz_issues) == 1
    assert tz_issues[0].severity == "warning"


# ─── 8. Quality score < floor → can_backtest=False ────────────────────


def test_low_quality_score_forces_can_backtest_false() -> None:
    """Stack enough criticals to push the score below the floor (40),
    while keeping the issue types non-blocking on their own (i.e. not
    out_of_order / not invalid_ohlc) so we isolate the score gate."""
    candles = _clean_candles(20)
    # Insert 7 duplicates → 7 * 10 = 70 points lost → score = 30 < 40.
    duplicated = candles + [candles[i] for i in range(7)]
    report = validate_candles(duplicated, expected_timeframe_minutes=5)
    assert report.quality_score < QUALITY_FLOOR_FOR_BACKTEST
    assert report.can_backtest is False
    assert "kharab" in report.summary_hinglish


# ─── 9. Determinism: same input → same output ─────────────────────────


def test_validator_is_deterministic() -> None:
    candles = _clean_candles(20)
    # Add a duplicate to ensure the issue list is non-empty.
    candles = [*candles, candles[3]]
    first = validate_candles(candles, expected_timeframe_minutes=5)
    second = validate_candles(candles, expected_timeframe_minutes=5)
    assert first == second
    assert first.issues == second.issues
    assert first.quality_score == second.quality_score


# ─── 10. AST inspection: no LLM / network imports ─────────────────────


_FORBIDDEN_PREFIXES: tuple[str, ...] = (
    "openai",
    "anthropic",
    "httpx",
    "requests",
    "urllib",
    "urllib3",
    "aiohttp",
    "websocket",
    "websockets",
    "socket",
)


def _data_quality_python_files() -> list[Path]:
    pkg_root = (
        Path(__file__).resolve().parents[3]
        / "app"
        / "strategy_engine"
        / "data_quality"
    )
    return sorted(p for p in pkg_root.glob("*.py"))


@pytest.mark.parametrize("source_file", _data_quality_python_files())
def test_data_quality_module_does_not_import_llm_or_network(
    source_file: Path,
) -> None:
    """Walk every import in every data_quality *.py file and assert it
    does not pull in an LLM SDK or any network/socket library. The
    validator is, by design, a pure deterministic pipeline."""
    tree = ast.parse(source_file.read_text(), filename=str(source_file))
    offenders: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if _is_forbidden(alias.name):
                    offenders.append(f"import {alias.name}")
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if _is_forbidden(module):
                offenders.append(f"from {module} import …")
    assert not offenders, (
        f"{source_file.name} pulls in forbidden modules: {offenders}"
    )


def _is_forbidden(name: str) -> bool:
    if not name:
        return False
    return any(
        name == pref or name.startswith(pref + ".") for pref in _FORBIDDEN_PREFIXES
    )


# ─── 11. Missing-percent gate forces can_backtest=False ───────────────


def test_excessive_missing_percent_forces_can_backtest_false() -> None:
    """Sparse stream where the gap-implied missing fraction exceeds
    :data:`MAX_MISSING_PERCENT` — the gate should block backtesting.

    We drop two contiguous 3-bar runs so each resulting gap is 4x
    timeframe (>2x -> missing_candle critical) and the implied missing
    total clearly clears the 10% threshold."""
    base = _clean_candles(30)
    keep = [c for i, c in enumerate(base) if i not in {10, 11, 12, 20, 21, 22}]
    report = validate_candles(keep, expected_timeframe_minutes=5)
    assert report.can_backtest is False
    assert any(i.issue_type == "missing_candle" for i in report.issues)
    # Confirm the threshold is the binding gate — i.e. > MAX_MISSING_PERCENT.
    from app.strategy_engine.data_quality.scorer import estimate_missing_percent

    assert estimate_missing_percent(keep, 5) > MAX_MISSING_PERCENT


# ─── 12. Time gap (warning band) → warning, not critical ──────────────


def test_time_gap_in_warning_band_emits_warning_only() -> None:
    """A 9-minute gap on a 5-minute timeframe lands in the
    1.5x < ratio <= 2.0x band → ``time_gap`` warning, NOT a
    ``missing_candle`` critical."""
    candles = [
        Candle(
            timestamp=_BASE_TS,
            open=100.0, high=101.0, low=99.0, close=100.5, volume=1_000.0,
        ),
        Candle(
            timestamp=_BASE_TS + timedelta(minutes=9),  # 1.8x of 5min
            open=100.0, high=101.0, low=99.0, close=100.5, volume=1_000.0,
        ),
    ]
    report = validate_candles(candles, expected_timeframe_minutes=5)
    types = {i.issue_type for i in report.issues}
    assert "time_gap" in types
    assert "missing_candle" not in types
    gap_issues = [i for i in report.issues if i.issue_type == "time_gap"]
    assert all(i.severity == "warning" for i in gap_issues)
