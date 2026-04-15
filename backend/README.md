# Trading Bridge — Backend

FastAPI trading engine that receives TradingView webhooks and places orders
across Indian brokers with built-in risk controls.

## Tech Stack

- Python 3.11+
- FastAPI + Pydantic v2
- SQLAlchemy 2.0 (async) + Alembic
- PostgreSQL + Redis
- Celery (async tasks)
- structlog (JSON logs) + prometheus-client
- pytest + mypy (strict) + ruff

## Prerequisites

- Python 3.11 or newer
- PostgreSQL 15+ (local or Docker)
- Redis 7+ (local or Docker)
- [uv](https://github.com/astral-sh/uv) (recommended) or pip

## Setup

```bash
# 1. Clone and enter backend directory
cd backend

# 2. Create virtualenv and install dependencies
#    Using uv (recommended):
uv venv
source .venv/bin/activate
uv pip install -e ".[dev]"

#    Or using pip:
python3.11 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# 3. Copy environment template and fill in values
cp .env.example .env
# Generate a Fernet key:
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
# Generate a JWT secret:
openssl rand -hex 32

# 4. Run the test suite
pytest

# 5. Type check
mypy app

# 6. Lint
ruff check app tests
ruff format --check app tests
```

## Running the Dev Server

> Dev server entrypoint lands in a later step; not yet wired up.

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

## Project Layout

```
backend/
├── app/
│   ├── api/              # FastAPI routers (webhook, auth, users, …)
│   ├── brokers/          # BrokerInterface + per-broker implementations
│   ├── core/             # Security, logging, Redis client, exceptions
│   ├── db/               # SQLAlchemy session + models
│   ├── schemas/          # Pydantic request/response models
│   ├── services/         # Business logic (orders, P&L, kill switch, …)
│   ├── tasks/            # Celery async tasks
│   └── templates/        # Notification templates (email/telegram)
├── migrations/           # Alembic migrations
├── tests/                # pytest suites
├── pyproject.toml
└── .env.example
```

## Development Discipline

- One file/module at a time — no file lands without tests.
- Type hints mandatory; mypy strict mode must pass.
- `Decimal` for money, never `float`.
- Magic strings/numbers live in enums or constants.
- Raise specific exceptions; never bare `Exception`.

## Phase 1 Scope

Webhook endpoint, BrokerInterface, Fyers integration, kill switch,
idempotency, strategies, notifications (Email + Telegram), Prometheus
metrics. No billing — admin manually provisions beta users.
