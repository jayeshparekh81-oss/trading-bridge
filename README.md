# Trading Bridge

Production-grade SaaS trading bridge for Indian markets. Receives TradingView
webhook alerts and routes them as live orders across multiple Indian brokers
(Fyers, Dhan, Shoonya, Zerodha, Upstox, AngelOne) with built-in risk controls.

## Highlights

- **Multi-broker** — single `BrokerInterface` contract, one file per broker (Zerodha, Dhan, Upstox, ICICI Direct, Angel One, Fyers)
- **Glass Box Indicator Engine** — 70+ technical indicators with per-bar audit logs (Phase F)
- **50+ Strategy Templates** — calibrated for Indian markets with honest backtest numbers
- **AlgoMitra** — in-product AI assistant (Claude-powered) in EN / Hindi / Hinglish / Gujarati
- **Kill switch** — per-user daily loss limit with automatic square-off
- **Circuit breaker** — market volatility protection (ALLOW/PAUSE/HALT)
- **Idempotency** — duplicate TradingView retries are safely deduplicated
- **Multi-strategy** — one user can run multiple isolated strategies in paper + live mode
- **15-layer security** — encryption, HMAC, JWT, brute-force protection, audit trail
- **Notifications** — Email (AWS SES) + Telegram with 16+ templates
- **Observability** — structured JSON logs, Prometheus metrics, audit trail
- **Compliance-first** — SEBI-aware: no return guarantees, no custody, no tip generation

## Architecture

```
TradingView → Webhook API → 7 Safety Gates → Broker Registry → Live Order
                  │                                    │
                Redis (cache + rate limit)       PostgreSQL (persistent)
                  │                                    │
              Celery (async jobs)              12-table schema
```

See [docs/architecture.md](docs/architecture.md) for full details.

## Quick Start

```bash
# Start infrastructure
docker-compose up -d postgres redis

# Backend setup
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env  # Edit: set ENCRYPTION_KEY + JWT_SECRET

# Run
alembic upgrade head
python -m scripts.seed_dev
uvicorn app.main:app --reload
```

Open http://localhost:8000/docs for interactive API documentation.

## Repository Layout

```
trading-bridge/
├── backend/           # FastAPI trading engine + broker integrations
│   ├── app/
│   │   ├── api/       # HTTP endpoints (auth, users, admin, webhook, kill-switch)
│   │   ├── brokers/   # Broker integrations (Fyers, Dhan, + 4 stubs)
│   │   ├── core/      # Config, security, Redis, logging, startup checks
│   │   ├── db/        # SQLAlchemy models (12 tables) + session management
│   │   ├── middleware/ # Security headers, rate limiting, request ID
│   │   ├── schemas/   # Pydantic validation models
│   │   ├── services/  # Business logic (order, kill-switch, notifications, auth)
│   │   ├── tasks/     # Celery scheduled tasks
│   │   └── templates/ # Email + Telegram notification templates
│   ├── tests/         # 620+ tests (unit + integration + benchmarks)
│   ├── scripts/       # Dev seed data
│   └── migrations/    # Alembic database migrations
├── docs/              # Architecture, API reference, deployment, roadmap
└── docker-compose.yml # Full local dev stack (Postgres + Redis + API + Celery)
```

## Test Suite

```bash
cd backend
pytest                    # 620+ tests
pytest --cov=app          # With coverage (92%+)
pytest tests/benchmarks/  # Performance benchmarks
```

## API Endpoints (50+)

| Tag | Endpoints | Auth |
|-----|-----------|------|
| Auth | 6 (register, login, refresh, logout, password, profile) | Mixed |
| Users | 19 (profile, brokers, webhooks, strategies, trades) | Bearer JWT |
| Webhook | 1 (TradingView receiver) | HMAC signature |
| Kill Switch | 8 (status, config, reset, history, test) | Bearer JWT |
| Admin | 11 (users, health, audit, announcements) | Admin JWT |
| Health | 3 (liveness, readiness, detailed) | None |

See [docs/api-reference.md](docs/api-reference.md) for full reference.

## Broker Roadmap

1. **Fyers** — Complete
2. **Dhan** — Complete
3. **Shoonya / Finvasia** — Stub (ready for implementation)
4. **Zerodha Kite** — Stub
5. **Upstox** — Stub
6. **AngelOne SmartAPI** — Stub

## Documentation

### Onboarding (read these first)

- [Architecture Overview](docs/ARCHITECTURE_OVERVIEW.md) — 15-minute system map for new contributors
- [API Getting Started](docs/API_GETTING_STARTED.md) — External developers integrating via webhook or REST
- [Contributing](docs/CONTRIBUTING.md) — Code style, test requirements, PR process, compliance guardrails
- [Deployment Guide](docs/DEPLOYMENT_GUIDE.md) — Environments, Gate 2 review, rollback playbooks

### Authoring guides

- [Indicator Authoring](docs/INDICATOR_AUTHORING_GUIDE.md) — Adding a new technical indicator end-to-end (Phase F Glass Box)
- [Strategy Template Authoring](docs/STRATEGY_TEMPLATE_AUTHORING.md) — Adding a new clone-able strategy template

### Deep dives (reference)

- [Full Architecture](docs/architecture.md) — Detailed system design, 15 security layers
- [API Reference](docs/api-reference.md) — Every endpoint, auth flow, webhook setup
- [Deployment Deep Dive](docs/deployment.md) — Local, Docker, AWS EC2, SSL
- [Roadmap](docs/roadmap.md) — Full product vision (12+ phases)
- [Strategy Templates Catalog](docs/STRATEGY_TEMPLATES_CATALOG.md) — All active templates
- [Indicator Registry](docs/indicator-registry.md) — Phase F audit notes

## Tech Stack

- **Runtime**: Python 3.11+, FastAPI, Uvicorn + uvloop
- **Database**: PostgreSQL 16, SQLAlchemy 2.0, Alembic
- **Cache**: Redis 7 (rate limiting, kill switch, P&L, sessions)
- **Queue**: Celery (notifications, scheduled tasks)
- **Security**: Fernet AES, bcrypt, HMAC-SHA256, JWT
- **Testing**: pytest (620+ tests), fakeredis, 92%+ coverage

## License

Proprietary. All rights reserved.
