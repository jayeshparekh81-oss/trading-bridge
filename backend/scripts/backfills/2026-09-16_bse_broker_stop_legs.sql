-- ═══════════════════════════════════════════════════════════════════════════
-- ONE-TIME BACKFILL — 2026-09-16. ARCHIVED, NOT LIVE. DO NOT RE-RUN BY HABIT.
-- ═══════════════════════════════════════════════════════════════════════════
--
-- WHAT THIS WAS FOR
-- ─────────────────
-- Three BSE Ltd (89423ecc) positions closed at Dhan by fills that existed in
-- the broker's book and NOWHERE in strategy_executions, because pine_replica
-- places its trailing stops straight at Dhan rather than through this
-- platform. The site therefore showed those round trips as open, unpriced, or
-- (worse) human_interfered — the founder's own engine's exits, published as if
-- a stranger had closed them.
--
-- This script wrote those legs into action_history by hand, once, so the
-- record since 1 Sep 2026 could be read at all.
--
-- WHY IT IS ARCHIVED AND NOT DELETED (founder's ruling, 2026-09-16)
-- ────────────────────────────────────────────────────────────────
-- Every value below is now IN the production record. Deleting the script
-- would leave rows whose provenance could not be re-derived by anyone reading
-- the repo later — the numbers would be true but unexplainable. The file is
-- kept as the receipt for exactly those writes.
--
-- 🔴 WHAT REPLACES IT
-- ───────────────────
-- app/domains/pnl_reconciler/ingest.py. The ingester does this job from
-- evidence instead of by hand: it reads the WS order-update tape, joins on
-- orderId, and attributes a stop child to its position through the recorded
-- chain (child fill -> algoOrdNo -> parent Forever order -> engine ledger ->
-- entry order id). Not one timestamp is compared. Run it with:
--
--     python -m app.domains.pnl_reconciler --strategy 89423ecc-... \
--         --tradebook <book.jsonl> --order-tape <tape.jsonl> --ingest
--
-- NOTHING NEW SHOULD EVER BE BACKFILLED BY HAND AGAIN. If a leg is missing,
-- that is the ingester's job, and if the ingester cannot attribute it, the
-- answer is "pehchaan nahi" and an alert — never a hand-written UPDATE.
--
-- SAFETY PROPERTIES OF THIS FILE, IF IT IS EVER RE-RUN
-- ────────────────────────────────────────────────────
-- Every statement is guarded and idempotent:
--   * the two broker_stop appends carry NOT (action_history @> ...broker_stop),
--     so a second run appends nothing;
--   * the d0086394 rewrite requires pnl_attribution='operator_estimate', which
--     is no longer true of that row;
--   * the operator_reconcile replacement requires that event to still exist,
--     and it keeps the old one nested under `superseded` — nothing is deleted.
-- It runs inside BEGIN/COMMIT with ON_ERROR_STOP.
--
-- PROVENANCE OF EVERY VALUE BELOW
-- ───────────────────────────────
-- Prices, quantities, order ids and timestamps are Dhan fills, read from the
-- broker trade book. The `attribution` strings name the exact evidence chain
-- used for each leg. No value here was estimated, modelled or inferred from
-- the shape of an order. The single exception is explicitly labelled: the
-- superseded 2026-09-11 operator estimate (3264.90), kept only as history.
--
-- ═══════════════════════════════════════════════════════════════════════════

\set ON_ERROR_STOP on
BEGIN;
-- A3 (founder review 2026-09-16): the 200 was closed by a MANUAL Dhan-app
-- ORDER, not by "no fill". The row must name it. The old operator_reconcile
-- event (written 11-09, price 3264.90, an estimate) is REPLACED — archived
-- inside the same entry under `superseded` so nothing is deleted.
UPDATE strategy_positions SET
  action_history = (
    SELECT jsonb_agg(
      CASE WHEN ev->>'leg_role' = 'operator_reconcile'
      THEN jsonb_build_object(
        'ts','2026-09-11T04:01:17+00:00','ts_ist','11-09 09:31','action','closed',
        'leg_role','manual_close','side','buy','qty',200,'price',3215.40,
        'broker_fill',true,'broker_order_id','35226091145606',
        'source','manual','label','manual se band',
        'superseded', ev)
      ELSE ev END)
    FROM jsonb_array_elements(action_history) AS ev)
WHERE id='d0086394-e66b-4b49-b557-7c337df777ac'
  AND action_history @> '[{"leg_role":"operator_reconcile"}]'::jsonb;

UPDATE strategy_positions SET
  final_pnl = NULL,
  pnl_attribution = 'human_interfered',
  pnl_attribution_detail = 'Closed by a MANUAL Dhan-app order 35226091145606, BUY 200 @3215.40, 2026-09-11 09:31:17 IST (orderPlatform=FAST), BETWEEN this position''s entry and its close. Founder rule: final_pnl NULL, "manual se band". Supersedes the 2026-09-11 operator estimate 3264.90 / 41769.71, recorded before that fill existed.',
  closed_at = timestamptz '2026-09-11 09:31:17+05:30',
  exit_reason = 'manual_close_dhan_app'
WHERE id='d0086394-e66b-4b49-b557-7c337df777ac' AND pnl_attribution='operator_estimate';

UPDATE strategy_positions SET action_history = action_history || jsonb_build_array(
  jsonb_build_object('ts','2026-09-04T07:41:13+00:00','action','exit','leg_role','broker_stop',
    'side','sell','qty',400,'price',3415.50,'broker_fill',true,
    'broker_order_id','312260904412406','parent_forever_order_id','32132609031621',
    'label','broker stop (auto)',
    'attribution','engine ledger: tape algoOrdNo -> parent 32132609031621 -> cron_bridge PLACED long 800 (03-09 10:00 IST) -> own_fills entry 32226090368506'),
  jsonb_build_object('leg_role','duplicate_exit','label','system galti: duplicate exit',
    'broker_order_id','23226090443106','side','sell','qty',400,'price',3415.80,
    'closed_by', jsonb_build_array(
      jsonb_build_object('broker_order_id','362260904291606','qty',200,'price',3426.70),
      jsonb_build_object('broker_order_id','222260904331206','qty',200,'price',3426.70)),
    'gross_pnl',-4360.00,
    'reason','13:11:13 engine stop child 312260904412406 SELL 400 @3415.50 took this position to zero. 13:15:12 platform SL_HIT 23226090443106 SELL 400 @3415.80 fired anyway and OPENED A SHORT 400 FROM FLAT (pine_replica closing_guard.py post-mortem). Closed 13:34 by two manual BUY 200 @3426.70. Not this position''s P&L; shown and counted as the system''s own loss.'))
WHERE id='844b8037-f192-40f8-88ce-09b091030c17'
  AND NOT (action_history @> '[{"leg_role":"broker_stop"}]'::jsonb);

UPDATE strategy_positions SET action_history = action_history || jsonb_build_array(
  jsonb_build_object('ts','2026-09-08T04:12:32+00:00','action','exit','leg_role','broker_stop',
    'side','sell','qty',800,'price',3394.025,'broker_fill',true,
    'broker_order_id','312260908126806','parent_forever_order_id','23132609071677',
    'label','broker stop (auto)',
    'attribution','engine ledger: stop_child_fired.json trade_key 2026-09-07 10:30:00+05:30|long -> parent 23132609071677 -> tape algoOrdNo on child 312260908126806'))
WHERE id='a13ddeb0-d875-474b-b40e-eb1facb36970'
  AND NOT (action_history @> '[{"leg_role":"broker_stop"}]'::jsonb);

\echo '--- after S2 ---'
SELECT left(id::text,8) AS id, status, final_pnl, coalesce(pnl_attribution,'-') AS attr,
       jsonb_array_length(action_history) AS hist
FROM strategy_positions WHERE strategy_id='89423ecc-c76e-432c-b107-0791508542f0' ORDER BY opened_at;
COMMIT;
