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
