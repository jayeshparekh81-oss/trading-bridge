"""R1.2 + R1.3 — a badge may not claim more than someone actually checked.

R1.2. "Dhan se verified ✅" used to mean only that a ``final_pnl`` existed and
its attribution tag was priced. That is a statement about OUR arithmetic, not
about Dhan: it says we did a sum, not that anyone compared the sum with the
broker. The badge now requires a STORED ``truth_check_runs`` row whose window
covers the position's close and whose verdict agreed with Dhan, and it shows
THAT RUN'S DATE — so a badge can never outlive the check that earned it.

R1.3. A position closed by a hand-placed Dhan-app order is not awaiting
verification. It has its answer: "manual se band". Showing "Dhan se verify
baaki" there promises a ✅ that can never arrive, because by the founder's own
rule that trade's P&L is not counted at all.

Every rule has a falsification twin, because "never show the badge" would pass
the headline assertions while making the feature useless.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone

import pytest

from app.api.strategy_positions import covering_truth_runs

IST = timezone(timedelta(hours=5, minutes=30))

CLOSE = datetime(2026, 9, 4, 7, 41, 13, tzinfo=UTC)   # 13:11 IST
WINDOW_START = datetime(2026, 9, 4, 0, 0, tzinfo=IST)
WINDOW_END = datetime(2026, 9, 4, 23, 59, 59, tzinfo=IST)
RAN_AT = datetime(2026, 9, 4, 15, 50, tzinfo=IST)


class _Rows:
    def __init__(self, rows):
        self._rows = rows

    def mappings(self):
        return self

    def all(self):
        return self._rows


class _Session:
    """Returns whatever run rows the test wants, or raises to mimic a DB with
    migration 048 not yet applied."""

    def __init__(self, rows=None, *, boom: bool = False):
        self._rows, self._boom = rows or [], boom

    async def execute(self, _stmt=None, params=None, **_k):
        if self._boom:
            raise RuntimeError('relation "truth_check_runs" does not exist')
        # Honour the verdict filter the real query applies in SQL. A fake that
        # returned every row regardless would make the badge tests vacuous —
        # they would pass whatever `_AGREEING_VERDICTS` contained.
        allowed = set((params or {}).get("ok") or [])
        if not allowed:
            return _Rows(self._rows)
        return _Rows([r for r in self._rows if str(r.get("verdict")) in allowed])


def _run(verdict="green", *, start=WINDOW_START, end=WINDOW_END, ran_at=RAN_AT):
    return {"window_start": start, "window_end": end, "ran_at": ran_at, "verdict": verdict}


class TestTheBadgeIsEarned:
    """R1.2 — the ✅ requires a stored run, and shows that run's date."""

    @pytest.mark.asyncio
    async def test_a_covering_green_run_earns_the_badge_and_names_its_date(self) -> None:
        out = await covering_truth_runs(_Session([_run()]), [CLOSE])
        assert out[CLOSE] == "2026-09-04", "the badge must show the RUN's date"

    @pytest.mark.asyncio
    async def test_an_attention_run_no_longer_counts(self) -> None:
        """CHANGED BY A.2. It used to: a day the founder traded by hand is
        still a day our record matched the broker. The founder's rule now says
        a ✅ comes only from GREEN, so an ATTENTION day earns no badge.

        Recorded as a deliberate tightening, not a regression — if he wants
        ATTENTION to license the badge again, it is one tuple entry."""
        out = await covering_truth_runs(_Session([_run("attention")]), [CLOSE])
        assert out == {}

    @pytest.mark.asyncio
    async def test_the_date_shown_is_the_runs_date_not_the_closes(self) -> None:
        """A re-check on a later day must say so. Otherwise a badge reading
        "verified 04-09" could be backed by a run from a fortnight later that
        nobody would think to distrust — or vice versa."""
        later = datetime(2026, 9, 18, 15, 50, tzinfo=IST)
        out = await covering_truth_runs(_Session([_run(ran_at=later)]), [CLOSE])
        assert out[CLOSE] == "2026-09-18"

    @pytest.mark.asyncio
    async def test_no_stored_run_means_no_badge(self) -> None:
        assert await covering_truth_runs(_Session([]), [CLOSE]) == {}

    @pytest.mark.asyncio
    async def test_a_run_that_does_not_cover_this_close_means_no_badge(self) -> None:
        """🔴 THE ONE THAT MATTERS. A run for a DIFFERENT day must not verify
        this row. Otherwise one green Monday would silently bless every
        position in the record."""
        other = _run(
            start=datetime(2026, 9, 5, 0, 0, tzinfo=IST),
            end=datetime(2026, 9, 5, 23, 59, 59, tzinfo=IST),
        )
        assert await covering_truth_runs(_Session([other]), [CLOSE]) == {}

    @pytest.mark.asyncio
    async def test_a_missing_table_fails_closed(self) -> None:
        """Migration 048 not applied yet ⇒ "verify baaki", never a silent ✅.
        Failing OPEN here would light up every badge on the page the moment the
        query broke, which is the worst possible direction to fail."""
        assert await covering_truth_runs(_Session(boom=True), [CLOSE]) == {}

    @pytest.mark.asyncio
    async def test_a_naive_close_is_read_as_utc(self) -> None:
        """Every stored timestamp on this platform is UTC. Reading a naive one
        as local would shift it 5h30m and push a 13:11 IST close outside its
        own day's window — losing the badge for exactly the rows that have it."""
        naive = CLOSE.replace(tzinfo=None)
        out = await covering_truth_runs(_Session([_run()]), [naive])
        assert out[naive] == "2026-09-04"

    @pytest.mark.asyncio
    async def test_falsification_twin_it_is_not_a_blanket_no(self) -> None:
        """The twin. A helper that returned {} always would pass every "no
        badge" test above and silently retire the feature."""
        out = await covering_truth_runs(_Session([_run()]), [CLOSE])
        assert out != {}

    @pytest.mark.asyncio
    async def test_a_red_run_is_never_queried_for(self) -> None:
        """Reds are excluded in SQL, not in Python — so a red day cannot be
        turned into a badge by a later refactor of the loop."""
        captured: dict = {}

        class _Spy(_Session):
            async def execute(self, _stmt, params=None):
                captured.update(params or {})
                return _Rows([])

        await covering_truth_runs(_Spy(), [CLOSE])
        ok = set(captured.get("ok", []))
        assert "red" not in ok
        # A.2 (18 Sep 2026) tightened this: ONLY a stored GREEN run may license
        # a ✅. "attention" used to qualify — a day the founder traded by hand
        # is still a day our record matched — but the founder's rule now names
        # GREEN and nothing else. "no_data" must never appear here: it is the
        # verdict for a session the check could not see, and treating it as
        # agreement is precisely the false green this round removed.
        assert ok == {"green"}
        assert "attention" not in ok
        assert "no_data" not in ok


class TestAManualCloseHasItsAnswer:
    """R1.3 — a hand-closed row has its answer, and it is not "verify baaki"."""

    def test_the_manual_row_reads_manual_se_band_not_verify_baaki(self) -> None:
        """d0086394. The founder's wording, and the point of it: a fill EXISTS
        (35226091145606, BUY 200 @3215.40) — it is simply a Dhan-app order, so
        by his rule this trade's P&L is not counted. "Verify baaki" would read
        as our data being missing rather than his rule being applied."""
        from app.api.strategy_positions import manual_close_note

        note = manual_close_note(
            [
                {
                    "leg_role": "manual_close", "qty": 200, "side": "buy",
                    "price": 3215.40, "broker_order_id": "35226091145606",
                    "ts_ist": "11-09 09:31",
                }
            ]
        )
        assert note is not None
        assert "manual Dhan-app order se band" in note
        assert "P&L nahi gina" in note
        assert "no broker fill" not in note
        assert "35226091145606" in note, "the fill is named, because it exists"

    def test_falsification_twin_an_ordinary_row_gets_no_manual_note(self) -> None:
        """The twin. A note returned for every row would mark the whole record
        as hand-closed and stop every badge on the page."""
        from app.api.strategy_positions import manual_close_note

        assert manual_close_note([{"leg_role": "broker_stop", "qty": 400}]) is None
        assert manual_close_note([]) is None
        assert manual_close_note(None) is None
