"""ORM models — one module per table (or table family).

Import side-effect: importing this package registers every model with
``Base.metadata``, which Alembic's ``env.py`` relies on for autogenerate.
Keep this file as the single source of truth for what tables exist.
"""

from __future__ import annotations

from app.db.models.algomitra_message import AlgoMitraMessage, AlgoMitraRole
from app.db.models.audit_log import ActorType, AuditLog
from app.db.models.broker_credential import BrokerCredential
from app.db.models.copy_trading import CopyTradingFollower, CopyTradingGroup
from app.db.models.idempotency import IdempotencyKey
from app.db.models.kill_switch import KillSwitchConfig, KillSwitchEvent
from app.db.models.strategy import Strategy
from app.db.models.strategy_execution import StrategyExecution
from app.db.models.strategy_position import StrategyPosition
from app.db.models.strategy_signal import StrategySignal
from app.db.models.trade import ProcessingStatus, Trade, TradeStatus
from app.db.models.user import User
from app.db.models.webhook_event import WebhookEvent
from app.db.models.webhook_token import WebhookToken

__all__ = [
    "ActorType",
    "AlgoMitraMessage",
    "AlgoMitraRole",
    "AuditLog",
    "BrokerCredential",
    "CopyTradingFollower",
    "CopyTradingGroup",
    "IdempotencyKey",
    "KillSwitchConfig",
    "KillSwitchEvent",
    "ProcessingStatus",
    "Strategy",
    "StrategyExecution",
    "StrategyPosition",
    "StrategySignal",
    "Trade",
    "TradeStatus",
    "User",
    "WebhookEvent",
    "WebhookToken",
]
