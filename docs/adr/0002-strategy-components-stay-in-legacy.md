# ADR 0002 — The strategy components stay in legacy until four small slices exist

- **Status:** Accepted
- **Date:** 2026-09-06
- **Supersedes nothing.** Refines ADR 0001 §"Deliberately not migrated now".
- **Decider:** Jayesh Parekh (founder) asked for the migration order
  signals → strategies → brokers → marketplace → billing → onboarding.

## Context

Slice 1 (signals) moved cleanly: three files, three layers, boundary lint green
first try, because slice 0 had already put every dependency in `src/shared`.

Strategies is not like that. Measured, not guessed:

| | files |
| --- | --- |
| `src/lib/strategies/explainers` | 47 — **zero** external `@/` imports |
| `src/components/strategies` (top level) | 27 |
| the three builders + pine importer | 24 |

The 51 components reach outside their own domain in exactly eight places, and
those eight are the whole problem:

| Importer | Reaches for | Domain it belongs to |
| --- | --- | --- |
| `beginner-builder/step-deploy.tsx` | `@/components/dashboard/paper-mode-banner` | paper/system-mode |
| `go-live-modal.tsx` | `@/hooks/useSystemMode` | system-mode |
| `kill-switch-summary.tsx` | `@/lib/kill-switch-label` | kill-switch |
| `builder-onboarding-modal.tsx` | `@/hooks/useLadder` | mode (Simple/Pro) |
| `indicator-library.tsx` | `@/components/indicators/IndicatorVerificationBadge` | indicators |
| `intermediate-builder/indicator-picker.tsx` | `@/components/indicators/ConventionWarning` | indicators |
| `expert-builder/indicator-section.tsx` | `@/lib/celebration` | shared (confetti) |
| `intermediate-builder/indicator-picker.tsx` | `@/lib/celebration` | shared (confetti) |

## Decision

**Migrate the strategy ENTITY now; leave the strategy COMPONENTS in legacy.**

`src/lib/strategies/explainers` → `src/entities/strategy/lib/explainers`, behind
a barrel. That is real, self-contained, and done.

The components wait, because moving them now would do one of two bad things:

1. **Drag four other domains along in the same commit.** A migrated slice may
   not import legacy (ADR 0001 §1), so the moment `kill-switch-summary.tsx`
   becomes a widget it needs `kill-switch-label` to be a slice too — and the
   same for system-mode, mode and indicators. That is a big-bang wearing a
   slice's clothing, and ADR 0001 rejected big-bang for a live product.
2. **Or force a fake layering to dodge the rule.** The honest tension is
   `step-deploy` (inside the builders) rendering `PaperModeBanner`. If both end
   up as widgets, that is a cross-slice import and the rule blocks it —
   correctly. The fix is not to bend the layers; it is for the page to compose
   the banner, or for paper-mode to become an entity + a shared presentational
   component. Either is a real design decision, and it should not be made in
   passing while migrating something else.

## Consequence: the migration order changes

The founder's order was signals → strategies → brokers → marketplace → billing
→ onboarding. Strategies is not second-cheapest; it is close to last, and it is
gated on four slices that are individually tiny (one file each for
kill-switch-label and useSystemMode). Recommended order from here:

```
3. kill-switch      (src/lib/kill-switch-label.ts — 1 file, already an owner module)
4. system-mode      (src/hooks/useSystemMode.ts   — 1 file)
5. mode             (useLadder + lib/simple/level  — the Simple/Pro ladder)
6. indicators       (src/components/indicators, src/lib/indicators)
7. shared: celebration  (confetti — domain-free, belongs in src/shared/lib)
   ...then strategy components become a normal slice
8. brokers → marketplace → billing → onboarding, as before
```

This is a proposal, not a fait accompli: the founder set the order and can
override it. What is NOT negotiable is that a slice lands green — a migration
that needs the boundary rule relaxed has not been done, it has been announced.

## Consequences

- `src/components/strategies/**` and `src/lib/strategy-templates/**` stay in the
  legacy element. The boundary rule still holds the line around them: legacy may
  import a migrated slice, never the reverse.
- The eight cross-domain imports above are the migration's actual to-do list.
  When they are all pointing at slices, the components move in one clean commit.
