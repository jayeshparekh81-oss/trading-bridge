"""Clone service — materialise a strategy from a template.

The endpoint ``POST /api/templates/{slug}/clone`` dispatches here.
The service:

    1. Loads the template by slug. 404 if not found.
    2. Returns 501 with a clear message if
       ``requires_options_builder=True``.
    3. Returns 409 if ``is_active=False`` (cataloged but not yet
       shipping). Distinct from 501 so the frontend renders the
       right CTA per state.
    4. Otherwise creates a :class:`Strategy` row mirroring the
       existing ``POST /api/users/me/strategies`` flow — same
       column writes, same defaults. We DO NOT call the existing
       HTTP endpoint internally (would be a self-call); we mirror
       its semantics via the ORM directly.
    5. Inserts a :class:`StrategyTemplateOrigin` row recording
       provenance.
    6. Re-validates the template's ``config_json`` defensively
       before committing — guards against a malformed catalog
       row leaking into a strategy.

The created :class:`Strategy` is intentionally minimal: name +
user_id + ``is_active=True``. Webhook + broker wiring is the
user's next step on the strategy detail page — same pattern as a
manually-created strategy. Phase 1 deliberately doesn't try to
auto-populate the strategy's execution-engine fields from
``config_json``; that's a Phase 7-8 backtest-engine concern.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.strategy import Strategy
from app.db.models.user import User
from app.templates.models import StrategyTemplate, StrategyTemplateOrigin
from app.templates.registry import get_template_by_slug
from app.templates.validator import (
    TemplateConfigError,
    validate_config_json,
)


class TemplateNotFoundError(LookupError):
    """Raised when the requested slug does not match any catalog row."""


class TemplateNotCloneableError(RuntimeError):
    """Raised when a template is on the catalog but not yet cloneable.

    Two sub-cases:
        * ``requires_options_builder=True`` — Phase 7-8 feature; 501
        * ``is_active=False`` (and not options) — Phase 1 cataloged
          but the config isn't ready; 409
    """

    def __init__(self, *, slug: str, http_status: int, message: str) -> None:
        super().__init__(message)
        self.slug = slug
        self.http_status = http_status
        self.message = message


async def clone_template(
    db: AsyncSession,
    user: User,
    slug: str,
    *,
    name_override: str | None = None,
) -> tuple[Strategy, StrategyTemplate]:
    """Materialise a strategy from a template.

    Returns the new :class:`Strategy` + the source :class:`StrategyTemplate`
    (caller uses both for the response envelope). Raises:

    * :class:`TemplateNotFoundError` — slug doesn't exist.
    * :class:`TemplateNotCloneableError` — present but not yet
      cloneable. Carries ``http_status`` (501 or 409) the API
      layer translates to the wire response.

    Re-validates the template's ``config_json`` before persisting.
    A catalog row with malformed config (e.g. created via direct
    SQL bypassing the registry) raises :class:`TemplateConfigError`,
    which the API layer surfaces as 500 — that indicates a data-
    integrity issue worth paging on.
    """
    template = await get_template_by_slug(db, slug)
    if template is None:
        raise TemplateNotFoundError(f"Template not found: {slug!r}")

    if template.requires_options_builder:
        raise TemplateNotCloneableError(
            slug=slug,
            http_status=501,
            message=(
                "Options-strategy templates require the options builder "
                "which is shipping in Phase 7-8. Save this template for "
                "later — we'll notify you when it's live."
            ),
        )

    if not template.is_active:
        raise TemplateNotCloneableError(
            slug=slug,
            http_status=409,
            message=(
                "This template is in the catalog but its trading config "
                "is still being finalised — coming soon."
            ),
        )

    # Defensive re-validation. The active path requires a populated
    # config_json; if a direct DB write bypassed the registry's
    # validation we want to catch it here, not at strategy-execute time.
    validate_config_json(template.config_json, is_active=True)

    strategy_name = (
        (name_override or "").strip()
        or f"{template.name} (from template)"
    )

    strategy = Strategy(
        user_id=user.id,
        name=strategy_name,
        webhook_token_id=None,
        broker_credential_id=None,
        max_position_size=0,
        allowed_symbols=[],
        is_active=True,
    )
    db.add(strategy)
    await db.flush()  # populate strategy.id without ending the transaction

    origin = StrategyTemplateOrigin(
        strategy_id=strategy.id,
        template_id=template.id,
        template_slug=template.slug,
        cloned_at=datetime.now(UTC),
    )
    db.add(origin)
    await db.flush()

    return strategy, template


__all__ = [
    "TemplateConfigError",
    "TemplateNotCloneableError",
    "TemplateNotFoundError",
    "clone_template",
]
