/**
 * The ONE place that turns execution LEGS into broker ORDERS.
 *
 * ⚠️ READ BEFORE CHANGING. Two screens count the same thing with this rule,
 * and if they ever disagree a customer sees one number on /trades and a
 * different one on the Overview for the identical activity.
 *
 * WHY IT EXISTS
 * ─────────────
 * `strategy_executions` stores one row per LEG. The founder's 07-Sep entry is
 * FOUR rows of 200 that all share `broker_order_id` 322260907150406 — because
 * Dhan filled one order of 800 in four clips. Listing the legs made a single
 * order look like four trades: the trades tab showed four rows, and the
 * Overview's "trades aaj" counted four where the broker counts one.
 *
 * The broker's own convention is the contract (founder, 2026-09-10): the trade
 * book is EXECUTED ORDERS, one row per order. So legs collapse, quantity is
 * the SUM of the legs, and the order's time is its FIRST leg — not whichever
 * leg happened to be read last.
 *
 * A LEG WITH NO ORDER ID STAYS ITS OWN ROW. We do not know which order it
 * belonged to, and merging on a guess would fuse orders that were never one.
 * It is keyed by its execution id so two unknowns can never collapse into
 * each other either.
 *
 * This module was extracted after the rule was written out twice — once in
 * `/trades` and once in the Overview — which is precisely the duplicated fact
 * ADR 0001 §2 forbids. Add a third caller here, never a third copy.
 */

/** The subset of an execution row this rule needs. */
export interface ExecutionLeg {
  id: string;
  broker_order_id: string | null;
  quantity: number;
  /** ISO timestamp used to date the ORDER. Callers pass whichever they render. */
  timestamp: string | null;
  broker_status?: string | null;
}

/** One broker order, assembled from its legs. */
export interface BrokerOrder<T extends ExecutionLeg> {
  /** Stable row key: the broker order id, or `leg:<execution id>` when absent. */
  key: string;
  /** The first leg seen — carries every field the caller wants to render. */
  first: T;
  /** Sum of the legs' quantities: what the broker actually filled. */
  quantity: number;
  /** How many legs collapsed into this order. 1 means it filled in one clip. */
  legs: number;
  /** Earliest leg timestamp — the order's own time. */
  timestamp: string | null;
  /** First non-null broker status across the legs. */
  brokerStatus: string | null;
}

/**
 * Collapse legs into orders, preserving the server's ordering.
 *
 * Insertion order is kept deliberately: the API returns newest-first and the
 * page must not silently re-sort into a different order than the one the
 * server chose.
 */
export function groupLegsIntoOrders<T extends ExecutionLeg>(
  rows: readonly T[],
): BrokerOrder<T>[] {
  const byOrder = new Map<string, BrokerOrder<T>>();
  for (const leg of rows) {
    const key = leg.broker_order_id ?? `leg:${leg.id}`;
    const seen = byOrder.get(key);
    if (!seen) {
      byOrder.set(key, {
        key,
        first: leg,
        quantity: leg.quantity,
        legs: 1,
        timestamp: leg.timestamp,
        brokerStatus: leg.broker_status ?? null,
      });
      continue;
    }
    seen.quantity += leg.quantity;
    seen.legs += 1;
    seen.brokerStatus ??= leg.broker_status ?? null;
    // The order's time is its EARLIEST leg. Compared as instants, not as
    // strings — two ISO timestamps in different offsets sort wrongly as text.
    if (
      leg.timestamp &&
      (!seen.timestamp || Date.parse(leg.timestamp) < Date.parse(seen.timestamp))
    ) {
      seen.timestamp = leg.timestamp;
    }
  }
  return [...byOrder.values()];
}

/** How many distinct broker ORDERS these legs represent. */
export function countOrders(rows: readonly ExecutionLeg[]): number {
  return groupLegsIntoOrders(rows).length;
}
