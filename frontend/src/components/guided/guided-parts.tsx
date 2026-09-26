"use client";

/**
 * Small pieces of the guided path: the progress bar, the never-stuck error card, and
 * AlgoMitra's guide panel. Design tokens only; every tap target is 44px+ (min-h-11).
 */

import Link from "next/link";
import { useState } from "react";
import { Check, CircleDot, Minus, Sparkles, TriangleAlert } from "lucide-react";

import { cn } from "@/shared/lib/utils";
import type { CustomerError, ErrorAction, GuideReply, GuidedStep, ProgressItem } from "@/lib/guided-path";

// ── progress bar: where they are and what is left ─────────────────────────────

export function ProgressBar({ items }: { items: ProgressItem[] }) {
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
        <span data-testid="guided-progress-count">Kadam {pos} / {counted.length}</span>
        <span>{left === 0 ? "Aakhri kadam" : `${left} kadam baaki`}</span>
      </div>
      <div className="h-2 w-full overflow-hidden rounded-full bg-muted" role="progressbar" aria-valuemin={0} aria-valuemax={100} aria-valuenow={pct}
        aria-label={current ? `Abhi: ${current.title}` : "Progress"}>
        <div className="h-full rounded-full bg-primary transition-all" style={{ width: `${pct}%` }} />
      </div>
      <ol className="flex flex-wrap gap-x-3 gap-y-1 text-sm" aria-label="Saare kadam">
        {items.map((i) => (
          <li key={i.step} data-testid={`guided-bar-${i.step}`} data-state={i.state}
            className={cn("inline-flex items-center gap-1",
              i.state === "CURRENT" ? "font-semibold text-foreground" : "text-muted-foreground",
              i.state === "NOT_NEEDED" && "line-through")}>
            {i.state === "DONE" ? <Check className="h-3 w-3 text-profit" aria-hidden />
              : i.state === "CURRENT" ? <CircleDot className="h-3 w-3 text-primary" aria-hidden />
                : i.state === "NOT_NEEDED" ? <Minus className="h-3 w-3" aria-hidden /> : null}
            {i.title}{i.state === "NOT_NEEDED" ? " (lagu nahi)" : ""}
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
  return (
    <div data-testid="guided-error" data-kind={err.kind} role="alert"
      className="flex flex-col gap-3 rounded-lg border border-loss/40 bg-loss/5 p-4">
      <div className="flex items-start gap-2">
        <TriangleAlert className="mt-0.5 h-5 w-5 shrink-0 text-loss" aria-hidden />
        <div className="flex flex-col gap-2 text-sm">
          <p><span className="font-semibold">Kya hua: </span><span data-testid="guided-error-what">{err.what_happened}</span></p>
          <p><span className="font-semibold">Iska matlab: </span>{err.what_it_means}</p>
          <p><span className="font-semibold">Ab kya karein: </span><span data-testid="guided-error-todo">{err.what_to_do}</span></p>
          {err.contact ? (
            <p data-testid="guided-error-contact" className="text-muted-foreground">
              Hum yeh theek nahi kar paaye to: {err.contact.who}.{" "}
              <Link href={err.contact.href} className="underline">Support kholo</Link>. Kya bhejna hai: {err.contact.send}
            </p>
          ) : null}
        </div>
      </div>
      <div className="flex flex-col gap-2 sm:flex-row">
        {err.action ? (
          err.action.href ? (
            <Link href={err.action.href} data-testid="guided-error-action"
              className="inline-flex min-h-11 flex-1 items-center justify-center rounded-md bg-primary px-4 text-sm font-medium text-primary-foreground">
              {err.action.label}
            </Link>
          ) : (
            <button type="button" data-testid="guided-error-action" onClick={() => onAction(err.action!)}
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

const CHIPS: Array<{ label: string; q: string }> = [
  { label: "Iska matlab?", q: "is screen ka matlab kya hai" },
  { label: "Kya karun?", q: "kya karun" },
  { label: "Risk kya hai?", q: "risk kya hai" },
];

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
        <Sparkles className="h-4 w-4 text-accent-gold" aria-hidden /> AlgoMitra — aapka guide
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
        {busy ? "Soch raha hu…" : shown ? shown.text : "Neeche se kuch bhi poocho."}
      </p>
      {failed ? <p className="text-sm text-muted-foreground">Abhi jawab nahi aa paaya — dobara poocho.</p> : null}
      <div className="flex flex-wrap gap-2">
        {CHIPS.map((c) => (
          <button key={c.label} type="button" onClick={() => run(c.q)} disabled={busy}
            className="inline-flex min-h-11 items-center rounded-full border border-border px-3 text-sm">
            {c.label}
          </button>
        ))}
      </div>
      <form className="flex gap-2" onSubmit={(e) => { e.preventDefault(); if (q.trim()) void run(q); }}>
        <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Apna sawaal likho (token ya password kabhi nahi)"
          aria-label="AlgoMitra se sawaal" maxLength={500}
          className="min-h-11 flex-1 rounded-md border border-border bg-background px-3 text-sm" />
        <button type="submit" disabled={busy || !q.trim()} className="min-h-11 rounded-md border border-border px-3 text-sm">Poocho</button>
      </form>
    </section>
  );
}
