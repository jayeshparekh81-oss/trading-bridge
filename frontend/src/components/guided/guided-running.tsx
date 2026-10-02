"use client";

/**
 * WHAT THEY SEE WHILE RUNNING (founder, 26 Sep 2026, rule 4): their position, whether a
 * stop is resting AT THE BROKER right now, today's P&L from billed charges, and a big
 * obvious STOP EVERYTHING with a confirm and a plain explanation of what it will do.
 *
 * Three states on every fetched fact: loading · empty (said in words) · error (the
 * never-stuck card). The stop line is Track A's broker receipt, verbatim; it is never
 * computed here. STOP EVERYTHING is two taps: preview (what will happen, nothing changes)
 * → "Haan, sab band karo" (a 2-minute one-time token).
 */

import { useCallback, useEffect, useState } from "react";
import { Loader2, OctagonX, ShieldAlert, ShieldCheck, ShieldQuestion } from "lucide-react";

import { cn } from "@/shared/lib/utils";
import {
  guidedApi,
  toCustomerError,
  type CustomerError,
  type ErrorAction,
  type Running,
  type StopPreview,
  type StopResult,
} from "@/lib/guided-path";
import { ErrorCard } from "@/components/guided/guided-parts";
import { guidedCopy } from "@/lib/i18n/copy/guided";
import { fill, useCopy } from "@/lib/i18n/core";

const POLL_MS = 30_000;

function StopTruth({ stop }: { stop: Running["stop"] }) {
  const { c } = useCopy(guidedCopy);
  const green = stop.verdict === "PROTECTED" || stop.verdict === "FLAT";
  const unknown = stop.verdict === "NOT_MEASURED" || stop.verdict.startsWith("UNKNOWN") || stop.verdict === "NOT MEASURED";
  const Icon = green ? ShieldCheck : unknown ? ShieldQuestion : ShieldAlert;
  return (
    <section data-testid="running-stop" data-verdict={stop.verdict}
      className={cn("flex items-start gap-3 rounded-lg border p-4", green ? "border-profit/40" : "border-loss/40 bg-loss/5")}>
      <Icon className={cn("h-6 w-6 shrink-0", green ? "text-profit" : unknown ? "text-muted-foreground" : "text-loss")} aria-hidden />
      <div className="flex flex-col gap-1 text-sm">
        <span className="font-semibold">{c.run_stop_title}</span>
        <span data-testid="running-stop-line">{stop.line}</span>
        <span className="text-sm text-muted-foreground">
          {stop.verified_at ? fill(c.run_last_check, { when: new Date(stop.verified_at).toLocaleString("en-IN", { timeZone: "Asia/Kolkata" }) }) : c.run_not_checked}
        </span>
      </div>
    </section>
  );
}

export function RunningDashboard({ onGoto, onRestart }: { onGoto: (a: ErrorAction) => void; onRestart?: () => void }) {
  const [data, setData] = useState<Running | null>(null);
  const [err, setErr] = useState<CustomerError | null>(null);
  const [loading, setLoading] = useState(true);
  const [preview, setPreview] = useState<StopPreview | null>(null);
  const [stopErr, setStopErr] = useState<CustomerError | null>(null);
  const [result, setResult] = useState<StopResult | null>(null);
  const [busy, setBusy] = useState(false);
  const { c, lang } = useCopy(guidedCopy);

  const load = useCallback(async () => {
    try {
      setData(await guidedApi.running());
      setErr(null);
    } catch (e) {
      setErr(toCustomerError(e, "running", lang));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    // first read + the 30 s refresh both run from timer callbacks (never setState in the effect body)
    const first = setTimeout(() => void load(), 0);
    const t = setInterval(() => void load(), POLL_MS);
    return () => { clearTimeout(first); clearInterval(t); };
    // eslint-disable-next-line react-hooks/exhaustive-deps -- `lang` only changes the error wording
  }, [load]);

  const askStop = async () => {
    setBusy(true);
    setStopErr(null);
    try { setPreview(await guidedApi.stopPreview()); } catch (e) { setStopErr(toCustomerError(e, "stop-preview", lang)); } finally { setBusy(false); }
  };
  const doStop = async () => {
    if (!preview) return;
    setBusy(true);
    try {
      setResult(await guidedApi.stop(preview.confirm_token));
      setPreview(null);
      await load();
    } catch (e) {
      setStopErr(toCustomerError(e, "stop", lang));
      setPreview(null);
      // a PARTIAL stop still disabled the strategy — show the fresh truth (what is still open)
      await load();
    } finally { setBusy(false); }
  };

  if (loading && !data) {
    return <p data-testid="running-loading" className="flex items-center gap-2 text-sm text-muted-foreground"><Loader2 className="h-4 w-4 animate-spin" aria-hidden /> {c.run_loading}</p>;
  }
  if (err && !data) {
    return <ErrorCard err={err} onAction={(a) => (a.step ? onGoto(a) : void load())} />;
  }
  if (!data) return null;
  return (
    <div data-testid="running" className="flex flex-col gap-4">
      <header className="flex flex-col gap-1">
        <h1 className="text-xl font-semibold">{data.stopped ? c.run_stopped : c.run_running}: {data.strategy ?? "NOT MEASURED"}</h1>
        <p data-testid="running-paper" className={cn("text-sm", data.is_paper ? "text-accent-gold" : "text-foreground")}>{data.paper_line}</p>
        <p className="text-sm text-muted-foreground">{data.market.line}</p>
      </header>
      {err ? <p role="alert" className="text-sm text-muted-foreground">{fill(c.run_stale, { todo: err.what_to_do })}</p> : null}
      <section data-testid="running-broker" data-state={data.broker.state} className="rounded-lg border border-border p-3 text-sm">
        {data.broker.line}
        {data.broker.action ? (
          <button type="button" onClick={() => onGoto(data.broker.action!)} className="ml-2 min-h-11 underline">{data.broker.action.label}</button>
        ) : null}
      </section>
      <section data-testid="running-position" className="rounded-lg border border-border p-4 text-sm">
        <span className="font-semibold">{c.run_position}</span>
        {data.positions.length ? <p data-testid="running-position-source" className="text-sm text-muted-foreground">{data.positions_line}</p> : null}
        {data.positions.length ? (
          <ul className="mt-1 flex flex-col gap-1">
            {data.positions.map((p) => (
              <li key={`${p.symbol}-${p.side}`}>{p.side === "buy" ? c.run_long : c.run_short} {p.quantity} · {p.symbol}{p.avg_price ? ` @ ${p.avg_price}` : ""}</li>
            ))}
          </ul>
        ) : <p className="mt-1 text-muted-foreground">{data.positions_line}</p>}
        {data.is_paper ? (
          <p data-testid="running-paper-where" className="mt-2 text-sm text-muted-foreground">
            {c.run_paper_where}
          </p>
        ) : null}
      </section>
      <StopTruth stop={data.stop} />
      <section data-testid="running-pnl" className="rounded-lg border border-border p-4 text-sm">
        <span className="font-semibold">{c.run_pnl}</span>
        <p className="mt-1">{data.today_pnl.line}</p>
      </section>

      {result ? (
        <section data-testid="stop-result" className="rounded-lg border border-profit/40 p-4 text-sm">
          <p className="font-semibold">{c.run_stopped_done}</p>
          <ul className="mt-1 list-disc pl-5">{result.lines.map((l) => <li key={l}>{l}</li>)}</ul>
          <p className="mt-1 text-muted-foreground">{result.restart_line}</p>
        </section>
      ) : null}
      {stopErr ? <ErrorCard err={stopErr} onAction={(a) => (a.step ? onGoto(a) : void askStop())} /> : null}

      {preview ? (
        <section data-testid="stop-confirm" role="dialog" aria-label={c.run_stop_dialog_aria} className="flex flex-col gap-3 rounded-lg border-2 border-loss p-4 text-sm">
          <p className="text-base font-semibold">{c.run_stop_will}</p>
          <ul className="flex flex-col gap-1" data-testid="stop-lines">{preview.lines.map((l) => <li key={l}>{l}</li>)}</ul>
          <button type="button" data-testid="stop-yes" disabled={busy} onClick={() => void doStop()}
            className="min-h-14 w-full rounded-md bg-loss text-base font-semibold text-primary-foreground">
            {busy ? c.run_stopping : c.run_stop_yes}
          </button>
          <button type="button" data-testid="stop-no" disabled={busy} onClick={() => setPreview(null)}
            className="min-h-11 w-full rounded-md border border-border">{c.run_stop_no}</button>
        </section>
      ) : data.stop_everything.enabled && !data.stopped ? (
        <button type="button" data-testid="stop-everything" disabled={busy} onClick={() => void askStop()}
          className="flex min-h-16 w-full items-center justify-center gap-2 rounded-lg bg-loss text-lg font-bold text-primary-foreground">
          <OctagonX className="h-6 w-6" aria-hidden /> {c.run_stop_everything}
        </button>
      ) : data.stopped ? (
        <div data-testid="stopped" className="flex flex-col gap-2 rounded-lg border border-border p-4 text-sm">
          <p>{c.run_stopped_line}</p>
          {onRestart ? (
            <button type="button" data-testid="restart" onClick={onRestart}
              className="min-h-11 w-full rounded-md border border-border">{c.run_restart}</button>
          ) : null}
        </div>
      ) : !data.stop_everything.enabled ? (
        <p data-testid="stop-off" className="text-sm text-muted-foreground">{c.run_stop_off}</p>
      ) : null}
    </div>
  );
}
