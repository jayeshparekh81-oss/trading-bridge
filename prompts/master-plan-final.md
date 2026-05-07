# Tradetri Plan
Done: Phase 0,1,2,3,4,5A,6,7A (commits 51d4abf to f8afaf9)
Tonight: Phase 9 indicators
Wed: Phase 5B frontend 11 modules
Thu: Pine + Paper trading
Fri: Broker guard
Sat: Market regime
Sun: Deviation monitor
Mon-Fri next week: Data quality, Audit logs, Feature flags, Hardening, Docs
Defer post-launch: Versioning, RBAC, 230+ indicators, Discovery pipeline
NEVER touch: services/algomitra_ai.py, services/ai_validator.py, broker code, Auto Kill Switch

## ADDITION: Strategy Coach (Hinglish Education Layer)

Goal: After backtest, beginner-friendly explanation of every metric in 
simple Hinglish. Show user's value vs ideal range with educational tip.

Module: backend/app/strategy_engine/coach/

Output: StrategyHealthCard with metric_grades for:
- Win Rate, Profit Factor, Max Drawdown, Risk-Reward Ratio
- Total Trades, Expectancy, Recovery Factor

Each metric: your_value, ideal_range (excellent/good/acceptable/concerning),
your_grade, hinglish_tip

Hinglish tip example:
"Aapki strategy ne ₹1 ka risk leke ₹1.40 kamaaye. Theek hai, par >1.5 
ideal hota hai. Aur 18% drawdown thoda zyada hai - <15% ideal."

Sequence position: After Paper Trading Engine, before Phase 5B Frontend.
Reason: Backend ready hona chahiye taaki Phase 5B UI usse display kare.

Estimated time: 75-90 min backend

## ADDITION: Hypnotic Frontend Polish

Goal: TRADETRI ko Bloomberg-grade professional + iPhone-simple delight 
banao. Customer ko wow feeling aaye, common man bhi engaged rahe.

When: After Phase 5B builders functional, before public launch.
Duration: 90 min focused session

Scope:
1. Strategy Dashboard hero upgrade
   - Animated stats (saved count, total backtests, avg trust score)
   - Pulse glow on TrustScoreBadge grade A
   - Smooth card hover animations
   - Motivational empty state

2. Backtest Result celebrations
   - Confetti burst on profitable backtest first load
   - Number count-up animation for P&L (0 to actual over 1.5s)
   - Equity curve dynamic color (green profit / red loss)
   - Ka-ching sound toggle on profit
   - Trust Score grade A pulse glow

3. Strategy Coach Card hypnotic
   - Massive grade letter with glow
   - Animated progress bars per metric
   - Smooth color transitions
   - Conversational Hinglish typography

4. Builder micro-delights
   - Slide transitions in Beginner Builder steps
   - Pulse on indicator card add
   - Gradient + glow on submit buttons

5. Brand consistency
   - Deep space dark mode primary
   - Neon green profit accent
   - Saffron/white/green candle inspiration
   - Glassmorphism across all panels

Technical:
- Lucide icons + selective emoji for celebrations
- Framer Motion for animations
- canvas-confetti for celebrations
- Use existing GlassmorphismCard primitives
- Respect prefers-reduced-motion

## ADDITION: Broker Execution Guard (Backend)

Goal: Pre-trade decision logic that blocks unsafe live orders.
Module: backend/app/strategy_engine/broker_guard/
Duration: 75-90 min

CRITICAL RULES:
- DO NOT modify services/fyers_*.py, services/dhan_*.py, services/broker_*.py
- DO NOT modify Auto Kill Switch code
- DO NOT modify order placement code
- ONLY ADD new module pure decision function
- Wiring into actual order placement is a SEPARATE future phase

Public API:
evaluate_broker_guard(strategy, backtest, reliability, truth, 
paper_readiness, broker_connected, auto_kill_switch_active, 
user_override_paper) -> GuardDecision

Returns: allowed bool, reason str, blocking_failures, warnings, info, checks_run

BLOCKING checks (any one = allowed=False):
1. Missing stop loss AND missing trailing stop
2. broker_connected = False
3. auto_kill_switch_active = True
4. truth_score < 55
5. trust_score < 70
6. paper not ready AND no user override

WARNING checks (allowed but flag):
7. truth.risk_level in high/extreme
8. backtest.total_trades < 30
9. backtest.max_drawdown_percent > 25

INFO checks:
10. paper_readiness.completed_sessions < 14

Constants (broker_guard/constants.py):
MIN_TRUTH_SCORE_FOR_LIVE = 55
MIN_TRUST_SCORE_FOR_LIVE = 70
HIGH_DRAWDOWN_WARNING = 0.25
LOW_TRADE_COUNT_WARNING = 30
RECOMMENDED_PAPER_SESSIONS = 14

Files: __init__.py, constants.py, models.py (GuardCheckResult, GuardDecision 
frozen Pydantic), checks.py (one fn per check), guard.py (orchestrator)

Tests: 10+ covering all blocking checks, override flag, all-pass case, 
determinism, AST inspection (no broker imports)

Quality gates: ruff + mypy strict + pytest. Regression must hold.

## NOTE: Commit 0715750 mixed contents
Includes Market Regime backend AND Samjho language tooltip system
(parallel session work merged inadvertently). Both verified working.

## ADDITION: Real Candle Data Integration (Dhan)

Goal: Replace synthetic 120-bar candles with real historical OHLCV from 
Dhan API (user has paid monthly subscription).

Module: backend/app/strategy_engine/data_provider/
Duration: 3-4 hours focused session

CRITICAL RULES:
- DO NOT modify existing services/dhan_adapter.py order placement code
- ONLY ADD new historical_data() method if not present
- Cache historical data locally to avoid re-fetching (rate limit safety)
- Validate fetched candles via Phase 11 Data Quality Engine

Phase A - Discovery (15 min): Read existing dhan adapter, verify Dhan 
historical API endpoint, document rate limits.
Phase B - Adapter extension (60 min): fetch_historical_candles method.
Phase C - Backtest endpoint integration (45 min): real candles flow.
Phase D - Frontend candle picker (45 min): symbol + date range UI.
Phase E - Testing (45 min): mocked Dhan responses.

Sequence position: After Phase 11 docs, before live broker wiring.

## ADDITION: Trade Quality Score UI Exposure
Backend exists in advisor module, surface in frontend.
Duration: 30 min

## ADDITION: AI Doctor Apply Fix and Compare Frontend
Backend exists, master prompt signature feature.
Duration: 90 min

## ADDITION: Walk-Forward Analysis Completion
Phase 4 placeholder needs full implementation.
Module: backend/app/strategy_engine/reliability/walk_forward.py
Duration: 90 min

## ADDITION: Live Broker Order Wiring (Phase 8 part 2)
Connect Broker Execution Guard to actual Dhan/Fyers order placement.
ONLY on Saturday with fresh judgement.
Duration: 4 hours careful session

## ADDITION: Audit Wrapper Wiring (TODO from audit doc)
Phase 1-9 call sites need to actually call audit.loggers wrappers.
Duration: 60 min

## SEQUENCE LOCKED (Thu May 7 night onwards)

### Aaj raat (Thu) - in progress
- Trade Quality Score backend (chal raha hai abhi Claude Code mein)
- Trade Quality UI wiring (~30 min after backend commit)

### Fri raat
- Indicator Versioning system (~5 hours)
  Module: backend/app/strategy_engine/versioning/
  Track: indicatorId, version, formulaVersion, changelog, createdAt, updatedAt
  Backtests must store indicator versions used (link to BacktestResult)

### Sat full day (8-10 hours)
- Strategy Versioning + rollback (~6 hours)
  Module: backend/app/strategy_engine/strategy_versioning/
  Each strategy: version number, rollback API, compare versions, change history
  DB migration #010 for strategy_versions table
- Live broker order wiring Phase 8 part 2 (~3 hours)
  Connect Broker Execution Guard to actual Dhan/Fyers order placement
  CRITICAL: existing broker code touched, audit-flagged risk
  Fresh judgement session - NOT after midnight

### Sun
- Real candle data integration Dhan (~3 hours)
- AI Doctor Apply Fix and Compare frontend (~90 min)
- Walk-forward analysis completion (~90 min)

### Next Mon
- Robustness Test Controls (~2.5 hours)
  Wire expert builder placeholder to actual sensitivity/walk-forward toggles
  Backend already exists Phase 4 - just frontend exposure
- Strategy Truth UI drill-down (~2 hours)
  Per-warning evidence display, why each warning fired
- Basic RBAC user+admin (~3 hours)
  Reduced scope from 5 roles. user + admin enough pre-launch.
  Module: backend/app/strategy_engine/permissions/
- License status exposure (~1 hour)
  Phase 7 license_status field already exists, just surface in Pine Import UI

### Next Tue
- Audit Wrapper Wiring TODO (~60 min)
  Phase 1-9 call sites need to actually call audit.loggers wrappers
- Trade Quality docs (~45 min)
- 11 remaining docs (~5 hours total)
- Manual verification all 25+ commits

### Next Wed
- Migration 009 production DB apply
- Migration 010 production DB apply (strategy versioning)
- Frontend FAQ statement decision
- PR review feature/ai-trading-system to main
- Self-review diff
- Merge to main
- Vercel auto-deploy
- AWS Mumbai backend pull + alembic upgrade + restart
- Smoke test tradetri.com

### Next Thu-Sun (Buffer)
- May 18 Fyers integration final prep
- Customer onboarding setup
- Marketing content
- Bug fixes from smoke test

## DEFERRED post-launch v1.1 (genuinely)

- Full RBAC 5 roles (user, pro_user, creator, admin, super_admin)
- Admin Indicator Approval Dashboard (full UI)
- Marketplace integration
- Weekly Discovery Pipeline (GitHub/marketplace connectors)
- 230+ indicators expansion (Packs 2-5, currently 20 active)
- Pine Importer expanded mappings beyond current 11
- Standalone Entry/Exit/Risk Builder UIs (currently embedded in builders)
- TradingView link review system
- Multi-language tips Gujarati Tamil Bengali

## TOTAL PRE-LAUNCH COMMITMENT

7 evenings + 1 full Saturday = world-class launch
May 18 Fyers integration on track but tight
NO MORE SCOPE CREEP after this point
