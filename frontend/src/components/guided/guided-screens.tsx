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
import {
  PASSWORD_RULES,
  inr,
  type Option,
  type Screen,
  type StrategyOption,
  type Summary,
} from "@/lib/guided-path";

export function ScreenHeader({ screen }: { screen: Screen }) {
  return (
    <header className="flex flex-col gap-1">
      <h1 data-testid="guided-title" className="text-xl font-semibold leading-snug">{screen.title}</h1>
      <p data-testid="guided-decision" className="text-base text-foreground">{screen.decision}</p>
      <p data-testid="guided-why" className="text-sm text-muted-foreground">
        <span className="font-medium">Kyun zaroori: </span>{screen.why}
      </p>
    </header>
  );
}

// ── SIGNUP ────────────────────────────────────────────────────────────────────

export interface SignupValue { full_name: string; email: string; password: string; risk_ack: boolean }

export function SignupScreen({ value, onChange }: { value: SignupValue; onChange: (v: SignupValue) => void }) {
  const set = (k: keyof SignupValue, v: string | boolean) => onChange({ ...value, [k]: v });
  return (
    <div data-testid="screen-SIGNUP" className="flex flex-col gap-3">
      <label className="flex flex-col gap-1 text-sm">Aapka naam
        <input className="min-h-11 rounded-md border border-border bg-background px-3" autoComplete="name"
          value={value.full_name} onChange={(e) => set("full_name", e.target.value)} />
      </label>
      <label className="flex flex-col gap-1 text-sm">Email
        <input className="min-h-11 rounded-md border border-border bg-background px-3" type="email" autoComplete="email" inputMode="email"
          value={value.email} onChange={(e) => set("email", e.target.value)} />
      </label>
      <label className="flex flex-col gap-1 text-sm">Password
        <input className="min-h-11 rounded-md border border-border bg-background px-3" type="password" autoComplete="new-password"
          value={value.password} onChange={(e) => set("password", e.target.value)} />
      </label>
      <ul data-testid="signup-rules" className="grid grid-cols-1 gap-1 text-sm sm:grid-cols-2">
        {PASSWORD_RULES.map((r) => {
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
        <span>Main samajhta hu: trading me nuksaan ho sakta hai; purana record aage ki guarantee nahi hai.</span>
      </label>
    </div>
  );
}

export function signupReady(v: SignupValue): boolean {
  return v.full_name.trim().length > 0 && /.+@.+\..+/.test(v.email) && v.risk_ack &&
    PASSWORD_RULES.every((r) => r.ok(v.password, { email: v.email, name: v.full_name }));
}

// ── BROKER ────────────────────────────────────────────────────────────────────

export interface BrokerValue { client_id: string; access_token: string }

export function BrokerScreen({ screen, value, onChange }: { screen: Screen; value: BrokerValue; onChange: (v: BrokerValue) => void }) {
  return (
    <div data-testid="screen-BROKER" className="flex flex-col gap-3">
      {screen.broker_state === "EXPIRED" ? (
        <p data-testid="broker-expired" className="rounded-md bg-accent-gold/10 p-3 text-sm">
          Aapki Dhan ki chabi (token) purani ho gayi hai. Nayi chabi daalo — baaki sab settings save hain.
        </p>
      ) : null}
      <p className="text-sm text-muted-foreground"><span className="font-medium text-foreground">Kahan milega: </span>{screen.where_to_find}</p>
      <label className="flex flex-col gap-1 text-sm">Dhan Client ID
        <input className="min-h-11 rounded-md border border-border bg-background px-3" inputMode="numeric" autoComplete="off"
          value={value.client_id} onChange={(e) => onChange({ ...value, client_id: e.target.value })} />
      </label>
      <label className="flex flex-col gap-1 text-sm">Dhan ki chabi (access token) — Dhan ki website se copy karke yahan chipkao
        <textarea className="min-h-20 rounded-md border border-border bg-background p-3 text-sm" autoComplete="off" spellCheck={false}
          value={value.access_token} onChange={(e) => onChange({ ...value, access_token: e.target.value })} />
      </label>
      <p className="flex items-start gap-2 text-sm text-muted-foreground">
        <ShieldCheck className="h-4 w-4 shrink-0" aria-hidden />
        Chabi (token) sirf is box me daalo — chat, WhatsApp ya email me kabhi nahi. Hum ise tala-band (encrypted) rakhte hain.
      </p>
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
  if (!opts.length) {
    return <p data-testid="screen-STRATEGY-empty" className="text-sm text-muted-foreground">{screen.empty_line}</p>;
  }
  return (
    <div data-testid="screen-STRATEGY">
      <ChoiceList testid="strategy" selected={value ?? screen.selected}
        options={opts.map((o) => ({ key: o.id, label: o.title, open: true,
          sub: o.price_inr && Number(o.price_inr) > 0 ? `Plan: ${inr(Number(o.price_inr))}/mahina` : "Abhi koi fees nahi" }))}
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
  const choices = screen.lot_choices ?? [2];
  // ONE SOURCE: the server computed every choice's numbers; this screen only looks them up.
  const row = screen.by_lots?.[String(value.lots)];
  const cap = row ?? (value.lots === screen.lots ? screen.capital : undefined);
  const shares = row?.shares ?? null;
  const dflt = row ? row.max_daily_loss_default : screen.max_daily_loss_default ?? null;
  return (
    <div data-testid="screen-SIZE" className="flex flex-col gap-4">
      <div className="flex flex-col gap-2">
        <span className="text-sm font-medium">Kitna bada sauda (lot)</span>
        <div className="flex items-center gap-3">
          <button type="button" aria-label="Kam karo" disabled={value.lots <= choices[0]}
            onClick={() => onChange({ ...value, lots: Math.max(choices[0], value.lots - 2) })}
            className="min-h-12 min-w-12 rounded-md border border-border text-lg">−</button>
          <span data-testid="size-lots" className="min-w-24 text-center text-lg font-semibold">{value.lots} lot</span>
          <button type="button" aria-label="Badhao" disabled={value.lots >= choices[choices.length - 1]}
            onClick={() => onChange({ ...value, lots: Math.min(choices[choices.length - 1], value.lots + 2) })}
            className="min-h-12 min-w-12 rounded-md border border-border text-lg">+</button>
        </div>
        <span className="text-sm text-muted-foreground">
          {shares ? `${new Intl.NumberFormat("en-IN").format(shares)} shares (${value.lots} lot). ` : ""}Hamesha 2, 4, 6… kyunki strategy aadha hissa pehle bechti hai. Sabse chhota 2.
        </span>
      </div>
      <dl data-testid="size-numbers" className="grid grid-cols-1 gap-2 rounded-md border border-border p-3 text-sm">
        {/* EVERY NUMBER EXPLAINED IN ONE LINE beside it, with WHOSE number it is
            (founder's rule, 26 Sep, point 6) — the server sends a plain basis for each. */}
        <div className="flex justify-between gap-2"><dt>Kam se kam paisa chahiye</dt><dd className="font-semibold">{inr(cap?.minimum_capital)}</dd></div>
        <p data-testid="basis-minimum" className="text-sm text-muted-foreground">
          {cap?.plain?.minimum_capital ?? "NOT MEASURED"} — yeh niyam hamara hai (hamari salah); Dhan ka margin naapa hua.
        </p>
        <div className="flex justify-between gap-2"><dt>Record ka sabse bura din</dt><dd className="font-semibold text-loss">{inr(cap?.worst_day)}</dd></div>
        <p data-testid="basis-worst-day" className="text-sm text-muted-foreground">
          {cap?.plain?.worst_day ?? "NOT MEASURED"} — naapa hua, strategy ke apne record se.
        </p>
        <div className="flex justify-between gap-2"><dt>Sabse badi girawat</dt><dd className="font-semibold text-loss">{inr(cap?.max_drawdown)}</dd></div>
        <p data-testid="basis-drawdown" className="text-sm text-muted-foreground">
          {cap?.plain?.max_drawdown ?? "NOT MEASURED"} — naapa hua, strategy ke apne record se.
        </p>
        <p className="text-sm text-muted-foreground">
          Record aage ki guarantee nahi hai.
          {cap?.margin_stale ? ` Dhan ke rok (margin) ka number ${cap.margin_as_of_human ?? "NOT MEASURED"} ko naapa tha — aaj thoda alag ho sakta hai.` : ""}
        </p>
      </dl>
      <label className="flex flex-col gap-1 text-sm">
        Ek din me zyada se zyada nuksaan (Rs)
        <input data-testid="size-loss" className="min-h-11 rounded-md border border-border bg-background px-3" inputMode="numeric"
          placeholder={typeof dflt === "number" ? `Khaali chhodo = ${inr(dflt)} (record ka sabse bura din)` : "Rs me likho"}
          value={value.max_daily_loss_inr} onChange={(e) => onChange({ ...value, max_daily_loss_inr: e.target.value.replace(/[^\d]/g, "") })} />
        <span className="text-sm text-muted-foreground">Khaali chhodna safe default hai.</span>
      </label>
    </div>
  );
}

// ── SUMMARY / CONFIRM ─────────────────────────────────────────────────────────

export function SummaryBlock({ s }: { s: Summary }) {
  return (
    <div data-testid="summary" className="flex flex-col gap-4 text-sm">
      <section>
        <h2 className="mb-1 font-semibold">Bot yeh karega</h2>
        <ul className="flex list-disc flex-col gap-1 pl-5" data-testid="summary-will-do">{s.will_do.map((x) => <li key={x}>{x}</li>)}</ul>
      </section>
      <section>
        <h2 className="mb-1 font-semibold">Bot yeh KABHI nahi karega</h2>
        <ul className="flex list-disc flex-col gap-1 pl-5" data-testid="summary-never">{s.will_never_do.map((x) => <li key={x}>{x}</li>)}</ul>
      </section>
      {s.not_yet.length ? (
        <section className="rounded-md border border-accent-gold/40 bg-accent-gold/5 p-3">
          <h2 className="mb-1 font-semibold">Abhi yeh bana NAHI hai (sach)</h2>
          <ul className="flex list-disc flex-col gap-1 pl-5" data-testid="summary-not-yet">{s.not_yet.map((x) => <li key={x}>{x}</li>)}</ul>
        </section>
      ) : null}
      <section>
        <h2 className="mb-1 font-semibold">Number (sab record se)</h2>
        <dl className="flex flex-col gap-1" data-testid="summary-numbers">
          {s.numbers.map((n) => (
            <div key={n.label} className="flex flex-col">
              <div className="flex justify-between gap-2"><dt>{n.label}</dt><dd className="font-semibold">{inr(n.value)}</dd></div>
              {/* walk finding: the summary read ~510 words; "where from" is one tap away, not always on */}
              <details className="text-sm text-muted-foreground">
                <summary className="min-h-11 cursor-pointer py-2">kahan se?</summary>
                {n.basis}
              </details>
            </div>
          ))}
        </dl>
      </section>
      <p className="text-sm text-muted-foreground">
        TRADETRI strategy automation tools deta hai. Hum koi guaranteed return nahi dete. Trading me risk hai; purana record aage ki guarantee nahi hai.
      </p>
    </div>
  );
}

export function ConfirmScreen({ screen, ack, onAck }: { screen: Screen; ack: boolean; onAck: (v: boolean) => void }) {
  const s = screen.summary;
  const short = useMemo(() => (s ? `${s.strategy} · ${s.vehicle} · ${s.lots} lot (packet)` : ""), [s]);
  return (
    <div data-testid="screen-CONFIRM" className="flex flex-col gap-3 text-sm">
      <p className="rounded-md border border-border p-3" data-testid="confirm-short">{short}</p>
      {s && s.not_yet.length ? <p className="text-muted-foreground">Yaad rahe: {s.not_yet[0]}</p> : null}
      <label className="flex min-h-11 items-start gap-2">
        <input type="checkbox" data-testid="confirm-ack" className="mt-1 h-5 w-5" checked={ack} onChange={(e) => onAck(e.target.checked)} />
        <span>Maine summary padh li. Bot kya karega aur kya nahi — samajh gaya.</span>
      </label>
    </div>
  );
}

export function useSignupValue(): [SignupValue, (v: SignupValue) => void] {
  return useState<SignupValue>({ full_name: "", email: "", password: "", risk_ack: false });
}
