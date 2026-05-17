# BLOCKERS — Marketing Launch Kit Drafts

**Branch:** `docs/marketing-launch-kit`
**Date:** 2026-05-17
**Sibling docs:** `docs/marketing/{TWITTER_LAUNCH_THREAD,LINKEDIN_POST,WHATSAPP_BROADCAST,WAITLIST_EMAIL_INVITE,ONBOARDING_TOUR_COPY_V2}.md`

---

## Drafts shipped

| File | Words | Status |
|---|---:|---|
| `TWITTER_LAUNCH_THREAD.md` | ~1100 | v0 — Hinglish primary, English secondary |
| `LINKEDIN_POST.md` | ~1200 | v0 — B2B/regulator framing |
| `WHATSAPP_BROADCAST.md` | ~800 | v0 — finfluencer affiliate kit |
| `WAITLIST_EMAIL_INVITE.md` | ~700 | v0 — Hinglish + English variants |
| `ONBOARDING_TOUR_COPY_V2.md` | ~1200 | v0 — 12 react-joyride steps |

All drafts ship in markdown. **Nothing is published.** Each file
has its own "Open questions for review" section; this consolidates
the cross-cutting decisions.

---

## Cross-cutting decisions needed

### Q1. Founder voice tone calibration

Five pieces ship with varying bhai-tone density:

| Piece | Bhai-tone density |
|---|---|
| Twitter thread | High (Hinglish-first by audience) |
| LinkedIn post | Low (professional B2B register) |
| WhatsApp broadcast | Very high (bhai-energy as default) |
| Waitlist email | Medium-high (Hinglish-first with English fallback) |
| Onboarding tour | Medium-high (in-app reads warmer than email) |

**Decision needed:** does the founder voice match across these
pieces, or does each medium get its own register? Recommendation:
match the current calibration — the audience is different per
medium, so register-per-medium is correct.

Specific words/phrases to ratify across all pieces:
- "Bhai" — used 9x across the kit
- "Paisa" — 4x
- "Discipline" — 6x (in serious-tone pieces)
- "L&T-engineer-built" — 7x (across all 5 pieces; intentional brand anchor)
- "Backtest nahi, Proof" — 5x (the tagline)

### Q2. Public P&L disclosure

The Twitter thread (tweet 9) and LinkedIn post (intro paragraph)
both reference "₹X across 6 algo subscriptions in 2024." Concrete
figure boosts credibility but commits the founder to a specific
number publicly.

Options:
- (A) Disclose specific figure (recommend: founder picks a real number, e.g. ₹2.3L)
- (B) Range ("₹1L-3L")
- (C) Stay anonymous ("six figures")
- (D) Skip the line entirely

Recommendation: (A) — specifics convert. The grift industry trades
on vagueness; we trade on transparency. Decision needed.

### Q3. Specific finfluencer partners to tag publicly

The WhatsApp kit assumes a vetted list of affiliates. The Twitter
thread does NOT tag any finfluencer publicly. Two approaches:

- (A) No public tagging in the launch thread. Privately invite 10-20
  high-trust finfluencers via the affiliate kit. They post
  independently with their tracking link.
- (B) Tag 3-5 key influencers in a follow-up tweet 12 hours after
  the thread launches (after the founder's own audience has had
  first crack).

Recommendation: (A) for v1 launch; (B) at the 30-day milestone if
the affiliate program has clear early winners.

Decision needed: confirm A; if B, identify the 3-5 names + clear
the tagging with them privately first.

### Q4. SEBI conversation framing

Three pieces (Twitter t7, LinkedIn body, Waitlist email footer)
reference "SEBI registration in flight." This is true (Q1 2026
filing per the LinkedIn copy) but the wording risks two failure
modes:

- **Overclaim:** if SEBI rejects or delays, the social media
  trail looks like a lie. Mitigation: language is "in flight" not
  "registered." Safe.
- **Underclaim:** the actual posture (paper-mode-first, kill-switch,
  audit trail, proactive outreach) is much stronger than "in flight"
  suggests. We undersell.

Decision needed: is the current framing "in flight + here's what
we built proactively" right? Or do we need a separate
`docs/SEBI_COMMITMENT.md` published page that the social media
posts link to for the long version?

### Q5. Tagline lock — "Backtest nahi, Proof"

The tagline appears 5x across the kit. Founder needs to lock the
exact rendering before launch:

Candidates:
- (A) "Backtest nahi, Proof." (current — em-dash separator, full stops)
- (B) "Backtest nahi — Proof." (em-dash with space)
- (C) "Backtest is not Proof." (English-first for non-Hinglish audiences)
- (D) "बैकटेस्ट नहीं, Proof." (Devanagari "नहीं")
- (E) "Backtest != Proof" (engineer-flavored typography)

Recommendation: (A) for Hinglish content + (C) for English content.
Twitter handle bio and product home page consistent across.

Decision needed: pick A/B/C/D/E + decide if Twitter/web/product all
match or vary by surface.

### Q6. Affiliate compensation model

WhatsApp kit mentions "paisa kaam aayega" but doesn't specify
compensation. Three models:

- (A) Flat per-signup (₹50-100 per sign-up)
- (B) Revenue share (10-15% of paid-tier conversions year 1)
- (C) Zero-financial — affiliates get social credit + first dibs
  on betas + lifetime free tier

Recommendation: (B). Aligns long-term incentives.
Decision needed: % + duration + clawback policy (cancellations
within 30 days don't pay out).

### Q7. Disclosure compliance for finfluencer broadcasts

SEBI Investment Advisor regulations bar undisclosed paid promotion.
Every finfluencer broadcasting our message MUST disclose the
affiliate relationship.

Draft disclosure (from WhatsApp kit):
```
"Disclosure: I am a TRADETRI affiliate. I receive [%] of paid
subscriptions from users who join via my link. This does NOT
affect my opinions of the product, but you should know."
```

Decision needed:
- Legal review of the exact text before launch
- Inclusion as a required affiliate-kit asset (not optional)
- A "verified disclosure" badge on the affiliate's profile page?

### Q8. Email open / signup metrics — define success thresholds

Before launch, lock thresholds for each piece:

| Piece | Success metric | Threshold to hit |
|---|---|---|
| Twitter thread | Engagement rate | 5%+ on tweet 1 |
| LinkedIn post | Profile views | 1000+ in 48h |
| Waitlist email | Click-through to onboarding | 25%+ |
| Onboarding tour | Completion rate | 60%+ |
| WhatsApp broadcasts | Sign-ups via affiliate link | 20+ per affiliate |

These are first-pass numbers. Decision needed: confirm thresholds OR
flag for marketing-ops input before sending anything.

### Q9. Compliance text on every piece

Each piece needs a "this is not investment advice / paper-mode-
first / SEBI in flight" boilerplate. Currently scattered:
- Waitlist email footer: present
- LinkedIn post body: present
- Twitter: NOT present (no room in 280 chars)
- WhatsApp: NOT present
- Onboarding tour step 10: present

Decision needed: where does compliance text go for Twitter +
WhatsApp? Options:
- (A) tradetri.com landing page footer covers everyone
- (B) Each linked URL adds `?disclaimer=1` and the page surfaces a
  modal on first visit
- (C) Twitter bio has compliance link permanently pinned

Recommendation: (A) + (C). The landing page is the single source
of truth; Twitter bio links to it.

---

## What this branch ships

```
docs/marketing/
    TWITTER_LAUNCH_THREAD.md
    LINKEDIN_POST.md
    WHATSAPP_BROADCAST.md
    WAITLIST_EMAIL_INVITE.md
    ONBOARDING_TOUR_COPY_V2.md
    BLOCKERS_MARKETING.md   (this file)
```

NOT touched:
- Any source code
- Any test
- Any non-marketing doc
- Any frontend asset (logos, demo videos — those are separate
  founder-task creation)

## What needs to happen post-review

1. Founder picks one P&L disclosure figure (Q2) and rewrites the 2
   references — Twitter t9, LinkedIn intro.
2. Founder locks tagline rendering (Q5) and ensures all 5 references
   match.
3. Founder confirms affiliate compensation model (Q6) and rewrites
   the WhatsApp kit's "paisa kaam aayega" lines to be specific.
4. Legal/compliance review of disclosure text (Q7) before any
   finfluencer broadcast.
5. Marketing-ops (or founder if solo) sets success thresholds (Q8)
   so we know what "launch worked" means.
6. (Optional, lower priority) Translation pass for Hindi-only
   waitlist email variant + onboarding tour Hindi mode.
