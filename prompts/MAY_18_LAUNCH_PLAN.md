# TRADETRI Launch Plan — Option B (Aggressive)
# Locked: Saturday May 9, 2026 morning

## Schedule

### Sat May 9 (today) — 18 hrs work

10:00-11:00 AM:  Local Docker setup verify
11:00 AM-1:00 PM: Live broker wiring Phase 8B-1 (design + audit)
1:00-1:30 PM:    Lunch
1:30-4:00 PM:    Live broker wiring Phase 8B-2 (Dhan order integration)
4:00-6:00 PM:    Live broker wiring Phase 8B-3 (tests + dry-run mode)
6:00-7:00 PM:    Dinner
7:00-9:00 PM:    Robustness Test Controls
9:00-11:00 PM:   Strategy Truth UI drill-down
11:00 PM-1:00 AM: Audit Wrapper Wiring
1:00-2:00 AM:    End-to-end local testing
2:00-3:00 AM:    Documentation files batch 1

### Sun May 10 — 18 hrs work

10:00-11:00 AM:  Migration #009 #010 design
11:00 AM-1:00 PM: Migration apply on STAGING (or create staging if missing)
1:00-1:30 PM:    Lunch
1:30-4:00 PM:    Production env vars + Sentry integration
4:00-6:00 PM:    Mobile responsiveness audit + fixes
6:00-7:00 PM:    Dinner
7:00-9:00 PM:    Frontend FAQ update + performance optimization
9:00-11:00 PM:   Documentation files batch 2 (5 docs)
11:00 PM-1:00 AM: Manual verification all commits + bug list
1:00-3:00 AM:    Bug fix sprint

### Mon May 11 — 3 hrs deploy

8:00-9:00 AM:    Final smoke test on staging
9:00-10:00 AM:   PR review + merge to main
10:00-11:00 AM:  Production deploy (Vercel + AWS Mumbai)

### Mon-Fri May 11-15 — Paper sessions (1 hour/day monitoring)

Mon May 11: Paper session 1 enabled for beta users (5-10 selected)
Tue May 12: Paper session 2
Wed May 13: Paper session 3
Thu May 14: Paper session 4
Fri May 15: Paper session 5
- Sat-Sun May 16-17: Market closed, rest

### Mon-Tue May 18-19 — Final paper sessions

Mon May 18: Paper session 6
Tue May 19: Paper session 7 complete - LIVE TRADING UNLOCKED ✅

### Wed May 20 — Live trading public

- First brave users with all safeguards passed
- Marketing announcement
- Customer support ready

## Public live trading: Wed May 20, 2026

## Critical safeguards (non-negotiable, code-locked)

1. 7 paper sessions REQUIRED (Phase 10A locked)
2. Trust Score >= 70 + Truth Score >= 55 (Broker Guard locked)
3. Auto Kill Switch always enabled
4. Audit logs mandatory
5. Feature flag LIVE_TRADING_ENABLED off by default per user
6. Manual approval first 10 users
7. Daily Sentry + audit log review

## Acknowledgments

- Founder chose 18-hour weekend pace (Option B)
- Mon May 18 commitment to Fyers shifts to Wed May 20 due to 
  market-day-dependent paper sessions (mathematical constraint, 
  not pace constraint)
- All quality safeguards remain non-negotiable

## ADDITION: Always-On AlgoMitra MVP (locked Sat May 9 afternoon)

GOAL: AlgoMitra side panel automatically opens when user enters Strategy 
Builder (Beginner/Intermediate/Expert). Continuous coaching tips. Dismissable.

SCOPE for v1.0 (~6 hours, Sunday afternoon):
- Side panel auto-opens on /strategies/new/* routes
- Static contextual tips per page section (indicators, entry, exit, risk)
- Dismissable with X button
- Re-open toggle button always visible
- Smooth slide-in/out animation
- Hinglish coaching content (pre-defined per field)

DEFERRED to v1.1 (post-launch):
- Real-time AI streaming (token-by-token)
- Context awareness (kya field, kya value typed)
- Per-event coaching triggers (on click, on field change)
- Voice mode
- Bias detection integration

Sunday May 10 schedule slot:
- 2:00-5:00 PM: Always-On AlgoMitra MVP build
- 5:00-6:00 PM: Polish + animations
- 6:00 PM: Lunch (delayed) / break

Files to create (estimate):
- frontend/src/components/algomitra/always-on-panel.tsx
- frontend/src/components/algomitra/coaching-tips-data.ts
- frontend/src/hooks/use-algomitra-context.ts
- Modifications to existing builder pages

