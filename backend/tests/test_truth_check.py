"""R3 — the site must equal Dhan, and the founder hears the same day.

BOTH VERDICTS ARE PROVEN. A checker that could only go green would pass a
"happy day" test forever while never catching anything; a checker that could
only go red would train the founder to ignore it within a week. So every rule
here is paired: the thing that must alarm, and the neighbouring case that must
stay quiet.

THE FOUR REDS: a fill we never recorded, a fill we cannot identify, a manual
trade on the bot's own symbol, and a duplicate exit.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from typing import ClassVar

from app.domains.pnl_reconciler.attribution import AccountFill
from app.domains.pnl_reconciler.truth_check import (
    ATTENTION,
    GREEN,
    MORNING,
    NO_DATA,
    RED,
    SAME_DAY,
    TruthCheckResult,
    evaluate,
    evaluate_same_day,
)
from app.domains.pnl_reconciler.truth_check_runner import ist_window

BOT = "34226090862006"
STOP = "312260904412406"
MANUAL = "35226091145606"
STRANGER = "99990001112223"


def _fill(order_id: str) -> AccountFill:
    return AccountFill(
        contract="68456", order_id=order_id, side="SELL", qty=400,
        price=Decimal("3415.5"), ts="2026-09-04T13:11:13", charges=Decimal("20"),
    )


def _stored(**kv: str) -> dict[str, dict[str, str]]:
    return {oid: {"provenance": prov, "order_platform": None} for oid, prov in kv.items()}


class TestAGreenDay:
    def test_everything_recorded_and_the_bots_is_quiet(self) -> None:
        fills = [_fill(BOT), _fill(STOP)]
        out = evaluate(
            fills,
            stored=_stored(**{BOT: "bot", STOP: "bot"}),
            tape_covered={BOT, STOP},
        )
        assert out.verdict == GREEN
        assert out.green is True
        assert out.details() == ""
        assert out.telegram_line("2026-09-04") == "TRADETRI = DHAN ✅ 2026-09-04 2 fills"

    def test_a_day_with_no_fills_is_no_data_not_green(self) -> None:
        """🔴 THIS TEST USED TO ENCODE THE BUG, and it is worth saying so.

        It previously asserted that no fills meant GREEN — "a quiet day is not
        a fault". The reasoning was right about a quiet day and wrong about
        everything else, because it could not tell a quiet day from a day the
        trade book simply refused to answer. On 2026-09-17 the book returned
        zero rows while the account traded 400 + 800, and this assertion is
        exactly what would have called that clean.

        A quiet day is still not a fault — it is NO-DATA, which says "nothing
        to check" without claiming "everything matched"."""
        out = evaluate([], stored={}, tape_covered=set(), tape_loaded=False)
        assert out.verdict == NO_DATA
        assert out.verdict != GREEN
        assert out.licenses_badge is False
        assert "DEKHA NAHI JA SAKA" in out.telegram_line("2026-09-05")

    def test_the_green_line_is_sent_every_day_not_only_on_a_red(self) -> None:
        """🔴 WHY GREEN IS NOISY ON PURPOSE. If only reds were sent, a dead
        timer and a clean day would look identical from the founder's phone —
        and the silence would be indistinguishable from safety."""
        out = evaluate([_fill(BOT)], stored=_stored(**{BOT: "bot"}), tape_covered={BOT})
        assert out.telegram_line("2026-09-04").startswith("TRADETRI = DHAN ✅")


class TestTheFourReds:
    def test_1_a_fill_we_never_recorded(self) -> None:
        out = evaluate([_fill(BOT), _fill(STRANGER)],
                       stored=_stored(**{BOT: "bot"}), tape_covered={BOT, STRANGER})
        assert out.verdict == RED
        assert out.unrecorded == [STRANGER]
        assert STRANGER in out.telegram_line("2026-09-04")
        assert out.telegram_line("2026-09-04").startswith("MISMATCH 🔴")

    def test_2_pehchaan_nahi_is_never_filed_as_manual(self) -> None:
        """🔴 THE ONE THAT MATTERS. An unidentified fill must alert under its own
        name. Filing it as manual would blame a human for the bot's own exit."""
        out = evaluate([_fill(STRANGER)],
                       stored=_stored(**{STRANGER: "unknown"}), tape_covered={STRANGER})
        assert out.verdict == RED
        assert out.unidentified == [STRANGER]
        assert out.manual == [], "an unknown fill must NOT be counted as manual"
        assert "PEHCHAAN NAHI" in out.telegram_line("2026-09-04")

    def test_3_a_manual_trade_is_attention_not_mismatch(self) -> None:
        """🔴 THE WORDING MATTERS AS MUCH AS THE DETECTION. A hand-placed trade
        is not a site-vs-Dhan mismatch: the record is RIGHT — the position is
        marked "manual se band" and its P&L correctly withheld. The founder is
        told, but under its own headline.

        Calling it MISMATCH would train him that the red means "you traded by
        hand", and then the day our record really IS wrong, the message looks
        exactly like the ones he has learned to dismiss."""
        out = evaluate([_fill(MANUAL)],
                       stored=_stored(**{MANUAL: "manual"}), tape_covered=set())
        assert out.verdict == ATTENTION
        assert out.manual == [MANUAL]
        line = out.telegram_line("2026-09-11")
        assert "HAATH SE TRADE ⚠️" in line
        assert MANUAL in line
        assert not line.startswith("MISMATCH"), "a manual trade is not a mismatch"
        assert out.agrees_with_dhan is True, "the badge is still earned that day"

    def test_a_real_mismatch_outranks_a_manual_trade_on_the_same_day(self) -> None:
        """The verdict is the WORST thing found. If both happen, the founder
        must see the red — the manual note must not downgrade it."""
        out = evaluate(
            [_fill(MANUAL), _fill(STRANGER)],
            stored=_stored(**{MANUAL: "manual"}),
            tape_covered={MANUAL, STRANGER},
        )
        assert out.verdict == RED
        assert out.telegram_line("2026-09-11").startswith("MISMATCH 🔴")
        assert out.agrees_with_dhan is False

    def test_4_a_duplicate_exit(self) -> None:
        out = evaluate([_fill(BOT)], stored=_stored(**{BOT: "bot"}),
                       tape_covered={BOT}, duplicate_exit_order_ids={"23226090443106"})
        assert out.verdict == RED
        assert out.duplicate_exits == ["23226090443106"]
        assert "duplicate exit" in out.telegram_line("2026-09-04")

    def test_one_bad_day_is_one_message_not_four(self) -> None:
        """A burst of alerts is an alert the founder learns to swipe away."""
        out = evaluate(
            [_fill(BOT), _fill(STRANGER), _fill(MANUAL)],
            stored={**_stored(**{BOT: "bot", MANUAL: "manual"}),
                    "x": {"provenance": "unknown"}},
            tape_covered={BOT},
            duplicate_exit_order_ids={"23226090443106"},
        )
        line = out.telegram_line("2026-09-04")
        assert out.verdict == RED
        assert line.count("MISMATCH") == 1
        assert "\n" not in line


class TestAnEmptyTapeIsOneRedNotAMassFlag:
    def test_it_reports_the_load_and_stops(self) -> None:
        """🔴 ADDITION B. When the tape last loaded empty (a glob expanded on
        the host, where the container's path does not exist) every non-bot fill
        would have been re-labelled at once — a page full of alarm caused by a
        mount, not by the account."""
        out = evaluate([_fill(BOT), _fill(MANUAL)], stored={}, tape_covered=set(),
                       tape_loaded=False)
        assert out.verdict == RED
        assert out.tape_gap is True
        assert out.unrecorded == [], "it must not also accuse every fill"
        assert out.unidentified == []
        assert "tape missing/incomplete" in out.telegram_line("2026-09-04")

    def test_falsification_twin_a_loaded_tape_still_checks_every_fill(self) -> None:
        """The twin. A guard that always short-circuited would pass the test
        above and silently stop the check ever examining anything."""
        out = evaluate([_fill(STRANGER)], stored={}, tape_covered={STRANGER},
                       tape_loaded=True)
        assert out.verdict == RED
        assert out.unrecorded == [STRANGER], "the fill itself must still be named"
        assert out.tape_gap is False


class TestTheMessageIsStable:
    def test_the_same_day_cannot_read_two_different_ways(self) -> None:
        """Order-dependence in an alert is a way to look like two incidents."""
        a = evaluate([_fill(STRANGER), _fill("88880001112223")],
                     stored={}, tape_covered={STRANGER, "88880001112223"})
        b = evaluate([_fill("88880001112223"), _fill(STRANGER)],
                     stored={}, tape_covered={STRANGER, "88880001112223"})
        assert a.telegram_line("2026-09-04") == b.telegram_line("2026-09-04")

    def test_a_repeated_fill_is_named_once(self) -> None:
        out = evaluate([_fill(STRANGER), _fill(STRANGER)], stored={},
                       tape_covered={STRANGER})
        assert out.unrecorded == [STRANGER]

    def test_the_window_is_ist_not_utc(self) -> None:
        """A UTC window would put a 15:50 IST run in the wrong day for 5h30m
        either side, and the badge would cite a run that never covered it."""
        start, end = ist_window(date(2026, 9, 4))
        assert start.utcoffset().total_seconds() == 5.5 * 3600
        assert start.astimezone(UTC) == datetime(2026, 9, 3, 18, 30, tzinfo=UTC)
        assert end.date() == date(2026, 9, 4)


class TestTheResultIsHonestByDefault:
    def test_a_fresh_result_is_green_with_nothing_claimed(self) -> None:
        r = TruthCheckResult()
        assert r.green is True and r.details() == "" and r.fills_checked == 0


class TestDeliveryAndDedupe:
    """The line has to reach the phone, at the right severity, exactly once.

    These patch the transport rather than calling it: a test that really sent
    would put a message on the founder's phone every CI run, and he would stop
    reading them — which is the failure mode this whole feature exists to avoid.
    """

    async def _run(self, monkeypatch, *, fills, stored, prior, send=True):
        import app.domains.pnl_reconciler.truth_check_runner as runner

        sent: list[tuple[str, str]] = []
        recorded: list[str] = []

        class _Session:
            async def execute(self, *a, **k):
                raise AssertionError("unexpected query")

            async def commit(self):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, *a):
                return False

        monkeypatch.setattr(runner, "get_sessionmaker", lambda: _Session)
        # A.1 added a witness-gathering step that reads the DB and the broker.
        # These tests are about DELIVERY, so it is stubbed to "a normal day".
        monkeypatch.setattr(
            runner, "gather_witnesses",
            lambda _d, _s, tape_frames=None: _async(({"tape_frames": 1}, [], {})),
        )
        monkeypatch.setattr(runner, "stored_provenance_map",
                            lambda _s, _ids: _async(stored))
        monkeypatch.setattr(runner, "already_ran", lambda _s, _a, _b: _async(prior))

        async def _record(_s, result, *, ran_at):
            recorded.append(result.verdict)
            return 1

        monkeypatch.setattr(runner, "record_run", _record)

        import app.services.telegram_alerts as alerts

        async def _send(level, message):
            sent.append((str(level), message))

        monkeypatch.setattr(alerts, "send_alert", _send)

        result = await runner.run_check(
            date(2026, 9, 4), security_ids={"68456"}, send=send,
            fills=fills, tape_covered={f.order_id for f in fills},
        )
        return result, sent, recorded

    async def test_a_red_day_goes_out_as_critical(self, monkeypatch) -> None:
        _, sent, recorded = await self._run(
            monkeypatch, fills=[_fill(STRANGER)], stored={}, prior=None,
        )
        assert len(sent) == 1
        level, message = sent[0]
        assert "CRITICAL" in level
        assert message.startswith("MISMATCH 🔴")
        assert recorded == [RED]

    async def test_a_green_day_goes_out_as_success(self, monkeypatch) -> None:
        _, sent, recorded = await self._run(
            monkeypatch, fills=[_fill(BOT)],
            stored=_stored(**{BOT: "bot"}), prior=None,
        )
        assert len(sent) == 1
        level, message = sent[0]
        assert "SUCCESS" in level
        assert message.startswith("TRADETRI = DHAN ✅")
        assert recorded == [GREEN]

    async def test_the_same_verdict_twice_sends_nothing_the_second_time(
        self, monkeypatch
    ) -> None:
        """A retry, a restart or a second manual run is not news."""
        _, sent, recorded = await self._run(
            monkeypatch, fills=[_fill(STRANGER)], stored={}, prior=RED,
        )
        assert sent == [], "the duplicate must not reach the phone"
        assert recorded == [], "and must not be written down again"

    async def test_falsification_twin_a_changed_verdict_still_gets_through(
        self, monkeypatch
    ) -> None:
        """The twin, and the one that matters. Dedupe that suppressed by DAY
        rather than by VERDICT would swallow the red that arrives after a green
        — the exact message the founder most needs."""
        _, sent, recorded = await self._run(
            monkeypatch, fills=[_fill(STRANGER)], stored={}, prior=GREEN,
        )
        assert len(sent) == 1
        assert sent[0][1].startswith("MISMATCH 🔴")
        assert recorded == [RED]

    async def test_dry_run_is_the_default_and_touches_no_phone(
        self, monkeypatch
    ) -> None:
        """The check can be pointed at any live day, any number of times,
        without alerting — which is what makes it safe to exercise."""
        _, sent, recorded = await self._run(
            monkeypatch, fills=[_fill(STRANGER)], stored={}, prior=None, send=False,
        )
        assert sent == []
        assert recorded == [RED], "the evidence is still written down"


async def _async(value):
    return value


class TestSeverityMatchesTheKindOfDay:
    """A hand-placed trade must not buzz like a record that disagrees with the
    broker. If every notification arrives at the same weight, the founder
    triages none of them."""

    async def test_a_manual_day_goes_out_as_warning_not_critical(
        self, monkeypatch
    ) -> None:
        _, sent, recorded = await TestDeliveryAndDedupe()._run(
            monkeypatch, fills=[_fill(MANUAL)],
            stored=_stored(**{MANUAL: "manual"}), prior=None,
        )
        assert len(sent) == 1
        level, message = sent[0]
        assert "WARNING" in level
        assert "CRITICAL" not in level
        assert "HAATH SE TRADE" in message
        assert recorded == [ATTENTION]

    async def test_falsification_twin_a_real_mismatch_is_still_critical(
        self, monkeypatch
    ) -> None:
        """The twin. Downgrading everything to WARNING would pass the test above
        and quietly strip the urgency from the message that matters."""
        _, sent, _ = await TestDeliveryAndDedupe()._run(
            monkeypatch, fills=[_fill(STRANGER)], stored={}, prior=None,
        )
        assert "CRITICAL" in sent[0][0]


class TestAnEmptyBookIsNeverGreen:
    """A.1 — the defect that made this whole round necessary.

    MEASURED 2026-09-17: Dhan's /trades returned ZERO rows for the session —
    all pages, unfiltered — while the account traded 400 + 800 and a live
    position silently desynced. The old check returned
    "TRADETRI = DHAN ✅ 2026-09-17 0 fills" and would have STORED that green,
    later licensing a "Dhan se verified ✅" badge for a day nothing was checked.

    Silence is not agreement.
    """

    WITNESSES_17_SEP: ClassVar[dict[str, int]] = {
        "tape_frames": 8, "day_qty_moved": 1200, "platform_executions": 4,
    }

    def test_17_sep_replayed_through_the_fix_is_red(self) -> None:
        """🔴 THE REGRESSION THAT MATTERS. The real day, the real numbers."""
        out = evaluate([], stored={}, tape_covered=set(), witnesses=self.WITNESSES_17_SEP)
        assert out.verdict == RED
        assert out.book_empty is True
        line = out.telegram_line("2026-09-17")
        assert line.startswith("MISMATCH 🔴")
        assert "EMPTY" in line
        assert "blind, not clean" in line

    def test_the_red_names_which_witness_saw_activity(self) -> None:
        """An alert that says only "something is wrong" is an alert nobody can
        act on. It must say WHAT it saw and how much."""
        out = evaluate([], stored={}, tape_covered=set(), witnesses=self.WITNESSES_17_SEP)
        joined = " ".join(out.witnesses_seen)
        assert "WS tape frames=8" in joined
        assert "day quantity=1200" in joined
        assert "strategy_executions rows=4" in joined

    def test_any_single_witness_is_enough(self) -> None:
        """One source seeing activity is enough to refuse a green. Requiring
        agreement between witnesses would let a single broken source hide a day."""
        for key in ("tape_frames", "day_qty_moved", "platform_executions"):
            out = evaluate([], stored={}, tape_covered=set(), witnesses={key: 1})
            assert out.verdict == RED, f"{key} alone must force a red"

    def test_a_genuinely_quiet_day_is_no_data_not_green(self) -> None:
        """🔴 AND NOT GREEN EITHER. A holiday and a broken pull look identical
        from here — the honest answer is "we did not check", which is a
        different sentence from "everything matched"."""
        out = evaluate([], stored={}, tape_covered=set(),
                       witnesses={"tape_frames": 0, "day_qty_moved": 0, "platform_executions": 0})
        assert out.verdict == NO_DATA
        assert out.verdict != GREEN
        line = out.telegram_line("2026-09-05")
        assert "DEKHA NAHI JA SAKA" in line
        assert "✅" not in line

    def test_no_data_never_licenses_a_badge(self) -> None:
        out = evaluate([], stored={}, tape_covered=set(), witnesses={})
        assert out.licenses_badge is False

    def test_falsification_twin_a_real_clean_day_is_still_green(self) -> None:
        """The twin, and the one that keeps this useful. If an empty book were
        the ONLY path to green, the fix would have turned the check into a
        permanent red nobody reads."""
        out = evaluate([_fill(BOT)], stored=_stored(**{BOT: "bot"}), tape_covered={BOT},
                       witnesses={"tape_frames": 3, "day_qty_moved": 400})
        assert out.verdict == GREEN
        assert out.licenses_badge is True
        assert out.telegram_line("2026-09-04").startswith("TRADETRI = DHAN ✅")

    def test_falsification_twin_witnesses_do_not_override_a_populated_book(self) -> None:
        """Witnesses only decide the EMPTY-book case. With fills present the
        ordinary rules must still run, or a busy day would mask a real fault."""
        out = evaluate([_fill(STRANGER)], stored={}, tape_covered={STRANGER},
                       witnesses={"tape_frames": 99})
        assert out.verdict == RED
        assert out.unrecorded == [STRANGER], "the fill itself must still be judged"
        assert out.book_empty is False


class TestThePhantomPosition:
    """A.3 — a row that says "open" about a position the broker does not have.

    `6c0b2196` sat open on the page for two days while Dhan held nothing
    against it. That is the most misleading thing this screen can print: it
    invites someone to act on exposure that is not there.
    """

    def test_a_phantom_forces_red_even_on_an_otherwise_clean_day(self) -> None:
        out = evaluate([_fill(BOT)], stored=_stored(**{BOT: "bot"}), tape_covered={BOT},
                       phantom_positions=["6c0b2196"])
        assert out.verdict == RED
        assert out.phantom_positions == ["6c0b2196"]
        assert "Dhan pe band, site pe khula" in out.telegram_line("2026-09-18")

    def test_a_phantom_is_activity_even_when_the_book_is_empty(self) -> None:
        """An empty book with no witness is NO-DATA — unless we already know a
        row disagrees with the broker, which is itself something we can see."""
        out = evaluate([], stored={}, tape_covered=set(), witnesses={},
                       phantom_positions=["6c0b2196"])
        assert out.verdict == RED
        assert out.verdict != NO_DATA

    def test_a_phantom_never_licenses_a_badge(self) -> None:
        out = evaluate([_fill(BOT)], stored=_stored(**{BOT: "bot"}), tape_covered={BOT},
                       phantom_positions=["6c0b2196"])
        assert out.licenses_badge is False

    def test_falsification_twin_no_phantom_no_red(self) -> None:
        """The twin. A check that always reported a phantom would pass every
        test above and turn every day red."""
        out = evaluate([_fill(BOT)], stored=_stored(**{BOT: "bot"}), tape_covered={BOT},
                       phantom_positions=[])
        assert out.verdict == GREEN
        assert out.phantom_positions == []

    def test_the_ids_are_stable_and_deduplicated(self) -> None:
        out = evaluate([], stored={}, tape_covered=set(),
                       phantom_positions=["b", "a", "b"])
        assert out.phantom_positions == ["a", "b"]


class TestTheSameDayCheck:
    """The 15:50 run — "did we RECORD what the account did today?"

    🔴 WHY IT EXISTS AS A SEPARATE CHECK. Dhan's trade book does not settle in
    time: MEASURED, the 17-Sep session was absent from /trades at 18-Sep 04:33
    IST and present by 20:20 — roughly forty hours. A 15:50 check that needed
    the book would be blind about the session it just watched, every single
    day. So this one never reads it.
    """

    def test_a_recorded_day_is_green(self) -> None:
        out = evaluate_same_day(
            tape_orders={"A", "B"}, platform_orders={"A", "B"}, day_qty_moved=1200,
        )
        assert out.verdict == GREEN
        assert out.kind == SAME_DAY

    def test_a_fill_the_tape_saw_and_we_did_not_record_is_red(self) -> None:
        """🔴 THE ONE THAT MATTERS, and the 17-Sep shape exactly: the engine's
        stop filled at Dhan and never reached strategy_executions."""
        out = evaluate_same_day(
            tape_orders={"22226091747006", "22226091785806"},
            platform_orders={"22226091785806"},
            day_qty_moved=1200,
        )
        assert out.verdict == RED
        assert out.unrecorded == ["22226091747006"]

    def test_a_quiet_day_is_green_not_no_data(self) -> None:
        """🔴 THE DIFFERENCE FROM THE MORNING CHECK. /positions day quantities
        are POSITIVE evidence that nothing traded — unlike an empty book, which
        is merely the absence of evidence. So a quiet day is provable here."""
        out = evaluate_same_day(tape_orders=set(), platform_orders=set(), day_qty_moved=0)
        assert out.verdict == GREEN
        assert out.verdict != NO_DATA

    def test_an_unreachable_broker_is_no_data_not_green(self) -> None:
        """If we could not ask the broker we know nothing. Say so."""
        out = evaluate_same_day(tape_orders=set(), platform_orders=set(), day_qty_moved=None)
        assert out.verdict == NO_DATA
        assert "unreachable" in " ".join(out.witnesses_seen)

    def test_quantity_moved_but_we_hold_nothing_is_red(self) -> None:
        out = evaluate_same_day(tape_orders=set(), platform_orders=set(), day_qty_moved=800)
        assert out.verdict == RED
        assert out.unrecorded

    def test_a_phantom_forces_red_here_too(self) -> None:
        out = evaluate_same_day(
            tape_orders={"A"}, platform_orders={"A"}, day_qty_moved=400,
            phantom_positions=["6c0b2196"],
        )
        assert out.verdict == RED
        assert "Dhan pe band, site pe khula" in out.telegram_line("2026-09-18")

    def test_an_empty_tape_beside_activity_is_one_red(self) -> None:
        out = evaluate_same_day(
            tape_orders=set(), platform_orders={"A"}, day_qty_moved=400, tape_loaded=False,
        )
        assert out.verdict == RED
        assert out.tape_gap is True

    def test_falsification_twin_it_is_not_a_blanket_red(self) -> None:
        """The twin. A check that always went red would pass most of the above
        and become a daily alarm nobody reads."""
        out = evaluate_same_day(
            tape_orders={"A"}, platform_orders={"A", "B"}, day_qty_moved=400,
        )
        assert out.verdict == GREEN, "extra platform rows are not a fault"

    def test_falsification_twin_it_never_licenses_a_badge(self) -> None:
        """🔴 THE BADGE BELONGS TO THE MORNING RUN. A green same-day run means
        "we wrote down what happened" — it has never seen a settled price or a
        billed charge, so it cannot support a claim about money."""
        out = evaluate_same_day(
            tape_orders={"A"}, platform_orders={"A"}, day_qty_moved=400,
        )
        assert out.verdict == GREEN
        assert out.licenses_badge is False


class TestTheTwoChecksAreDistinct:
    def test_only_a_morning_green_licenses_the_badge(self) -> None:
        morning = evaluate([_fill(BOT)], stored=_stored(**{BOT: "bot"}), tape_covered={BOT},
                           witnesses={"tape_frames": 1})
        assert morning.kind == MORNING
        assert morning.verdict == GREEN
        assert morning.licenses_badge is True

        same_day = evaluate_same_day(
            tape_orders={"A"}, platform_orders={"A"}, day_qty_moved=400,
        )
        assert same_day.verdict == GREEN
        assert same_day.licenses_badge is False

    def test_the_morning_check_still_refuses_an_empty_book(self) -> None:
        """Splitting the checks must not lose A.1. The morning run reads the
        settled book, so an empty one there — with witnesses — is still a red."""
        out = evaluate([], stored={}, tape_covered=set(),
                       witnesses={"tape_frames": 8, "day_qty_moved": 1200})
        assert out.kind == MORNING
        assert out.verdict == RED
        assert "blind, not clean" in out.telegram_line("2026-09-17")
