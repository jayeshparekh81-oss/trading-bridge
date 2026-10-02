"use client";

/**
 * THE FIRST-TIMER GUIDED PATH — the orchestrator (founder, 26 Sep 2026).
 *
 * Every screen: the progress bar (where they are, what is left) · ONE decision · the one
 * line of why · the safe default pre-chosen · AlgoMitra beside it · a way FORWARD and a
 * way BACK that never loses work · errors as the never-stuck card. A closed tab resumes
 * on the server's saved step (the local mirror only picks the loading line).
 */

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { ArrowLeft, ChevronRight, Loader2 } from "lucide-react";

import { useAuthOptional } from "@/lib/auth";
import {
  guidedApi,
  lastStep,
  rememberStep,
  signupError,
  toCustomerError,
  type CustomerError,
  type ErrorAction,
  type GuidedState,
  type GuidedStep,
  type GuideReply, markGuidedLeft, clearGuidedLeft } from "@/lib/guided-path";
import { ErrorCard, GuidePanel, ProgressBar } from "@/components/guided/guided-parts";
import { RunningDashboard } from "@/components/guided/guided-running";
import {
  BrokerScreen,
  ConfirmScreen,
  ScreenHeader,
  SignupScreen,
  SizeScreen,
  StrategyScreen,
  StrikeScreen,
  SummaryBlock,
  VehicleScreen,
  signupReady,
  type BrokerValue,
  type SignupValue,
  type SizeValue,
} from "@/components/guided/guided-screens";

const NEXT_LABEL: Partial<Record<GuidedStep, string>> = {
  SIGNUP: "Account banao",
  BROKER: "Bina Dhan ke aage badho (practice)",
  SUMMARY: "Samajh gaya, aage",
  CONFIRM: "Haan, shuru karo",
};

function hasToken(): boolean {
  try { return typeof window !== "undefined" && !!localStorage.getItem("tb_access_token"); } catch { return false; }
}

export function GuidedPath() {
  const auth = useAuthOptional();
  const [state, setState] = useState<GuidedState | null>(null);
  const [error, setError] = useState<CustomerError | null>(null);
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [signup, setSignup] = useState<SignupValue>({ full_name: "", email: "", password: "", risk_ack: false });
  const [broker, setBroker] = useState<BrokerValue>({ client_id: "", access_token: "" });
  const [strategyId, setStrategyId] = useState<string | null>(null);
  const [vehicle, setVehicle] = useState("FUTURES");
  const [moneyness, setMoneyness] = useState("OTM");
  const [size, setSize] = useState<SizeValue>({ lots: 2, max_daily_loss_inr: "" });
  const [ack, setAck] = useState(false);
  const [resumeHint] = useState<GuidedStep | null>(() => lastStep());

  const adopt = useCallback((s: GuidedState) => {
    setState(s);
    setError(null);
    rememberStep(s.step);
    const d = s.draft;
    if (d) {
      setStrategyId(d.strategy_id ?? (s.screen.selected as string | null) ?? null);
      setVehicle(d.vehicle || "FUTURES");
      setMoneyness(d.moneyness || "OTM");
      setSize({ lots: d.lots || 2, max_daily_loss_inr: d.max_daily_loss_inr != null ? String(d.max_daily_loss_inr) : "" });
      setAck(!!d.acknowledged);
    } else if (s.screen.selected) {
      setStrategyId(s.screen.selected);
    }
  }, []);

  const load = useCallback(async () => {
    clearGuidedLeft();                       // they came back to the guide: the dashboard may send them here again
    try {
      adopt(hasToken() ? await guidedApi.state() : await guidedApi.publicStart());
    } catch (e) {
      const ce = toCustomerError(e, "start");
      // a FIRST-timer with a stale token gets the signup form; a RETURNING customer (the
      // mirror says they got past signup) gets "Login karo" — never a form that would make
      // them create a second account.
      const returning = resumeHint !== null && resumeHint !== "SIGNUP";
      if (ce.kind === "SIGNED_OUT" && !returning) {
        try { adopt(await guidedApi.publicStart()); return; } catch { /* fall through to the card */ }
      }
      setError(ce);
    } finally {
      setLoading(false);
    }
  }, [adopt, resumeHint]);

  // the first read runs from a timer callback (an effect only SUBSCRIBES; state is set in callbacks)
  useEffect(() => {
    const t = setTimeout(() => void load(), 0);
    return () => clearTimeout(t);
  }, [load]);

  const run = async (fn: () => Promise<GuidedState | void>, screen: string, mapErr = toCustomerError) => {
    setBusy(true);
    setError(null);
    try {
      const s = await fn();
      if (s) adopt(s);
    } catch (e) {
      setError(mapErr(e, screen));
    } finally {
      setBusy(false);
    }
  };

  const step = state?.step ?? "SIGNUP";

  const forward = () => {
    switch (step) {
      case "SIGNUP":
        return run(async () => {
          await guidedApi.signup(signup);
          // tell the app's auth context too, so a later dashboard link does not bounce to /login
          await auth?.refreshUser().catch(() => undefined);
          return guidedApi.state();
        }, "signup", (e) => signupError(e));
      case "BROKER":
        // 2 Oct 2026 (THE LOOP + item 6): the ONE primary on this step is "Baad me karunga" — a practice
        // account needs no Dhan token. A real connect is the quiet second button inside the screen.
        return run(() => guidedApi.choose("BROKER", { later: true }), "broker");
      case "STRATEGY":
        return run(() => guidedApi.choose("STRATEGY", { strategy_id: strategyId }), "strategy");
      case "VEHICLE":
        return run(() => guidedApi.choose("VEHICLE", { vehicle }), "vehicle");
      case "STRIKE":
        return run(() => guidedApi.choose("STRIKE", { moneyness }), "strike");
      case "SIZE":
        return run(() => guidedApi.choose("SIZE", { lots: size.lots, max_daily_loss_inr: size.max_daily_loss_inr }), "size");
      case "SUMMARY":
        return run(() => guidedApi.choose("SUMMARY", {}), "summary");
      case "CONFIRM":
        return run(async () => { await guidedApi.confirm(); return guidedApi.state(); }, "confirm");
      default:
        return undefined;
    }
  };

  const backward = () => (state?.back ? run(() => guidedApi.back(step), "back") : undefined);

  /** An error's button: its step is where to go (walk back to it; the server resumes
   * forward steps itself), otherwise it is "try again". */
  const onErrAction = async (a: ErrorAction) => {
    if (!a.step || a.step === step) { setError(null); return; }
    // BROKER (token expired / not connected) and RUNNING: let the SERVER resume there. Walking
    // back with /back would move the saved cursor to BROKER, and a re-connect would then
    // send the customer through Strategy → Vehicle → Size → Summary again (walk-1 F2 by
    // another door — found reviewing the UI path after walk 2).
    if (a.step === "RUNNING" || a.step === "BROKER") { await load(); return; }
    setBusy(true);
    try {
      let s = state;
      for (let i = 0; i < 9 && s && s.step !== a.step && s.back; i++) s = await guidedApi.back(s.step);
      if (s) adopt(s); else await load();
    } catch (e) { setError(toCustomerError(e, "back")); } finally { setBusy(false); }
  };

  const ask = async (q: string): Promise<GuideReply | null> => {
    try { return await guidedApi.ask(step, q); } catch { return null; }
  };

  /** After STOP: the explicit restart only OPENS the confirm screen (summary + tick). */
  const restart = () => run(() => guidedApi.restart(), "restart");

  if (loading && !state) {
    return (
      <p data-testid="guided-loading" className="flex items-center gap-2 text-sm text-muted-foreground">
        <Loader2 className="h-4 w-4 animate-spin" aria-hidden />
        {resumeHint && resumeHint !== "SIGNUP" ? "Aap jahan ruke the, wahi khol rahe hain…" : "Khul raha hai…"}
      </p>
    );
  }
  if (!state) {
    return error ? <ErrorCard err={error} onAction={() => void load()} /> : null;
  }
  if (step === "RUNNING") {
    return (
      <div className="flex flex-col gap-4">
        <RunningDashboard onGoto={(a) => void onErrAction(a)} onRestart={() => void restart()} />
        <GuidePanel step="RUNNING" guide={state.guide} warnings={state.warnings ?? []} ask={ask} />
      </div>
    );
  }

  const sc = state.screen;
  const summaryMerged = !(state.progress ?? []).some((p) => p.step === "SUMMARY");
  const errorLeads = !!error?.action;
  const canGo =
    step === "SIGNUP" ? signupReady(signup)
      : step === "BROKER" ? true
        : step === "STRATEGY" ? !!strategyId
          : step === "CONFIRM" ? ack : true;

  return (
    <div data-testid="guided" data-step={step} className="flex flex-col gap-4">
      <ProgressBar items={state.progress} />
      <ScreenHeader screen={sc} />
      {sc.default_note ? <p data-testid="guided-default" className="text-sm text-muted-foreground">Pehle se chuna hua: {sc.default_note}</p> : null}

      {step === "SIGNUP" ? <SignupScreen value={signup} onChange={setSignup} /> : null}
      {step === "BROKER" ? <BrokerScreen screen={sc} value={broker} onChange={setBroker} busy={busy}
        onConnect={() => void run(() => guidedApi.broker(broker.client_id, broker.access_token), "broker")} /> : null}
      {step === "STRATEGY" ? <StrategyScreen screen={sc} value={strategyId} onChange={setStrategyId} /> : null}
      {step === "VEHICLE" ? <VehicleScreen screen={sc} value={vehicle} onChange={setVehicle} /> : null}
      {step === "STRIKE" ? <StrikeScreen screen={sc} value={moneyness} onChange={setMoneyness} /> : null}
      {step === "SIZE" ? <SizeScreen screen={sc} value={size} onChange={setSize} /> : null}
      {/* SIGNUP CUT 2 (26 Sep night): a server that merged SUMMARY into CONFIRM sends no
          SUMMARY step on the bar — then the confirm screen carries the summary itself (one
          screen, one tap fewer). An older server still sends the SUMMARY screen: unchanged. */}
      {(step === "SUMMARY" || (step === "CONFIRM" && summaryMerged)) && sc.summary ? <SummaryBlock s={sc.summary} /> : null}
      {step === "CONFIRM" ? <ConfirmScreen screen={sc} ack={ack} onAck={setAck} compact={summaryMerged} /> : null}

      {error ? <ErrorCard err={error} onAction={(a) => void onErrAction(a)} onBack={(a) => void onErrAction(a)} /> : null}

      {/* the two ways out of every screen: forward (the one CTA) and back (never loses work) */}
      <nav data-testid="guided-nav" className="flex flex-col gap-2">
        {/* ONE big primary per screen (founder's rule, 26 Sep, point 2): when an error card
            shows its own "what to do" button, THAT is the one thing to tap — the forward
            button steps down to a quiet outline so two green buttons never compete. */}
        <button type="button" data-testid="guided-next" data-primary={errorLeads ? undefined : "true"}
          disabled={busy || !canGo} onClick={() => void forward()}
          className={errorLeads
            ? "inline-flex min-h-12 w-full items-center justify-center rounded-md border border-border px-4 text-base font-medium disabled:opacity-50"
            : "inline-flex min-h-12 w-full items-center justify-center rounded-md bg-primary px-4 text-base font-medium text-primary-foreground disabled:opacity-50"}>
          {busy ? <Loader2 className="mr-2 h-4 w-4 animate-spin" aria-hidden /> : null}
          {NEXT_LABEL[step] ?? "Aage"}
          <ChevronRight className="ml-1 h-4 w-4" aria-hidden />
        </button>
        {state.back ? (
          <button type="button" data-testid="guided-back" disabled={busy} onClick={() => void backward()}
            className="inline-flex min-h-11 w-full items-center justify-center gap-2 rounded-md border border-border text-sm">
            <ArrowLeft className="h-4 w-4" aria-hidden /> Pichhla kadam (kuch nahi mitega)
          </button>
        ) : step === "SIGNUP" ? (
          <Link href="/login?next=/start" data-testid="guided-back" className="inline-flex min-h-11 w-full items-center justify-center rounded-md border border-border text-sm">
            Pehle se account hai? Login karo
          </Link>
        ) : (
          <Link href="/" data-testid="guided-back" onClick={markGuidedLeft}
            className="inline-flex min-h-11 w-full items-center justify-center rounded-md border border-border text-sm">
            Baad me karunga (sab save hai)
          </Link>
        )}
        {!canGo && step === "CONFIRM" ? <p className="text-center text-sm text-muted-foreground">Upar tick lagao, tab button chalega.</p> : null}
        {!canGo && step === "SIGNUP" ? <p className="text-center text-sm text-muted-foreground">Upar ki saari line hari (✓) hon aur tick laga ho, tab button chalega.</p> : null}
      </nav>

      <GuidePanel step={step} guide={state.guide} warnings={state.warnings ?? []} ask={ask} />
    </div>
  );
}
