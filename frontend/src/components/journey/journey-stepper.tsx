"use client";

/**
 * The journey stepper — ONE screen per step, ONE next step, mobile first.
 *
 * Rules it renders by (Track C item 6, 25 Sep 2026):
 *   - wapas one tap: the back arrow is always the first thing on the screen;
 *   - what's next visible: the NEXT step is the headline, the rest are a short list;
 *   - three states on every fetched fact: loading / empty (NOT MEASURED, with why) / error;
 *   - thumb-reachable: the one CTA sits at the bottom, full width, 44px+ tall;
 *   - no number that was not measured: NOT MEASURED is the literal string;
 *   - design tokens only (no hex, no px in classes).
 */

import Link from "next/link";
import { useMemo } from "react";
import { ArrowLeft, Check, CircleHelp, ChevronRight, Loader2 } from "lucide-react";

import { useApi } from "@/shared/api/use-api";
import { cn } from "@/shared/lib/utils";
import { customerDashboardEnabled } from "@/lib/account-truth";
import {
  JOURNEY_STEPS,
  STEP_COPY,
  measured,
  notMeasured,
  resolveJourney,
  type JourneyInputs,
  type JourneyStep,
  type JourneySubscription,
  type StepState,
} from "@/lib/customer-journey";

interface SubscriptionsResponse {
  subscriptions: Array<{
    id: string;
    status: string;
    execution_mode?: string | null;
    direction_filter?: string | null;
    lots_override?: number | null;
    is_paper?: boolean | null;
    listing_title?: string | null;
    open_position?: { symbol: string; quantity: number; side?: string | null } | null;
  }>;
  count: number;
}
interface BillingMe { plan_status: string; is_active: boolean }
interface BrokerRow { name: string; status: string }
interface LaneStatus { connected: boolean; reason: string; eligibility: string; message: string }
interface TruthCard { verdict: string; line: string; next_step_hi: string }

/** null = the flag says this surface is not mounted: NOT MEASURED, never a fetch that 404s into "empty". */
function laneUrl(path: string, mounted: boolean): string | null {
  return mounted ? path : null;
}

export interface JourneyStepperProps {
  /** which step the customer opened (from the URL); default = the resolved NEXT */
  step?: JourneyStep | null;
  /** the lane's charging switch, from the billing ledger when mounted; false today */
  chargingEnabled?: boolean;
  className?: string;
}

export function JourneyStepper({ step, chargingEnabled = false, className }: JourneyStepperProps) {
  const dashboardMounted = customerDashboardEnabled();
  const subs = useApi<SubscriptionsResponse>("/marketplace/subscriptions/me", null);
  const billing = useApi<BillingMe>("/billing/me", null);
  const brokers = useApi<BrokerRow[]>("/brokers", null);
  const lane = useApi<LaneStatus>(laneUrl("/customer-lane/me/status", dashboardMounted), null);
  const truth = useApi<TruthCard>(laneUrl("/customer-lane/dashboard/truth", dashboardMounted), null);

  const loading = subs.isLoading || billing.isLoading || brokers.isLoading || lane.isLoading || truth.isLoading;

  const inputs: JourneyInputs = useMemo(() => ({
    billing: billing.error ? notMeasured(`plan surface failed: ${billing.error}`) : billing.data ? measured(billing.data) : notMeasured("plan surface not read"),
    charging_enabled: chargingEnabled,
    subscriptions: subs.error
      ? notMeasured(`subscriptions failed: ${subs.error}`)
      : subs.data
        ? measured<JourneySubscription[]>(subs.data.subscriptions.map((s) => ({
          id: s.id, status: s.status, execution_mode: s.execution_mode, direction_filter: s.direction_filter,
          lots: s.lots_override ?? null, is_paper: s.is_paper, listing_title: s.listing_title, open_position: s.open_position ?? null,
        })))
        : notMeasured("subscriptions not read"),
    brokers: brokers.error ? notMeasured(`broker list failed: ${brokers.error}`) : brokers.data ? measured(brokers.data) : notMeasured("broker list not read"),
    lane: !dashboardMounted ? notMeasured("customer-lane status surface not mounted (flag OFF)") : lane.error ? notMeasured(`lane status failed: ${lane.error}`) : lane.data ? measured(lane.data) : notMeasured("lane status not read"),
    truth: !dashboardMounted ? notMeasured("truth card surface not mounted (flag OFF)") : truth.error ? notMeasured(`truth card failed: ${truth.error}`) : truth.data ? measured(truth.data) : notMeasured("truth card not read"),
  }), [billing.data, billing.error, subs.data, subs.error, brokers.data, brokers.error, lane.data, lane.error, truth.data, truth.error, dashboardMounted, chargingEnabled]);

  const res = useMemo(() => resolveJourney(inputs), [inputs]);
  const current: JourneyStep = step && JOURNEY_STEPS.includes(step) ? step : res.next;
  const idx = JOURNEY_STEPS.indexOf(current);
  const prev = idx > 0 ? JOURNEY_STEPS[idx - 1] : null;
  const state = res.steps.find((s) => s.step === current)!;
  const anyError = subs.error || billing.error || brokers.error || lane.error || truth.error;

  return (
    <div data-testid="journey" data-step={current} data-next={res.next} className={cn("mx-auto flex w-full max-w-md flex-col gap-4", className)}>
      {/* wapas: ONE tap, always first */}
      <div className="flex items-center justify-between">
        <Link
          href={prev ? `/journey?step=${prev}` : "/marketplace/me"}
          data-testid="journey-back"
          className="inline-flex min-h-11 items-center gap-2 text-sm text-muted-foreground hover:text-foreground"
        >
          <ArrowLeft className="h-4 w-4" aria-hidden />
          {prev ? STEP_COPY[prev].title : "Dashboard"}
        </Link>
        <span className="text-sm text-muted-foreground">{idx + 1} / {JOURNEY_STEPS.length}</span>
      </div>

      {/* the ONE headline: what is next */}
      <div className="rounded-lg border border-border bg-card p-4">
        <div className="text-sm uppercase tracking-wide text-muted-foreground">{STEP_COPY[current].title}</div>
        <h2 className="mt-1 text-lg font-semibold leading-snug">{STEP_COPY[current].what}</h2>
        {loading ? (
          <div data-testid="journey-loading" className="mt-3 flex items-center gap-2 text-sm text-muted-foreground">
            <Loader2 className="h-4 w-4 animate-spin" aria-hidden /> Check ho raha hai…
          </div>
        ) : (
          <p data-testid="journey-line" className={cn("mt-3 text-sm", state.state === "UNKNOWN" ? "text-muted-foreground" : "text-foreground")}>
            {state.line}
          </p>
        )}
        {anyError && !loading ? (
          <p data-testid="journey-error" role="alert" className="mt-2 text-sm text-loss">
            Kuch cheezein check nahi ho paayi — upar jo NOT MEASURED likha hai, woh isi wajah se hai. Thodi der me dobara kholo.
          </p>
        ) : null}
      </div>

      {/* the short list: DONE / NEXT / LATER / UNKNOWN, tappable */}
      <ol className="flex flex-col gap-1" aria-label="Journey steps">
        {res.steps.map((s) => (
          <StepRow key={s.step} s={s} active={s.step === current} />
        ))}
      </ol>

      {/* the ONE thumb-reachable CTA (a Link styled with the button tokens — this
          repo's Button has no asChild) */}
      <div data-testid="journey-cta">
        <Link
          href={state.href}
          className="inline-flex min-h-12 w-full items-center justify-center rounded-md bg-primary px-4 text-sm font-medium text-primary-foreground hover:bg-primary/90"
        >
          {state.state === "DONE" ? "Aage badho" : STEP_COPY[current].cta}
          <ChevronRight className="ml-1 h-4 w-4" aria-hidden />
        </Link>
      </div>
      <p className="text-center text-sm text-muted-foreground">{res.headline}</p>
    </div>
  );
}

function StepRow({ s, active }: { s: StepState; active: boolean }) {
  const icon = s.state === "DONE" ? <Check className="h-4 w-4 text-profit" aria-hidden />
    : s.state === "UNKNOWN" ? <CircleHelp className="h-4 w-4 text-muted-foreground" aria-hidden />
      : <span className={cn("inline-block h-2 w-2 rounded-full", s.state === "NEXT" ? "bg-primary" : "bg-muted")} aria-hidden />;
  return (
    <li>
      <Link
        href={`/journey?step=${s.step}`}
        data-testid={`journey-step-${s.step}`}
        data-state={s.state}
        className={cn("flex min-h-11 items-center gap-3 rounded-md px-3 text-sm",
          active ? "bg-accent text-accent-foreground" : "text-muted-foreground hover:bg-accent/50")}
      >
        <span className="flex w-5 justify-center">{icon}</span>
        <span className="flex-1 truncate">{STEP_COPY[s.step].title}</span>
        <span className="text-sm">{s.state === "NEXT" ? "ab" : s.state === "DONE" ? "ho gaya" : s.state === "UNKNOWN" ? "pata nahi" : ""}</span>
      </Link>
    </li>
  );
}
