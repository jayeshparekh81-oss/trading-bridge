/**
 * The ONE place that decides whether an order is SIMULATED or REAL MONEY.
 *
 * ⚠️ READ BEFORE CHANGING ANYTHING HERE. This module decides whether a screen
 * tells a customer "broker ko koi asli order nahi jaata". Getting it wrong on
 * a live row is the worst lie this product can tell.
 *
 * WHY THIS EXISTS (defect, 2026-09-09, founder's own account)
 * ───────────────────────────────────────────────────────────
 * `PaperModeBanner` derived paper-ness from ONE global platform flag —
 * `GET /api/system/mode` → `paper_mode` — and was mounted on /positions,
 * which renders the OWNER's REAL-MONEY rows. His BSE LTD Futures strategy is
 * `is_paper = false`; the page told him his orders were simulated while the
 * broker held a real futures position. The flag was not merely the wrong
 * scope: it CONTRADICTS the backend's own resolution rule.
 *
 * THE BACKEND'S RULE, WHICH THIS MIRRORS
 * ──────────────────────────────────────
 * `app/services/paper_mode_resolver.py::resolve_paper_mode` is the execution
 * path's single source of truth (migration 027, incident 2026-05-18):
 *
 *     effective_paper = (strategy.is_paper
 *                        if strategy.is_paper is not None
 *                        else settings.strategy_paper_mode)
 *
 * The PER-STRATEGY flag WINS. The global flag is only a fallback for a
 * strategy row that carries no explicit value — and production rows always
 * carry one, so in production the global flag decides nothing. A UI that
 * reads only the global flag is therefore reading a value the executor
 * ignores. `kill_switch_service.py:577` already says it out loud: paper-ness
 * is decided "by per-strategy paper_mode_resolver, NOT by global settings
 * flag."
 *
 * NEVER NAME A STATE YOU HAVE NOT READ. `null` means unknown, and unknown
 * prints nothing — never a reassuring default. "We could not load it" and
 * "it is simulated" are different facts and only one is safe to print.
 *
 * SCOPE IS THE WHOLE POINT. A banner is a claim about EVERY row beneath it.
 * It may only be shown when every row in scope is simulated. A page that
 * mixes paper and live rows gets per-row labels instead — /positions today
 * returns both the live "BSE LTD Futures" rows and a paper "PAPER FANOUT
 * TEST" row, so no single sentence about that page can be true.
 */

/**
 * Effective paper-mode for one strategy, mirroring `resolve_paper_mode`.
 *
 * @param strategyIsPaper the strategy's own `is_paper`, or null/undefined
 *   when we have not read it (NOT "false" — absence is not a live claim).
 * @param platformPaperMode the global `paper_mode` from `/api/system/mode`,
 *   used ONLY as the fallback the backend uses it as.
 * @returns true (simulated) | false (real money) | null (unknown — say nothing)
 */
export function resolvePaperMode(
  strategyIsPaper: boolean | null | undefined,
  platformPaperMode: boolean | null | undefined,
): boolean | null {
  if (strategyIsPaper === true || strategyIsPaper === false) {
    return strategyIsPaper;
  }
  if (platformPaperMode === true || platformPaperMode === false) {
    return platformPaperMode;
  }
  return null;
}

/**
 * What a whole surface may honestly claim about the rows it is showing.
 *
 * `all-paper`  — every row is simulated; a blanket banner is TRUE.
 * `mixed`      — some simulated, some real; only per-row labels can be true.
 * `none-paper` — nothing here is simulated; there is nothing to disclose.
 * `unknown`    — at least one row's mode has not been read; claim nothing.
 */
export type PaperScope = "all-paper" | "mixed" | "none-paper" | "unknown";

/**
 * Reduce the per-row modes of one surface to the strongest claim it may make.
 *
 * An EMPTY scope is `none-paper`, not `all-paper`: "every one of zero rows is
 * simulated" is vacuously true and would print a paper banner over an empty
 * table. Unknown is contagious — one unread row poisons the blanket claim,
 * because a banner speaks for rows it cannot see.
 */
export function paperScope(
  flags: readonly (boolean | null | undefined)[],
): PaperScope {
  if (flags.length === 0) return "none-paper";
  if (flags.some((f) => f !== true && f !== false)) return "unknown";

  const simulated = flags.filter((f) => f === true).length;
  if (simulated === flags.length) return "all-paper";
  if (simulated === 0) return "none-paper";
  return "mixed";
}

/** The subscription fields that can testify to a subscriber's execution mode. */
export interface SubscriptionModeSource {
  /** The subscription's own flag. Not served today — read when it appears. */
  is_paper?: boolean | null;
  /** "paper" | "auto" | "one_click" | "offline". Only "paper" proves paper. */
  execution_mode?: string | null;
  open_position?: { paper_mode?: boolean | null } | null;
}

/**
 * Effective paper-mode for one marketplace SUBSCRIPTION row.
 *
 * Three server-derived witnesses, strongest first. Nothing here is hardcoded:
 * if the server says nothing, this returns `null` and the surface says nothing.
 *
 *  1. `is_paper` — the subscription's own column. It EXISTS on
 *     `marketplace_subscriptions` but is NOT currently serialised by
 *     `SubscriptionRead`, so this branch is dormant until that one additive
 *     field ships. Read first because it is the flag the fan-out owns.
 *  2. `execution_mode === "paper"` — an explicit customer choice to simulate.
 *     Any OTHER value proves nothing: "auto" still executes as paper until
 *     live trading is enabled (Phase 3 / empanelment), so it cannot be read
 *     as evidence of real money.
 *  3. `open_position.paper_mode` — how the position actually executing right
 *     now was filled. Only present once a position exists.
 *
 * Deliberately NOT done: assuming "subscribers are always paper today". It is
 * true right now (`marketplace_fanout.py` dispatches with `paper=True`), but a
 * sentence that is only true while a flag stays off is a hardcoded claim
 * waiting to become a lie. When the flag flips, this stays correct.
 */
export function subscriptionPaperMode(
  sub: SubscriptionModeSource | null | undefined,
): boolean | null {
  if (!sub) return null;
  if (sub.is_paper === true || sub.is_paper === false) return sub.is_paper;
  if (sub.execution_mode === "paper") return true;
  const fromPosition = sub.open_position?.paper_mode;
  if (fromPosition === true || fromPosition === false) return fromPosition;
  return null;
}

/** The word every surface prints for a simulated row. */
export const PAPER_WORD = "Paper";
/** The word every surface prints for a real-money row. */
export const LIVE_WORD = "LIVE";

export default resolvePaperMode;
