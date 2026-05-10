#!/usr/bin/env python3
"""Manual Dhan integration test runner — pre-launch validation only.

⚠️  NOT FOR CI/CD.

Founder runs this against the live Dhan API before each production
deploy to verify the broker integration end-to-end. Defaults to
``dry_run=True`` everywhere so no real orders go out unless the
operator explicitly passes ``--live`` AND types ``CONFIRM`` at the
prompt.

Six test steps in order:

    1. Token validity (GET /v2/profile)
    2. Historical data fetch (1 day NIFTY 5m)
    3. User funds (GET /v2/fundlimit, read-only)
    4. SafetyChain preflight (6 active checks; the 7th is fail-open
       per the live_orders module's docstring)
    5. Dry-run order via place_live_order(dry_run=True)
    6. REAL order via place_live_order(dry_run=False) — gated behind
       ``--live`` + interactive confirmation + qty cap

Reads from environment (or .env via python-dotenv if installed):

    DHAN_ACCESS_TOKEN   — required for any test that hits the API
    DHAN_CLIENT_ID      — required for any test that hits the API
    DATABASE_URL        — required for tests 4-6 (SafetyChain reads DB)
    TEST_USER_EMAIL     — required for tests 4-6 (looks up the user)
    TEST_STRATEGY_NAME  — required for tests 4-6 (looks up strategy)

Usage:

    # Token check only (cheapest):
    ./dhan_integration_test.py --check-token

    # Historical fetch only:
    ./dhan_integration_test.py --test-historical

    # Full flow, dry-run (default — no real orders):
    ./dhan_integration_test.py --test-flow

    # Full flow with REAL ORDER — interactive confirm required:
    ./dhan_integration_test.py --test-flow --live --symbol NIFTY --quantity 1

    # All steps sequentially:
    ./dhan_integration_test.py --all

Exit codes:

    0 — every test that ran passed
    1 — at least one test failed
    2 — bad CLI args / missing required env

Logs land in ``logs/dhan_integration_<UTC-timestamp>.log`` next to
the script. The console gets a colour-coded summary; the file
captures the full per-step detail (request URLs, response shapes,
timings) for post-mortem.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
import time
from collections.abc import Awaitable, Callable
from contextlib import suppress
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path

# ─── Constants ────────────────────────────────────────────────────────

#: Dhan REST base URL. Mirrors the production setting; the script
#: reads the live value from env when set so a sandbox URL can be
#: substituted without code edits.
DHAN_API_BASE_URL_DEFAULT = "https://api.dhan.co/v2"

#: Hard cap on the ``--quantity`` flag. Founder-facing safety net:
#: even if someone fat-fingers ``--quantity 100`` the script refuses
#: to send. Defended in addition to the dry_run default + interactive
#: confirm prompt — defence in depth, not redundancy.
QUANTITY_HARD_CAP = 5

#: Seconds the script counts down before placing a real order.
#: Long enough for the operator to ctrl-C if they realise they
#: typo'd the symbol or quantity.
REAL_ORDER_COUNTDOWN_SECONDS = 5

#: Default symbol for the historical-fetch test. NIFTY is the most
#: liquid index; using a known security id sidesteps a scrip-master
#: lookup that could fail for unrelated reasons.
NIFTY_SECURITY_ID = "13"
NIFTY_EXCHANGE_SEGMENT = "IDX_I"
NIFTY_INSTRUMENT = "INDEX"


# ─── ANSI helpers (no external deps) ─────────────────────────────────

_RESET = "\033[0m"
_GREEN = "\033[0;32m"
_RED = "\033[0;31m"
_YELLOW = "\033[1;33m"
_BLUE = "\033[0;34m"
_BOLD = "\033[1m"


def _supports_color() -> bool:
    """Best-effort check — disable colour when piping to a file or
    when ``NO_COLOR`` is set (the de-facto convention)."""
    if os.environ.get("NO_COLOR"):
        return False
    return sys.stdout.isatty()


def _c(code: str, msg: str) -> str:
    if not _supports_color():
        return msg
    return f"{code}{msg}{_RESET}"


def _info(msg: str) -> None:
    print(_c(_BLUE, "[INFO]"), msg)


def _step(num: int, label: str) -> None:
    print()
    print(_c(_BOLD, f"━━━ Step {num}: {label} ━━━"))


def _pass(msg: str) -> None:
    print(_c(_GREEN, "  ✓"), msg)


def _fail(msg: str) -> None:
    print(_c(_RED, "  ✗"), msg)


def _warn(msg: str) -> None:
    print(_c(_YELLOW, "  ⚠"), msg)


# ─── Result accounting ───────────────────────────────────────────────


@dataclass
class StepResult:
    """One test step's outcome — collected into the run summary."""

    name: str
    status: str  # "passed" / "failed" / "skipped"
    detail: str = ""
    duration_ms: float = 0.0


@dataclass
class RunSummary:
    """Mutable accumulator passed across steps."""

    results: list[StepResult] = field(default_factory=list)
    notable_order_ids: list[str] = field(default_factory=list)

    def add(self, result: StepResult) -> None:
        self.results.append(result)
        line = (
            f"{result.name}: {result.status} "
            f"({result.duration_ms:.1f}ms) {result.detail}"
        )
        logging.info(line)

    @property
    def all_passed(self) -> bool:
        return all(r.status == "passed" for r in self.results)

    def render(self) -> None:
        """Print a one-screen summary at the end of the run."""
        print()
        print(_c(_BOLD, "━━━ Summary ━━━"))
        passed = sum(1 for r in self.results if r.status == "passed")
        failed = sum(1 for r in self.results if r.status == "failed")
        skipped = sum(1 for r in self.results if r.status == "skipped")
        for r in self.results:
            tag = {
                "passed": _c(_GREEN, "PASS"),
                "failed": _c(_RED, "FAIL"),
                "skipped": _c(_YELLOW, "SKIP"),
            }[r.status]
            print(f"  {tag}  {r.name}  ({r.duration_ms:.1f}ms)")
            if r.detail:
                print(f"        {r.detail}")
        print()
        print(
            _c(_BOLD, f"Totals: {passed} passed, {failed} failed, {skipped} skipped")
        )
        if self.notable_order_ids:
            print()
            print(_c(_RED, _c(_BOLD, "🚨 ORDERS WERE PLACED — MANUALLY CANCEL IF NEEDED:")))
            for oid in self.notable_order_ids:
                print(f"  → order_id = {oid}")


# ─── Step decorator ──────────────────────────────────────────────────


def _timed_step(
    summary: RunSummary, name: str
) -> Callable[
    [Callable[[], Awaitable[tuple[bool, str]]]], Awaitable[bool]
]:
    """Decorator-style wrapper that runs a coroutine, times it, and
    appends the result to the summary. Returns the boolean
    ``passed`` flag so callers can short-circuit a multi-step flow
    when an upstream step fails."""

    async def _wrap(
        coro: Callable[[], Awaitable[tuple[bool, str]]],
    ) -> bool:
        t0 = time.perf_counter()
        try:
            passed, detail = await coro()
        except Exception as exc:
            elapsed = (time.perf_counter() - t0) * 1000.0
            summary.add(
                StepResult(
                    name=name,
                    status="failed",
                    detail=f"raised: {type(exc).__name__}: {exc}",
                    duration_ms=elapsed,
                )
            )
            _fail(f"{name} raised {type(exc).__name__}: {exc}")
            return False
        elapsed = (time.perf_counter() - t0) * 1000.0
        summary.add(
            StepResult(
                name=name,
                status="passed" if passed else "failed",
                detail=detail,
                duration_ms=elapsed,
            )
        )
        if passed:
            _pass(f"{name} — {detail}")
        else:
            _fail(f"{name} — {detail}")
        return passed

    return _wrap


# ─── Test step implementations ───────────────────────────────────────


async def _step_token_check(
    summary: RunSummary,
    base_url: str,
    access_token: str | None,
    client_id: str | None,
) -> bool:
    """Hit GET /v2/profile to confirm the access token is live.

    No state mutation; cheapest possible signal that the token
    + client id pair are valid."""
    _step(1, "Dhan token validity")
    if access_token is None or client_id is None:
        _warn("DHAN_ACCESS_TOKEN / DHAN_CLIENT_ID not set — skipping")
        summary.add(
            StepResult(
                name="token_check",
                status="skipped",
                detail="missing env (stub mode)",
            )
        )
        return True

    import httpx

    runner = _timed_step(summary, "token_check")

    async def _do() -> tuple[bool, str]:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                f"{base_url}/profile",
                headers={
                    "access-token": access_token,
                    "client-id": client_id,
                    "Accept": "application/json",
                },
            )
        if resp.status_code != 200:
            return False, f"HTTP {resp.status_code}: {resp.text[:200]}"
        body = resp.json()
        if not isinstance(body, dict):
            return False, f"unexpected response shape: {type(body).__name__}"
        return True, f"profile responded: dhanClientId={body.get('dhanClientId')}"

    return await runner(_do)


async def _step_historical_fetch(
    summary: RunSummary,
    access_token: str | None,
) -> bool:
    """Fetch one trading day of NIFTY 5m candles via the existing
    fetcher. Verifies (a) credentials are accepted, (b) the parser
    + retry path are intact, (c) we get a non-empty candle list."""
    _step(2, "Historical data fetch (NIFTY, 5m, 1 day)")
    if access_token is None:
        _warn("DHAN_ACCESS_TOKEN not set — skipping")
        summary.add(
            StepResult(
                name="historical_fetch",
                status="skipped",
                detail="missing env",
            )
        )
        return True

    from app.strategy_engine.data_provider.dhan_client import (
        fetch_from_dhan,
        parse_candles,
    )
    from app.strategy_engine.data_provider.models import (
        HistoricalDataRequest,
    )

    runner = _timed_step(summary, "historical_fetch")

    async def _do() -> tuple[bool, str]:
        end = datetime.now(UTC)
        start = end - timedelta(days=2)
        req = HistoricalDataRequest(
            symbol="NIFTY",
            timeframe="5m",
            from_date=start,
            to_date=end,
        )
        # ``fetch_from_dhan`` is sync — wrap in a thread so we don't
        # block the event loop in case other steps are running.
        payload = await asyncio.to_thread(
            fetch_from_dhan,
            req,
            access_token=access_token,
            security_id=NIFTY_SECURITY_ID,
            exchange_segment=NIFTY_EXCHANGE_SEGMENT,
            instrument=NIFTY_INSTRUMENT,
        )
        candles = parse_candles(payload)
        if len(candles) == 0:
            return False, "fetched 0 candles (market may be closed)"
        return True, f"got {len(candles)} candles, latest close = {candles[-1].close}"

    return await runner(_do)


async def _step_funds_check(
    summary: RunSummary,
    base_url: str,
    access_token: str | None,
    client_id: str | None,
) -> bool:
    """Read user's available margin via GET /v2/fundlimit. Pure
    read — never moves money."""
    _step(3, "User funds (read-only)")
    if access_token is None or client_id is None:
        _warn("creds missing — skipping")
        summary.add(
            StepResult(
                name="funds_check",
                status="skipped",
                detail="missing env",
            )
        )
        return True

    import httpx

    runner = _timed_step(summary, "funds_check")

    async def _do() -> tuple[bool, str]:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                f"{base_url}/fundlimit",
                headers={
                    "access-token": access_token,
                    "client-id": client_id,
                    "Accept": "application/json",
                },
            )
        if resp.status_code != 200:
            return False, f"HTTP {resp.status_code}: {resp.text[:200]}"
        body = resp.json()
        # Dhan returns ``availabelBalance`` — yes, with the typo.
        # Defensive lookup so a one-off field rename doesn't break
        # the test wholesale; we just report whatever's present.
        avail = body.get("availabelBalance") or body.get("availableBalance") or "n/a"
        return True, f"available balance = {avail}"

    return await runner(_do)


async def _step_safety_chain(
    summary: RunSummary,
    test_user_email: str | None,
    test_strategy_name: str | None,
) -> bool:
    """Run the SafetyChain against the configured test user +
    strategy. Reports per-check verdict so the operator sees which
    gate (if any) blocks live trading."""
    _step(4, "SafetyChain preflight (6 active checks)")
    if test_user_email is None or test_strategy_name is None:
        _warn("TEST_USER_EMAIL / TEST_STRATEGY_NAME not set — skipping")
        summary.add(
            StepResult(
                name="safety_chain",
                status="skipped",
                detail="missing env",
            )
        )
        return True

    from sqlalchemy import select

    from app.db.models.strategy import Strategy
    from app.db.models.user import User
    from app.db.session import get_sessionmaker
    from app.strategy_engine.live_orders.safety_chain import run_safety_chain

    runner = _timed_step(summary, "safety_chain")

    async def _do() -> tuple[bool, str]:
        maker = get_sessionmaker()
        async with maker() as db:
            user = (
                await db.execute(
                    select(User).where(User.email == test_user_email)
                )
            ).scalar_one_or_none()
            if user is None:
                return False, f"test user {test_user_email!r} not found"
            strategy = (
                await db.execute(
                    select(Strategy).where(
                        Strategy.user_id == user.id,
                        Strategy.name == test_strategy_name,
                    )
                )
            ).scalar_one_or_none()
            if strategy is None:
                return False, (
                    f"test strategy {test_strategy_name!r} not found "
                    f"for user {test_user_email}"
                )
            result = await run_safety_chain(
                user_id=user.id,
                strategy_id=strategy.id,
                db_session=db,
            )

        # Per-check breakdown — useful even when all_passed=True.
        for check in result.checks:
            tag = "✓" if check.passed else "✗"
            print(f"      {tag} {check.check_name}: {check.reason_hinglish}")

        if result.all_passed:
            return True, f"all {len(result.checks)} checks passed"
        blocking = result.blocking_check
        return False, (
            f"blocked by {blocking.check_name if blocking else '?'}: "
            f"{blocking.reason_hinglish if blocking else '(no reason)'}"
        )

    return await runner(_do)


async def _step_dry_run_order(
    summary: RunSummary,
    test_user_email: str | None,
    test_strategy_name: str | None,
    symbol: str,
    quantity: int,
) -> bool:
    """Place an order with ``dry_run=True``. Exercises SafetyChain +
    BrokerGuard + the orchestrator without sending anything to
    Dhan. Returns ``order_id="DRY_RUN_SIMULATED"`` on success."""
    _step(5, f"Dry-run order ({symbol}, qty={quantity}, dry_run=True)")
    if test_user_email is None or test_strategy_name is None:
        _warn("TEST_USER_EMAIL / TEST_STRATEGY_NAME not set — skipping")
        summary.add(
            StepResult(
                name="dry_run_order",
                status="skipped",
                detail="missing env",
            )
        )
        return True

    from sqlalchemy import select

    from app.db.models.strategy import Strategy
    from app.db.models.user import User
    from app.db.session import get_sessionmaker
    from app.strategy_engine.live_orders.models import LiveOrderRequest
    from app.strategy_engine.live_orders.order_router import place_live_order

    runner = _timed_step(summary, "dry_run_order")

    async def _do() -> tuple[bool, str]:
        maker = get_sessionmaker()
        async with maker() as db:
            user = (
                await db.execute(
                    select(User).where(User.email == test_user_email)
                )
            ).scalar_one_or_none()
            if user is None:
                return False, f"user {test_user_email!r} not found"
            strategy = (
                await db.execute(
                    select(Strategy).where(
                        Strategy.user_id == user.id,
                        Strategy.name == test_strategy_name,
                    )
                )
            ).scalar_one_or_none()
            if strategy is None:
                return False, f"strategy {test_strategy_name!r} not found"

            req = LiveOrderRequest(
                strategy_id=strategy.id,
                symbol=symbol,
                side="BUY",
                quantity=quantity,
                dry_run=True,
            )
            result = await place_live_order(req, db_session=db, user_id=user.id)

        if not result.success:
            return False, (
                f"dry-run rejected: {result.failure_reason_hinglish or '(no reason)'}"
            )
        return True, (
            f"order_id={result.order_id} (simulated), "
            f"safety_passed={result.safety_chain_result.all_passed if result.safety_chain_result else 'n/a'}"
        )

    return await runner(_do)


async def _step_real_order(
    summary: RunSummary,
    test_user_email: str | None,
    test_strategy_name: str | None,
    symbol: str,
    quantity: int,
) -> bool:
    """The real thing. Behind --live + interactive CONFIRM + countdown.

    The operator must:
      1. Pass --live on the CLI
      2. Type 'CONFIRM' at the prompt (case-sensitive)
      3. Wait through the countdown (ctrl-C still aborts)

    Order id is logged loudly so the operator can manually cancel
    via the broker app if anything looks off."""
    _step(6, f"REAL ORDER ({symbol}, qty={quantity})")

    if quantity > QUANTITY_HARD_CAP:
        _fail(
            f"quantity {quantity} exceeds hard cap {QUANTITY_HARD_CAP} — refusing"
        )
        summary.add(
            StepResult(
                name="real_order",
                status="failed",
                detail=f"qty>{QUANTITY_HARD_CAP} hard cap",
            )
        )
        return False

    print(_c(_RED, _c(_BOLD, "  ⚠  This will place a REAL order with REAL money.")))
    print(_c(_YELLOW, f"     Symbol: {symbol}   Quantity: {quantity}"))
    print(_c(_YELLOW, "     Type 'CONFIRM' (case-sensitive) to proceed, anything else aborts:"))
    answer = input("     > ").strip()
    if answer != "CONFIRM":
        _warn("not confirmed — skipping real order")
        summary.add(
            StepResult(
                name="real_order",
                status="skipped",
                detail="operator declined",
            )
        )
        return True

    print(_c(_YELLOW, f"     Placing in {REAL_ORDER_COUNTDOWN_SECONDS} seconds — ctrl-C to abort"))
    try:
        for i in range(REAL_ORDER_COUNTDOWN_SECONDS, 0, -1):
            print(_c(_YELLOW, f"       {i}…"))
            await asyncio.sleep(1)
    except (KeyboardInterrupt, asyncio.CancelledError):
        _warn("aborted during countdown")
        summary.add(
            StepResult(
                name="real_order",
                status="skipped",
                detail="ctrl-C during countdown",
            )
        )
        return True

    if test_user_email is None or test_strategy_name is None:
        _fail("TEST_USER_EMAIL / TEST_STRATEGY_NAME required for real order")
        summary.add(
            StepResult(
                name="real_order",
                status="failed",
                detail="missing env",
            )
        )
        return False

    from sqlalchemy import select

    from app.db.models.strategy import Strategy
    from app.db.models.user import User
    from app.db.session import get_sessionmaker
    from app.strategy_engine.live_orders.models import LiveOrderRequest
    from app.strategy_engine.live_orders.order_router import place_live_order

    runner = _timed_step(summary, "real_order")

    async def _do() -> tuple[bool, str]:
        maker = get_sessionmaker()
        async with maker() as db:
            user = (
                await db.execute(
                    select(User).where(User.email == test_user_email)
                )
            ).scalar_one_or_none()
            if user is None:
                return False, f"user {test_user_email!r} not found"
            strategy = (
                await db.execute(
                    select(Strategy).where(
                        Strategy.user_id == user.id,
                        Strategy.name == test_strategy_name,
                    )
                )
            ).scalar_one_or_none()
            if strategy is None:
                return False, f"strategy {test_strategy_name!r} not found"

            req = LiveOrderRequest(
                strategy_id=strategy.id,
                symbol=symbol,
                side="BUY",
                quantity=quantity,
                dry_run=False,
            )
            result = await place_live_order(req, db_session=db, user_id=user.id)

        if not result.success:
            return False, (
                f"order rejected: {result.failure_reason_hinglish or '(no reason)'}"
            )
        oid = result.order_id or "(no id returned)"
        summary.notable_order_ids.append(oid)
        return True, f"placed order_id={oid}"

    return await runner(_do)


# ─── CLI + orchestration ─────────────────────────────────────────────


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Manual Dhan integration test runner. Defaults to dry-run; "
            "real orders require --live + 'CONFIRM' typed at the prompt."
        )
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check-token", action="store_true")
    mode.add_argument("--test-historical", action="store_true")
    mode.add_argument("--test-funds", action="store_true")
    mode.add_argument("--test-safety", action="store_true")
    mode.add_argument("--test-flow", action="store_true")
    mode.add_argument("--all", action="store_true")
    parser.add_argument(
        "--live",
        action="store_true",
        help=(
            "Enable the real-order step in --test-flow / --all. Without "
            "this flag the script stops after the dry-run step."
        ),
    )
    parser.add_argument(
        "--symbol",
        default="NIFTY",
        help="Symbol for the dry-run + real order steps. Default NIFTY.",
    )
    parser.add_argument(
        "--quantity",
        type=int,
        default=1,
        help=(
            f"Order quantity. Hard cap = {QUANTITY_HARD_CAP}. Default 1."
        ),
    )
    return parser.parse_args(argv)


def _setup_logging(script_dir: Path) -> Path:
    logs_dir = script_dir / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    log_path = logs_dir / f"dhan_integration_{ts}.log"
    logging.basicConfig(
        filename=str(log_path),
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )
    return log_path


def _load_dotenv_if_present() -> None:
    """Pick up .env from the repo's backend dir if python-dotenv is
    installed. Silent no-op otherwise — env-var-only usage stays
    fully supported."""
    with suppress(ImportError):
        from dotenv import load_dotenv

        backend_root = Path(__file__).resolve().parents[1]
        env_path = backend_root / ".env"
        if env_path.exists():
            load_dotenv(env_path)


async def _run_async(args: argparse.Namespace) -> int:
    base_url = os.environ.get("DHAN_API_BASE_URL", DHAN_API_BASE_URL_DEFAULT)
    access_token = os.environ.get("DHAN_ACCESS_TOKEN")
    client_id = os.environ.get("DHAN_CLIENT_ID")
    test_user_email = os.environ.get("TEST_USER_EMAIL")
    test_strategy_name = os.environ.get("TEST_STRATEGY_NAME")

    summary = RunSummary()

    _info(f"base url: {base_url}")
    _info(
        f"creds: token={'set' if access_token else 'MISSING'} "
        f"client_id={'set' if client_id else 'MISSING'}"
    )
    if args.live:
        _info(_c(_RED, "live mode enabled — real-order step will prompt for CONFIRM"))

    quantity = args.quantity
    if quantity < 1 or quantity > QUANTITY_HARD_CAP:
        _fail(
            f"--quantity must be in [1, {QUANTITY_HARD_CAP}]; got {quantity}"
        )
        return 2

    # Run the relevant steps based on the mode flags.
    if args.check_token or args.all:
        await _step_token_check(summary, base_url, access_token, client_id)
    if args.test_historical or args.all:
        await _step_historical_fetch(summary, access_token)
    if args.test_funds or args.all:
        await _step_funds_check(summary, base_url, access_token, client_id)
    if args.test_safety or args.test_flow or args.all:
        await _step_safety_chain(
            summary, test_user_email, test_strategy_name
        )
    if args.test_flow or args.all:
        # The dry-run step always runs in flow mode — it's the
        # cheapest way to exercise the full orchestrator.
        await _step_dry_run_order(
            summary,
            test_user_email,
            test_strategy_name,
            args.symbol,
            quantity,
        )
        if args.live:
            await _step_real_order(
                summary,
                test_user_email,
                test_strategy_name,
                args.symbol,
                quantity,
            )
        else:
            _info(
                "Skipping real-order step (no --live flag). "
                "Pass --live to exercise the full path."
            )

    summary.render()
    return 0 if summary.all_passed else 1


def main(argv: list[str] | None = None) -> int:
    """CLI entry point. Returns the appropriate exit code."""
    args = _parse_args(argv)
    _load_dotenv_if_present()
    log_path = _setup_logging(Path(__file__).resolve().parent)
    _info(f"detailed log: {log_path}")
    logging.info("dhan_integration_test start argv=%s", json.dumps(sys.argv))
    try:
        return asyncio.run(_run_async(args))
    except KeyboardInterrupt:
        print()
        _warn("interrupted by user")
        return 1


if __name__ == "__main__":
    sys.exit(main())
