"use client";

/**
 * Small pieces of the guided path: the progress bar, the never-stuck error card, and
 * AlgoMitra's guide panel. Design tokens only; every tap target is 44px+ (min-h-11).
 */

import Link from "next/link";
import { useState } from "react";
import { Check, CircleDot, Sparkles, TriangleAlert } from "lucide-react";

import { cn } from "@/shared/lib/utils";
import type { CustomerError, ErrorAction, GuideReply, GuidedStep, ProgressItem } from "@/lib/guided-path";
import { guidedCopy } from "@/lib/i18n/copy/guided";
import { fill, useCopy } from "@/lib/i18n/core";

// ── progress bar: where they are and what is left ─────────────────────────────

export function ProgressBar({ items }: { items: ProgressItem[] }) {
  const { c } = useCopy(guidedCopy);
  const counted = items.filter((i) => i.state !== "NOT_NEEDED");
  const idx = counted.findIndex((i) => i.state === "CURRENT");
  const done = counted.filter((i) => i.state === "DONE").length;
  const pos = idx >= 0 ? idx + 1 : done;
  const left = Math.max(counted.length - pos, 0);
  const pct = counted.length ? Math.round((pos / counted.length) * 100) : 0;
  const current = items.find((i) => i.state === "CURRENT");
  return (
    <div data-testid="guided-progress" className="flex flex-col gap-2">
      <div className="flex items-baseline justify-between text-sm text-muted-foreground">
        <span data-testid="guided-progress-count">{fill(c.step_count, { pos, total: counted.length })}</span>
        <span>{left === 0 ? c.last_step : fill(c.steps_left, { n: left })}</span>
      </div>
      <div className="h-2 w-full overflow-hidden rounded-full bg-muted" role="progressbar" aria-valuemin={0} aria-valuemax={100} aria-valuenow={pct}
        aria-label={current ? fill(c.now_prefix, { title: current.title }) : c.progress_aria}>
        <div className="h-full rounded-full bg-primary transition-all" style={{ width: `${pct}%` }} />
      </div>
      {/* 2 Oct 2026 (founder, item 5): steps that do NOT apply are HIDDEN, not struck out — a
          first-timer read "Kis cheez me trade (lagu nahi)" as "I did something wrong". Only the
          steps this customer will actually take are listed, and they are what "Kadam X / Y" counts. */}
      <ol className="flex flex-wrap gap-x-3 gap-y-1 text-sm" aria-label={c.all_steps_aria}>
        {counted.map((i) => (
          <li key={i.step} data-testid={`guided-bar-${i.step}`} data-state={i.state}
            className={cn("inline-flex items-center gap-1",
              i.state === "CURRENT" ? "font-semibold text-foreground" : "text-muted-foreground")}>
            {i.state === "DONE" ? <Check className="h-3 w-3 text-profit" aria-hidden />
              : i.state === "CURRENT" ? <CircleDot className="h-3 w-3 text-primary" aria-hidden /> : null}
            {i.title}
          </li>
        ))}
      </ol>
    </div>
  );
}

// ── the never-stuck error card ────────────────────────────────────────────────

export function ErrorCard({ err, onAction, onBack }: {
  err: CustomerError;
  onAction: (a: ErrorAction) => void;
  onBack?: (a: ErrorAction) => void;
}) {
  const { c } = useCopy(guidedCopy);
  return (
    <div data-testid="guided-error" data-kind={err.kind} role="alert"
      className="flex flex-col gap-3 rounded-lg border border-loss/40 bg-loss/5 p-4">
      <div className="flex items-start gap-2">
        <TriangleAlert className="mt-0.5 h-5 w-5 shrink-0 text-loss" aria-hidden />
        <div className="flex flex-col gap-2 text-sm">
          <p><span className="font-semibold">{c.err_what}</span><span data-testid="guided-error-what">{err.what_happened}</span></p>
          <p><span className="font-semibold">{c.err_means}</span>{err.what_it_means}</p>
          <p><span className="font-semibold">{c.err_todo}</span><span data-testid="guided-error-todo">{err.what_to_do}</span></p>
          {err.contact ? (
            <p data-testid="guided-error-contact" className="text-muted-foreground">
              {fill(c.err_contact_1, { who: err.contact.who })}{" "}
              <Link href={err.contact.href} className="underline">{c.err_contact_link}</Link>. {fill(c.err_contact_2, { send: err.contact.send })}
            </p>
          ) : null}
        </div>
      </div>
      <div className="flex flex-col gap-2 sm:flex-row">
        {err.action ? (
          err.action.href ? (
            <Link href={err.action.href} data-testid="guided-error-action" data-primary="true"
              className="inline-flex min-h-11 flex-1 items-center justify-center rounded-md bg-primary px-4 text-sm font-medium text-primary-foreground">
              {err.action.label}
            </Link>
          ) : (
            <button type="button" data-testid="guided-error-action" data-primary="true" onClick={() => onAction(err.action!)}
              className="inline-flex min-h-11 flex-1 items-center justify-center rounded-md bg-primary px-4 text-sm font-medium text-primary-foreground">
              {err.action.label}
            </button>
          )
        ) : null}
        {err.back && onBack ? (
          <button type="button" data-testid="guided-error-back" onClick={() => onBack(err.back!)}
            className="inline-flex min-h-11 flex-1 items-center justify-center rounded-md border border-border px-4 text-sm">
            {err.back.label}
          </button>
        ) : null}
      </div>
    </div>
  );
}

// ── AlgoMitra, the guide ──────────────────────────────────────────────────────


export function GuidePanel({ step, guide, warnings, ask }: {
  step: GuidedStep;
  guide: GuideReply | null;
  warnings: string[];
  ask: (q: string) => Promise<GuideReply | null>;
}) {
  const [reply, setReply] = useState<GuideReply | null>(null);
  const [q, setQ] = useState("");
  const [busy, setBusy] = useState(false);
  const [failed, setFailed] = useState(false);
  const { c } = useCopy(guidedCopy);
  const CHIPS: Array<{ label: string; q: string }> = [
    { label: c.chip_meaning, q: c.chip_meaning_q },
    { label: c.chip_do, q: c.chip_do_q },
    { label: c.chip_risk, q: c.chip_risk_q },
  ];
  const shown = reply ?? guide;
  const run = async (question: string) => {
    setBusy(true);
    setFailed(false);
    const r = await ask(question);
    setBusy(false);
    if (r) setReply(r);
    else setFailed(true);
  };
  return (
    <section data-testid="guided-guide" data-step={step} aria-label="AlgoMitra guide"
      className="flex flex-col gap-2 rounded-lg border border-border bg-card p-3">
      <div className="flex items-center gap-2 text-sm font-semibold text-muted-foreground">
        <Sparkles className="h-4 w-4 text-accent-gold" aria-hidden /> {c.guide_title}
      </div>
      {warnings.length ? (
        <ul data-testid="guided-warnings" className="flex flex-col gap-1">
          {warnings.map((w) => (
            <li key={w} className="flex gap-2 text-sm text-foreground">
              <TriangleAlert className="mt-0.5 h-4 w-4 shrink-0 text-accent-gold" aria-hidden />{w}
            </li>
          ))}
        </ul>
      ) : null}
      <p data-testid="guided-guide-text" className="text-sm text-foreground">
        {busy ? c.thinking : shown ? shown.text : c.ask_anything}
      </p>
      {failed ? <p className="text-sm text-muted-foreground">{c.ask_failed}</p> : null}
      <div className="flex flex-wrap gap-2">
        {CHIPS.map((c) => (
          <button key={c.label} type="button" onClick={() => run(c.q)} disabled={busy}
            className="inline-flex min-h-11 items-center rounded-full border border-border px-3 text-sm">
            {c.label}
          </button>
        ))}
      </div>
      <form className="flex gap-2" onSubmit={(e) => { e.preventDefault(); if (q.trim()) void run(q); }}>
        <input value={q} onChange={(e) => setQ(e.target.value)} placeholder={c.ask_placeholder}
          aria-label={c.ask_aria} maxLength={500}
          className="min-h-11 flex-1 rounded-md border border-border bg-background px-3 text-sm" />
        <button type="submit" disabled={busy || !q.trim()} className="min-h-11 rounded-md border border-border px-3 text-sm">{c.ask_btn}</button>
      </form>
    </section>
  );
}
