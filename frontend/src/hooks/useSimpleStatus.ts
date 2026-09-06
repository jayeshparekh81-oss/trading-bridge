"use client";

/**
 * Everything the Simple home needs to know, from endpoints that already exist:
 *   broker  — GET /brokers/dhan/status            (the same truth the /brokers badge uses)
 *   joined  — GET /marketplace/subscriptions/me    (the customer's subscriptions)
 *   signals — GET /marketplace/subscriptions/signals?status=received  (15 s poll, like /signals)
 *   built   — GET /strategies?limit=5              (own strategies: built / cloned)
 * Also derives the ladder FACTS that can be read from the server, so a customer
 * who did things in Pro mode (or another tab) is credited on the next home load.
 */

import { useMemo } from "react";
import { useApi } from "@/shared/api/use-api";
import { killSwitchLabel, type KillSwitchWireState } from "@/lib/kill-switch-label";
import type { SubscriberSignal, SubscriberSignalListResponse } from "@/lib/signals";
import type { JourneyFacts } from "@/lib/simple/level";

interface DhanStatus {
  connected: boolean;
  expires_estimate?: string | null;
}

interface SubscriptionRow {
  id: string;
  status: string;
  execution_mode?: string | null;
  is_paper?: boolean | null;
  listing_id: string;
  listing_title?: string | null;
}

interface StrategyRow {
  id: string;
  is_active?: boolean;
  is_paper?: boolean;
  template_slug?: string | null;
}

function rows<T>(data: unknown, key: string): T[] {
  if (Array.isArray(data)) return data as T[];
  if (data && typeof data === "object" && Array.isArray((data as Record<string, unknown>)[key])) {
    return (data as Record<string, T[]>)[key];
  }
  return [];
}

/** IST calendar day of an ISO timestamp, as YYYY-MM-DD. */
export function istDay(iso: string | Date): string {
  const d = typeof iso === "string" ? new Date(iso) : iso;
  return new Date(d.getTime() + 5.5 * 3_600_000).toISOString().slice(0, 10);
}

export interface SimpleStatus {
  loading: boolean;
  /**
   * ADR 0001 §4. Non-null when any of the four fetches failed. It matters more
   * here than anywhere else in the product: every boolean below is derived by
   * ABSENCE — a failed /brokers/dhan/status yields brokerConnected=false, which
   * in turn makes learningMode=true. So without this field a Simple customer
   * whose broker call merely timed out is told "Broker juda nahi hai" and
   * "Seekhne wala mode — asli paisa nahi", when their money may well be live.
   * A consumer that renders any of these facts must check this first and say
   * "pata nahi" rather than assert the negative.
   */
  error: string | null;
  /** False while broker state is unknown (loading or failed) — do not assert either way. */
  brokerKnown: boolean;
  /** True when the kill switch is down. Nothing runs, whatever is deployed. */
  killSwitchTripped: boolean;
  brokerConnected: boolean;
  strategyRunning: boolean;
  learningMode: boolean;
  signalsToday: number;
  latestSignal: SubscriberSignal | null;
  facts: Partial<JourneyFacts>;
  subscriptions: SubscriptionRow[];
  strategies: StrategyRow[];
  refetchSignals: () => void;
}

export function useSimpleStatus(enabled = true): SimpleStatus {
  const broker = useApi<DhanStatus>(enabled ? "/brokers/dhan/status" : null, null, 60_000);
  const subs = useApi<unknown>(enabled ? "/marketplace/subscriptions/me" : null, null, 60_000);
  const signals = useApi<SubscriberSignalListResponse>(
    enabled ? "/marketplace/subscriptions/signals?status=received&limit=50" : null,
    null,
    15_000,
  );
  const strategies = useApi<unknown>(enabled ? "/strategies?limit=5" : null, null, 120_000);
  // Simple mode used to assert "Strategy — Chalu hai" while the kill switch was
  // TRIPPED in Pro, because this hook never read the switch. Nothing can be
  // running when the switch is down, so it is read here — through the SAME
  // owner module the Pro surfaces use, so one switch cannot get two names.
  const kill = useApi<KillSwitchWireState>(enabled ? "/kill-switch/status" : null, null, 30_000);

  return useMemo(() => {
    const now = new Date();
    const b = broker.data;
    const brokerConnected =
      !!b?.connected && (!b.expires_estimate || new Date(b.expires_estimate).getTime() > now.getTime());
    const subRows = rows<SubscriptionRow>(subs.data, "subscriptions");
    const activeSubs = subRows.filter((s) => s.status === "active");
    const stratRows = rows<StrategyRow>(strategies.data, "strategies");
    const runningSubs = activeSubs.filter((s) => s.execution_mode !== "offline");
    // A tripped kill switch is a veto: whatever is deployed, no order goes out.
    const killLabel = killSwitchLabel(kill.data);
    const tripped = killLabel?.kind === "tripped";
    const strategyRunning =
      !tripped && (runningSubs.length > 0 || stratRows.some((s) => s.is_active));
    const liveSubs = runningSubs.filter((s) => s.execution_mode && s.execution_mode !== "paper" && !s.is_paper);
    const learningMode = !brokerConnected || liveSubs.length === 0;

    const today = istDay(now);
    const sig = signals.data?.signals ?? [];
    const todays = sig.filter((s) => s.received_at && istDay(s.received_at) === today);
    const latest = todays.length ? [...todays].sort((a, b) => b.received_at.localeCompare(a.received_at))[0] : null;

    const facts: Partial<JourneyFacts> = {};
    if (brokerConnected) facts.brokerConnected = true;
    if (activeSubs.length > 0 || subRows.length > 0) facts.hasSubscription = true;
    // The home hero renders the latest signal, so a signal in the list IS a signal seen.
    if (sig.length > 0) facts.firstSignalSeen = true;
    if (stratRows.length > 0) {
      // A strategy row exists: it was cloned from a template or built. Either
      // way the customer has crossed the "make one yours" line.
      facts.templateCloned = true;
      facts.strategyBuilt = true;
    }

    return {
      loading: broker.isLoading || subs.isLoading || signals.isLoading,
      error: broker.error ?? subs.error ?? signals.error ?? strategies.error ?? kill.error ?? null,
      killSwitchTripped: tripped,
      brokerKnown: !broker.isLoading && !broker.error,
      brokerConnected,
      strategyRunning,
      learningMode,
      signalsToday: todays.length,
      latestSignal: latest,
      facts,
      subscriptions: subRows,
      strategies: stratRows,
      refetchSignals: signals.refetch,
    };
  }, [
    broker.data, broker.isLoading, broker.error,
    subs.data, subs.isLoading, subs.error,
    signals.data, signals.isLoading, signals.error, signals.refetch,
    strategies.data, strategies.error,
    kill.data, kill.error,
  ]);
}
