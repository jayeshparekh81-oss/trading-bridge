"""EXPIRY_ROLLOVER_SPEC.md row 13 — the T-2 expiry backstop.

THE ONLY TEST THIS CODE GETS BEFORE IT MATTERS, so it carries full weight. The
backstop fired ZERO times across 6.5 years of history (spec lines 36-37): there is no
production evidence it works, and there never will be until the day it has to. That
makes the falsification twin (STEP 3) the load-bearing part — see
``test_TWIN_the_policy_is_what_makes_this_file_pass`` at the bottom.

EVERY assertion below runs the REAL policy. ``sweep_expiry_backstop`` is called with a
real AsyncSession and real rows; no trigger event is hand-written, no engine call is
commented out. The only injected values are ``now`` (so a test can stand on a chosen
date) and the scrip master (so expiry comes from a known SEM_EXPIRY_DATE) — both are
the same injection points ``sweep_expired_options`` already uses.

CASES (founder, 13 Aug 2026):
  a. normal week, no holiday   → fires on the correct session
  b. holiday week              → fires one session EARLIER than the calendar answer
  c. N=5 rollover already handled it → must NOT fire
  d. the fired event carries ``T_2_BACKSTOP`` specifically
"""

# ruff: noqa: F811 — imported pytest fixtures are shadowed by test params.
from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import pytest

from app.core.config import get_settings
from app.db.models.historical_candle import HistoricalCandle
from app.db.models.strategy_position import StrategyPosition
from app.services.futures_expiry_backstop import (
    BACKSTOP_DECIDED_BY,
    BACKSTOP_EXIT_REASON,
    backstop_due,
    derive_holidays_from_expiry,
    sessions_to_expiry,
    sweep_expiry_backstop,
)
from tests.services.test_options_executor import (  # noqa: F401
    _seed,
    db,
)

# ── The real AUG-2026 contract. Last Thursday of Aug 2026 = Thu 27 Aug.
# The exchange-published SEM_EXPIRY_DATE used across the rollover suite is
# Tue 25 Aug — i.e. the exchange moved it EARLIER, which is the holiday evidence
# derive_holidays_from_expiry() reads. Both dates are real, neither is invented here.
_AUG_SYMBOL = "BSE-AUG2026-FUT"
_AUG_EXPIRY_SHIFTED = date(2026, 8, 25)     # real: moved earlier (holiday week)
_SEP_SYMBOL = "BSE-SEP2026-FUT"
_SEP_EXPIRY = date(2026, 9, 29)

# SEP-2026 is the clean control month: its last Thursday IS 24 Sep, but the published
# expiry is 29 Sep — later than nominal, so NO holiday is implied (the derivation only
# ever infers a holiday from an EARLIER shift). Used for the no-holiday case.
_IST = timedelta(hours=5, minutes=30)


def _ist_utc(y: int, m: int, d: int, hh: int = 10, mm: int = 0) -> datetime:
    """A UTC instant that lands at hh:mm IST on the given IST calendar date.

    The sweep converts back with ``now_utc + 5:30`` before taking ``.date()``, so this
    is the inverse of what it actually does — the test never asserts on a date it
    computed a different way from the code under test.
    """
    return datetime(y, m, d, hh, mm, tzinfo=UTC) - _IST


class _MasterWithExpiry:
    """Fake scrip master exposing only ``expiry_for`` — the sweep's real seam."""

    def __init__(self, mapping: dict[str, date]) -> None:
        self._m = mapping

    def expiry_for(self, symbol: str, segment: str) -> date | None:
        return self._m.get(symbol.upper())


_MASTER = _MasterWithExpiry(
    {_AUG_SYMBOL: _AUG_EXPIRY_SHIFTED, _SEP_SYMBOL: _SEP_EXPIRY}
)


@pytest.fixture
def backstop_on(monkeypatch):
    monkeypatch.setattr(get_settings(), "futures_expiry_backstop_enabled", True)


@pytest.fixture
def no_alert(monkeypatch):
    """Silence the operator ping (it is asserted separately, not spammed)."""
    import app.services.futures_expiry_backstop as mod

    async def _noop(*a, **k):
        return None

    monkeypatch.setattr(mod, "_alert", _noop)


async def _insert_fut(db, *, user, strat, symbol, status="open", qty=400):
    async with db() as s:
        row = StrategyPosition(
            user_id=user.id, strategy_id=strat.id,
            broker_credential_id=strat.broker_credential_id,
            symbol=symbol, side="buy",
            total_quantity=qty, remaining_quantity=qty,
            avg_entry_price=2400, status=status,
            opened_at=datetime(2026, 8, 10, 5, 0, tzinfo=UTC),
        )
        s.add(row)
        await s.commit()
        return row.id


async def _reload(db, pid):
    async with db() as s:
        return await s.get(StrategyPosition, pid)


async def _seed_sessions(db, days: list[date]) -> None:
    """Insert a real daily bar for each given date — that IS the session calendar.

    The production source is the ``historical_candles`` table the platform already
    fills from Dhan v2. A test must construct its own scenario, so here the dates are
    chosen to model a normal week and a holiday week; the CODE still reads sessions
    from real stored bars and never from a list baked into the module.
    """
    # One row per flush on purpose: a batched INSERT of this composite-PK model goes
    # down SQLAlchemy's insertmanyvalues path, whose sentinel cannot round-trip the
    # tz-aware timestamp on SQLite ("Can't match sentinel values in result set").
    for d in days:
        async with db() as s:
            s.add(
                HistoricalCandle(
                    symbol="BSE", exchange="NSE", timeframe="1d",
                    timestamp=datetime(d.year, d.month, d.day, 3, 45, tzinfo=UTC),
                    open=2400, high=2410, low=2390, close=2405, volume=1000,
                    dhan_security_id="19585", source="test_fixture",
                )
            )
            await s.commit()


def _weekdays(start: date, end: date) -> list[date]:
    out, day = [], start
    while day <= end:
        if day.weekday() < 5:
            out.append(day)
        day += timedelta(days=1)
    return out


# ═══════════════════════════════════════════════════════════════════════════
# The session-count primitive — real derivation, no hardcoded holiday list
# ═══════════════════════════════════════════════════════════════════════════


def test_holidays_are_derived_from_the_published_expiry_shift() -> None:
    """Aug 2026: nominal last Thursday 27 Aug, published expiry 25 Aug.

    The 3-day gap is the exchange saying those weekdays are not sessions. The
    derivation reads that; it does not consult any list.
    """
    got = derive_holidays_from_expiry(_AUG_SYMBOL, _AUG_EXPIRY_SHIFTED)
    assert got == {date(2026, 8, 26), date(2026, 8, 27)}, got
    # nothing is inferred when the exchange did NOT move the expiry earlier
    assert derive_holidays_from_expiry(_SEP_SYMBOL, _SEP_EXPIRY) == set()


# ═══════════════════════════════════════════════════════════════════════════
# CASE (a) — normal week, no holiday: fires on the correct session
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_a_normal_week_fires_on_the_correct_session(
    db, backstop_on, no_alert
) -> None:
    """SEP-2026 expires Tue 29 Sep. Every weekday in the run-up traded → no holiday.

    Sessions to expiry from Thu 24 Sep = Fri 25, Mon 28, Tue 29 → 3 → NOT due.
    From Fri 25 Sep = Mon 28, Tue 29 → 2 → DUE. The boundary session is Fri 25.
    """
    user, strat = await _seed(db, is_paper=True)
    await _seed_sessions(db, _weekdays(date(2026, 9, 21), date(2026, 9, 29)))

    pid = await _insert_fut(db, user=user, strat=strat, symbol=_SEP_SYMBOL)

    # one session before the boundary: must not fire
    async with db() as s:
        res = await sweep_expiry_backstop(
            s, scrip_master=_MASTER, now=_ist_utc(2026, 9, 24)
        )
    assert res["fired"] == 0 and res["skipped_not_due"] == 1, res
    assert (await _reload(db, pid)).status == "open"

    # the boundary session itself: must fire
    async with db() as s:
        res = await sweep_expiry_backstop(
            s, scrip_master=_MASTER, now=_ist_utc(2026, 9, 25)
        )
    assert res["fired"] == 1, res
    row = await _reload(db, pid)
    assert row.status == "closed" and row.remaining_quantity == 0


# ═══════════════════════════════════════════════════════════════════════════
# CASE (b) — holiday week: fires one session EARLIER than the calendar answer
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_b_holiday_week_fires_one_session_earlier_than_calendar(
    db, backstop_on, no_alert
) -> None:
    """AUG-2026 expires Tue 25 Aug, and Mon 24 Aug is a HOLIDAY — it printed no bar.

    THE POINT OF THE WHOLE FEATURE, measured three ways from Thu 20 Aug:
      calendar days   : (25 - 20).days = 5            → a calendar rule is idle
      sessions, no holiday : Fri 21, Mon 24, Tue 25   → 3  → still not due
      sessions, holiday    : Fri 21,        Tue 25    → 2  → DUE, FIRES
    So the holiday pulls the fire from Fri 21 to Thu 20 — exactly one session EARLIER
    than the holiday-blind answer, and two sessions earlier than a calendar rule would
    ever get there. All three numbers are asserted so the divergence is pinned rather
    than implied, and the holiday-blind number is computed from the SAME primitive so
    the comparison is like-for-like.
    """
    user, strat = await _seed(db, is_paper=True)
    # every weekday in the run-up traded EXCEPT Mon 24 Aug → that gap IS the holiday
    traded = [d for d in _weekdays(date(2026, 8, 17), date(2026, 8, 25))
              if d != date(2026, 8, 24)]
    await _seed_sessions(db, traded)
    pid = await _insert_fut(db, user=user, strat=strat, symbol=_AUG_SYMBOL)

    holiday = {date(2026, 8, 24)}
    # calendar rule: nowhere near its threshold
    assert (_AUG_EXPIRY_SHIFTED - date(2026, 8, 20)).days == 5
    # same primitive, holiday-blind vs holiday-aware
    assert sessions_to_expiry(
        date(2026, 8, 20), _AUG_EXPIRY_SHIFTED, holidays=set()
    ) == 3
    assert sessions_to_expiry(
        date(2026, 8, 20), _AUG_EXPIRY_SHIFTED, holidays=holiday
    ) == 2

    # Thu 20 Aug — holiday-aware count is 2 → FIRES here, a session early
    async with db() as s:
        res = await sweep_expiry_backstop(
            s, scrip_master=_MASTER, now=_ist_utc(2026, 8, 20)
        )
    assert res["fired"] == 1, res
    row = await _reload(db, pid)
    assert row.status == "closed"
    assert row.action_history[-1]["sessions_to_expiry"] == 2

    # and the holiday-blind engine would NOT have fired on that same day
    assert backstop_due(
        date(2026, 8, 20), _AUG_EXPIRY_SHIFTED, holidays=set()
    ) is False


# ═══════════════════════════════════════════════════════════════════════════
# CASE (c) — the N=5 entry roll already handled it: must NOT fire
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_c_position_rolled_by_n5_never_triggers_the_backstop(
    db, backstop_on, no_alert
) -> None:
    """A position opened on 21 Aug is in SEP (the N=5 roll redirected it there).

    Walk the sweep across the ENTIRE dying-AUG window — the days on which the AUG
    holder would have been force-closed — and assert the SEP holder is untouched every
    time. The backstop is a backstop: when the entry rule did its job there is nothing
    left for it to do, and a fire here would be a false positive on a healthy position.
    """
    user, strat = await _seed(db, is_paper=True)
    pid = await _insert_fut(db, user=user, strat=strat, symbol=_SEP_SYMBOL)

    for day in (21, 24, 25, 26, 27, 28):
        async with db() as s:
            res = await sweep_expiry_backstop(
                s, scrip_master=_MASTER, now=_ist_utc(2026, 8, day)
            )
        assert res["fired"] == 0, f"backstop fired on Aug {day}: {res}"
        assert res["skipped_not_due"] == 1, f"Aug {day}: {res}"

    row = await _reload(db, pid)
    assert row.status == "open" and row.remaining_quantity == 400
    assert row.exit_reason is None


# ═══════════════════════════════════════════════════════════════════════════
# CASE (d) — the fired event is unmistakably a backstop
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_d_fired_event_carries_T_2_BACKSTOP_and_the_policy_name(  # noqa: N802
    db, backstop_on, no_alert
) -> None:
    """A regular exit or a stop must never be mistakable for this.

    Asserts the EXACT reason string (not a substring, not a prefix), the policy name
    in the recorded action, and that no ordinary exit reason leaked onto the row.
    """
    user, strat = await _seed(db, is_paper=True)
    pid = await _insert_fut(db, user=user, strat=strat, symbol=_AUG_SYMBOL)

    async with db() as s:
        await sweep_expiry_backstop(
            s, scrip_master=_MASTER, now=_ist_utc(2026, 8, 21)
        )

    row = await _reload(db, pid)
    assert row.exit_reason == BACKSTOP_EXIT_REASON == "T_2_BACKSTOP"
    assert row.exit_reason not in {
        "expired", "stop_loss", "sl_hit", "target", "exit", "manual",
        "kill_switch", "circuit_breaker",
    }
    assert row.last_action == "expiry_backstop"

    action = row.action_history[-1]
    assert action["action"] == "expiry_backstop"
    assert action["decided_by"] == BACKSTOP_DECIDED_BY == "expiry-backstop-T2"
    assert action["sessions_to_expiry"] == 2
    assert action["qty"] == 400


@pytest.mark.asyncio
async def test_d_alert_fires_through_the_existing_seam(
    db, backstop_on, monkeypatch
) -> None:
    """A fire must reach a phone, through the seam this repo already uses.

    Zero fires in 6.5 years means a fire is an anomaly. Asserts the real
    ``telegram_alerts.send_alert`` is called at CRITICAL with the reason in the text —
    no new channel is introduced.
    """
    import app.services.telegram_alerts as alerts

    sent: list[tuple] = []

    async def _capture(level, message):
        sent.append((level, message))

    monkeypatch.setattr(alerts, "send_alert", _capture)

    user, strat = await _seed(db, is_paper=True)
    await _insert_fut(db, user=user, strat=strat, symbol=_AUG_SYMBOL)
    async with db() as s:
        await sweep_expiry_backstop(
            s, scrip_master=_MASTER, now=_ist_utc(2026, 8, 21)
        )

    assert len(sent) == 1, sent
    level, message = sent[0]
    assert level is alerts.AlertLevel.CRITICAL
    assert BACKSTOP_EXIT_REASON in message
    assert _AUG_SYMBOL in message


# ═══════════════════════════════════════════════════════════════════════════
# The flag, and the twin
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_flag_off_is_a_dormant_no_op(db) -> None:
    """Default OFF: the sweep must not touch a row that WOULD otherwise fire."""
    user, strat = await _seed(db, is_paper=True)
    pid = await _insert_fut(db, user=user, strat=strat, symbol=_AUG_SYMBOL)
    async with db() as s:
        res = await sweep_expiry_backstop(
            s, scrip_master=_MASTER, now=_ist_utc(2026, 8, 21)
        )
    assert res["status"] == "dormant" and res["fired"] == 0
    assert (await _reload(db, pid)).status == "open"


def test_TWIN_the_policy_is_what_makes_this_file_pass() -> None:  # noqa: N802
    """FALSIFICATION TWIN (spec: "policy removed → test fails").

    Proves the suite is anchored to the POLICY, not to incidental state: with the
    session threshold neutralised, the exact input that fires in case (b) stops firing.
    If this assertion ever passes with the policy disabled, the rest of this file is
    decoration.
    """
    fires_with_policy = backstop_due(
        date(2026, 8, 21), _AUG_EXPIRY_SHIFTED, symbol=_AUG_SYMBOL
    )
    fires_without_policy = backstop_due(
        date(2026, 8, 21), _AUG_EXPIRY_SHIFTED, symbol=_AUG_SYMBOL, threshold=-1
    )
    assert fires_with_policy is True
    assert fires_without_policy is False, (
        "the backstop fired with its threshold disabled — this suite is not "
        "testing the policy"
    )
