# ADR 0001 — Frontend architecture: Feature-Sliced Design, one source per fact, tokens, three states

- **Status:** Accepted
- **Date:** 2026-09-06
- **Decider:** Jayesh Parekh (founder)
- **Applies to:** `frontend/` (Next.js 16, App Router). The backend is out of scope.

## Context

The frontend grew feature by feature over months with no enforced structure. Three consequences are now
visible to customers, and all three were hit by the founder on his own production walk:

1. **The same fact is computed in more than one place**, so two screens disagree. The Overview says trading
   is on while the line under it says no order can go without a broker. The kill switch reads "Active" on
   one page and "NORMAL" on another.
2. **A change in one place breaks another**, because there is no rule about who may import whom. Business
   logic sits inside route files, so it cannot be reused without copying it — which is how duplicate facts
   appear in the first place.
3. **Surfaces are incomplete in ways nobody notices until production**: a page renders data and a spinner,
   but has no empty state and no error state, so a customer with no rows or a failed request sees a blank
   box, or worse, copy that asserts something false.

Grouping by file type (`components/`, `lib/`, `hooks/`) made this worse: a domain's parts are scattered
across three trees, so "where does this fact live" has no answer, and the cheapest thing a developer can do
is recompute it locally.

We are fixing the foundation before fixing the defects, because the defects are symptoms.

## Decision

### 1. Feature-Sliced Design, with imports flowing downward only

Five layers. A module may import only from layers **strictly below** it:

```
app        Next.js routes, layouts, providers, global styles. THIN — no fetching, no business logic.
widgets    Self-contained page blocks: the Pro overview, the sidebar, the header shell, the page template.
features   One user action with business meaning: subscribe to a strategy, connect a broker, arm the kill
           switch, pick a mode, finish onboarding.
entities   Business nouns and their data access: strategy, signal, broker, position, subscription, user,
           kill-switch. THE FACTS LIVE HERE (see §2).
shared     Domain-free: UI primitives, the API client, formatting utils, design tokens, generic hooks.
```

- `app → widgets → features → entities → shared`. Never upward.
- **Slices within a layer do not import each other.** Two entities that need to meet, meet in a feature; two
  features that need to meet, meet in a widget. This is what stops the tangle from re-forming.
- Each slice groups by **business domain**, never by file type, and colocates its own `ui/`, `model/`,
  `api/`, `lib/`.
- Each slice exposes a **public API** (its `index.ts`). Reaching into another slice's internals is a
  violation even when the direction is legal.

Route files under `app/` compose widgets and features. A page that fetches, or that derives a fact, is a bug.

### 2. One source per fact

Every fact the UI asserts to a customer — *is the broker connected, is the kill switch armed, how many
signals today, what is today's P&L, is this strategy running* — has **exactly one** owning hook or selector,
in the entity that owns it. Simple mode, Pro mode and the public site all read that one owner.

Two components may never independently derive the same fact. Two components calling the same hook is
correct and expected; two components each computing "connected" from a broker list is not.

The consequence is enforceable and testable: if a fact has one owner, two screens **cannot** disagree.
The current owners and their consumers are recorded in `docs/architecture/FACT_MAP.md`, which is part of this
decision and is kept current.

### 3. Design tokens

One source for colour, type, spacing, radius and motion: the Tailwind v4 `@theme` block and custom
properties in `frontend/src/app/globals.css`. Components use token-backed utilities.

No hardcoded hex, `rgb()`/`hsl()` literals, or raw-pixel arbitrary values in components. Tailwind scale
utilities (`p-4`, `h-16`, `rounded-lg`) already resolve to tokens and are fine. A genuinely new value gets a
token first, then gets used.

Exceptions are declared, not assumed: the token file itself, and charting libraries whose APIs take literal
colours. Those are listed in the lint configuration, so an exception is a visible decision.

### 4. Three states are mandatory

Every data surface ships **loading, empty and error**, and the empty state says **what to do next**.

"There are no positions" is incomplete. "No position is open. Add a strategy — when a signal arrives it
shows up here," with the action attached, is complete. A surface missing any of the three is unfinished
work, not a small gap: the customer meets it on their very first visit, when everything is empty.

### 5. IA before UI

The route map and the fact map are written before the code and are the contract the code follows. A new
route that is in no navigation group, or a second path to something that already exists, is rejected at the
map, not discovered later in a walk.

`docs/architecture/ROUTE_MAP.md` and `docs/architecture/FACT_MAP.md` are those contracts.

### 6. Simple and Pro are one app

Simple and Pro are two renderings of the same facts, never two implementations. The mode changes the chrome
(no sidebar, bigger targets, plain Hinglish, one thing at a time) and the ordering, never the numbers and
never the vocabulary of a state. A card, a stat or a status word that exists in both modes comes from one
component fed by one fact owner. The same holds for the public site: the public Track Record and the in-app
marketplace render one strategy card from one data source.

### 7. Enforcement lives in CI, not in review

Each rule above has a check that fails the build:

| Rule | Check |
| --- | --- |
| Layer direction, slice isolation | `eslint-plugin-boundaries` element types + allowed-import matrix |
| Tokens | ESLint rule banning raw colour/pixel design values outside declared exceptions |
| One page template, one header shell | Test walking the route map |
| Three states | Test walking every data surface |
| One source per fact | Test asserting each duplicated fact resolves to its single owner |

A rule that has never been proven to fail is not enforcement. Each rule is verified by injecting a violation
and observing the failure before it is accepted.

## Consequences

**Accepted costs.** Imports get longer and more explicit. Adding a fact takes a deliberate step (decide the
owner) instead of an inline `useApi`. Some legitimate code must move for reasons that feel bureaucratic in
the moment. Migration touches many files, and every moved file is a chance to break a test.

**What we get.** Two screens cannot disagree, because there is one owner. A change is contained, because the
import graph is a DAG with known direction. A new developer (or a new session) can find a domain's code by
its name. Empty and error states stop being discovered by customers.

**Migration is incremental — a strangler, not a rewrite.** Slices move one domain at a time with the suite
green after each. Unmigrated files are held in an explicit legacy allowlist that the boundary rule tolerates
but **cannot grow**: new violations fail the build. The allowlist shrinks as slices land, and reaching zero
is the definition of done. A big-bang migration of a live trading product is rejected: the blast radius is
the whole app and the rollback is a revert of everything.

**Deliberately not migrated now:** the strategy builders and the chart module. They are the deepest tangles,
they carry the most business risk, and moving them buys the least. They stay in the legacy allowlist with
their reason recorded, and get their own ADR when their turn comes.

## Alternatives considered

- **Leave the structure, fix the ten defects.** Rejected: the defects are symptoms of duplicate facts. The
  same two screens would disagree again after the next feature.
- **Atomic Design (atoms/molecules/organisms).** Rejected: it classifies by visual size, not by business
  meaning, so it gives no answer to "where does this fact live" — the actual problem.
- **A `src/modules/<domain>` split with no layers.** Rejected: domain grouping without a direction rule
  still allows cycles, which is how the current tangle formed.
- **Nx / Turborepo package boundaries.** Rejected for now: real enforcement, but it imposes a build-graph
  migration on a live product at the same time as the structural one. ESLint boundaries gets the same
  guarantee at a fraction of the risk, and does not preclude packages later.

## Follow-ups

Each later structural decision gets its own short ADR: `0002-…`, `0003-…`. An ADR is one decision, its
context, and what it costs — not a status report.
