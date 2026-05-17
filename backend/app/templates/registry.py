"""Catalog registry — seed-loader + query helpers.

Provides the bridge between the static seed JSON
(``backend/data/strategy_templates_seed.json``) and the live
``strategy_templates`` table.

Phase 1 split: the seed file is the source of truth for both schema
shape and content. A future Phase 3+ admin UI can overwrite catalog
rows directly, but Phase 1 expects the seed to be the canonical
input — re-running ``load_from_seed_file`` is idempotent and brings
the table to match the file.

Public API:
    :func:`load_from_seed_file`
        Idempotent upsert of seed rows into the catalog. Returns
        counts of inserted vs updated rows. Used by the seed CLI
        (``scripts/seed_strategy_templates.py``) and by tests.

    :func:`list_templates`
        Filtered list query for the picker endpoint.

    :func:`get_template_by_slug`
        Detail lookup.

    :func:`category_counts`
        Aggregate counts for the picker's filter sidebar.

Seed file path resolves via ``settings.STRATEGY_TEMPLATES_SEED_PATH``
if configured (test isolation), else defaults to the project's
``backend/data/strategy_templates_seed.json``.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import Integer, case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.templates.models import StrategyTemplate
from app.templates.validator import (
    TemplateConfigError,
    validate_config_json,
)


_REPO_ROOT = Path(__file__).resolve().parents[3]
_DEFAULT_SEED_PATH = (
    _REPO_ROOT / "backend" / "data" / "strategy_templates_seed.json"
)


# ─── Seed loader ───────────────────────────────────────────────────────


class SeedLoadResult:
    """Outcome of :func:`load_from_seed_file`. Plain data class for
    easy assertion in tests."""

    __slots__ = ("inserted", "updated", "total_in_file", "validated_active")

    def __init__(
        self,
        inserted: int,
        updated: int,
        total_in_file: int,
        validated_active: int,
    ) -> None:
        self.inserted = inserted
        self.updated = updated
        self.total_in_file = total_in_file
        self.validated_active = validated_active

    def __repr__(self) -> str:
        return (
            f"SeedLoadResult(inserted={self.inserted}, "
            f"updated={self.updated}, total={self.total_in_file}, "
            f"validated_active={self.validated_active})"
        )


def _coerce_seed_row(row: dict[str, Any], now: datetime) -> dict[str, Any]:
    """Coerce a seed JSON entry to a dict ready for ORM upsert.

    Validates ``config_json`` against the active/inactive rules.
    Fills in defaults for optional fields. Raises ``TemplateConfigError``
    on validation failure with the slug prefixed for traceability.
    """
    slug = row.get("slug")
    if not isinstance(slug, str) or not slug:
        raise TemplateConfigError(
            f"seed row missing 'slug': {row.get('name', '?')!r}"
        )

    is_active = bool(row.get("is_active", False))
    config = row.get("config_json", {})
    try:
        validate_config_json(config, is_active=is_active)
    except TemplateConfigError as exc:
        raise TemplateConfigError(f"[slug={slug}] {exc}") from exc

    return {
        "slug": slug,
        "name": row["name"],
        "segment": row["segment"],
        "instrument_type": row["instrument_type"],
        "category": row["category"],
        "complexity": row["complexity"],
        "description_en": row.get("description_en", ""),
        "description_hi": row.get("description_hi", ""),
        "config_json": config,
        "risk_level": row["risk_level"],
        "recommended_capital_inr": int(row.get("recommended_capital_inr", 0)),
        "timeframe": row.get("timeframe", "5m"),
        "indicators_used": row.get("indicators_used", []),
        "index_filter": row.get("index_filter", []),
        "tags": row.get("tags", []),
        "is_active": is_active,
        "requires_options_builder": bool(
            row.get("requires_options_builder", False)
        ),
        "legs_count": row.get("legs_count"),
        "display_order": int(row.get("display_order", 0)),
        "created_at": now,
        "updated_at": now,
    }


async def load_from_seed_file(
    db: AsyncSession,
    *,
    seed_path: Path | None = None,
) -> SeedLoadResult:
    """Idempotently upsert seed rows into ``strategy_templates``.

    Looks up each row by ``slug``. If present, UPDATE the row's
    metadata + ``config_json`` (preserves ``id`` + ``created_at``).
    If absent, INSERT a new row. Returns a :class:`SeedLoadResult`
    with insert/update counts.

    Validates ``config_json`` of every row before any DB writes
    happen — if any row fails validation the entire load is aborted
    and the database is left untouched (no partial writes).
    """
    path = seed_path or _DEFAULT_SEED_PATH
    if not path.exists():
        raise FileNotFoundError(f"Seed file not found: {path}")

    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or "templates" not in raw:
        raise TemplateConfigError(
            "Seed file must be {'templates': [...]} object"
        )

    rows = raw["templates"]
    if not isinstance(rows, list):
        raise TemplateConfigError("Seed 'templates' must be a list")

    now = datetime.now(UTC)
    coerced = [_coerce_seed_row(row, now) for row in rows]
    validated_active = sum(1 for r in coerced if r["is_active"])

    existing_slugs = {
        slug
        for (slug,) in (
            await db.execute(select(StrategyTemplate.slug))
        ).all()
    }

    inserted = 0
    updated = 0
    for data in coerced:
        if data["slug"] in existing_slugs:
            existing = (
                await db.execute(
                    select(StrategyTemplate).where(
                        StrategyTemplate.slug == data["slug"]
                    )
                )
            ).scalar_one()
            for field, value in data.items():
                if field == "created_at":
                    continue  # preserve original created_at
                setattr(existing, field, value)
            updated += 1
        else:
            db.add(StrategyTemplate(**data))
            inserted += 1

    await db.flush()

    return SeedLoadResult(
        inserted=inserted,
        updated=updated,
        total_in_file=len(coerced),
        validated_active=validated_active,
    )


# ─── Query helpers ─────────────────────────────────────────────────────


async def list_templates(
    db: AsyncSession,
    *,
    category: str | None = None,
    complexity: str | None = None,
    segment: str | None = None,
    is_active: bool | None = None,
    search: str | None = None,
) -> list[StrategyTemplate]:
    """Filtered list query for the picker endpoint.

    All filters are ANDed. ``search`` does a case-insensitive
    substring match against ``name`` and ``description_en``.
    Results are ordered by ``(is_active DESC, display_order ASC,
    name ASC)`` so active templates surface first and the human-
    curated ``display_order`` controls within-bucket sequencing.
    """
    stmt = select(StrategyTemplate)
    if category is not None:
        stmt = stmt.where(StrategyTemplate.category == category)
    if complexity is not None:
        stmt = stmt.where(StrategyTemplate.complexity == complexity)
    if segment is not None:
        stmt = stmt.where(StrategyTemplate.segment == segment)
    if is_active is not None:
        stmt = stmt.where(StrategyTemplate.is_active == is_active)
    if search is not None and search.strip():
        like = f"%{search.strip().lower()}%"
        stmt = stmt.where(
            func.lower(StrategyTemplate.name).like(like)
            | func.lower(StrategyTemplate.description_en).like(like)
        )
    stmt = stmt.order_by(
        StrategyTemplate.is_active.desc(),
        StrategyTemplate.display_order.asc(),
        StrategyTemplate.name.asc(),
    )
    rows = (await db.execute(stmt)).scalars().all()
    return list(rows)


async def get_template_by_slug(
    db: AsyncSession, slug: str
) -> StrategyTemplate | None:
    """Detail lookup by stable slug. Returns ``None`` if not found."""
    stmt = select(StrategyTemplate).where(StrategyTemplate.slug == slug)
    return (await db.execute(stmt)).scalar_one_or_none()


async def category_counts(
    db: AsyncSession,
) -> list[tuple[str, int, int]]:
    """Per-category counts: ``(category, total, active_only)``.

    Powers the picker's filter sidebar "(N)" badges. Returned as a
    list of tuples sorted by category name; the API layer wraps into
    :class:`CategoryCounts`.
    """
    active_int = case(
        (StrategyTemplate.is_active.is_(True), 1),
        else_=0,
    )
    stmt = (
        select(
            StrategyTemplate.category,
            func.count(StrategyTemplate.id),
            func.coalesce(func.sum(active_int), 0).cast(Integer),
        )
        .group_by(StrategyTemplate.category)
        .order_by(StrategyTemplate.category)
    )
    rows = (await db.execute(stmt)).all()
    return [(cat, int(total or 0), int(active or 0)) for cat, total, active in rows]


__all__ = [
    "SeedLoadResult",
    "category_counts",
    "get_template_by_slug",
    "list_templates",
    "load_from_seed_file",
]
