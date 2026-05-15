-- ═══════════════════════════════════════════════════════════════════════
-- Phase C — futures_resolver deploy pre-check queries
-- ═══════════════════════════════════════════════════════════════════════
--
-- Run BOTH queries against prod Postgres on Monday morning BEFORE the
-- supervised deploy. Save the output to the deploy runbook so we can
-- compare pre/post resolution-symbol distributions.
--
-- Why this matters
--     The futures_resolver mutates the symbol that hits Dhan AND the
--     symbol that gets persisted in ``strategy_signals.symbol``. If
--     existing in-flight signals or open positions use a non-canonical
--     symbol form (e.g. ``NSE:BSE``, ``BSE1!``) then deploying the
--     resolver will start writing the canonical ``BSE-MAY2026-FUT``
--     form going forward — which can BREAK position-lookup-by-symbol
--     for any unclosed position still tagged with the old form.
--
-- Risk decision
--     * Both result sets EMPTY  → GREEN  → safe to deploy
--     * Result sets contain only canonical ``ROOT-MMMYYYY-FUT`` rows
--                                → GREEN  → safe to deploy
--     * Either set contains ``NSE:BSE``, ``BSE1!``, ``BSE:NSE``, or
--       a bare ``BSE`` row with a non-zero ``position_count``
--                                → YELLOW → needs a position-symbol
--                                  remap script BEFORE deploy
--     * Result sets contain other unfamiliar BSE-prefixed strings
--                                → RED    → STOP. Surface to Jayesh
--                                  for analysis before any deploy.
-- ═══════════════════════════════════════════════════════════════════════


-- ───────────────────────────────────────────────────────────────────────
-- Query 1 — Existing BSE symbol formats in strategy_signals
-- ───────────────────────────────────────────────────────────────────────
--
-- Reveals what symbol strings have flowed through the webhook over
-- recent history. The ``signal_count`` column tells us how often each
-- form is used — a high count for a non-canonical form means the
-- resolver will rewrite many signals starting Monday.
--
-- Save the output. After deploy, re-run and confirm the canonical
-- ``BSE-<MMM>YYYY-FUT`` form starts dominating.

SELECT
    symbol,
    COUNT(*) AS signal_count,
    MIN(created_at) AS first_seen,
    MAX(created_at) AS last_seen
FROM strategy_signals
WHERE symbol ILIKE 'BSE%' OR symbol ILIKE '%BSE%'
GROUP BY symbol
ORDER BY signal_count DESC;


-- ───────────────────────────────────────────────────────────────────────
-- Query 2 — Existing BSE positions in strategy_positions
-- ───────────────────────────────────────────────────────────────────────
--
-- The blast-radius query. Any open position whose ``symbol`` is in a
-- non-canonical form will become orphaned the moment the resolver
-- starts writing canonical symbols. The exit logic looks up positions
-- by ``(strategy_id, symbol)``; the new canonical form WILL NOT match
-- the old non-canonical row → exit signal misroutes as a fresh entry.
--
-- Look for:
--     * symbol = 'NSE:BSE'                  → REMAP REQUIRED
--     * symbol = 'BSE1!'                    → REMAP REQUIRED
--     * symbol = 'BSE:NSE'                  → REMAP REQUIRED
--     * symbol = 'BSE' (bare, no month)     → REMAP REQUIRED
--     * symbol = 'BSE-MAY2026-FUT' (or any  → SAFE (already canonical)
--                month-stamped form)
--     * symbol = 'BSE-MAY2026-3600-CE' or   → OUT OF SCOPE — option
--                ...-PE                       contract; resolver does
--                                             NOT touch options.
--
-- If REMAP REQUIRED rows have ``position_count > 0``, we MUST run a
-- one-off update before the deploy:
--
--     UPDATE strategy_positions
--     SET symbol = 'BSE-<active-month>2026-FUT'
--     WHERE symbol IN ('NSE:BSE', 'BSE1!', 'BSE:NSE', 'BSE');
--
-- ...where ``<active-month>`` is whatever the resolver would resolve
-- to on Monday morning (typically the current month, unless we're
-- deploying after 15:30 IST on a last-Thursday).

SELECT
    symbol,
    side,
    status,
    COUNT(*) AS position_count,
    SUM(total_quantity) AS total_quantity_sum,
    SUM(remaining_quantity) AS remaining_quantity_sum,
    MIN(opened_at) AS first_opened,
    MAX(opened_at) AS last_opened
FROM strategy_positions
WHERE symbol ILIKE 'BSE%' OR symbol ILIKE '%BSE%'
GROUP BY symbol, side, status
ORDER BY position_count DESC, symbol;


-- ═══════════════════════════════════════════════════════════════════════
-- Diagnostic: cross-check against trade_markers (Phase A table)
-- ═══════════════════════════════════════════════════════════════════════
-- If the above shows non-canonical positions, also check trade_markers
-- to understand the full BSE history we're carrying. EXIT markers
-- with linked entries in non-canonical form are the same drift class.

SELECT
    symbol,
    side,
    mode,
    COUNT(*) AS marker_count,
    MIN(timestamp_utc) AS first_seen,
    MAX(timestamp_utc) AS last_seen
FROM trade_markers
WHERE symbol ILIKE 'BSE%' OR symbol ILIKE '%BSE%'
GROUP BY symbol, side, mode
ORDER BY marker_count DESC, symbol;
