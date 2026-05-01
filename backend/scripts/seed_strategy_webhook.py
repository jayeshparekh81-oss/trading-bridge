"""Seed the strategy webhook for end-to-end paper-mode testing.

Run with::

    python -m scripts.seed_strategy_webhook

Idempotent. Looks up the target user by ``USER_ID`` (set in this module
or via the ``TRADETRI_SEED_USER_ID`` env var) and:

    1. Finds an *active* Dhan ``BrokerCredential`` for that user.
    2. Creates (or reuses) a ``WebhookToken`` labelled ``strategy-paper-test``.
    3. Creates (or reuses) a ``Strategy`` row binding the token →
       credential, configured for paper-mode 1-lot entries with AI
       validation disabled so the executor honours the configured lot
       count without needing 17 Pine indicator fields in every payload.

On the first run the raw token + HMAC secret are printed to stdout —
save them, they are not stored in plaintext anywhere. Subsequent runs
detect the existing rows and skip recreation; the token cannot be
recovered after that point (token_hash is one-way, hmac_secret_enc is
Fernet-encrypted), so re-running with ``--rotate`` issues a new token.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import os
import sys
from pathlib import Path
from uuid import UUID

# Ensure the backend package is on sys.path when run as a script.
_BACKEND = Path(__file__).resolve().parent.parent
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))


#: User to seed for. Override via env var if you want to seed a different
#: account without editing the script.
DEFAULT_USER_ID = UUID("46a56dd5-492c-489a-a315-86204f36a022")

#: Strategy label that anchors the webhook → broker binding. Re-using
#: this label on subsequent runs makes the script idempotent.
STRATEGY_NAME = "tradetri-strategy-paper-test"
TOKEN_LABEL = "strategy-paper-test"

#: Symbols the Pine mapper falls back to when an alert omits ``symbol``.
#: BSE1! is included for the BSE futures track; NIFTY/BANKNIFTY for NSE.
ALLOWED_SYMBOLS: list[str] = ["NIFTY", "BSE1!", "BANKNIFTY"]


async def seed(*, user_id: UUID, rotate_token: bool) -> None:
    from sqlalchemy import select

    from app.core.security import (
        encrypt_credential,
        generate_webhook_token,
    )
    from app.db.models.broker_credential import BrokerCredential
    from app.db.models.strategy import Strategy
    from app.db.models.user import User
    from app.db.models.webhook_token import WebhookToken
    from app.db.session import dispose_engine, get_sessionmaker
    from app.schemas.broker import BrokerName

    maker = get_sessionmaker()

    async with maker() as session:
        user = (
            await session.execute(select(User).where(User.id == user_id))
        ).scalar_one_or_none()
        if user is None:
            sys.exit(
                f"  [error] User {user_id} not found. Register first via "
                "POST /api/auth/register."
            )

        # Prefer Dhan (auto-login covered tonight); fall back to any active
        # credential so users on Fyers-only setups still see the e2e flow.
        creds_q = await session.execute(
            select(BrokerCredential).where(
                BrokerCredential.user_id == user_id,
                BrokerCredential.is_active.is_(True),
            )
        )
        all_creds = creds_q.scalars().all()
        if not all_creds:
            sys.exit(
                f"  [error] No active broker credentials for user {user_id}. "
                "Add a Dhan or Fyers credential first."
            )

        cred = next(
            (c for c in all_creds if c.broker_name == BrokerName.DHAN),
            all_creds[0],
        )
        print(
            f"  [pick] Broker credential: {cred.broker_name.value} "
            f"({cred.id})"
        )

        existing_token = (
            await session.execute(
                select(WebhookToken).where(
                    WebhookToken.user_id == user_id,
                    WebhookToken.label == TOKEN_LABEL,
                    WebhookToken.is_active.is_(True),
                )
            )
        ).scalar_one_or_none()

        if existing_token is not None and not rotate_token:
            print(
                f"  [skip] Webhook token already exists "
                f"(id={existing_token.id}); pass --rotate to issue a new one."
            )
            token_id = existing_token.id
            raw_token: str | None = None
            hmac_secret: str | None = None
        else:
            if existing_token is not None:
                existing_token.is_active = False
                print(f"  [rotate] Deactivating old token id={existing_token.id}.")
            raw_token = generate_webhook_token()
            hmac_secret = generate_webhook_token(16)
            token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
            wt = WebhookToken(
                user_id=user_id,
                token_hash=token_hash,
                hmac_secret_enc=encrypt_credential(hmac_secret),
                label=TOKEN_LABEL,
                is_active=True,
            )
            session.add(wt)
            await session.flush()
            token_id = wt.id
            print(f"  [created] Webhook token id={token_id}")

        # ── Strategy: webhook_token → broker_credential, paper-friendly ──
        existing_strategy = (
            await session.execute(
                select(Strategy).where(
                    Strategy.user_id == user_id,
                    Strategy.name == STRATEGY_NAME,
                )
            )
        ).scalar_one_or_none()

        if existing_strategy is not None:
            existing_strategy.webhook_token_id = token_id
            existing_strategy.broker_credential_id = cred.id
            existing_strategy.is_active = True
            existing_strategy.entry_lots = 1
            existing_strategy.partial_profit_lots = 0
            existing_strategy.trail_lots = 0
            existing_strategy.allowed_symbols = ALLOWED_SYMBOLS
            existing_strategy.ai_validation_enabled = False
            print(f"  [updated] Strategy id={existing_strategy.id}")
        else:
            strategy = Strategy(
                user_id=user_id,
                name=STRATEGY_NAME,
                webhook_token_id=token_id,
                broker_credential_id=cred.id,
                entry_lots=1,
                partial_profit_lots=0,
                trail_lots=0,
                allowed_symbols=ALLOWED_SYMBOLS,
                ai_validation_enabled=False,
                is_active=True,
            )
            session.add(strategy)
            await session.flush()
            print(f"  [created] Strategy id={strategy.id}")

        await session.commit()

    await dispose_engine()

    print()
    if raw_token is not None and hmac_secret is not None:
        print("  ── COPY THESE NOW. Token + secret are not retrievable later. ──")
        print(f"  WEBHOOK_TOKEN={raw_token}")
        print(f"  HMAC_SECRET={hmac_secret}")
        print()
        print("  Webhook URL: POST /api/webhook/strategy/<WEBHOOK_TOKEN>")
        print(
            "  Sign payloads with: python scripts/sign_webhook.py "
            "--secret $HMAC_SECRET --body <payload.json>"
        )


def _parse_user_id(raw: str | None) -> UUID:
    if not raw:
        return DEFAULT_USER_ID
    try:
        return UUID(raw)
    except ValueError:
        sys.exit(f"  [error] TRADETRI_SEED_USER_ID is not a valid UUID: {raw!r}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--rotate",
        action="store_true",
        help="Deactivate the existing token and issue a new one.",
    )
    parser.add_argument(
        "--user-id",
        default=os.environ.get("TRADETRI_SEED_USER_ID"),
        help="UUID of the user to seed (defaults to the founder account).",
    )
    args = parser.parse_args()

    print("\n=== TRADETRI — Seed Strategy Webhook (Paper Mode) ===\n")
    asyncio.run(
        seed(
            user_id=_parse_user_id(args.user_id),
            rotate_token=args.rotate,
        )
    )
    print()


if __name__ == "__main__":
    main()
