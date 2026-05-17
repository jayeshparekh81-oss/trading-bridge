# LinkedIn Launch Post — TRADETRI

**Draft status:** v0 — needs founder voice review (especially the SEBI / regulator framing).
**Audience:** B2B-adjacent — Indian fintech operators, ex-engineers turned founders, SEBI-watching analysts, compliance leads at brokerages.
**Tone:** Professional, technical, "what we built and why it matters" — not bhai-tone (that lives on Twitter). Hinglish phrases used sparingly for authenticity, not as the dominant register.
**Length:** ~600 words. LinkedIn's algo favours 1200-1500 chars for the visible portion + "see more" expand.

---

## Headline (the first 1200 chars — what shows before "see more")

```
After 17 years building production systems at Larsen & Toubro, I'm
launching TRADETRI — India's first transparent, paper-mode-first
algo-trading platform. The Indian retail algo space has industrialised
one specific con: beautiful backtests, brutal live trading. I lost
₹X across 6 algo subscriptions in 2024 finding this out the slow way.

TRADETRI ships with three founding constraints:

1. The backtest IS the live engine. Same code path, same broker
   simulation, same cost model. There is no "now it's different
   because it's live" — that gap is the grift.

2. Public deviation ledger. Every live trade is compared to its
   backtest-expected outcome. >0.5% deviation → flag. Customers see
   their own ledger; aggregated metrics are publicly browseable.

3. Mandatory paper-mode for first 30 days per user. SEBI hasn't
   asked for this — we built it because it's the right thing.

[see more] → full post body below
```

## Full post body (after "see more")

```
What we're shipping at launch:

— 45 active equity strategy templates (preview-only at launch;
   full trading unlocks with the no-code Strategy Builder in
   Phase 5)
— 113 total templates across equity + futures + options (options
   builder ships Phase 7-8)
— Multi-broker integration (Fyers + Dhan live; Zerodha + Upstox
   in flight)
— Read-only audit trail on every order — exportable as CSV for
   tax filing
— Kill-switch system: founder/operator can halt any strategy in
   <1 second from a single admin endpoint

What we built that nobody else does (yet):

— A "deviation monitor" that compares live execution to backtest
   expected at the trade level, not just the portfolio level. If
   your strategy expected entry at 22000.00 and the broker filled
   at 22015.40, that 0.07% slippage is logged, attributed
   (timing? routing? broker queue?), and surfaced.
— Pre-trade safety chain. Every order passes through 7 gates:
   kill-switch active? max-position size? allowed-symbols list?
   funds-available? trading-hours? webhook-token valid? user-
   active? Any fail → block + structured error log.
— L&T-style operations runbook. Every deploy ships with a
   rollback playbook. Every WARN/ERROR is structured JSON with
   named fields (user_id, request_id, sample_errors) — no
   per-item logging in a loop.

What we deliberately don't ship at launch:

— Live trading button for general retail. Paper-mode-only for
   the first 30 days per account. The button literally doesn't
   render in the UI until the cooldown passes.
— "Guaranteed returns" anywhere. Read our Truth Score doc.
— Hidden costs. Brokerage + STT + GST + slippage all surface on
   the order ticket, in INR, before you confirm.
— A marketplace where retail traders sell strategies to other
   retail traders without an L&T-style validation lifecycle. We
   know it's coming — Phase 9 with full backtest + live-deviation
   + reliability gating before any strategy can be listed.

SEBI conversation:

We've reached out to SEBI's Investment Advisor Regulation team
proactively, sharing our paper-mode-first design, kill-switch
infrastructure, and audit trail architecture. We believe the
right regulatory posture for retail algo platforms is built
together with the regulator, not against. If you're at SEBI or
adjacent and want a demo, my DMs are open.

For Indian retail traders:

Waitlist live at tradetri.com. First 500 sign-ups get lifetime
free tier + first dibs on the no-code Strategy Builder beta.

For ex-engineers turned founders:

The repo is private for now but the architecture decisions are
all documented in public design docs. Happy to share them on
request. Our test coverage is 96%+ across the production
codebase — not because we love tests, because L&T taught us
that "production is not prototype" is non-negotiable.

For everyone else reading this:

If your algo subscription's backtest doesn't match your live
broker statement, screenshot both. DM me. We're building the
public deviation ledger so the next person doesn't have to find
out the slow way.

— Jayesh Parekh, founder
```

---

## Hashtags

```
#TRADETRI #AlgoTrading #IndianMarkets #SEBI #FinTech #SystemsEngineering
#LarsenAndToubro #PaperTrading #BacktestingNotEnough #TransparencyInFinTech
```

(LinkedIn's hashtag yield is lower than Twitter's — these are mostly for
search-discovery, not engagement amplification.)

---

## Comments-section pre-staged

Three replies the founder can paste-and-fire when specific kinds of
comments show up:

### Reply A — "How is this different from QuantInsti / Streak / AlgoTest?"

```
Genuine question, here's the honest answer:

— Streak: great UI, but the backtest engine and the live engine are
  different code paths. They use proxy-fills for backtests and broker
  API for live; the divergence is the source of most "backtest looked
  great but live lost money" stories. We ran the same code through both.

— QuantInsti: educational platform, not a runtime. Different category.

— AlgoTest: closer in spirit, but no public deviation ledger and no
  paper-mode-first mandate.

Each has things we don't have yet (Streak's UI polish is real). Where
we want to win first: transparency + L&T-style operational discipline.
```

### Reply B — "What's your SEBI status?"

```
SEBI Investment Advisor registration is in flight (filed Q1 2026).
Pre-registration, we're operating as a paper-mode-only platform —
which is permissible per current SEBI guidance for software tools
that don't take custody of funds and don't issue trading advice.

Live trading flips on per-user only after their 30-day paper-mode
cooldown AND only when they've connected their own broker account
directly (Fyers/Dhan/etc). We never hold customer capital.

I'd rather be transparent about the timeline than ship with
ambiguity.
```

### Reply C — "Can I see code samples?"

```
Architecture is documented in public design docs (linked below). For
specific module deep-dives — backtest engine, kill-switch, deviation
monitor — DM and I'll share the relevant section.

Repo will go partly-public after Phase 5 ships (with the visual
builder). Until then, the design docs ARE the source of truth.
```

---

## Open questions for review

1. **The "₹X across 6 algo subscriptions" line.** Concrete figure
   (e.g. "₹2.3 lakh") would be far more credible — but it commits
   the founder to that specific number publicly. Recommend filling
   in the real figure.

2. **Specific competitor names.** Reply A names Streak, QuantInsti,
   AlgoTest. Could remove names entirely or keep them. Naming
   competitors is risky on LinkedIn (their employees see it); also
   makes the post more useful for readers comparing options.
   Recommendation: keep, founder voice can soften.

3. **SEBI DM line.** "If you're at SEBI or adjacent and want a demo,
   my DMs are open" — this is a power move that can backfire if SEBI
   reads it as showboating. Soften to "happy to walk anyone at SEBI
   through the architecture in detail"?

4. **L&T name-drop frequency.** Appears 4× in the post (headline,
   body, "L&T-style operations runbook", closing). Risk: over-using.
   Recommendation: keep 2× max — the headline mention + one
   substantive technical mention (operations runbook).

5. **Hashtag mix.** Indian audience leans #IndianMarkets / #SEBI;
   global engineering audience leans #SystemsEngineering. Pick lean.
