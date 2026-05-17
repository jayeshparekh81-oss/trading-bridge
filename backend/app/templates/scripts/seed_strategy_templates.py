"""Idempotent seed loader CLI for the Strategy Template System.

Usage::

    python -m app.templates.scripts.seed_strategy_templates
    python -m app.templates.scripts.seed_strategy_templates --seed-path /custom/path.json
    python -m app.templates.scripts.seed_strategy_templates --dry-run

Runs the ``load_from_seed_file`` registry helper inside a single
managed AsyncSession bound to the canonical engine + sessionmaker
exposed by :mod:`app.db.session`. Idempotent — re-running against
an already-seeded table updates each row in place by ``slug``,
preserving the original ``id`` and ``created_at``.

Exit codes
    0  Success. Counts printed to stdout in machine-parseable form.
    1  Generic runtime error (DB connection, unexpected exception).
    2  Validation error in the seed file
       (:class:`app.templates.validator.TemplateConfigError`).
    3  Seed file missing.

Output format (stdout, on success)::

    seed_loader.success inserted=N updated=N total_in_file=N validated_active=N
    seed_loader.row_counts total=N active=N inactive=N options_pending=N

Both lines emit key=value pairs so the deploy runbook can `grep` for
the markers without parsing JSON.

Dry-run mode runs the validator across every seed row but rolls back
the transaction at the end, so no DB writes hit the schema. Useful
for "lint" runs in CI before the actual deploy seed step.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

from sqlalchemy import case, func, select

from app.db.session import get_engine, get_sessionmaker
from app.templates.models import StrategyTemplate
from app.templates.registry import (
    SeedLoadResult,
    load_from_seed_file,
)
from app.templates.validator import TemplateConfigError


async def _run(seed_path: Path | None, dry_run: bool) -> int:
    factory = get_sessionmaker()
    try:
        async with factory() as db:
            try:
                result: SeedLoadResult = await load_from_seed_file(
                    db, seed_path=seed_path
                )
            except FileNotFoundError as exc:
                print(
                    f"seed_loader.error type=FileNotFoundError detail={exc}",
                    file=sys.stderr,
                )
                return 3
            except TemplateConfigError as exc:
                print(
                    f"seed_loader.error type=TemplateConfigError detail={exc}",
                    file=sys.stderr,
                )
                return 2

            if dry_run:
                await db.rollback()
                print(
                    "seed_loader.dry_run "
                    f"would_insert={result.inserted} "
                    f"would_update={result.updated} "
                    f"total_in_file={result.total_in_file} "
                    f"validated_active={result.validated_active}",
                )
                return 0

            await db.commit()

            # Re-query for the verification line — the result above
            # reflects the seed file; this line confirms what is now
            # actually in the table (catches any phantom out-of-band
            # rows that the seed loader doesn't touch).
            active_int = case(
                (StrategyTemplate.is_active.is_(True), 1), else_=0
            )
            options_int = case(
                (StrategyTemplate.requires_options_builder.is_(True), 1),
                else_=0,
            )
            row = (
                await db.execute(
                    select(
                        func.count(StrategyTemplate.id),
                        func.coalesce(func.sum(active_int), 0),
                        func.coalesce(func.sum(options_int), 0),
                    )
                )
            ).one()
            total, active_count, options_pending = (
                int(row[0]),
                int(row[1]),
                int(row[2]),
            )
            inactive = total - active_count

            print(
                "seed_loader.success "
                f"inserted={result.inserted} "
                f"updated={result.updated} "
                f"total_in_file={result.total_in_file} "
                f"validated_active={result.validated_active}",
            )
            print(
                "seed_loader.row_counts "
                f"total={total} "
                f"active={active_count} "
                f"inactive={inactive} "
                f"options_pending={options_pending}",
            )
    finally:
        # CLI process exits after this — but disposing the engine
        # explicitly emits a clean asyncpg connection shutdown rather
        # than relying on Python's garbage collector + ResourceWarning
        # at process exit.
        await get_engine().dispose()

    return 0


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="python -m app.templates.scripts.seed_strategy_templates",
        description=(
            "Idempotently load the Strategy Template System seed JSON "
            "into the strategy_templates table."
        ),
    )
    parser.add_argument(
        "--seed-path",
        type=Path,
        default=None,
        metavar="PATH",
        help=(
            "Override seed file location. Defaults to "
            "backend/data/strategy_templates_seed.json relative to the "
            "repo root."
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help=(
            "Validate every row + show what would be inserted/updated, "
            "then rollback. No DB writes."
        ),
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv if argv is not None else sys.argv[1:])
    try:
        return asyncio.run(_run(args.seed_path, args.dry_run))
    except KeyboardInterrupt:
        print("seed_loader.error type=KeyboardInterrupt", file=sys.stderr)
        return 1
    except Exception as exc:  # noqa: BLE001 — top-level CLI guard
        print(
            f"seed_loader.error type={type(exc).__name__} detail={exc}",
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    sys.exit(main())
