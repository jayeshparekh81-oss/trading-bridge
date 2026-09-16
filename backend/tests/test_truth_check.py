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

from app.domains.pnl_reconciler.attribution import AccountFill
from app.domains.pnl_reconciler.truth_check import (
    ATTENTION,
    GREEN,
    RED,
    TruthCheckResult,
    evaluate,
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

    def test_a_day_with_no_fills_at_all_is_green(self) -> None:
        """A quiet day is not a fault. 05-Sep and 12-Sep had zero fills — and no
        tape file, which is normal, because the tape only gets a file when an
        order update arrives."""
        out = evaluate([], stored={}, tape_covered=set(), tape_loaded=False)
        assert out.verdict == GREEN
        assert out.telegram_line("2026-09-05") == "TRADETRI = DHAN ✅ 2026-09-05 0 fills"

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
