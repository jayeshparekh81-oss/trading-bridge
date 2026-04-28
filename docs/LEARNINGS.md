# LEARNINGS

Durable design + collaboration decisions for the TRADETRI codebase. Read before changing branding, theme, or design tokens.

---

## 2026-04-28 — Tiranga design intent

**Decision:** The `PAST · PRESENT · FUTURE` labels on the login page use the Indian flag tricolor — saffron `#FF9933` / white / green `#138808` — NOT a single brand gold. This is deliberate and matches the Tiranga triangle in the logo (`public/tradetri-icon.svg`).

**Rule for future contributors (human or AI):** If a prompt or review suggests "make these consistent with brand color" → **REJECT**. The tricolor is the design. Confirm with the owner before any change to those three tokens.

---

## 2026-04-28 — There is no `#D4AF37` brand gold

The brand's gold/saffron token is `--accent-gold` in `src/app/globals.css`, which **varies by theme** (`#D97706`, `#F59E0B`, `#FBBF24`, `#FCD34D`, `#FFD700`, etc.). The wordmark logo's "TRI" is a gradient (`#FFD700 → #00FF88`), not a flat hex.

**Rule:** Use `text-accent-gold` (or `var(--accent-gold)`) wherever you need the brand gold. Don't hardcode hexes — they break theme switching and don't match anything they're claimed to match.

**Exception:** TRI/त्रि prefix tokens use the logo gradient, not `text-accent-gold`. See 2026-04-29 entry.

---

## 2026-04-28 — AI assistant collaboration: investigate first, modify second

Chat-mode AI sees vision and intent; code-aware AI (Claude Code) sees reality. Prompts pasted from a planning session frequently contain assertions that don't match the repo: invented file paths, hexes that don't exist, alleged bugs that are already handled, changes that would erase intentional design.

**Rule:** Before executing any multi-step prompt, do a recon pass — read the files it references, grep for the colors/strings it cites, check claimed bugs against current behavior. Surface conflicts as a structured findings list and wait for confirmation before writing code. When prompt and repo disagree, prefer the repo's existing patterns.

---

## 2026-04-29 — Founder QA caught brand gradient inconsistency

**What happened:** HighlightTri was rendering flat text-accent-gold while the logo wordmark uses a gold→neon-green gradient. Technically correct per code, visually wrong per brand.

**What I learned:** Theme tokens are good for theme-awareness, but when matching a specific visual element (like a logo gradient), sometimes you need to mirror the exact treatment, not abstract it.

**Rule going forward:** Every "TRI" / "त्रि" on the entire site MUST visually match the logo wordmark's gradient — same colors, same direction, same feel. This is non-negotiable brand identity.

**Known testing edge case (verify on Android QA):** The Hindi `त्रि` cluster is composed of three combining glyphs (`त्` + `र` + `ि`) that the browser composes into a single visual unit. `bg-clip-text text-transparent` works on the rendered glyphs, so this should look right in modern Chrome/Safari/Firefox — but older Android WebViews have occasionally surprised here. Specifically check: (a) gradient renders inside the conjunct (not a transparent void), (b) the prefix doesn't break the line at an unexpected place. If broken on a real device, fall back to a flat `#FFD700` for the Hindi prefix only — but not without confirming with the owner first.

---

## 2026-04-29 (later) — Mantra reorder for brand storytelling

**Decision:** Mantra reads `TRIKALA · TRISHUL · TRISKELION · KALACHAKRA` (English) and `ॐ · त्रिकाल · त्रिशूल · त्रिस्केलियन · कालचक्र` (Hindi).

**Why:** Front-loads the 3 gradient TRI/त्रि tokens for visual rhythm; KALACHAKRA at the end becomes the resolution word, reinforcing the "Anant kaal tak" / Wheel of Eternal Time founder philosophy.

**Rule:** Never reorder back to KALACHAKRA-first. The current sequence IS the brand story.
