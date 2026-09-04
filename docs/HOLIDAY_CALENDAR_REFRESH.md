# Adding next year's NSE holiday list — the yearly ritual

**One file. One list. Do not create a second one.**

`orderflow_engine/holidays.yaml` is the estate's single exchange-holiday source.
It is git-tracked and already read by:

| consumer | what it does with it |
|---|---|
| `orderflow_engine/recorder/scheduler.py` | tick recorder session clock |
| `orderflow_engine/recorder/depth_main.py` | depth recorder session clock |
| `orderflow_engine/alerts/pulse.py` | G0 clean-session counter |
| `orderflow_engine/scripts/morning_watchdog_v2.py` | goes quiet on a holiday |
| `pine_replica/executor/session_calendar.py` | live T-2 expiry backstop (strict reader) |
| `backend/app/domains/customer_lane/calendar.py` | customer reminder ladder (strict reader) |

## When

From **1 November** the customer lane's `coverage_alarm()` starts reporting that
next year's list is absent. `pine_replica/scripts/calendar_health.py` runs daily
on the production box and watches the same file. Do not wait for 31 December —
the list must be in before the first trading day of the new year.

## How (about ten minutes)

1. Get the official circular. NSE publishes the trading-holiday list for the
   coming year: nseindia.com → *Market Timings & Holidays* → Trading Holidays.
   Save the year's list.
2. **Cross-verify against a second published source** (the existing entries were
   checked against ClearTax and Groww). Two independent lists must agree before a
   date goes in. This is not ceremony: over-listing a real trading day skips a
   live session and loses it forever.
3. Append the new year's dates to `holidays.yaml`, keeping the existing format —
   ISO date, then a `#` comment with the weekday and the holiday name:
   ```yaml
     - 2027-01-26   # Tue — Republic Day
   ```
4. **Do not list weekends.** They are skipped automatically. A Sunday entry is
   noise; a Sunday *Muhurat* session is explicitly out of scope.
5. **Trading holidays only.** Clearing/settlement holidays are a different list
   and do not belong here.
6. Update the header: record the date you verified and against which sources.
7. Verify:
   ```bash
   cd backend && .venv/bin/python -c "from app.domains.customer_lane import calendar as c; print(c.coverage_end()); print(len(c.load_holidays()))"
   ```
   `coverage_end()` must now report 31 December of the new year.
8. Commit the file. Nothing else needs changing — every consumer reads it live.

## What happens if you forget

Nothing silent. The customer lane refuses:

- a date past coverage raises `CalendarCoverageError` naming the file and the year;
- a missing or unparseable file raises `CalendarUnavailable`;
- neither ever degrades to "assume it is a trading day".

The recorder's own loader (`recorder.scheduler.load_holidays`) is deliberately more
forgiving — it warns and returns an empty set, which is safe for a recorder that
merely connects and records nothing on a closed day. It is **not** safe for the
customer lane, which is why the lane has its own strict reader rather than reusing
that loader.
