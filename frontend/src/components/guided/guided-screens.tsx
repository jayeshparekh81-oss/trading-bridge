"use client";

/**
 * One component per screen of the guided path. Each renders ONE decision with the safe
 * default already chosen, a one-line "why this matters", and nothing it did not get from
 * the server (numbers arrive as numbers or the literal "NOT MEASURED").
 *
 * Controlled: a screen holds only the value being edited and hands it to `onChoice`; the
 * orchestrator decides what "Aage" does. Mobile first: stacked, full-width, 44px+ targets.
 */

import { useMemo, useState } from "react";
import { Check, Lock, ShieldCheck, X } from "lucide-react";

import { cn } from "@/shared/lib/utils";
import { guidedCopy } from "@/lib/i18n/copy/guided";
import { fill, useCopy } from "@/lib/i18n/core";
import {
  passwordRules,
  inr,
  type Option,
  type Screen,
  type StrategyOption,
  type Summary,
} from "@/lib/guided-path";

export function ScreenHeader({ screen }: { screen: Screen }) {
  const { c } = useCopy(guidedCopy);
  return (
    <header className="flex flex-col gap-1">
      <h1 data-testid="guided-title" className="text-xl font-semibold leading-snug">{screen.title}</h1>
      <p data-testid="guided-decision" className="text-base text-foreground">{screen.decision}</p>
      <p data-testid="guided-why" className="text-sm text-muted-foreground">
        <span className="font-medium">{c.why_prefix}</span>{screen.why}
      </p>
    </header>
  );
}

// ── SIGNUP ────────────────────────────────────────────────────────────────────

export interface SignupValue { full_name: string; email: string; password: string; risk_ack: boolean }

export function SignupScreen({ value, onChange }: { value: SignupValue; onChange: (v: SignupValue) => void }) {
  const set = (k: keyof SignupValue, v: string | boolean) => onChange({ ...value, [k]: v });
  const { c, lang } = useCopy(guidedCopy);
  const rules = passwordRules(lang);
  return (
    <div data-testid="screen-SIGNUP" className="flex flex-col gap-3">
      <label className="flex flex-col gap-1 text-sm">{c.your_name}
        <input className="min-h-11 rounded-md border border-border bg-background px-3" autoComplete="name"
          value={value.full_name} onChange={(e) => set("full_name", e.target.value)} />
      </label>
      <label className="flex flex-col gap-1 text-sm">{c.email}
        <input className="min-h-11 rounded-md border border-border bg-background px-3" type="email" autoComplete="email" inputMode="email"
          value={value.email} onChange={(e) => set("email", e.target.value)} />
      </label>
      <label className="flex flex-col gap-1 text-sm">{c.password}
        <input className="min-h-11 rounded-md border border-border bg-background px-3" type="password" autoComplete="new-password"
          value={value.password} onChange={(e) => set("password", e.target.value)} />
      </label>
      <ul data-testid="signup-rules" className="grid grid-cols-1 gap-1 text-sm sm:grid-cols-2">
        {rules.map((r) => {
          const ok = r.ok(value.password, { email: value.email, name: value.full_name });
          return (
            <li key={r.label} className={cn("flex items-center gap-1", ok ? "text-profit" : "text-muted-foreground")}>
              {ok ? <Check className="h-3 w-3" aria-hidden /> : <X className="h-3 w-3" aria-hidden />}{r.label}
            </li>
          );
        })}
      </ul>
      <label className="flex min-h-11 items-start gap-2 text-sm">
        <input type="checkbox" className="mt-1 h-5 w-5" checked={value.risk_ack} onChange={(e) => set("risk_ack", e.target.checked)} />
        <span>{c.risk_ack}</span>
      </label>
    </div>
  );
}

export function signupReady(v: SignupValue): boolean {
  return v.full_name.trim().length > 0 && /.+@.+\..+/.test(v.email) && v.risk_ack &&
    passwordRules("en").every((r) => r.ok(v.password, { email: v.email, name: v.full_name }));
}

// ── BROKER ────────────────────────────────────────────────────────────────────

export interface BrokerValue { client_id: string; access_token: string }

export function BrokerScreen({ screen, value, onChange, onConnect, busy = false }: {
  screen: Screen; value: BrokerValue; onChange: (v: BrokerValue) => void; onConnect?: () => void; busy?: boolean;
}) {
  // 2 Oct 2026 (founder, item 6 + THE LOOP): a PRACTICE account never needs a real Dhan token. The
  // ONE primary on this step (the footer's "Bina Dhan ke aage badho (practice)") skips it; the token
  // form sits behind a quiet disclosure for the customer who wants to connect now.
  const canConnect = value.client_id.trim().length > 0 && value.access_token.trim().length > 0;
  const { c } = useCopy(guidedCopy);
  return (
    <div data-testid="screen-BROKER" className="flex flex-col gap-3">
      {screen.broker_state === "EXPIRED" ? (
        <p data-testid="broker-expired" className="rounded-md bg-accent-gold/10 p-3 text-sm">{c.broker_expired}</p>
      ) : null}
      <p data-testid="broker-practice-line" className="rounded-md border border-accent-gold/40 bg-accent-gold/10 p-3 text-sm text-foreground">
        {c.broker_practice_1}<span className="font-semibold">{c.broker_practice_b}</span>{c.broker_practice_2}
      </p>
      <details data-testid="broker-connect-now" className="rounded-md border border-border p-3">
        <summary className="min-h-11 cursor-pointer list-none text-sm font-medium">{c.broker_now_summary}</summary>
        <div className="mt-3 flex flex-col gap-3">
          <p className="text-sm text-muted-foreground"><span className="font-medium text-foreground">{c.broker_where}</span>{screen.where_to_find}</p>
          <label className="flex flex-col gap-1 text-sm">{c.broker_client_id}
            <input className="min-h-11 rounded-md border border-border bg-background px-3" inputMode="numeric" autoComplete="off"
              value={value.client_id} onChange={(e) => onChange({ ...value, client_id: e.target.value })} />
          </label>
          <label className="flex flex-col gap-1 text-sm">{c.broker_token_label}
            <textarea className="min-h-20 rounded-md border border-border bg-background p-3 text-sm" autoComplete="off" spellCheck={false}
              value={value.access_token} onChange={(e) => onChange({ ...value, access_token: e.target.value })} />
          </label>
          <p className="flex items-start gap-2 text-sm text-muted-foreground">
            <ShieldCheck className="h-4 w-4 shrink-0" aria-hidden />
            {c.broker_token_safety}
          </p>
          {/* a quiet second button — never data-primary (one primary per screen) */}
          <button type="button" data-testid="broker-connect" disabled={busy || !canConnect || !onConnect} onClick={onConnect}
            className="inline-flex min-h-11 w-full items-center justify-center rounded-md border border-border px-4 text-sm font-medium disabled:opacity-50">
            {c.broker_connect_btn}
          </button>
        </div>
      </details>
    </div>
  );
}

// ── choices with a default and locks ─────────────────────────────────────────

function ChoiceList({ testid, options, selected, onSelect }: {
  testid: string;
  options: Array<{ key: string; label: string; open: boolean; why?: string; sub?: string }>;
  selected: string | null | undefined;
  onSelect: (k: string) => void;
}) {
  return (
    <div role="radiogroup" data-testid={testid} className="flex flex-col gap-2">
      {options.map((o) => {
        const on = o.key === selected;
        return (
          <button key={o.key} type="button" role="radio" aria-checked={on} disabled={!o.open}
            data-testid={`${testid}-${o.key}`} data-open={o.open} onClick={() => o.open && onSelect(o.key)}
            className={cn("flex min-h-12 w-full items-start gap-3 rounded-md border p-3 text-left text-sm",
              on ? "border-primary bg-primary/5" : "border-border",
              !o.open && "cursor-not-allowed opacity-60")}>
            <span className={cn("mt-0.5 inline-flex h-5 w-5 shrink-0 items-center justify-center rounded-full border",
              on ? "border-primary bg-primary text-primary-foreground" : "border-border")}>
              {on ? <Check className="h-3 w-3" aria-hidden /> : !o.open ? <Lock className="h-3 w-3" aria-hidden /> : null}
            </span>
            <span className="flex flex-col gap-0.5">
              <span className="font-medium">{o.label}</span>
              {o.sub ? <span className="text-sm text-muted-foreground">{o.sub}</span> : null}
              {!o.open && o.why ? <span className="text-sm text-muted-foreground">{o.why}</span> : null}
            </span>
          </button>
        );
      })}
    </div>
  );
}

export function StrategyScreen({ screen, value, onChange }: { screen: Screen; value: string | null; onChange: (id: string) => void }) {
  const opts = (screen.options ?? []) as StrategyOption[];
  const { c } = useCopy(guidedCopy);
  if (!opts.length) {
    return <p data-testid="screen-STRATEGY-empty" className="text-sm text-muted-foreground">{screen.empty_line}</p>;
  }
  return (
    <div data-testid="screen-STRATEGY">
      <ChoiceList testid="strategy" selected={value ?? screen.selected}
        options={opts.map((o) => ({ key: o.id, label: o.title, open: true,
          sub: o.price_inr && Number(o.price_inr) > 0 ? fill(c.strategy_fee, { price: inr(Number(o.price_inr)) }) : c.strategy_free }))}
        onSelect={onChange} />
    </div>
  );
}

export function VehicleScreen({ screen, value, onChange }: { screen: Screen; value: string; onChange: (v: string) => void }) {
  const opts = (screen.options ?? []) as Option[];
  return (
    <div data-testid="screen-VEHICLE">
      <ChoiceList testid="vehicle" selected={value}
        options={opts.map((o) => ({ key: o.name, label: o.label_hi, open: o.open, why: o.why }))} onSelect={onChange} />
    </div>
  );
}

export function StrikeScreen({ screen, value, onChange }: { screen: Screen; value: string; onChange: (v: string) => void }) {
  const opts = (screen.options ?? []) as Option[];
  return (
    <div data-testid="screen-STRIKE" className="flex flex-col gap-2">
      {screen.applies === false ? <p className="text-sm text-muted-foreground">{screen.applies_line}</p> : null}
      <ChoiceList testid="strike" selected={value}
        options={opts.map((o) => ({ key: o.name, label: o.label_hi, open: o.open && screen.applies !== false }))} onSelect={onChange} />
    </div>
  );
}

// ── SIZE + max risk ───────────────────────────────────────────────────────────

export interface SizeValue { lots: number; max_daily_loss_inr: string }

export function SizeScreen({ screen, value, onChange }: { screen: Screen; value: SizeValue; onChange: (v: SizeValue) => void }) {
  const { c } = useCopy(guidedCopy);
  const choices = screen.lot_choices ?? [2];
  // ONE SOURCE: the server computed every choice's numbers; this screen only looks them up.
  const row = screen.by_lots?.[String(value.lots)];
  const cap = row ?? (value.lots === screen.lots ? screen.capital : undefined);
  const shares = row?.shares ?? null;
  const dflt = row ? row.max_daily_loss_default : screen.max_daily_loss_default ?? null;
  return (
    <div data-testid="screen-SIZE" className="flex flex-col gap-4">
      <div className="flex flex-col gap-2">
        <span className="text-sm font-medium">{c.size_label}</span>
        <div className="flex items-center gap-3">
          <button type="button" aria-label={c.size_minus} disabled={value.lots <= choices[0]}
            onClick={() => onChange({ ...value, lots: Math.max(choices[0], value.lots - 2) })}
            className="min-h-12 min-w-12 rounded-md border border-border text-lg">−</button>
          <span data-testid="size-lots" className="min-w-24 text-center text-lg font-semibold">{fill(c.size_lot, { n: value.lots })}</span>
          <button type="button" aria-label={c.size_plus} disabled={value.lots >= choices[choices.length - 1]}
            onClick={() => onChange({ ...value, lots: Math.min(choices[choices.length - 1], value.lots + 2) })}
            className="min-h-12 min-w-12 rounded-md border border-border text-lg">+</button>
        </div>
        <span className="text-sm text-muted-foreground">
          {shares ? fill(c.size_shares, { shares: new Intl.NumberFormat("en-IN").format(shares), lots: value.lots }) : ""}{c.size_even}
        </span>
      </div>
      <dl data-testid="size-numbers" className="grid grid-cols-1 gap-2 rounded-md border border-border p-3 text-sm">
        {/* EVERY NUMBER EXPLAINED IN ONE LINE beside it, with WHOSE number it is
            (founder's rule, 26 Sep, point 6) — the server sends a plain basis for each. */}
        <div className="flex justify-between gap-2"><dt>{c.size_min_capital}</dt><dd className="font-semibold">{inr(cap?.minimum_capital)}</dd></div>
        <p data-testid="basis-minimum" className="text-sm text-muted-foreground">
          {fill(c.size_basis_min, { basis: cap?.plain?.minimum_capital ?? "NOT MEASURED" })}
        </p>
        <div className="flex justify-between gap-2"><dt>{c.size_worst_day}</dt><dd className="font-semibold text-loss">{inr(cap?.worst_day)}</dd></div>
        <p data-testid="basis-worst-day" className="text-sm text-muted-foreground">
          {fill(c.size_basis_worst, { basis: cap?.plain?.worst_day ?? "NOT MEASURED" })}
        </p>
        <div className="flex justify-between gap-2"><dt>{c.size_drawdown}</dt><dd className="font-semibold text-loss">{inr(cap?.max_drawdown)}</dd></div>
        <p data-testid="basis-drawdown" className="text-sm text-muted-foreground">
          {fill(c.size_basis_dd, { basis: cap?.plain?.max_drawdown ?? "NOT MEASURED" })}
        </p>
        <p className="text-sm text-muted-foreground">
          {c.size_no_guarantee}
          {cap?.margin_stale ? fill(c.size_margin_stale, { when: cap.margin_as_of_human ?? "NOT MEASURED" }) : ""}
        </p>
      </dl>
      <label className="flex flex-col gap-1 text-sm">
        {c.size_loss_label}
        <input data-testid="size-loss" className="min-h-11 rounded-md border border-border bg-background px-3" inputMode="numeric"
          placeholder={typeof dflt === "number" ? fill(c.size_loss_ph_default, { amount: inr(dflt) }) : c.size_loss_ph}
          value={value.max_daily_loss_inr} onChange={(e) => onChange({ ...value, max_daily_loss_inr: e.target.value.replace(/[^\d]/g, "") })} />
        <span className="text-sm text-muted-foreground">{c.size_loss_safe}</span>
      </label>
    </div>
  );
}

// ── SUMMARY / CONFIRM ─────────────────────────────────────────────────────────

export function SummaryBlock({ s }: { s: Summary }) {
  const { c } = useCopy(guidedCopy);
  return (
    <div data-testid="summary" className="flex flex-col gap-4 text-sm">
      <section>
        <h2 className="mb-1 font-semibold">{c.sum_will_do}</h2>
        <ul className="flex list-disc flex-col gap-1 pl-5" data-testid="summary-will-do">{s.will_do.map((x) => <li key={x}>{x}</li>)}</ul>
      </section>
      <section>
        <h2 className="mb-1 font-semibold">{c.sum_never}</h2>
        <ul className="flex list-disc flex-col gap-1 pl-5" data-testid="summary-never">{s.will_never_do.map((x) => <li key={x}>{x}</li>)}</ul>
      </section>
      {s.not_yet.length ? (
        <section className="rounded-md border border-accent-gold/40 bg-accent-gold/5 p-3">
          <h2 className="mb-1 font-semibold">{c.sum_not_yet}</h2>
          <ul className="flex list-disc flex-col gap-1 pl-5" data-testid="summary-not-yet">{s.not_yet.map((x) => <li key={x}>{x}</li>)}</ul>
        </section>
      ) : null}
      <section>
        <h2 className="mb-1 font-semibold">{c.sum_numbers}</h2>
        <dl className="flex flex-col gap-1" data-testid="summary-numbers">
          {s.numbers.map((n) => (
            <div key={n.label} className="flex flex-col">
              <div className="flex justify-between gap-2"><dt>{n.label}</dt><dd className="font-semibold">{inr(n.value)}</dd></div>
              {/* walk finding: the summary read ~510 words; "where from" is one tap away, not always on */}
              <details className="text-sm text-muted-foreground">
                <summary className="min-h-11 cursor-pointer py-2">{c.sum_where_from}</summary>
                {n.basis}
              </details>
            </div>
          ))}
        </dl>
      </section>
      <p className="text-sm text-muted-foreground">
        {c.sum_disclaimer}
      </p>
    </div>
  );
}

export function ConfirmScreen({ screen, ack, onAck, compact = false }: {
  screen: Screen; ack: boolean; onAck: (v: boolean) => void;
  /** the summary is shown right above on this same screen (signup cut 2) — do not repeat it */
  compact?: boolean;
}) {
  const s = screen.summary;
  const { c } = useCopy(guidedCopy);
  const short = useMemo(() => (s ? fill(c.confirm_short, { strategy: s.strategy, vehicle: s.vehicle, lots: s.lots }) : ""), [s, c]);
  return (
    <div data-testid="screen-CONFIRM" className="flex flex-col gap-3 text-sm">
      {compact ? null : <p className="rounded-md border border-border p-3" data-testid="confirm-short">{short}</p>}
      {!compact && s && s.not_yet.length ? <p className="text-muted-foreground">{fill(c.confirm_remember, { line: s.not_yet[0] })}</p> : null}
      <label className="flex min-h-11 items-start gap-2">
        <input type="checkbox" data-testid="confirm-ack" className="mt-1 h-5 w-5" checked={ack} onChange={(e) => onAck(e.target.checked)} />
        <span>{c.confirm_ack}</span>
      </label>
    </div>
  );
}

export function useSignupValue(): [SignupValue, (v: SignupValue) => void] {
  return useState<SignupValue>({ full_name: "", email: "", password: "", risk_ack: false });
}
