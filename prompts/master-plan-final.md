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
