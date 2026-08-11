"""Unit tests for :mod:`app.services.futures_resolver` (Phase C prep).

The resolver is documented to **never raise**. Every failure mode logs
ERROR/WARNING and returns the input symbol unchanged. These tests
codify that contract and cover the date arithmetic, the N=5 entry-roll
boundary (EXPIRY_ROLLOVER_SPEC), and the separate 14:30 settlement guard
that drive BSE continuous-future resolution.

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
    _contracts_for_root,
    _entry_vehicle_policy,
    _last_thursday_of_month,
    _past_settlement,
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
# Pure helpers — _last_thursday_of_month, _entry_vehicle_policy, _past_settlement
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


class TestEntryVehiclePolicy:
    """The N-rule SELECTION POLICY (EXPIRY_ROLLOVER_SPEC): earliest
    contract with ``(expiry - today).days > N``, N=5, EXCLUSIVE."""

    _CONTRACTS = [
        ("BSE-MAY2026-FUT", date(2026, 5, 28)),
        ("BSE-JUN2026-FUT", date(2026, 6, 25)),
        ("BSE-JUL2026-FUT", date(2026, 7, 30)),
    ]

    def test_picks_front_when_comfortably_out(self) -> None:
        # Mid-May: MAY has 14 days — front month qualifies.
        picked = _entry_vehicle_policy(self._CONTRACTS, _ist(2026, 5, 14, 12, 0))
        assert picked == ("BSE-MAY2026-FUT", date(2026, 5, 28))

    def test_boundary_is_exclusive_days_equal_n_redirects(self) -> None:
        """T-5 exactly (days == 5): NOT > 5 → next month. The exclusive
        boundary is the spec's core sentence — asserted at the policy."""
        picked = _entry_vehicle_policy(self._CONTRACTS, _ist(2026, 5, 23, 10, 0))
        assert picked == ("BSE-JUN2026-FUT", date(2026, 6, 25))

    def test_days_equal_n_plus_one_keeps_front(self) -> None:
        """T-6 (days == 6): 6 > 5 → front month, last front-entry day."""
        picked = _entry_vehicle_policy(self._CONTRACTS, _ist(2026, 5, 22, 10, 0))
        assert picked == ("BSE-MAY2026-FUT", date(2026, 5, 28))

    def test_intraday_time_is_irrelevant_to_the_policy(self) -> None:
        """CALENDAR-day subtraction — 09:16 and 15:29 answer identically."""
        early = _entry_vehicle_policy(self._CONTRACTS, _ist(2026, 5, 23, 9, 16))
        late = _entry_vehicle_policy(self._CONTRACTS, _ist(2026, 5, 23, 15, 29))
        assert early == late == ("BSE-JUN2026-FUT", date(2026, 6, 25))

    def test_returns_none_when_no_contract_satisfies_n(self) -> None:
        """Spec amendment (9 Aug 2026): nothing qualifies → None, and the
        caller passes through. NEVER the dying front month."""
        only_dying = [("BSE-MAY2026-FUT", date(2026, 5, 28))]
        assert _entry_vehicle_policy(only_dying, _ist(2026, 5, 24, 10, 0)) is None

    def test_empty_contracts_returns_none(self) -> None:
        assert _entry_vehicle_policy([], _ist(2026, 5, 14)) is None

    def test_min_days_is_tunable(self) -> None:
        """N is a parameter — the depth reading can tune 5 vs 3 without
        touching the structure."""
        picked = _entry_vehicle_policy(
            self._CONTRACTS, _ist(2026, 5, 24, 10, 0), min_days_to_expiry=3
        )
        assert picked == ("BSE-MAY2026-FUT", date(2026, 5, 28))


class TestPastSettlementGuard:
    """The SEPARATE 14:30 settlement guard — protects against
    N-misconfiguration; asserted independently of the policy."""

    def test_future_expiry_not_settled(self) -> None:
        assert _past_settlement(date(2026, 5, 28), _ist(2026, 5, 14, 12, 0)) is False

    def test_expiry_day_pre_1430_not_settled(self) -> None:
        assert _past_settlement(date(2026, 5, 28), _ist(2026, 5, 28, 14, 0)) is False

    def test_expiry_day_at_1430_exact_settled(self) -> None:
        """``>= 14:30`` — the settlement instant itself is dead."""
        assert _past_settlement(date(2026, 5, 28), _ist(2026, 5, 28, 14, 30)) is True

    def test_expiry_day_post_1430_settled(self) -> None:
        assert _past_settlement(date(2026, 5, 28), _ist(2026, 5, 28, 16, 0)) is True

    def test_past_expiry_settled(self) -> None:
        assert _past_settlement(date(2026, 5, 28), _ist(2026, 6, 1, 9, 0)) is True


class TestContractsForRoot:
    """The contract UNIVERSE — ``_by_symbol`` iteration + segment/prefix filter."""

    def test_filters_by_NSE_FNO_segment(self) -> None:
        _seed_contracts(
            ("BSE-MAY2026-FUT", "NSE_FNO"),
            ("BSE-JUN2026-FUT", "NSE_EQ"),  # wrong segment — must be skipped
            ("BSE-JUL2026-FUT", "BSE_FNO"),  # wrong segment — must be skipped
        )
        contracts = _contracts_for_root("BSE")
        symbols = sorted(s for s, _ in contracts)
        assert symbols == ["BSE-MAY2026-FUT"]

    def test_filters_by_root_prefix(self) -> None:
        _seed_contracts(
            ("BSE-MAY2026-FUT", "NSE_FNO"),
            ("NIFTY-MAY2026-FUT", "NSE_FNO"),  # different root
            ("BANKNIFTY-MAY2026-FUT", "NSE_FNO"),  # different root
        )
        contracts = _contracts_for_root("BSE")
        symbols = sorted(s for s, _ in contracts)
        assert symbols == ["BSE-MAY2026-FUT"]

    def test_filters_by_FUT_suffix(self) -> None:
        _seed_contracts(
            ("BSE-MAY2026-FUT", "NSE_FNO"),
            ("BSE-MAY2026-3600-CE", "NSE_FNO"),  # option, not FUT
            ("BSE-MAY2026-3700-PE", "NSE_FNO"),  # option, not FUT
        )
        contracts = _contracts_for_root("BSE")
        assert len(contracts) == 1
        assert contracts[0][0] == "BSE-MAY2026-FUT"

    def test_bad_month_token_silently_skipped(self) -> None:
        _seed_contracts(
            ("BSE-MAY2026-FUT", "NSE_FNO"),
            ("BSE-XYZ2026-FUT", "NSE_FNO"),  # garbage month — skip
            ("BSE-JUNFOO-FUT", "NSE_FNO"),  # garbage year — skip
        )
        contracts = _contracts_for_root("BSE")
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
    """Resolve-level N-rule behavior under the last-Thursday FALLBACK
    expiry regime (no SEM_EXPIRY_DATE seeded; computed MAY = May 28).

    Pre-N history: expiry day pre-14:30 used to serve the dying front.
    Under N=5 an entry anywhere inside T-5 gets the next month — the
    expiry-day question no longer reaches the 14:30 branch for entries.
    """

    @pytest.mark.asyncio
    async def test_expiry_day_pre_1430_redirects_to_next_month(self) -> None:
        """May 28, 2026 14:00 IST — entries NEVER get the dying front,
        even while it is still technically tradeable (spec test 4)."""
        _seed_contracts(
            ("BSE-MAY2026-FUT", "NSE_FNO"),
            ("BSE-JUN2026-FUT", "NSE_FNO"),
        )
        result = await resolve_or_passthrough(
            "NSE:BSE", now_ist=_ist(2026, 5, 28, 14, 0)
        )
        assert result == "BSE-JUN2026-FUT"

    @pytest.mark.asyncio
    async def test_expiry_day_post_settlement_redirects_too(self) -> None:
        """May 28, 2026 16:00 IST — same answer after settlement."""
        _seed_contracts(
            ("BSE-MAY2026-FUT", "NSE_FNO"),
            ("BSE-JUN2026-FUT", "NSE_FNO"),
        )
        result = await resolve_or_passthrough(
            "NSE:BSE", now_ist=_ist(2026, 5, 28, 16, 0)
        )
        assert result == "BSE-JUN2026-FUT"

    @pytest.mark.asyncio
    async def test_t6_last_front_entry_day_keeps_front(self) -> None:
        """May 22 (T-6, days=6 > 5) — the LAST day the front month is
        served for entries (spec test 1, fallback regime)."""
        _seed_contracts(
            ("BSE-MAY2026-FUT", "NSE_FNO"),
            ("BSE-JUN2026-FUT", "NSE_FNO"),
        )
        result = await resolve_or_passthrough(
            "NSE:BSE", now_ist=_ist(2026, 5, 22, 10, 30)
        )
        assert result == "BSE-MAY2026-FUT"

    @pytest.mark.asyncio
    async def test_t5_first_redirect_day_serves_next(self) -> None:
        """May 23 (T-5, days=5, NOT > 5) — first redirected entry day
        (spec test 2, fallback regime; exclusive boundary)."""
        _seed_contracts(
            ("BSE-MAY2026-FUT", "NSE_FNO"),
            ("BSE-JUN2026-FUT", "NSE_FNO"),
        )
        result = await resolve_or_passthrough(
            "NSE:BSE", now_ist=_ist(2026, 5, 23, 10, 30)
        )
        assert result == "BSE-JUN2026-FUT"

    @pytest.mark.asyncio
    async def test_non_expiry_week_returns_current_month(self) -> None:
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
    async def test_real_expiry_keeps_front_where_computed_would_redirect(
        self,
    ) -> None:
        """June 20: real JUN expiry Tue 30 → days=10 > 5, JUN stays.

        The R4 discriminator under N=5: the legacy computed last-Thursday
        (Jun 25) would give days=5 → redirect to JUL. Only the REAL
        SEM_EXPIRY_DATE keeps the front month here — this test fails if
        anyone reverts to computed expiries."""
        _seed_with_expiry(
            ("CDSL-JUN2026-FUT", "NSE_FNO", date(2026, 6, 30)),
            ("CDSL-JUL2026-FUT", "NSE_FNO", date(2026, 7, 28)),
        )
        result = await resolve_or_passthrough(
            "NSE:CDSL", now_ist=_ist(2026, 6, 20, 10, 0)
        )
        assert result == "CDSL-JUN2026-FUT"

    @pytest.mark.asyncio
    async def test_pre_1430_on_real_expiry_day_redirects_for_entries(self) -> None:
        """Tue May 26 13:00 — pre-settlement, but ENTRIES are inside the
        N-window (days=0) → JUN. The dying front is exit-only territory
        (exits pin to the stored symbol downstream, never through here)."""
        _seed_with_expiry(
            ("CDSL-MAY2026-FUT", "NSE_FNO", date(2026, 5, 26)),
            ("CDSL-JUN2026-FUT", "NSE_FNO", date(2026, 6, 30)),
        )
        result = await resolve_or_passthrough(
            "NSE:CDSL", now_ist=_ist(2026, 5, 26, 13, 0)
        )
        assert result == "CDSL-JUN2026-FUT"

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
        # Computed last-Thu = May 28; on May 14 days=14 > 5 → MAY. The
        # fallback expiry feeds the SAME N-policy as a real one.
        result = await resolve_or_passthrough(
            "NSE:CDSL", now_ist=_ist(2026, 5, 14, 10, 0)
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
    re-resolved through the entry policy (inheriting N); live/future
    canonical inputs, unknown symbols, and non-FUT inputs pass through
    unchanged (deliberate selection of a still-valid contract is
    preserved)."""

    @pytest.mark.asyncio
    async def test_expired_canonical_rolls_through_entry_policy(self) -> None:
        """Wed May 27: explicit BSE-MAY2026-FUT (expired Tue 26) → JUN
        (days=34, satisfies N)."""
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


# ═══════════════════════════════════════════════════════════════════════
# N=5 entry-roll boundary — EXPIRY_ROLLOVER_SPEC test matrix 1–5
# Real SEM_EXPIRY_DATE fixtures: AUG=Tue 2026-08-25, SEP=Tue 2026-09-29.
# ═══════════════════════════════════════════════════════════════════════


_AUG = ("BSE-AUG2026-FUT", "NSE_FNO", date(2026, 8, 25))
_SEP = ("BSE-SEP2026-FUT", "NSE_FNO", date(2026, 9, 29))


class TestEntryRollBoundarySpecMatrix:
    """Spec tests 1–4: the live AUG→SEP boundary, real expiry dates.

    AUG expires Tue 25 Aug ⇒ last AUG entry day is Wed 19 Aug (T-6);
    SEP serves entries from Thu 20 Aug (T-5). EXCLUSIVE calendar
    boundary by date subtraction — never sessions.
    """

    @pytest.mark.asyncio
    async def test_1_t6_last_front_entry_day_serves_aug(self) -> None:
        _seed_with_expiry(_AUG, _SEP)
        result = await resolve_or_passthrough(
            "NSE:BSE", now_ist=_ist(2026, 8, 19, 10, 0)
        )
        assert result == "BSE-AUG2026-FUT"

    @pytest.mark.asyncio
    async def test_2_t5_first_redirect_day_serves_sep(self) -> None:
        """Both sides of the exclusive boundary: 20 Aug (days=5) → SEP."""
        _seed_with_expiry(_AUG, _SEP)
        result = await resolve_or_passthrough(
            "NSE:BSE", now_ist=_ist(2026, 8, 20, 10, 0)
        )
        assert result == "BSE-SEP2026-FUT"

    @pytest.mark.asyncio
    async def test_3_t4_serves_sep(self) -> None:
        _seed_with_expiry(_AUG, _SEP)
        result = await resolve_or_passthrough(
            "NSE:BSE", now_ist=_ist(2026, 8, 21, 10, 0)
        )
        assert result == "BSE-SEP2026-FUT"

    @pytest.mark.asyncio
    async def test_4_expiry_day_serves_sep_pre_and_post_settlement(self) -> None:
        """Expiry day 25 Aug: SEP both before AND after 14:30 — entries
        never touch the dying AUG (the 14:30 guard is asserted separately
        in TestPastSettlementGuard + the misconfiguration test below)."""
        _seed_with_expiry(_AUG, _SEP)
        pre = await resolve_or_passthrough(
            "NSE:BSE", now_ist=_ist(2026, 8, 25, 10, 0)
        )
        futures_resolver._RESOLUTION_CACHE.clear()  # same day → same key
        post = await resolve_or_passthrough(
            "NSE:BSE", now_ist=_ist(2026, 8, 25, 15, 0)
        )
        assert pre == post == "BSE-SEP2026-FUT"

    @pytest.mark.asyncio
    async def test_4b_settlement_guard_blocks_a_misconfigured_policy(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """N-misconfiguration defence: force the policy to return a
        SETTLED contract; the separate guard must refuse to serve it
        (passthrough), never letting a dying contract out the door."""
        _seed_with_expiry(_AUG, _SEP)

        def _bad_policy(*_a: Any, **_k: Any) -> tuple[str, date]:
            return ("BSE-AUG2026-FUT", date(2026, 8, 25))

        monkeypatch.setattr(futures_resolver, "_entry_vehicle_policy", _bad_policy)
        result = await resolve_or_passthrough(
            "NSE:BSE", now_ist=_ist(2026, 8, 25, 15, 0)  # post-settlement
        )
        assert result == "NSE:BSE"

    @pytest.mark.asyncio
    async def test_holiday_shifted_expiry_moves_the_boundary_with_it(
        self,
    ) -> None:
        """SEM_EXPIRY_DATE is the ONLY authority: expiry shifted to Mon
        24 Aug (holiday Tuesday) ⇒ T-6 becomes 18 Aug, T-5 becomes
        19 Aug. The boundary follows the real date, no hardcoded
        calendar."""
        shifted_aug = ("BSE-AUG2026-FUT", "NSE_FNO", date(2026, 8, 24))
        _seed_with_expiry(shifted_aug, _SEP)
        on_t6 = await resolve_or_passthrough(
            "NSE:BSE", now_ist=_ist(2026, 8, 18, 10, 0)
        )
        futures_resolver._RESOLUTION_CACHE.clear()
        on_t5 = await resolve_or_passthrough(
            "NSE:BSE", now_ist=_ist(2026, 8, 19, 10, 0)
        )
        assert on_t6 == "BSE-AUG2026-FUT"
        assert on_t5 == "BSE-SEP2026-FUT"

    @pytest.mark.asyncio
    async def test_no_next_month_listed_passes_through_never_dying_front(
        self,
    ) -> None:
        """Spec amendment (9 Aug 2026), resolve-level: only AUG listed and
        we are inside its N-window → passthrough (Dhan rejects loudly).
        Serving the dying front instead is the failure the rule exists
        to prevent."""
        _seed_with_expiry(_AUG)
        result = await resolve_or_passthrough(
            "NSE:BSE", now_ist=_ist(2026, 8, 21, 10, 0)
        )
        assert result == "NSE:BSE"


class TestEntryRollInheritance:
    """Spec test 5: every root, every alias form, and the
    expired-explicit re-roll path inherit N with zero extra wiring."""

    @pytest.mark.parametrize(
        ("alias", "root"),
        [
            ("NSE:CDSL", "CDSL"),
            ("CDSL1!", "CDSL"),
            ("NSE:ANGELONE", "ANGELONE"),
            ("ANGELONE:NSE", "ANGELONE"),
        ],
    )
    @pytest.mark.asyncio
    async def test_multi_root_aliases_redirect_at_t5(
        self, alias: str, root: str
    ) -> None:
        _seed_with_expiry(
            (f"{root}-AUG2026-FUT", "NSE_FNO", date(2026, 8, 25)),
            (f"{root}-SEP2026-FUT", "NSE_FNO", date(2026, 9, 29)),
        )
        result = await resolve_or_passthrough(
            alias, now_ist=_ist(2026, 8, 20, 10, 0)
        )
        assert result == f"{root}-SEP2026-FUT"

    @pytest.mark.asyncio
    async def test_expired_explicit_reroll_inherits_n(self) -> None:
        """A dead explicit JUL contract arriving on 21 Aug (inside AUG's
        N-window) re-resolves to SEP — NOT to the still-tradeable-but-
        dying AUG. The re-roll path funnels through the same policy."""
        _seed_with_expiry(
            ("BSE-JUL2026-FUT", "NSE_FNO", date(2026, 7, 28)),
            _AUG,
            _SEP,
        )
        result = await resolve_or_passthrough(
            "BSE-JUL2026-FUT", now_ist=_ist(2026, 8, 21, 10, 0)
        )
        assert result == "BSE-SEP2026-FUT"

    @pytest.mark.asyncio
    async def test_still_valid_explicit_contract_is_never_redirected(
        self,
    ) -> None:
        """Deliberate selection preserved: an explicit AUG symbol sent on
        21 Aug (T-4, still tradeable) passes through UNCHANGED — the
        N-rule governs continuous-form entry selection and the re-roll
        of DEAD contracts, not a live explicit choice."""
        _seed_with_expiry(_AUG, _SEP)
        result = await resolve_or_passthrough(
            "BSE-AUG2026-FUT", now_ist=_ist(2026, 8, 21, 10, 0)
        )
        assert result == "BSE-AUG2026-FUT"
