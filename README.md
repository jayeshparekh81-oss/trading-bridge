# Trading Bridge

Production-grade SaaS trading bridge for Indian markets. Receives TradingView
webhook alerts and routes them as live orders across multiple Indian brokers
(Fyers, Dhan, Shoonya, Zerodha, Upstox, AngelOne) with built-in risk controls.

## Highlights

- **Multi-broker** — single `BrokerInterface` contract, one file per broker.
- **Kill switch** — per-user daily loss limit with automatic square-off.
- **Idempotency** — duplicate TradingView retries are safely deduplicated.
- **Multi-strategy** — one user can run multiple isolated strategies.
- **Observability** — structured JSON logs, Prometheus metrics, audit trail.

## Repository Layout

```
trading-bridge/
├── backend/      # FastAPI trading engine + broker integrations
├── frontend/     # Next.js 14 dashboard (added in later phase)
├── infra/        # Terraform, monitoring, nginx (added in later phase)
├── docs/         # Architecture & runbooks (added in later phase)
└── docker-compose.yml  # Full local dev stack (added in later phase)
```

## Current Phase

**Phase 1 — Backend MVP.** Webhook receiver, BrokerInterface, Fyers
integration, kill switch, notifications (Email + Telegram). See
`backend/README.md` for setup.

## Broker Roadmap

1. Fyers — Phase 1
2. Dhan — Phase 2
3. Shoonya / Finvasia — Phase 3
4. Zerodha Kite — Phase 4
5. Upstox — Phase 5
6. AngelOne SmartAPI — Phase 6

## License

Proprietary. All rights reserved.
