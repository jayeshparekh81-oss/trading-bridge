"""Atomic broker-credential rotation with strategy relink.

Single helper called by both the manual paste-token flow
(``POST /api/users/me/brokers``) and the cron auto-login script
(``scripts/auto_login.py``). Guarantees: deactivate old active creds,
insert new cred, relink strategies — all-or-nothing.

Why same module for both callers: the SQL statement order is the
contract. Cron uses raw psycopg (no SQLAlchemy app boot) so it
implements the same order in raw SQL — comments here are canonical.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.db.models.broker_credential import BrokerCredential
from app.db.models.strategy import Strategy
from app.schemas.broker import BrokerName

logger = get_logger("app.services.cred_relink")


@dataclass(frozen=True)
class RelinkResult:
    new_credential_id: UUID
    deactivated_credential_ids: tuple[UUID, ...]
    relinked_strategy_count: int


async def relink_strategies_to_new_credential(
    session: AsyncSession,
    *,
    user_id: UUID,
    broker_name: BrokerName,
    new_cred: BrokerCredential,
) -> RelinkResult:
    """Atomic rotation: deactivate active creds → INSERT new_cred → relink strategies.

    Caller owns the surrounding transaction (commit/rollback). Caller
    constructs ``new_cred`` with matching ``user_id`` + ``broker_name``,
    ``is_active=True``, encrypted fields populated.

    Statement order (race-safe — see notes below):
      1. SELECT ALL prior cred ids (active OR inactive) for same
         user+broker → snapshot. Includes inactive rows so a
         disconnect-first frontend flow — where the previous cred has
         already been flipped to is_active=false before this function
         runs — still produces a non-empty snapshot. Without this,
         strategies orphaned by the prior disconnect would never be
         relinked.
      2. UPDATE broker_credentials SET is_active=false
         WHERE id IN (snapshot) AND is_active=true
         (id-pinned for race safety vs concurrent INSERT; is_active=true
         filter avoids needless WAL writes against historical inactive
         rows in the broadened snapshot.)
      3. session.add(new_cred); flush  → trips ``uniq_active_broker_per_user``
         partial index if a concurrent writer beat us. IntegrityError
         propagates; caller rolls back + retries.
      4. UPDATE strategies SET broker_credential_id=new_cred.id
         WHERE user_id=... AND broker_credential_id IN (snapshot)
         (ALL strategies — active + inactive; all prior creds — active
         + inactive.)

    Cross-user safety: every WHERE pins user_id. Cross-broker safety:
    snapshot SELECT filters by broker_name; relink UPDATE only touches
    strategies whose old FK is in the broker-scoped snapshot.
    """
    assert new_cred.user_id == user_id
    assert new_cred.broker_name == broker_name
    assert new_cred.is_active is True

    select_stmt = select(BrokerCredential.id).where(
        BrokerCredential.user_id == user_id,
        BrokerCredential.broker_name == broker_name,
    )
    old_ids: tuple[UUID, ...] = tuple(
        (await session.execute(select_stmt)).scalars().all()
    )

    if old_ids:
        await session.execute(
            update(BrokerCredential)
            .where(
                BrokerCredential.id.in_(old_ids),
                BrokerCredential.is_active.is_(True),
            )
            .values(is_active=False)
        )

    session.add(new_cred)
    await session.flush()

    relinked_count = 0
    if old_ids:
        result = await session.execute(
            update(Strategy)
            .where(
                Strategy.user_id == user_id,
                Strategy.broker_credential_id.in_(old_ids),
            )
            .values(broker_credential_id=new_cred.id)
        )
        relinked_count = result.rowcount or 0

    logger.info(
        "cred_relink.completed",
        user_id=str(user_id),
        broker_name=broker_name.value,
        new_credential_id=str(new_cred.id),
        deactivated_credential_ids=[str(x) for x in old_ids],
        relinked_strategy_count=relinked_count,
    )
    return RelinkResult(
        new_credential_id=new_cred.id,
        deactivated_credential_ids=old_ids,
        relinked_strategy_count=relinked_count,
    )


__all__ = ["RelinkResult", "relink_strategies_to_new_credential"]
