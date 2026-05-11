"""Dhan historical-data adapter tests.

Every HTTP call is mocked through the ``http_post`` injection seam on
``fetch_historical_candles`` — no real network traffic. Sleep is
mocked the same way so retry tests run in microseconds.
"""

from __future__ import annotations

import ast
from collections.abc import Generator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import httpx
import pytest

from app.strategy_engine.data_provider import (
    DhanFetchError,
    HistoricalDataRequest,
    HistoricalDataResponse,
    clear_cache,
    fetch_historical_candles,
    normalise_symbol,
)
from app.strategy_engine.data_provider.constants import (
    INITIAL_BACKOFF_SECONDS,
    MAX_RETRY_ATTEMPTS,
)

# ─── Builders ──────────────────────────────────────────────────────────


_NOW = datetime(2026, 5, 7, tzinfo=UTC)


def _ts_seconds(start: datetime, minute_offset: int) -> int:
    return int((start + timedelta(minutes=minute_offset)).timestamp())


def _columnar_payload(n: int = 6, *, start: datetime | None = None) -> dict[str, list[Any]]:
    """Mock Dhan response — six tightly-spaced 1-minute bars."""
    base = start or datetime(2026, 4, 1, 9, 30, tzinfo=UTC)
    return {
        "open": [100.0 + i for i in range(n)],
        "high": [101.0 + i for i in range(n)],
        "low": [99.0 + i for i in range(n)],
        "close": [100.5 + i for i in range(n)],
        "volume": [1_000 + i for i in range(n)],
        "timestamp": [_ts_seconds(base, i) for i in range(n)],
    }


def _mock_response(
    payload: dict[str, Any] | str | None = None,
    *,
    status_code: int = 200,
    headers: dict[str, str] | None = None,
) -> httpx.Response:
    """Build a real :class:`httpx.Response` with the requested status
    + JSON body. Real Response keeps the parsing/JSON contract honest
    without standing up a server."""
    request = httpx.Request("POST", "https://api.dhan.co/v2/charts/intraday")
    if payload is None:
        content = b""
    elif isinstance(payload, str):
        content = payload.encode("utf-8")
    else:
        import json

        content = json.dumps(payload).encode("utf-8")
    return httpx.Response(
        status_code=status_code,
        content=content,
        headers=headers or {},
        request=request,
    )


def _request_1m(*, symbol: str = "NIFTY", days: int = 1) -> HistoricalDataRequest:
    end = datetime(2026, 4, 7, 15, 30, tzinfo=UTC)
    return HistoricalDataRequest(
        symbol=symbol,
        timeframe="1m",
        from_date=end - timedelta(days=days),
        to_date=end,
    )


@pytest.fixture(autouse=True)
def _clean_cache() -> Generator[None, None, None]:
    """Empty the on-disk cache before *and* after every test so files
    written by one test don't leak into the next."""
    clear_cache()
    yield
    clear_cache()


# ─── 1. Happy path: response → HistoricalDataResponse ─────────────────


def test_fetch_returns_historical_data_response_with_candles() -> None:
    request = _request_1m()
    http_post = MagicMock(return_value=_mock_response(_columnar_payload(n=6)))
    sleep = MagicMock()

    result = fetch_historical_candles(
        request,
        access_token="test-token",
        http_post=http_post,
        sleep_fn=sleep,
    )

    assert isinstance(result, HistoricalDataResponse)
    assert len(result.candles) == 6
    assert result.cache_hit is False
    assert result.request == request
    # Dhan headers set by the client.
    call_kwargs = http_post.call_args.kwargs
    assert call_kwargs["headers"]["access-token"] == "test-token"
    assert "intraday" in http_post.call_args.args[0]
    body = call_kwargs["json"]
    assert body["interval"] == 1
    assert body["securityId"] == "13"  # NIFTY


# ─── 2. Cache hit on second identical request ─────────────────────────


def test_second_identical_request_is_served_from_cache() -> None:
    request = _request_1m()
    http_post = MagicMock(return_value=_mock_response(_columnar_payload(n=6)))

    first = fetch_historical_candles(request, access_token="t", http_post=http_post)
    assert first.cache_hit is False
    assert http_post.call_count == 1

    second = fetch_historical_candles(request, access_token="t", http_post=http_post)
    assert second.cache_hit is True
    # No new HTTP call.
    assert http_post.call_count == 1
    # Candle payload identical between the two responses.
    assert second.candles == first.candles


# ─── 3. Cache miss when use_cache=False ───────────────────────────────


def test_use_cache_false_always_hits_the_network() -> None:
    request = _request_1m()
    http_post = MagicMock(return_value=_mock_response(_columnar_payload(n=6)))

    a = fetch_historical_candles(request, use_cache=False, access_token="t", http_post=http_post)
    b = fetch_historical_candles(request, use_cache=False, access_token="t", http_post=http_post)
    assert a.cache_hit is False
    assert b.cache_hit is False
    assert http_post.call_count == 2


# ─── 4. clear_cache empties the cache directory ───────────────────────


def test_clear_cache_drops_existing_entries() -> None:
    request = _request_1m()
    http_post = MagicMock(return_value=_mock_response(_columnar_payload(n=6)))

    fetch_historical_candles(request, access_token="t", http_post=http_post)
    # Sanity — second call hits the cache.
    second = fetch_historical_candles(request, access_token="t", http_post=http_post)
    assert second.cache_hit is True

    clear_cache()

    third = fetch_historical_candles(request, access_token="t", http_post=http_post)
    assert third.cache_hit is False
    assert http_post.call_count == 2  # initial + post-clear


# ─── 5. 429 → retry with exponential backoff ──────────────────────────


def test_429_response_triggers_retry_with_backoff() -> None:
    """Two 429s, then a success — succeed on the third attempt and
    sleep twice (between attempts 0→1 and 1→2)."""
    request = _request_1m()
    success = _mock_response(_columnar_payload(n=3))
    too_many = _mock_response({"errorMessage": "rate limited"}, status_code=429)
    http_post = MagicMock(side_effect=[too_many, too_many, success])
    sleep = MagicMock()

    result = fetch_historical_candles(
        request, access_token="t", http_post=http_post, sleep_fn=sleep
    )
    assert len(result.candles) == 3
    assert http_post.call_count == 3
    assert sleep.call_count == 2
    # Exponential schedule: INITIAL_BACKOFF * (2**attempt) for
    # attempts 0, 1.
    assert sleep.call_args_list[0].args[0] == pytest.approx(INITIAL_BACKOFF_SECONDS * 1)
    assert sleep.call_args_list[1].args[0] == pytest.approx(INITIAL_BACKOFF_SECONDS * 2)


def test_retry_after_header_overrides_exponential_backoff() -> None:
    request = _request_1m()
    too_many = _mock_response(
        {"errorMessage": "rate limited"},
        status_code=429,
        headers={"Retry-After": "7"},
    )
    success = _mock_response(_columnar_payload(n=2))
    http_post = MagicMock(side_effect=[too_many, success])
    sleep = MagicMock()

    fetch_historical_candles(request, access_token="t", http_post=http_post, sleep_fn=sleep)
    assert sleep.call_args_list[0].args[0] == pytest.approx(7.0)


# ─── 6. After MAX_RETRY_ATTEMPTS, raises clear error ──────────────────


def test_persistent_429_raises_dhan_fetch_error_after_max_retries() -> None:
    request = _request_1m()
    too_many = _mock_response({"errorMessage": "rate"}, status_code=429)
    http_post = MagicMock(return_value=too_many)
    sleep = MagicMock()

    with pytest.raises(DhanFetchError) as info:
        fetch_historical_candles(request, access_token="t", http_post=http_post, sleep_fn=sleep)
    assert info.value.status_code == 429
    assert http_post.call_count == MAX_RETRY_ATTEMPTS


# ─── 7. Symbol normalisation ──────────────────────────────────────────


@pytest.mark.parametrize(
    "raw,expected",
    [
        # Trimmed in Step 3 from 19 inline cases to ~6 representative
        # ones, one per distinct behaviour. Per-entry coverage moved
        # to :func:`test_normalised_symbols_resolve_in_known_symbols`
        # below (programmatic loop), which scales to KNOWN_SYMBOLS at
        # any size without diff bloat. Behaviours pinned here:
        #   * uppercase normalisation + alias hit
        #   * edge whitespace trim
        #   * alias miss / pass-through
        #   * internal whitespace preservation (policy pin)
        #   * index alias hit
        #   * equity-name alias hit
        ("nifty 50", "NIFTY"),
        ("  NIFTY  ", "NIFTY"),
        ("BANKNIFTY", "BANKNIFTY"),
        # NIFTY NEXT 50 is no longer in KNOWN_SYMBOLS (Dhan rejects
        # sec_id 38 with HTTP 400 — see docs/POST_LAUNCH_TECH_DEBT.md),
        # but the normaliser's whitespace-preservation policy still
        # applies as a pure function. Kept here as the canonical
        # synthetic example of a spaced input.
        ("  NIFTY  NEXT  50  ", "NIFTY NEXT 50"),
        ("Nifty Midcap Select", "MIDCPNIFTY"),
        ("HDFC BANK", "HDFCBANK"),
    ],
)
def test_symbol_normalisation_canonicalises_user_input(raw: str, expected: str) -> None:
    assert normalise_symbol(raw) == expected


def test_normalised_symbols_resolve_in_known_symbols() -> None:
    """Every KNOWN_SYMBOLS key and every SYMBOL_ALIASES key must
    round-trip through :func:`normalise_symbol` to a valid
    KNOWN_SYMBOLS entry.

    Programmatic loop (Step 3): replaced the previous inline list of
    22 hand-curated raw strings. Scales to any KNOWN_SYMBOLS size
    automatically; catches typo drift between the alias map's RHS
    and the dict's keys on future edits without per-entry test
    maintenance.
    """
    import itertools

    from app.strategy_engine.data_provider.constants import (
        KNOWN_SYMBOLS,
        SYMBOL_ALIASES,
    )

    for raw in itertools.chain(KNOWN_SYMBOLS.keys(), SYMBOL_ALIASES.keys()):
        canonical = normalise_symbol(raw)
        assert canonical in KNOWN_SYMBOLS, (
            f"{raw!r} normalised to {canonical!r}, which is not in "
            f"KNOWN_SYMBOLS"
        )


def test_known_symbols_shape_invariants() -> None:
    """Every KNOWN_SYMBOLS entry must produce a wire-format-correct
    Dhan request body. Catches typos (empty sec_id, lowercase
    segment, nonsense instrument) at PR time rather than at
    backtest time.

    Source of truth for the valid sets:
    ``backend/app/strategy_engine/data_provider/DHAN_API_NOTES.md``
    sections on ``exchangeSegment`` and ``instrument`` enums.

    Note on uniqueness: ABB equity (sec_id=13, NSE_EQ) and NIFTY
    index (sec_id=13, IDX_I) intentionally share a numeric ID under
    different segments. Dhan disambiguates via the (security_id,
    segment) tuple, so we do NOT assert bare-ID uniqueness here.
    """
    from app.strategy_engine.data_provider.constants import KNOWN_SYMBOLS

    VALID_SEGMENTS = {
        "IDX_I",
        "NSE_EQ", "NSE_FNO", "NSE_CURRENCY",
        "BSE_EQ", "BSE_FNO", "BSE_CURRENCY",
        "MCX_COMM",
    }
    VALID_INSTRUMENTS = {
        "INDEX", "EQUITY",
        "FUTIDX", "OPTIDX",
        "FUTSTK", "OPTSTK",
        "FUTCOM", "OPTFUT",
        "FUTCUR", "OPTCUR",
    }

    for key, meta in KNOWN_SYMBOLS.items():
        assert isinstance(meta.security_id, str), \
            f"{key!r}: security_id is not str ({type(meta.security_id).__name__})"
        assert meta.security_id, f"{key!r}: security_id is empty"
        assert meta.security_id.isdigit(), (
            f"{key!r}: security_id {meta.security_id!r} must be a "
            "numeric string (Dhan API requirement)"
        )
        assert meta.exchange_segment in VALID_SEGMENTS, (
            f"{key!r}: exchange_segment {meta.exchange_segment!r} not in "
            f"{VALID_SEGMENTS}"
        )
        assert meta.instrument in VALID_INSTRUMENTS, (
            f"{key!r}: instrument {meta.instrument!r} not in "
            f"{VALID_INSTRUMENTS}"
        )


def test_unknown_symbol_without_overrides_raises_value_error() -> None:
    request = HistoricalDataRequest(
        symbol="UNKNOWN_TICKER",
        timeframe="1m",
        from_date=datetime(2026, 4, 6, 9, 30, tzinfo=UTC),
        to_date=datetime(2026, 4, 6, 15, 30, tzinfo=UTC),
    )
    with pytest.raises(ValueError, match="not in the bundled KNOWN_SYMBOLS"):
        fetch_historical_candles(request, access_token="t")


def test_unknown_symbol_with_overrides_uses_them() -> None:
    request = HistoricalDataRequest(
        symbol="EXOTIC",
        timeframe="1m",
        from_date=datetime(2026, 4, 6, 9, 30, tzinfo=UTC),
        to_date=datetime(2026, 4, 6, 15, 30, tzinfo=UTC),
        security_id="99999",
        exchange_segment="NSE_EQ",
        instrument="EQUITY",
    )
    http_post = MagicMock(return_value=_mock_response(_columnar_payload(n=2)))
    fetch_historical_candles(request, access_token="t", http_post=http_post)
    body = http_post.call_args.kwargs["json"]
    assert body["securityId"] == "99999"
    assert body["exchangeSegment"] == "NSE_EQ"
    assert body["instrument"] == "EQUITY"


# ─── 8. Invalid timeframe → pydantic validation error ─────────────────


def test_invalid_timeframe_rejected_by_request_validation() -> None:
    with pytest.raises(ValueError):
        HistoricalDataRequest(
            symbol="NIFTY",
            timeframe="2m",  # type: ignore[arg-type]
            from_date=datetime(2026, 4, 1, tzinfo=UTC),
            to_date=datetime(2026, 4, 7, tzinfo=UTC),
        )


# ─── 9. from_date >= to_date → validation error ───────────────────────


def test_from_date_after_to_date_is_rejected() -> None:
    with pytest.raises(ValueError, match="must be strictly earlier"):
        HistoricalDataRequest(
            symbol="NIFTY",
            timeframe="1m",
            from_date=datetime(2026, 4, 7, tzinfo=UTC),
            to_date=datetime(2026, 4, 1, tzinfo=UTC),
        )


def test_intraday_window_above_90_days_is_rejected() -> None:
    with pytest.raises(ValueError, match="at most 90 days"):
        HistoricalDataRequest(
            symbol="NIFTY",
            timeframe="1m",
            from_date=datetime(2026, 1, 1, tzinfo=UTC),
            to_date=datetime(2026, 5, 1, tzinfo=UTC),
        )


# ─── 10. Quality warnings attached when stream has gaps ───────────────


def test_quality_warnings_attached_when_stream_has_gaps() -> None:
    """A 1-minute timeframe payload with a 30-minute jump fires the
    Phase 11 missing-candle / time-gap detector."""
    base = datetime(2026, 4, 1, 9, 30, tzinfo=UTC)
    payload = {
        "open": [100.0, 100.0],
        "high": [101.0, 101.0],
        "low": [99.0, 99.0],
        "close": [100.5, 100.5],
        "volume": [1000, 1000],
        # 30-minute jump on a 1-minute timeframe → ratio 30x → critical.
        "timestamp": [int(base.timestamp()), int((base + timedelta(minutes=30)).timestamp())],
    }
    request = _request_1m()
    http_post = MagicMock(return_value=_mock_response(payload))

    result = fetch_historical_candles(request, access_token="t", http_post=http_post)
    assert result.quality_warnings, "expected at least one quality warning"
    joined = " ".join(result.quality_warnings).lower()
    assert "gap" in joined or "missing" in joined


def test_clean_stream_produces_no_quality_warnings() -> None:
    request = _request_1m()
    http_post = MagicMock(return_value=_mock_response(_columnar_payload(n=10)))
    result = fetch_historical_candles(request, access_token="t", http_post=http_post)
    assert result.quality_warnings == []


# ─── 11. Determinism: same mocked response → same parsed candles ──────


def test_same_mocked_response_produces_identical_candles() -> None:
    payload = _columnar_payload(n=4)
    request = _request_1m()
    http_post = MagicMock(side_effect=[_mock_response(payload), _mock_response(payload)])

    a = fetch_historical_candles(request, use_cache=False, access_token="t", http_post=http_post)
    b = fetch_historical_candles(request, use_cache=False, access_token="t", http_post=http_post)
    assert a.candles == b.candles


# ─── 12. AST inspection: only allowed imports ─────────────────────────


_FORBIDDEN_PREFIXES: tuple[str, ...] = (
    "openai",
    "anthropic",
    "sqlalchemy",
    "alembic",
    "asyncpg",
    "psycopg2",
    "app.db",
    "app.brokers",
    "app.services",
    # ``requests`` is not used; the existing codebase standardises on
    # ``httpx``. Pin that decision.
    "requests",
)


def _is_forbidden(name: str) -> bool:
    if not name:
        return False
    return any(name == pref or name.startswith(pref + ".") for pref in _FORBIDDEN_PREFIXES)


def _data_provider_python_files() -> list[Path]:
    pkg_root = Path(__file__).resolve().parents[3] / "app" / "strategy_engine" / "data_provider"
    return sorted(p for p in pkg_root.glob("*.py"))


@pytest.mark.parametrize("source_file", _data_provider_python_files())
def test_data_provider_module_does_not_import_forbidden_modules(
    source_file: Path,
) -> None:
    """Walk every import in every data_provider ``*.py`` and assert
    no DB/ORM, broker SDK, LLM SDK, or requests-style HTTP library
    leaks in. ``httpx`` is explicitly allowed (it's the existing
    standard)."""
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
    assert not offenders, f"{source_file.name} pulls in forbidden modules: {offenders}"


# ─── 13. Non-2xx non-retryable status surfaces error ──────────────────


def test_non_retryable_4xx_raises_dhan_fetch_error_immediately() -> None:
    """A 400 response is not retried — the error is surfaced verbatim."""
    request = _request_1m()
    bad = _mock_response(
        {"errorMessage": "Bad request", "errorCode": "DH-400"},
        status_code=400,
    )
    http_post = MagicMock(return_value=bad)
    sleep = MagicMock()

    with pytest.raises(DhanFetchError) as info:
        fetch_historical_candles(request, access_token="t", http_post=http_post, sleep_fn=sleep)
    assert info.value.status_code == 400
    assert info.value.error_code == "DH-400"
    assert "Bad request" in str(info.value)
    assert http_post.call_count == 1
    assert sleep.call_count == 0


# ─── 14. Daily timeframe routes to /charts/historical ─────────────────


def test_daily_timeframe_routes_to_daily_endpoint() -> None:
    """``timeframe="1d"`` hits ``/charts/historical`` (no ``interval``
    in the body) and uses YYYY-MM-DD date strings."""
    request = HistoricalDataRequest(
        symbol="RELIANCE",
        timeframe="1d",
        from_date=datetime(2026, 1, 1, tzinfo=UTC),
        to_date=datetime(2026, 4, 1, tzinfo=UTC),
    )
    payload = _columnar_payload(n=2, start=datetime(2026, 1, 1, tzinfo=UTC))
    http_post = MagicMock(return_value=_mock_response(payload))

    fetch_historical_candles(request, access_token="t", http_post=http_post)

    url = http_post.call_args.args[0]
    body = http_post.call_args.kwargs["json"]
    assert "/charts/historical" in url
    assert "interval" not in body
    assert body["fromDate"] == "2026-01-01"
    assert body["toDate"] == "2026-04-01"
