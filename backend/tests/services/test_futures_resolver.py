"""Unit tests for :mod:`app.services.futures_resolver` (Phase C prep).

The resolver is documented to **never raise**. Every failure mode logs
ERROR/WARNING and returns the input symbol unchanged. These tests
codify that contract and cover the date-arithmetic + 15:30 expiry-day
rollover boundary that drives BSE continuous-future resolution.

DB / network strategy
    * No HTTP — we pre-populate the module-level
      :data:`app.brokers.dhan._SCRIP_MASTER` cache so
      ``_ensure_scrip_master_loaded`` short-circuits on
      ``is_loaded() is True`` and the ``httpx.AsyncClient`` branch is
      never exercised. The single load-failure test monkeypatches the
      lazy-loader directly to raise.
    * No frozen-time library — the public function accepts a
      ``now_ist`` kwarg, so every time-sensitive test passes the
      synthetic moment explicitly. Less magic, more readable.

Module-level state hygiene
    Both the per-day resolution cache and the scrip-master singleton
    are process-global. The autouse ``_isolate_resolver_state``
    fixture swaps both for clean per-test instances via monkeypatch
    so an earlier test's cache hit can't pollute a later one.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Any
from zoneinfo import ZoneInfo

import pytest

from app.brokers.dhan import _SCRIP_MASTER
from app.services import futures_resolver
from app.services.futures_resolver import (
    _last_thursday_of_month,
    _list_fut_contracts,
    _pick_active_contract,
    resolve_or_passthrough,
)


# IST tz-aware datetimes only — the resolver compares against
# ``ZoneInfo("Asia/Kolkata")`` internally.
_IST = ZoneInfo("Asia/Kolkata")


def _ist(year: int, month: int, day: int, hour: int = 10, minute: int = 0) -> datetime:
    """Build an IST tz-aware datetime for test inputs."""
    return datetime(year, month, day, hour, minute, 0, tzinfo=_IST)


# ═══════════════════════════════════════════════════════════════════════
# Fixtures — module-state isolation
# ═══════════════════════════════════════════════════════════════════════


@pytest.fixture(autouse=True)
def _isolate_resolver_state(monkeypatch: pytest.MonkeyPatch) -> None:
    """Reset both global caches before every test.

    * ``_RESOLUTION_CACHE`` — per-day resolved symbols. A stale entry
      from a sibling test would mask the next test's full code path.
    * ``_SCRIP_MASTER._by_symbol`` + ``_loaded_at`` — pre-populated
      empty so ``is_loaded() is True`` (skips httpx) AND the contract
      list starts empty. Individual tests then mutate ``_by_symbol``
      to seed the rows they need.
    """
    monkeypatch.setattr(futures_resolver, "_RESOLUTION_CACHE", {})
    monkeypatch.setattr(_SCRIP_MASTER, "_by_symbol", {})
    monkeypatch.setattr(_SCRIP_MASTER, "_expiry_by_symbol", {})
    monkeypatch.setattr(_SCRIP_MASTER, "_loaded_at", datetime.now(UTC))


def _seed_contracts(*entries: tuple[str, str]) -> None:
    """Populate the scrip master with ``(symbol, segment)`` keys.

    Values (security_id) are placeholder strings — the resolver only
    iterates keys, so the values don't affect any branch under test.
    """
    _SCRIP_MASTER._by_symbol = {(sym, seg): f"id-{sym}" for sym, seg in entries}


# ═══════════════════════════════════════════════════════════════════════
# Pure helpers — _last_thursday_of_month, _pick_active_contract
# ═══════════════════════════════════════════════════════════════════════


class TestLastThursdayOfMonth:
    """Calendar arithmetic for last-Thursday computation."""

    @pytest.mark.parametrize(
        ("token", "expected"),
        [
            ("MAY2026", date(2026, 5, 28)),  # last Thu = 28th
            ("JUN2026", date(2026, 6, 25)),  # 30 - (Tue=1, offset 5) → 25
            ("JUL2026", date(2026, 7, 30)),  # 31 - (Fri=4, offset 1) → 30
            ("DEC2026", date(2026, 12, 31)),  # 31st IS a Thursday
            ("JAN2027", date(2027, 1, 28)),  # year-rollover (next month = Feb)
            ("FEB2026", date(2026, 2, 26)),  # short month
        ],
    )
    def test_known_months(self, token: str, expected: date) -> None:
        assert _last_thursday_of_month(token) == expected

    def test_invalid_month_token_raises(self) -> None:
        with pytest.raises(ValueError, match="bad month/year"):
            _last_thursday_of_month("XYZ2026")

    def test_invalid_year_token_raises(self) -> None:
        with pytest.raises(ValueError, match="bad month/year"):
            _last_thursday_of_month("MAYABCD")


class TestPickActiveContract:
    """The 15:30 expiry-day boundary picker."""

    def test_picks_earliest_future_contract(self) -> None:
        contracts = [
            ("BSE-MAY2026-FUT", date(2026, 5, 28)),
            ("BSE-JUN2026-FUT", date(2026, 6, 25)),
            ("BSE-JUL2026-FUT", date(2026, 7, 30)),
        ]
        # Mid-May, well before any expiry.
        picked = _pick_active_contract(contracts, _ist(2026, 5, 14, 12, 0))
        assert picked == ("BSE-MAY2026-FUT", date(2026, 5, 28))

    def test_pre_1530_on_expiry_day_keeps_current_month(self) -> None:
        contracts = [
            ("BSE-MAY2026-FUT", date(2026, 5, 28)),
            ("BSE-JUN2026-FUT", date(2026, 6, 25)),
        ]
        picked = _pick_active_contract(contracts, _ist(2026, 5, 28, 14, 0))
        assert picked == ("BSE-MAY2026-FUT", date(2026, 5, 28))

    def test_at_1530_exact_rolls_forward(self) -> None:
        """``< 15:30`` is the predicate — 15:30:00.000 itself rolls."""
        contracts = [
            ("BSE-MAY2026-FUT", date(2026, 5, 28)),
            ("BSE-JUN2026-FUT", date(2026, 6, 25)),
        ]
        picked = _pick_active_contract(contracts, _ist(2026, 5, 28, 15, 30))
        assert picked == ("BSE-JUN2026-FUT", date(2026, 6, 25))

    def test_post_1530_on_expiry_day_rolls(self) -> None:
        contracts = [
            ("BSE-MAY2026-FUT", date(2026, 5, 28)),
            ("BSE-JUN2026-FUT", date(2026, 6, 25)),
        ]
        picked = _pick_active_contract(contracts, _ist(2026, 5, 28, 16, 0))
        assert picked == ("BSE-JUN2026-FUT", date(2026, 6, 25))

    def test_all_expired_returns_none(self) -> None:
        contracts = [
            ("BSE-MAY2026-FUT", date(2026, 5, 28)),
        ]
        picked = _pick_active_contract(contracts, _ist(2026, 6, 1, 12, 0))
        assert picked is None

    def test_empty_contracts_returns_none(self) -> None:
        assert _pick_active_contract([], _ist(2026, 5, 14)) is None


class TestListFutContracts:
    """The ``_by_symbol`` dict iteration + segment/prefix filter."""

    def test_filters_by_NSE_FNO_segment(self) -> None:
        _seed_contracts(
            ("BSE-MAY2026-FUT", "NSE_FNO"),
            ("BSE-JUN2026-FUT", "NSE_EQ"),  # wrong segment — must be skipped
            ("BSE-JUL2026-FUT", "BSE_FNO"),  # wrong segment — must be skipped
        )
        contracts = _list_fut_contracts("BSE")
        symbols = sorted(s for s, _ in contracts)
        assert symbols == ["BSE-MAY2026-FUT"]

    def test_filters_by_root_prefix(self) -> None:
        _seed_contracts(
            ("BSE-MAY2026-FUT", "NSE_FNO"),
            ("NIFTY-MAY2026-FUT", "NSE_FNO"),  # different root
            ("BANKNIFTY-MAY2026-FUT", "NSE_FNO"),  # different root
        )
        contracts = _list_fut_contracts("BSE")
        symbols = sorted(s for s, _ in contracts)
        assert symbols == ["BSE-MAY2026-FUT"]

    def test_filters_by_FUT_suffix(self) -> None:
        _seed_contracts(
            ("BSE-MAY2026-FUT", "NSE_FNO"),
            ("BSE-MAY2026-3600-CE", "NSE_FNO"),  # option, not FUT
            ("BSE-MAY2026-3700-PE", "NSE_FNO"),  # option, not FUT
        )
        contracts = _list_fut_contracts("BSE")
        assert len(contracts) == 1
        assert contracts[0][0] == "BSE-MAY2026-FUT"

    def test_bad_month_token_silently_skipped(self) -> None:
        _seed_contracts(
            ("BSE-MAY2026-FUT", "NSE_FNO"),
            ("BSE-XYZ2026-FUT", "NSE_FNO"),  # garbage month — skip
            ("BSE-JUNFOO-FUT", "NSE_FNO"),  # garbage year — skip
        )
        contracts = _list_fut_contracts("BSE")
        symbols = sorted(s for s, _ in contracts)
        assert symbols == ["BSE-MAY2026-FUT"]


# ═══════════════════════════════════════════════════════════════════════
# Public API — resolve_or_passthrough
# ═══════════════════════════════════════════════════════════════════════


class TestPassthrough:
    """Inputs the resolver explicitly does NOT touch."""

    @pytest.mark.parametrize(
        "symbol",
        ["RELIANCE", "TCS", "NIFTY", "HDFC", "INFY", "BANKNIFTY", "NSE:RELIANCE"],
    )
    @pytest.mark.asyncio
    async def test_unknown_symbols_pass_through(self, symbol: str) -> None:
        """Anything not in the TV→Dhan root map is returned unchanged."""
        # No scrip master needed — the lookup short-circuits before any DB hit.
        result = await resolve_or_passthrough(symbol, now_ist=_ist(2026, 5, 14))
        assert result == symbol

    @pytest.mark.asyncio
    async def test_empty_string_returned_unchanged(self) -> None:
        assert await resolve_or_passthrough("") == ""

    @pytest.mark.asyncio
    async def test_whitespace_only_returned_unchanged(self) -> None:
        assert await resolve_or_passthrough("   ") == "   "

    @pytest.mark.asyncio
    async def test_non_string_returned_unchanged(self) -> None:
        # The function defensively handles non-string per its
        # ``isinstance(symbol, str)`` guard. Type ignore for the test.
        result: Any = await resolve_or_passthrough(None)  # type: ignore[arg-type]
        assert result is None


class TestResolveExpiryBoundary:
    """The 15:30 IST expiry-day rollover — load-bearing for live trading."""

    @pytest.mark.asyncio
    async def test_pre_1530_on_expiry_day_returns_current_month(self) -> None:
        """May 28, 2026 14:00 IST — MAY contract still active."""
        _seed_contracts(
            ("BSE-MAY2026-FUT", "NSE_FNO"),
            ("BSE-JUN2026-FUT", "NSE_FNO"),
        )
        result = await resolve_or_passthrough(
            "NSE:BSE", now_ist=_ist(2026, 5, 28, 14, 0)
        )
        assert result == "BSE-MAY2026-FUT"

    @pytest.mark.asyncio
    async def test_post_1530_on_expiry_day_rolls_forward(self) -> None:
        """May 28, 2026 16:00 IST — MAY settled; JUN takes over."""
        _seed_contracts(
            ("BSE-MAY2026-FUT", "NSE_FNO"),
            ("BSE-JUN2026-FUT", "NSE_FNO"),
        )
        result = await resolve_or_passthrough(
            "NSE:BSE", now_ist=_ist(2026, 5, 28, 16, 0)
        )
        assert result == "BSE-JUN2026-FUT"

    @pytest.mark.asyncio
    async def test_at_1530_exact_rolls(self) -> None:
        """The boundary itself — ``< 15:30`` predicate excludes 15:30:00."""
        _seed_contracts(
            ("BSE-MAY2026-FUT", "NSE_FNO"),
            ("BSE-JUN2026-FUT", "NSE_FNO"),
        )
        result = await resolve_or_passthrough(
            "NSE:BSE", now_ist=_ist(2026, 5, 28, 15, 30)
        )
        assert result == "BSE-JUN2026-FUT"

    @pytest.mark.asyncio
    async def test_non_expiry_day_returns_current_month(self) -> None:
        """Mid-May, no rollover question — MAY contract is the answer."""
        _seed_contracts(
            ("BSE-MAY2026-FUT", "NSE_FNO"),
            ("BSE-JUN2026-FUT", "NSE_FNO"),
        )
        result = await resolve_or_passthrough(
            "NSE:BSE", now_ist=_ist(2026, 5, 14, 10, 30)
        )
        assert result == "BSE-MAY2026-FUT"


class TestFailurePathsPassthrough:
    """Resolver contract: every failure mode returns input unchanged."""

    @pytest.mark.asyncio
    async def test_no_contracts_in_scrip_master_passthrough(self) -> None:
        """Scrip master loaded but holds zero BSE-*-FUT rows."""
        _seed_contracts(
            ("NIFTY-MAY2026-FUT", "NSE_FNO"),  # different root
            ("RELIANCE", "NSE_EQ"),
        )
        result = await resolve_or_passthrough(
            "NSE:BSE", now_ist=_ist(2026, 5, 14)
        )
        # No BSE futures → log error → return original.
        assert result == "NSE:BSE"

    @pytest.mark.asyncio
    async def test_all_contracts_already_expired_passthrough(self) -> None:
        """Today is past every contract's expiry → no active contract."""
        _seed_contracts(("BSE-MAY2026-FUT", "NSE_FNO"))
        result = await resolve_or_passthrough(
            "NSE:BSE", now_ist=_ist(2026, 7, 1, 10, 0)
        )
        assert result == "NSE:BSE"

    @pytest.mark.asyncio
    async def test_scrip_master_load_failure_passthrough(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The lazy-loader raises → resolver swallows + returns input."""

        # Force the resolver to take the load path: claim "not loaded".
        monkeypatch.setattr(_SCRIP_MASTER, "_loaded_at", None)

        async def _boom() -> None:
            raise RuntimeError("simulated scrip master HTTP failure")

        monkeypatch.setattr(
            futures_resolver, "_ensure_scrip_master_loaded", _boom
        )
        result = await resolve_or_passthrough(
            "NSE:BSE", now_ist=_ist(2026, 5, 14)
        )
        assert result == "NSE:BSE"

    @pytest.mark.asyncio
    async def test_expiry_more_than_60_days_out_passthrough(self) -> None:
        """Sanity bound — picked contract too far in the future is rejected."""
        # Today is Mar 1, 2026; only AUG2026 (Aug 27 — 179 days out) is
        # in the scrip. The picker returns it; the days_to_expiry guard
        # then rejects.
        _seed_contracts(("BSE-AUG2026-FUT", "NSE_FNO"))
        result = await resolve_or_passthrough(
            "BSE", now_ist=_ist(2026, 3, 1, 10, 0)
        )
        assert result == "BSE"  # passthrough — over the 60-day bound.


class TestSymbolAliasMapping:
    """Every TV-side alias resolves to the same canonical Dhan contract."""

    @pytest.mark.parametrize(
        "alias",
        ["NSE:BSE", "BSE:NSE", "BSE", "BSE1!"],
    )
    @pytest.mark.asyncio
    async def test_all_four_aliases_resolve_consistently(
        self, alias: str
    ) -> None:
        _seed_contracts(("BSE-MAY2026-FUT", "NSE_FNO"))
        result = await resolve_or_passthrough(
            alias, now_ist=_ist(2026, 5, 14, 12, 0)
        )
        assert result == "BSE-MAY2026-FUT"

    @pytest.mark.asyncio
    async def test_lowercase_input_uppercased_for_lookup(self) -> None:
        """The function does ``symbol.strip().upper()`` before mapping."""
        _seed_contracts(("BSE-MAY2026-FUT", "NSE_FNO"))
        result = await resolve_or_passthrough(
            "nse:bse", now_ist=_ist(2026, 5, 14, 12, 0)
        )
        assert result == "BSE-MAY2026-FUT"

    @pytest.mark.asyncio
    async def test_input_with_surrounding_whitespace(self) -> None:
        """Strip + upper should normalise leading/trailing whitespace."""
        _seed_contracts(("BSE-MAY2026-FUT", "NSE_FNO"))
        result = await resolve_or_passthrough(
            "  BSE  ", now_ist=_ist(2026, 5, 14, 12, 0)
        )
        assert result == "BSE-MAY2026-FUT"


class TestCaching:
    """Per-day cache short-circuits the second call."""

    @pytest.mark.asyncio
    async def test_second_call_serves_from_cache(self) -> None:
        _seed_contracts(("BSE-MAY2026-FUT", "NSE_FNO"))
        now = _ist(2026, 5, 14, 12, 0)

        first = await resolve_or_passthrough("NSE:BSE", now_ist=now)
        # Mutate scrip master AFTER the first call; if the cache works,
        # the second call still returns the original answer.
        _SCRIP_MASTER._by_symbol = {("BSE-JUN2026-FUT", "NSE_FNO"): "id-X"}
        second = await resolve_or_passthrough("NSE:BSE", now_ist=now)

        assert first == "BSE-MAY2026-FUT"
        assert second == "BSE-MAY2026-FUT"  # cache hit, not the post-mutation value
        # Cache key shape is documented contract.
        assert ("BSE", now.date().isoformat()) in futures_resolver._RESOLUTION_CACHE

    @pytest.mark.asyncio
    async def test_ensure_scrip_master_loaded_takes_load_path(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Cover the lazy-load body when ``is_loaded() is False``.

        The autouse fixture seeds ``_loaded_at`` to "now" so every other
        test skips this branch; here we deliberately reset it and stub
        ``_SCRIP_MASTER.ensure_loaded`` to a no-op so the inner
        ``async with httpx.AsyncClient`` + ``ensure_loaded`` call site
        is exercised without any real HTTP round-trip.
        """
        monkeypatch.setattr(_SCRIP_MASTER, "_loaded_at", None)
        called = {"n": 0}

        async def _stub_ensure_loaded(*_args: Any, **_kwargs: Any) -> None:
            called["n"] += 1
            # Mark as loaded so the resolver's downstream lookups have
            # a non-empty (well, empty-but-loaded) state to inspect.
            _SCRIP_MASTER._loaded_at = datetime.now(UTC)

        monkeypatch.setattr(_SCRIP_MASTER, "ensure_loaded", _stub_ensure_loaded)
        await futures_resolver._ensure_scrip_master_loaded()
        assert called["n"] == 1

    @pytest.mark.asyncio
    async def test_different_day_does_not_share_cache(self) -> None:
        """Cache is keyed by ``today_iso`` — a new day misses."""
        _seed_contracts(("BSE-MAY2026-FUT", "NSE_FNO"))
        first = await resolve_or_passthrough(
            "NSE:BSE", now_ist=_ist(2026, 5, 14, 12, 0)
        )
        # Same scrip master content → same answer, but it's a fresh
        # cache lookup (different day key).
        second = await resolve_or_passthrough(
            "NSE:BSE", now_ist=_ist(2026, 5, 15, 12, 0)
        )
        assert first == second == "BSE-MAY2026-FUT"
        assert len(futures_resolver._RESOLUTION_CACHE) == 2


# ═══════════════════════════════════════════════════════════════════════
# R4 — real SEM_EXPIRY_DATE drives rollover (not computed last-Thursday)
# ═══════════════════════════════════════════════════════════════════════


def _seed_with_expiry(*entries: tuple[str, str, date]) -> None:
    """Seed both ``_by_symbol`` and ``_expiry_by_symbol``.

    ``entries`` are ``(symbol, segment, real_expiry)``. This mirrors what
    :meth:`_ScripMaster._parse` builds from SEM_EXPIRY_DATE so the resolver
    reads the published expiry via ``expiry_for`` instead of recomputing.
    """
    _SCRIP_MASTER._by_symbol = {(s, seg): f"id-{s}" for s, seg, _ in entries}
    _SCRIP_MASTER._expiry_by_symbol = {(s, seg): exp for s, seg, exp in entries}


class TestRealExpiryDrivesRollover:
    """The R4 fix: NSE moved monthly stock F&O expiry to the last Tuesday.

    Real expiries (Dhan SEM_EXPIRY_DATE): MAY=Tue 2026-05-26,
    JUN=Tue 2026-06-30, JUL=Tue 2026-07-28. The legacy last-Thursday
    computation would say MAY=Thu 28 / JUN=Thu 25, which both mis-rolled.
    """

    @pytest.mark.asyncio
    async def test_post_real_expiry_rolls_forward_not_late(self) -> None:
        """May 27: MAY expired Tue 26 → must serve JUN (was the late-roll bug)."""
        _seed_with_expiry(
            ("CDSL-MAY2026-FUT", "NSE_FNO", date(2026, 5, 26)),
            ("CDSL-JUN2026-FUT", "NSE_FNO", date(2026, 6, 30)),
        )
        result = await resolve_or_passthrough(
            "NSE:CDSL", now_ist=_ist(2026, 5, 27, 10, 0)
        )
        assert result == "CDSL-JUN2026-FUT"

    @pytest.mark.asyncio
    async def test_no_early_roll_when_real_expiry_after_computed(self) -> None:
        """June 26: JUN live until Tue 30 → must NOT roll to JUL (early-roll bug)."""
        _seed_with_expiry(
            ("CDSL-JUN2026-FUT", "NSE_FNO", date(2026, 6, 30)),
            ("CDSL-JUL2026-FUT", "NSE_FNO", date(2026, 7, 28)),
        )
        result = await resolve_or_passthrough(
            "NSE:CDSL", now_ist=_ist(2026, 6, 26, 10, 0)
        )
        assert result == "CDSL-JUN2026-FUT"

    @pytest.mark.asyncio
    async def test_pre_1430_on_real_expiry_day_keeps_month(self) -> None:
        """Tue May 26 13:00 — pre-14:30 settlement, MAY still active."""
        _seed_with_expiry(
            ("CDSL-MAY2026-FUT", "NSE_FNO", date(2026, 5, 26)),
            ("CDSL-JUN2026-FUT", "NSE_FNO", date(2026, 6, 30)),
        )
        result = await resolve_or_passthrough(
            "NSE:CDSL", now_ist=_ist(2026, 5, 26, 13, 0)
        )
        assert result == "CDSL-MAY2026-FUT"

    @pytest.mark.asyncio
    async def test_post_1430_on_real_expiry_day_rolls(self) -> None:
        """Tue May 26 15:00 — post-14:30 settlement, JUN takes over."""
        _seed_with_expiry(
            ("CDSL-MAY2026-FUT", "NSE_FNO", date(2026, 5, 26)),
            ("CDSL-JUN2026-FUT", "NSE_FNO", date(2026, 6, 30)),
        )
        result = await resolve_or_passthrough(
            "NSE:CDSL", now_ist=_ist(2026, 5, 26, 15, 0)
        )
        assert result == "CDSL-JUN2026-FUT"

    @pytest.mark.asyncio
    async def test_falls_back_to_last_thursday_when_master_omits_expiry(
        self,
    ) -> None:
        """No SEM_EXPIRY_DATE → legacy last-Thursday fallback (back-compat)."""
        # _by_symbol present, _expiry_by_symbol empty → expiry_for() is None.
        _SCRIP_MASTER._by_symbol = {("CDSL-MAY2026-FUT", "NSE_FNO"): "id-x"}
        _SCRIP_MASTER._expiry_by_symbol = {}
        # Computed last-Thu = May 28; on May 27 it's still "future" → MAY.
        result = await resolve_or_passthrough(
            "NSE:CDSL", now_ist=_ist(2026, 5, 27, 10, 0)
        )
        assert result == "CDSL-MAY2026-FUT"

    @pytest.mark.asyncio
    async def test_bse_uses_real_expiry_too(self) -> None:
        """The live BSE strategy benefits identically (same Tuesday expiry)."""
        _seed_with_expiry(
            ("BSE-MAY2026-FUT", "NSE_FNO", date(2026, 5, 26)),
            ("BSE-JUN2026-FUT", "NSE_FNO", date(2026, 6, 30)),
        )
        result = await resolve_or_passthrough(
            "NSE:BSE", now_ist=_ist(2026, 5, 27, 10, 0)
        )
        assert result == "BSE-JUN2026-FUT"

    @pytest.mark.asyncio
    async def test_already_canonical_symbol_passes_through(self) -> None:
        """A resolved contract symbol isn't a TV form → returned unchanged."""
        _seed_with_expiry(
            ("BSE-MAY2026-FUT", "NSE_FNO", date(2026, 5, 26)),
        )
        result = await resolve_or_passthrough(
            "BSE-MAY2026-FUT", now_ist=_ist(2026, 5, 25, 12, 0)
        )
        assert result == "BSE-MAY2026-FUT"


# ═══════════════════════════════════════════════════════════════════════
# Expired-canonical roll-forward (backend mitigation for hardcoded inputs)
# ═══════════════════════════════════════════════════════════════════════


class TestExpiredCanonicalRollforward:
    """An explicit canonical FUT whose OWN contract has already expired is
    rolled to the active front month; live/future canonical inputs, unknown
    symbols, and non-FUT inputs pass through unchanged (deliberate selection
    of a still-valid contract is preserved)."""

    @pytest.mark.asyncio
    async def test_expired_canonical_rolls_to_front_month(self) -> None:
        """Wed May 27: explicit BSE-MAY2026-FUT (expired Tue 26) → JUN."""
        _seed_with_expiry(
            ("BSE-MAY2026-FUT", "NSE_FNO", date(2026, 5, 26)),
            ("BSE-JUN2026-FUT", "NSE_FNO", date(2026, 6, 30)),
        )
        result = await resolve_or_passthrough(
            "BSE-MAY2026-FUT", now_ist=_ist(2026, 5, 27, 10, 0)
        )
        assert result == "BSE-JUN2026-FUT"

    @pytest.mark.asyncio
    async def test_live_canonical_passes_through_unchanged(self) -> None:
        """Wed May 27: explicit BSE-JUN2026-FUT (live until Jun 30) → unchanged."""
        _seed_with_expiry(
            ("BSE-MAY2026-FUT", "NSE_FNO", date(2026, 5, 26)),
            ("BSE-JUN2026-FUT", "NSE_FNO", date(2026, 6, 30)),
        )
        result = await resolve_or_passthrough(
            "BSE-JUN2026-FUT", now_ist=_ist(2026, 5, 27, 10, 0)
        )
        assert result == "BSE-JUN2026-FUT"

    @pytest.mark.asyncio
    async def test_pre_expiry_canonical_passes_through(self) -> None:
        """May 25 (pre-expiry): BSE-MAY2026-FUT not yet expired → unchanged."""
        _seed_with_expiry(
            ("BSE-MAY2026-FUT", "NSE_FNO", date(2026, 5, 26)),
            ("BSE-JUN2026-FUT", "NSE_FNO", date(2026, 6, 30)),
        )
        result = await resolve_or_passthrough(
            "BSE-MAY2026-FUT", now_ist=_ist(2026, 5, 25, 10, 0)
        )
        assert result == "BSE-MAY2026-FUT"

    @pytest.mark.asyncio
    async def test_expiry_day_pre_close_keeps_contract(self) -> None:
        """Tue May 26 13:00 (< 14:30): MAY still tradeable → unchanged."""
        _seed_with_expiry(
            ("BSE-MAY2026-FUT", "NSE_FNO", date(2026, 5, 26)),
            ("BSE-JUN2026-FUT", "NSE_FNO", date(2026, 6, 30)),
        )
        result = await resolve_or_passthrough(
            "BSE-MAY2026-FUT", now_ist=_ist(2026, 5, 26, 13, 0)
        )
        assert result == "BSE-MAY2026-FUT"

    @pytest.mark.asyncio
    async def test_expiry_day_post_close_rolls(self) -> None:
        """Tue May 26 15:00 (≥ 14:30): MAY settled → JUN."""
        _seed_with_expiry(
            ("BSE-MAY2026-FUT", "NSE_FNO", date(2026, 5, 26)),
            ("BSE-JUN2026-FUT", "NSE_FNO", date(2026, 6, 30)),
        )
        result = await resolve_or_passthrough(
            "BSE-MAY2026-FUT", now_ist=_ist(2026, 5, 26, 15, 0)
        )
        assert result == "BSE-JUN2026-FUT"

    @pytest.mark.asyncio
    async def test_canonical_unknown_to_master_passes_through(self) -> None:
        """Canonical shape but no expiry in the master → unchanged (no roll)."""
        _seed_with_expiry(("BSE-MAY2026-FUT", "NSE_FNO", date(2026, 5, 26)))
        result = await resolve_or_passthrough(
            "FOO-MAY2026-FUT", now_ist=_ist(2026, 5, 27, 10, 0)
        )
        assert result == "FOO-MAY2026-FUT"

    @pytest.mark.asyncio
    async def test_non_fut_input_passes_through(self) -> None:
        """A plain equity symbol isn't canonical-FUT shaped → unchanged."""
        _seed_with_expiry(("BSE-MAY2026-FUT", "NSE_FNO", date(2026, 5, 26)))
        result = await resolve_or_passthrough(
            "RELIANCE", now_ist=_ist(2026, 5, 27, 10, 0)
        )
        assert result == "RELIANCE"

    @pytest.mark.asyncio
    async def test_expired_but_no_live_contract_returns_original(self) -> None:
        """Expired explicit contract, nothing live to roll to → original
        (Dhan will reject; the resolver never fabricates a contract)."""
        _seed_with_expiry(("BSE-MAY2026-FUT", "NSE_FNO", date(2026, 5, 26)))
        result = await resolve_or_passthrough(
            "BSE-MAY2026-FUT", now_ist=_ist(2026, 5, 27, 10, 0)
        )
        assert result == "BSE-MAY2026-FUT"
