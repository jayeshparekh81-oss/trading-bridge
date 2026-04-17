# Product Roadmap

**Mission**: Democratize trading for 95% retail traders who lack access to
professional-grade algorithmic trading tools.

## Phase 1-2: The Bridge (DONE)

- [x] TradingView webhook receiver
- [x] BrokerInterface abstraction
- [x] Fyers v3 integration (complete)
- [x] Dhan HQ integration (complete)
- [x] 4 broker stubs (Shoonya, Zerodha, Upstox, AngelOne)
- [x] Kill switch (per-user daily loss limit + auto square-off)
- [x] Circuit breaker (market volatility protection)
- [x] Idempotency (duplicate signal prevention)
- [x] Multi-strategy support
- [x] JWT authentication + brute-force protection
- [x] Email (AWS SES) + Telegram notifications
- [x] Admin panel API
- [x] User profile + broker management API
- [x] Trade history + CSV export + P&L stats
- [x] Docker Compose full stack
- [x] 620+ tests, 92%+ coverage

## Phase 3-4: Frontend + Launch

- [ ] Next.js 14 dashboard
  - Real-time P&L display
  - Trade history with charts
  - Broker connection wizard
  - Kill switch control panel
  - Strategy builder (visual)
  - Webhook setup helper
- [ ] User onboarding flow
- [ ] Billing integration (Razorpay)
- [ ] Landing page + marketing site
- [ ] Beta launch (50 users)
- [ ] Public launch

## Phase 5-6: Strategy Builder + Marketplace

- [ ] Visual strategy builder (no-code)
- [ ] Strategy backtesting engine
- [ ] Paper trading mode
- [ ] Strategy marketplace
  - Top strategies ranked by returns
  - One-click copy trading
  - Revenue sharing for strategy creators
- [ ] Copy trading groups
- [ ] Social trading feed

## Phase 7-8: Charting + Options Analytics

- [ ] TradingView-grade charting (lightweight-charts)
- [ ] Real-time market data (WebSocket)
- [ ] Options chain viewer
- [ ] Greeks calculator (Delta, Gamma, Theta, Vega)
- [ ] Options strategy builder (Iron Condor, Straddle, etc.)
- [ ] IV surface visualization
- [ ] Max pain calculator
- [ ] OI analysis dashboard
- [ ] Opstra-level options analytics

## Phase 8-9: AI Forecast + Investment Calculator

- [ ] ML-based price prediction models
- [ ] Sentiment analysis (news + social)
- [ ] AI trade signals
- [ ] SIP calculator
- [ ] Lumpsum vs SIP comparison
- [ ] Retirement planning calculator
- [ ] Tax-loss harvesting suggestions
- [ ] Portfolio optimizer (Modern Portfolio Theory)

## Phase 9-11: Asset Class Expansion

- [ ] Mutual Fund integration
  - Direct plan investment
  - SIP automation
  - Fund comparison + ratings
- [ ] ETF trading
- [ ] Commodity trading (MCX)
- [ ] Currency/Forex trading
- [ ] US stocks (via INDMoney/Vested integration)
- [ ] Crypto trading (WazirX/CoinDCX API)

## Phase 12+: Platform Expansion

- [ ] Desktop app (Tauri — native performance, web tech)
  - Windows + macOS + Linux
  - System tray with live P&L
  - Multi-monitor support
- [ ] Mobile apps
  - React Native (iOS + Android)
  - Push notifications
  - Quick trade from notification
  - Biometric auth
- [ ] Voice trading
  - "Buy 50 NIFTY at market"
  - Alexa / Google Assistant integration
  - Voice alerts for kill switch events
- [ ] Telegram bot trading
  - Full trade execution via chat
  - Portfolio status commands
  - Strategy management

## Infrastructure Roadmap

- [ ] Multi-region deployment (Mumbai + Singapore)
- [ ] WebSocket real-time updates
- [ ] gRPC for inter-service communication
- [ ] Event sourcing for trade audit
- [ ] Kubernetes orchestration
- [ ] Auto-scaling based on market hours
- [ ] CDN for static assets
- [ ] 99.99% uptime SLA
