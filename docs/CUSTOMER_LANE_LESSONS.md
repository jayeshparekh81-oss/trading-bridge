# Lessons from the customer-lane build

Three mistakes were made across these runs, caught by the person or the process, and
reported. Reports live in chat; a future session inherits nothing from them. This file is
what it inherits. Keep it short enough to actually read.

---

## 1. An absence claim from a partial search

**What happened.** Twice, "X does not exist in this repo" was written after searching only
`backend/`.

- *Holiday calendar.* `orderflow_engine/holidays.yaml` was git-tracked in the same repo the
  whole time — 16 NSE dates, already driving five consumers and a daily `calendar_health`
  cron. The search found `backend/app/strategy_engine/trading_calendar.py`, a weekday helper
  that holds **no dates**, and generalised from it.
- *Notification transport.* `channels.py` asserted a real provider "must be a NEW class",
  implying nothing existed. `app/services/notification_service.py` is a working service with
  email + Telegram, templates, per-user preferences — and an existing `broker_session_expired`
  event type that nearly matches the ladder's use case.

**What it cost.** The first shipped: an empty holiday set was hard-coded into
`config.py` and the wrong claim propagated into `ladder.py` and the runbook. Left alone it
would have messaged customers on Diwali. The second cost a near-duplicate transport layer.

**How it was caught.** Both by the founder pushing back on the claim, not by the search.

**The rule.** *An absence claim requires a whole-repo search, and the commands go in the
report.* Search five ways, because each finds what the others miss:

| angle | example |
|---|---|
| by name | `git ls-files \| grep -i holiday` |
| by content | the literal data the thing would hold — a holiday list is a list of dates |
| by usage | who answers this question today? `grep -rn is_trading_day` |
| by dependency | is a library already installed? is it actually imported? |
| by sibling | other repos, git worktrees, `orderflow_engine/`, `scripts/`, `frontend/` |

And: **if an obvious consumer exists, the source exists.** A live engine that trades daily,
a per-trading-day download job, a daily `calendar_health` cron — each is proof. Keep looking.

## 2. Rejecting a correct hypothesis on an insufficient experiment

**What happened.** 24 tests failed only in a full-suite run. The first hypothesis — a
module-level `os.environ.setdefault("DATABASE_URL", "sqlite…")` — was correct. It was tested
as a **pair** (polluter + victim), the pair passed, and the hypothesis was discarded.

The real chain needs **three** files: the leak is inert until a *third* file calls
`get_settings.cache_clear()` and Settings is rebuilt from the poisoned environment.

**What it cost.** A wrong root cause was reported, then a second contributing cause was found
and fixed, and only the workflow's independent diagnosis restored the first.

**The rule.** *A hypothesis is not rejected until the experiment reproduces the full chain.*
A negative result from a smaller setup than the failure needs is not evidence of absence —
it is an under-powered test. Before discarding, ask: does my repro include every ingredient
the real failure had? If the failure appears only at full scale, test at full scale.

## 3. Re-making a mistake already fixed once

**What happened.** Branch and base regression runs were pointed at the **same** test
database. The branch run migrated it to `047`; base, which has no `047`, then failed 4
integration tests. This was diagnosed and fixed in run F — and repeated in run G, producing
base = 71 instead of 67.

**What it cost.** One wasted comparison, caught only because the number did not match a
figure known from the previous run.

**The rule.** *Branch and base never share a database, a cache, or an environment.* More
generally: a fix from an earlier run is not knowledge unless it is written down or enforced.
That is what this file and the checks below are for.

---

## Pre-flight before claiming anything does not exist

1. `git ls-files | xargs grep -lni "<concept>"` — the whole repo, not one directory.
2. Search by the **data** the thing would contain, not only its name.
3. Search sibling repos and worktrees: `git worktree list`, `ls ~/projects`.
4. Ask who answers this question today — an existing consumer proves an existing source.
5. Check installed packages, and whether anything imports them.
6. Write the commands into the report so the claim is falsifiable.

## What is enforced by code, and what relies on being read

| lesson | enforcement |
|---|---|
| calendar must resolve or refuse | **CODE** — `calendar.py` raises `CalendarUnavailable` / `CalendarCoverageError`; `preflight.assert_can_arm()` blocks beat registration |
| no second calendar | **CODE** — the lane reads the shared file; `test_c8` asserts the path is `orderflow_engine/holidays.yaml`, not a copy |
| no silent fallback to a shared egress | **CODE** — `EgressNotConfigured` / `EgressNotExclusive` |
| rung times stay off the pre-market grid | **CODE** — `test_c2_ladder.py` collision table, falsification-proven |
| historical_candles must not run on the wrong engine | **CODE** — the fixture pins its URL and fails loudly if the engine is not Postgres |
| missing scratch DB names its own fix | **CODE** — `tests/customer_lane/conftest.py` |
| absence claims need a whole-repo search | **READ ONLY** — judgement; no check can prove a negative |
| hypotheses need a full-chain experiment | **READ ONLY** — judgement |
| branch and base never share a database | **READ ONLY** — but see `scripts/cl_test_db.sh`, which takes `CL_DB` so a second database is one variable away |
