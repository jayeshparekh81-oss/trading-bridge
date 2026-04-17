"""Development seed data.

Run with: python -m scripts.seed_dev

Creates test users, broker credentials, webhook tokens, and kill switch
configs so a developer can start testing immediately after ``docker-compose up``.
"""

from __future__ import annotations

import asyncio
import hashlib
import os
import sys
from decimal import Decimal
from pathlib import Path

# Ensure the backend package is on sys.path when run as a script.
_BACKEND = Path(__file__).resolve().parent.parent
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))


async def seed() -> None:
    """Create seed data in the database."""
    from app.core.config import get_settings
    from app.core.security import encrypt_credential, generate_webhook_token, hash_password
    from app.db.models.kill_switch import KillSwitchConfig
    from app.db.models.user import User
    from app.db.models.webhook_token import WebhookToken
    from app.db.models.broker_credential import BrokerCredential
    from app.db.session import get_sessionmaker, dispose_engine

    settings = get_settings()
    maker = get_sessionmaker()

    async with maker() as session:
        from sqlalchemy import select

        # ── 1. Admin user ──────────────────────────────────────────────
        admin_email = "admin@tradingbridge.in"
        existing = (
            await session.execute(select(User).where(User.email == admin_email))
        ).scalar_one_or_none()

        if existing:
            print(f"  [skip] Admin user already exists: {admin_email}")
            admin = existing
        else:
            admin = User(
                email=admin_email,
                password_hash=hash_password("Admin123!"),
                full_name="Admin User",
                is_active=True,
                is_admin=True,
                notification_prefs={"email": True, "telegram": False},
            )
            session.add(admin)
            await session.flush()
            session.add(
                KillSwitchConfig(
                    user_id=admin.id,
                    max_daily_loss_inr=Decimal("50000"),
                    max_daily_trades=200,
                    enabled=True,
                    auto_square_off=True,
                )
            )
            print(f"  [created] Admin: {admin_email} / Admin123!")

        # ── 2. Test user ───────────────────────────────────────────────
        test_email = "test@tradingbridge.in"
        existing = (
            await session.execute(select(User).where(User.email == test_email))
        ).scalar_one_or_none()

        if existing:
            print(f"  [skip] Test user already exists: {test_email}")
            test_user = existing
        else:
            test_user = User(
                email=test_email,
                password_hash=hash_password("Test123!"),
                full_name="Test Trader",
                is_active=True,
                is_admin=False,
                notification_prefs={"email": True, "telegram": False},
            )
            session.add(test_user)
            await session.flush()
            session.add(
                KillSwitchConfig(
                    user_id=test_user.id,
                    max_daily_loss_inr=Decimal("5000"),
                    max_daily_trades=50,
                    enabled=True,
                    auto_square_off=True,
                )
            )
            print(f"  [created] Test user: {test_email} / Test123!")

        # ── 3. Webhook token for test user ─────────────────────────────
        raw_token = generate_webhook_token()
        hmac_secret = generate_webhook_token(16)
        token_hash = hashlib.sha256(raw_token.encode()).hexdigest()

        wt = WebhookToken(
            user_id=test_user.id,
            token_hash=token_hash,
            hmac_secret_enc=encrypt_credential(hmac_secret),
            label="dev-webhook",
            is_active=True,
        )
        session.add(wt)
        print(f"  [created] Webhook token: {raw_token[:16]}...")
        print(f"            HMAC secret:   {hmac_secret[:16]}...")
        print(f"            URL: POST /api/webhook/{raw_token}")

        # ── 4. Fake Fyers broker credential for test user ──────────────
        cred = BrokerCredential(
            user_id=test_user.id,
            broker_name="FYERS",
            client_id_enc=encrypt_credential("DEV_CLIENT_ID"),
            api_key_enc=encrypt_credential("DEV_API_KEY"),
            api_secret_enc=encrypt_credential("DEV_API_SECRET"),
            is_active=True,
        )
        session.add(cred)
        print("  [created] Fyers broker credential (dev/fake)")

        await session.commit()

    await dispose_engine()

    print("\n  Seed complete. You can now:")
    print(f"    POST /api/auth/login  {{\"email\": \"{admin_email}\", \"password\": \"Admin123!\"}}")
    print(f"    POST /api/auth/login  {{\"email\": \"{test_email}\", \"password\": \"Test123!\"}}")


def main() -> None:
    print("\n=== Trading Bridge — Seeding Development Data ===\n")
    asyncio.run(seed())
    print()


if __name__ == "__main__":
    main()
