# Waitlist Invite Email — "You're in"

**Draft status:** v0 — needs founder voice review (especially the urgency framing).
**Audience:** Waitlist sign-ups who have NOT yet received their invite link.
**Tone:** Hinglish bhai-tone (lighter than WhatsApp; this is an inbox, not a phone). Direct + functional. The reader is opening their email to find their access link, not to be entertained.
**Length:** ~250 words. Email lift drops sharply past 300.

---

## Subject line options (A/B test candidates)

1. **"Bhai, TRADETRI ka access ready hai"** — bhai-tone, direct. Recommended.
2. **"Your TRADETRI invite is here (lifetime free tier)"** — English variant; broader appeal.
3. **"TRADETRI — your turn"** — minimalist, mystery-hook.
4. **"Backtest nahi, Proof. Andar aao."** — bold tagline-first.

Recommendation: ship (1) for 70% of waitlist, (4) for 30% as a tagline-driven A/B. Compare 7-day signup-completion rate. Subject line is the single highest-leverage copy decision in the launch — get it right.

---

## Email body

```
Subject: Bhai, TRADETRI ka access ready hai

Pre-header: 113 templates, paper-mode-first, L&T-engineer-built.
Lifetime free tier (you're in the first 500).

────────────────────────────────────────────────────────

Hey {{first_name}},

Waitlist join karne ke liye thanks. Aap first 500 mein ho, so
lifetime free tier locked.

Yeh aap ka access link hai:

  → {{access_link}}

Click karke 5 min mein:

  1. Account create karo (Fyers / Dhan account ki zarurat nahi —
     yet)
  2. 45 active strategy templates browse karo (3 cheez har
     template ki dekhao: SL %, TP %, indicator stack)
  3. Ek pick karo, paper-trade run karo (NIFTY 5-min default;
     change kar sakte ho)
  4. Hourly reports — strategy ne kya kiya, kyun, kaise

Day-1 mein DELIBERATELY locked hai:

  — Live trading button (30-day paper-mode cooldown mandatory)
  — Real-money strategy marketplace (Phase 9)
  — Pine Script import (Phase 5)

Yeh bug nahi hain. Yeh discipline hai.

Reply karke do cheez batao:

  — Aap kya algo-trading mein try kar chuke ho jo kaam nahi
    kiya (taaki hum genuinely better build karein)
  — Top 3 strategy categories aap personally use karte ho
    (top picks ko prioritise karein backtest engine sprint
    mein)

Yeh genuinely meri inbox mein aata hai. Pichle 2 mahine mein
har waitlist reply ka jawab diya. Continue karenge.

— Jayesh
   Founder, TRADETRI
   ex-L&T (17 years; refineries → algo-trading is a logical
   sequel, I promise)

P.S. Tagline yeh hai: Backtest nahi, Proof. Agle 30 din mein
proof banana hum dono ka kaam hai.

────────────────────────────────────────────────────────

Unsubscribe: {{unsubscribe_link}} (single click, no question)
TRADETRI is a paper-mode-only platform during onboarding.
SEBI IA registration in flight. tradetri.com/disclosures
```

---

## English-first variant (for non-Hinglish-comfortable waitlist sign-ups)

For sign-ups whose locale/IP suggests they aren't Hindi-reading
(non-India, NRI segment, or who joined the waitlist with English-
only browser locale):

```
Subject: Your TRADETRI access is ready — lifetime free tier locked

Hey {{first_name}},

Thanks for joining the waitlist. You're in the first 500, so
your lifetime free tier is locked in.

Your access link:

  → {{access_link}}

5 minutes from now, you can:

  1. Create your account (no broker connection required yet)
  2. Browse 45 active equity strategy templates
  3. Pick one and run a paper-trade (default: NIFTY 5-min)
  4. Read hourly transparent reports of what the strategy did
     and why

Day 1 DELIBERATELY does not include:

  — A live trading button (paper-mode cooldown is mandatory)
  — Real-money marketplace (Phase 9)
  — Pine Script import (Phase 5)

These aren't bugs. They're discipline.

Reply with two things:

  — What algo-trading product you tried that didn't work
    (so we know what NOT to repeat)
  — Your top 3 strategy categories (we'll prioritise
    those in the next backtest-engine sprint)

Replies go to my actual inbox.

— Jayesh
   Founder, TRADETRI
   ex-Larsen & Toubro engineer (17 years before this)

P.S. Tagline: Backtest is not Proof. The next 30 days are about
turning your strategies into proof.
```

---

## Open questions for review

1. **{{first_name}} fallback.** If the waitlist signup form didn't
   capture a name, what's the salutation? Options:
   - "Hey,"
   - "Hey friend,"
   - "Hey bhai,"
   - "Hey there,"
   Recommendation: "Hey bhai," for Hinglish variant; "Hey there,"
   for English. Decision needed.

2. **P.S. line — keep or drop?** "Backtest nahi, Proof. Agle 30 din
   mein proof banana hum dono ka kaam hai." establishes the tagline
   + creates a 30-day partnership framing. Pro: memorable. Con: adds
   ~25 words to an already-tight email.
   Recommendation: keep.

3. **Unsubscribe placement.** Standard practice puts unsubscribe at
   the footer. We could ALSO put it in the pre-header for radical
   transparency. Pro: trust signal. Con: increases unsub rate.
   Recommendation: standard footer only.

4. **Founder reply commitment.** "Pichle 2 mahine mein har waitlist
   reply ka jawab diya. Continue karenge." This commits the founder
   to personal replies for every waitlist email. At 500 sign-ups
   that's manageable; at 5,000 it isn't.
   Recommendation: keep for v1; revisit when waitlist clears 1,000.
   Decision needed.

5. **"5 minutes from now, you can" — set the right expectation.**
   The actual time to first paper-trade depends on broker connection
   (which the email says "not required yet" but the customer might
   want to do anyway). If real flow is 10-15 min, "5 minutes" reads
   like overpromise. Recommendation: stress-test the actual onboarding
   flow with 5 waitlist sign-ups before this email goes out; adjust
   the number to whatever is honest.
