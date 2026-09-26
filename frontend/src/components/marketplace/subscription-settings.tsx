"use client";

/**
 * Per-subscription sizing + execution-mode controls.
 *
 * ONE SCREEN, ONE DECISION (founder, 26 Sep 2026, after walking the live site — REQUIREMENTS §13):
 *   1. one line per vehicle (needs · risk label · worst real day, each with its basis);
 *      every other honest word stays, collapsed behind "Aur jaano";
 *   2. the four choices are four STEPS — Kis cheez me → Kitna size → Kis taraf → Signal par
 *      kya ho — and only the current step is on screen; Back never loses a choice;
 *   3. "Settings save karo" is the ONE primary button, sticky at the bottom, above the
 *      phone's own bottom bar (the shell sets --bottom-chrome), at least 44px tall;
 *   4. when the SAVED mode is paper, a banner pinned at the top says his words exactly:
 *      "Practice mode: nakli order, asli paisa nahi lagta" — read from the server's
 *      is_paper, never assumed (a failed read shows no banner, only the red line);
 *   5. nothing wider than the phone: min-w-0 on every row, long words wrap.
 * The safe defaults are already chosen: FUTURES (the strategy's own contract), the
 * smallest size 2, both directions (the fan-out's 'all'), the saved mode.
 *
 * Validation is client-side (even / min-2) AND server-side. The backend persists these
 * only after the fan-out (M4) merge — until then it returns ``applied: false`` and we
 * render a paper-only PREVIEW (honest copy: nothing trades for real yet).
 *
 * Pure access/config UI — no trading code, no broker calls.
 */

import { useEffect, useRef, useState } from "react";
import { ChevronLeft, ChevronRight, Loader2, Minus, Plus, Save, ShieldAlert } from "lucide-react";
import { Button } from "@/shared/ui/button";
import { Input } from "@/shared/ui/input";
import { Tabs, TabsList, TabsTrigger } from "@/shared/ui/tabs";
import { api, ApiError } from "@/shared/api/client";
import { cn } from "@/shared/lib/utils";
import { SINGLE_SIDE_NOTE } from "@/lib/direction-record";
import {
  DIRECTION_FILTERS,
  DIRECTION_LABELS,
  type DirectionFilter,
  VEHICLE_ALLOWED_DIRECTIONS,
  EXECUTION_MODE_HELP,
  EXECUTION_MODE_LABELS,
  EXECUTION_MODES,
  type ExecutionMode,
  LOTS_MAX,
  LOTS_MIN,
  LOTS_STEP,
  type SubscriptionSettings,
  type Vehicle,
  VEHICLE_LABELS,
  VEHICLES,
  validateLotsOverride,
} from "@/lib/billing/subscription-settings";
import { RiskLegend } from "@/components/risk/risk-chip";
import { VehiclePicker } from "@/components/marketplace/vehicle-picker";
import { customerVehiclesEnabled } from "@/lib/customer-vehicles";
import { CROSS_SEGMENT_METRICS_WARNING } from "@/lib/risk-labels";
import { toast } from "sonner";

interface Props {
  subscriptionId: string;
  /** Historical max drawdown % for the risk note, when known. */
  maxDrawdownPct?: number | null;
}

/** His exact words (26 Sep 2026, point 4). One source: the banner and its test read this. */
export const PRACTICE_BANNER = "Practice mode: nakli order, asli paisa nahi lagta";

/** The four steps, in his order of decisions. `short` names the step on the "Agla" button. */
export const SETTINGS_STEPS = [
  { key: "vehicle", title: "Kis cheez me chalana hai", short: "Kis cheez me" },
  { key: "size", title: "Har signal par kitna size", short: "Kitna size" },
  { key: "direction", title: "Kis taraf ke trade", short: "Kis taraf" },
  { key: "mode", title: "Signal aane par kya ho", short: "Signal par kya ho" },
] as const;

export function SubscriptionSettings({ subscriptionId, maxDrawdownPct }: Props) {
  const [settings, setSettings] = useState<SubscriptionSettings | null>(null);
  // Safe default already chosen (founder's point 4 of the 10): the smallest size, 2.
  // Overwritten by the saved value when the GET answers.
  const [lots, setLots] = useState<string>(String(LOTS_MIN));
  // MANUAL by default — matches the backend's new-subscription default
  // (execution_mode 'offline' since migration 040). Overwritten by the GET
  // below when settings load; this fallback governs only the GET-failure case.
  const [mode, setMode] = useState<ExecutionMode>("offline");
  const [isPaper, setIsPaper] = useState(true);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  // A FAILED read is said out loud (founder's rule, 26 Sep, points 8 + 10): the form
  // below then shows DEFAULTS, and those must never pass for the customer's saved values.
  const [loadFailed, setLoadFailed] = useState(false);
  const [reloadKey, setReloadKey] = useState(0);
  // ONE decision on screen at a time. The choices live up here, so moving between
  // steps (Back included) never loses one.
  const [step, setStep] = useState(0);
  const stepHeading = useRef<HTMLHeadingElement | null>(null);
  const movedByUser = useRef(false);

  // DIRECTION is now REAL: the PATCH persists it and the fan-out entry gate
  // enforces it (_direction_allows). Exits are never filtered, so narrowing it
  // can never strand an open position. Its SAVED value is loaded below (it was
  // not, before 26 Sep: a saved "short" showed as "Dono" and Save overwrote it).
  const [direction, setDirection] = useState<DirectionFilter>("all");
  // VEHICLE stays DISABLED. The platform cannot honestly execute a futures
  // signal as cash or options — wrong price basis, no share sizing, cash cannot
  // be shorted, and every certified number we publish is futures-basis. It is a
  // FACT derived from the strategy, never a customer choice.
  const [vehicle] = useState<Vehicle>("futures");

  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        const s = await api.get<SubscriptionSettings>(
          `/marketplace/subscriptions/${subscriptionId}/settings`,
        );
        if (!alive) return;
        setSettings(s);
        setLots(s.lots_override != null ? String(s.lots_override) : String(LOTS_MIN));
        setMode(s.execution_mode);
        setIsPaper(s.is_paper);
        setDirection(s.direction_filter ?? "all");
        setLoadFailed(false);
      } catch {
        // Defaults stay in the form — and the banner below says so.
        if (alive) setLoadFailed(true);
      } finally {
        if (alive) setLoading(false);
      }
    })();
    return () => {
      alive = false;
    };
  }, [subscriptionId, reloadKey]);

  // A step change moves the reader to the new step's title (keyboard + screen reader).
  useEffect(() => {
    if (movedByUser.current) stepHeading.current?.focus();
  }, [step]);

  const lotsNum = lots.trim() === "" ? null : Number(lots);
  const lotsError = validateLotsOverride(lotsNum);

  // Even-qty stepper: blank → first press lands on the minimum; otherwise
  // step by 2 and clamp to [MIN, MAX]. Reuses the same even/2-20 rule the
  // input validates against.
  function stepLots(delta: number) {
    const next =
      lotsNum == null
        ? LOTS_MIN
        : Math.min(LOTS_MAX, Math.max(LOTS_MIN, lotsNum + delta));
    setLots(String(next));
  }
  const decDisabled = lotsNum != null && lotsNum <= LOTS_MIN;
  const incDisabled = lotsNum != null && lotsNum >= LOTS_MAX;


  function goTo(i: number) {
    movedByUser.current = true;
    setStep(Math.max(0, Math.min(SETTINGS_STEPS.length - 1, i)));
  }

  async function save() {
    if (lotsError) return;
    setSaving(true);
    try {
      const res = await api.patch<SubscriptionSettings>(
        `/marketplace/subscriptions/${subscriptionId}/settings`,
        // direction_filter IS sent (Both === 'all'). Vehicle is NOT and never
        // will be from here: it is DERIVED from the strategy's
        // instrument_type, a fact about the strategy rather than a choice.
        {
          lots_override: lotsNum,
          execution_mode: mode,
          is_paper: isPaper,
          direction_filter: direction,
        },
      );
      setSettings(res);
      if (res.applied) {
        toast.success("Settings save ho gayi.");
      } else {
        toast.info(
          "Preview ke roop mein save hua — yeh settings tab lagengi jab live trading chalu hogi.",
        );
      }
    } catch (err) {
      const msg = err instanceof ApiError ? err.detail : "Settings save nahi ho payi";
      toast.error(msg);
    } finally {
      setSaving(false);
    }
  }

  if (loading) {
    return (
      <p className="text-sm text-muted-foreground flex items-center gap-1.5">
        <Loader2 className="h-3 w-3 animate-spin" /> Aapki settings khol rahe hain…
      </p>
    );
  }

  const preview = settings?.applied === false;
  // The ONE source for the mode shown in the banner: what the server says is saved.
  const savedPaper = settings?.is_paper === true;
  const current = SETTINGS_STEPS[step];
  const next = SETTINGS_STEPS[step + 1];

  return (
    <div className="min-w-0 space-y-3 pt-1" data-testid="subscription-settings">
      {savedPaper ? (
        <div
          role="status"
          data-testid="practice-banner"
          className="sticky top-[var(--top-chrome,0px)] z-20 rounded-md border border-profit/40 bg-surface-deep/95 px-3 py-2 text-sm font-medium text-foreground backdrop-blur wrap-break-word"
        >
          {PRACTICE_BANNER}
        </div>
      ) : null}
      {loadFailed ? (
        <div role="alert" data-testid="settings-load-failed" className="rounded-md border border-loss/40 bg-loss/5 px-3 py-2 text-sm wrap-break-word">
          Aapki saved settings abhi load nahi huin. Neeche jo dikh raha hai woh <strong>default</strong> hai — aapki saved
          settings nahi. Save dabane se pehle{" "}
          <button type="button" className="inline-flex min-h-11 items-center underline" onClick={() => { setLoading(true); setReloadKey((k) => k + 1); }}>
            dobara load karo
          </button>
          .
        </div>
      ) : null}
      {preview ? (
        <p className="wrap-break-word text-xs text-foreground/70 leading-relaxed">
          Preview — yeh settings tab lagengi jab live trading chalu hogi. Abhi sab
          kuch <strong>seekhne wala mode</strong> mein chalta hai (asli order nahi).
        </p>
      ) : null}

      {/* Where the customer is: "Kadam 2 / 4 · Kitna size". Text, not a second row of buttons. */}
      <p data-testid="settings-step-count" className="text-xs text-muted-foreground">
        Kadam {step + 1} / {SETTINGS_STEPS.length}
      </p>
      <h3
        ref={stepHeading}
        tabIndex={-1}
        data-testid="settings-step-title"
        className="min-w-0 wrap-break-word text-base font-semibold text-foreground outline-none"
      >
        {current.title}
      </h3>

      {/* ── STEP 1 · Kis cheez me ─────────────────────────────────────────── */}
      <section data-testid="settings-step-vehicle" hidden={step !== 0} className="min-w-0 space-y-2">
        {/* CUST-1 (founder, 2026-09-24): the vehicle picker, now ONE LINE per vehicle
            (26 Sep). Behind NEXT_PUBLIC_CUSTOMER_VEHICLES; with the flag unset the
            old disabled control below is what shows, collapsed the same way. */}
        {customerVehiclesEnabled() ? (
          <VehiclePicker compact lots={lotsNum ?? LOTS_MIN} className="block" />
        ) : (
          <>
            <p data-testid="vehicle-one-line" className="min-w-0 wrap-break-word rounded-lg border border-profit/40 bg-profit/10 px-3 py-2.5 text-sm text-foreground">
              Futures — yeh strategy isi me chalti hai (abhi seekhne wale mode me). Cash aur Options abhi band hain.
            </p>
            <details data-testid="vehicle-more" className="min-w-0 rounded-lg border border-white/[0.06] px-3">
              <summary className="min-h-tap cursor-pointer py-2.5 text-sm font-medium text-foreground/90">
                Aur jaano
              </summary>
              {/* Vehicle — DISABLED + "Abhi band" (founder decision), kept word for word.
                  Vehicle does NOT persist and is not enforced — its real value is the
                  strategy's instrument_type once the backend exposes it. A disabled
                  control is honest; an enabled one that silently does nothing is a lie. */}
              <div className="min-w-0 space-y-1 pb-3 opacity-60">
                <span className="text-xs font-medium text-foreground/90 flex items-center gap-1.5">
                  Kis cheez me (vehicle)
                  <span
                    data-testid="vehicle-coming-soon"
                    className="text-xs uppercase tracking-wide px-1.5 py-0.5 rounded bg-muted text-muted-foreground border border-border"
                  >
                    Abhi band
                  </span>
                </span>
                <Tabs value={vehicle}>
                  <TabsList className="w-full">
                    {VEHICLES.map((v) => (
                      <TabsTrigger key={v} value={v} data-testid={`vehicle-${v}`} disabled>
                        {VEHICLE_LABELS[v]}
                      </TabsTrigger>
                    ))}
                  </TabsList>
                </Tabs>
                <span className="text-xs text-muted-foreground block">
                  Strategy ke instrument se aayega. Abhi ye set nahi hota — isliye
                  disabled hai.
                </span>
              </div>
              {/* EDUCATIONAL legend — all three segments together. NOT a rating of
                  this strategy: the API doesn't expose instrument_type, so a single
                  chip here would claim a segment we cannot verify. */}
              <RiskLegend activeSegment={vehicle} className="mb-3" />
              {/* Cross-segment honesty: every certified number we publish is
                  futures-priced, so selecting Cash/Options shows this warning and
                  NO segment-specific metric is rendered anywhere for it. */}
              {vehicle !== "futures" ? (
                <p
                  data-testid="cross-segment-metrics-warning"
                  className="text-xs text-amber-300/80 leading-relaxed block mb-3"
                >
                  {CROSS_SEGMENT_METRICS_WARNING}
                </p>
              ) : null}
            </details>
          </>
        )}
      </section>

      {/* ── STEP 2 · Kitna size ───────────────────────────────────────────── */}
      <section data-testid="settings-step-size" hidden={step !== 1} className="min-w-0 space-y-2">
        <label className="space-y-1 block min-w-0">
          <span className="block min-w-0 wrap-break-word text-sm text-foreground/90">
            Har signal par kitne lot (packet) — 2 se 20, jodi me. Pehle se 2 chuna hai, sabse chhota.
          </span>
          <div className="flex items-center gap-1.5">
            <Button
              type="button"
              variant="outline"
              size="icon-sm"
              onClick={() => stepLots(-LOTS_STEP)}
              disabled={decDisabled}
              aria-label="2 kam karo"
              data-testid="lots-dec"
            >
              <Minus className="h-3.5 w-3.5" />
            </Button>
            <Input
              type="number"
              inputMode="numeric"
              min={2}
              max={20}
              step={2}
              value={lots}
              onChange={(e) => setLots(e.target.value)}
              aria-invalid={lotsError != null}
              aria-label="Har signal par kitna size (lot)"
              placeholder="default"
              className="w-16 min-h-tap text-center"
              data-testid="lots-override-input"
            />
            <Button
              type="button"
              variant="outline"
              size="icon-sm"
              onClick={() => stepLots(LOTS_STEP)}
              disabled={incDisabled}
              aria-label="2 badhao"
              data-testid="lots-inc"
            >
              <Plus className="h-3.5 w-3.5" />
            </Button>
          </div>
          <span className="text-xs text-muted-foreground block">
            Save hua:{" "}
            {settings?.lots_override != null
              ? `${settings.lots_override} lot (packet)`
              : loadFailed
                ? "load nahi hua"
                : "strategy ka apna size"}
          </span>
          {lotsError ? (
            <span className="text-xs text-loss block" data-testid="lots-error">
              {lotsError}
            </span>
          ) : null}
        </label>
        <details data-testid="size-more" className="min-w-0 rounded-lg border border-white/[0.06] px-3">
          <summary className="min-h-tap cursor-pointer py-2.5 text-sm font-medium text-foreground/90">
            Aur jaano
          </summary>
          <div className="min-w-0 space-y-2 pb-3">
            <p className="wrap-break-word text-xs text-muted-foreground leading-relaxed">
              Lot (packet) = exchange ka tay kiya hua packet. Box khaali chhodo to strategy ka apna size lagega.
            </p>
            {/* Risk note — honest, never a guaranteed return */}
            <div className="flex items-start gap-2 rounded-md bg-white/[0.02] border border-white/[0.05] px-3 py-2">
              <ShieldAlert className="h-3.5 w-3.5 text-amber-300/80 mt-0.5 shrink-0" />
              <p className="min-w-0 wrap-break-word text-xs text-muted-foreground leading-relaxed">
                {typeof maxDrawdownPct === "number" ? (
                  <>
                    Purane data par test me sabse bada gir (max drawdown) ~
                    <span className="text-loss">{Math.abs(maxDrawdownPct).toFixed(1)}%</span> tha — naapa hua, guarantee nahi.
                    Bada size = bade utaar-chadhaav.{" "}
                  </>
                ) : (
                  <>Trading me nuksaan ka risk hai — size dheere dheere badhao. </>
                )}
                Purana result aage ki guarantee nahi.
              </p>
            </div>
          </div>
        </details>
      </section>

      {/* ── STEP 3 · Kis taraf ────────────────────────────────────────────────
          Direction — REAL. Persisted by the settings PATCH and enforced at
          the fan-out entry gate. Cash is long-only (VEHICLE_ALLOWED_DIRECTIONS),
          so Short/Both are unavailable for a Cash strategy.

          ⚠️ NO PERFORMANCE NUMBERS SIT BESIDE THIS CONTROL, deliberately. The
          published record is the long+short system; the long-only and
          short-only slices in the artifact are explicitly NOT an
          independently-validated standalone strategy, because those trades
          were taken inside a system that was also trading the other side.
          See lib/direction-record.ts.
          On a 375px phone the three choices sit one under the other, full width,
          so "Sirf kharid (long)" is never cut. */}
      <section data-testid="settings-step-direction" hidden={step !== 2} className="min-w-0 space-y-2">
        <Tabs orientation="vertical" value={direction} onValueChange={(v) => setDirection(v as DirectionFilter)}>
          <TabsList className="flex h-auto w-full flex-col items-stretch gap-1.5 bg-transparent p-0">
            {DIRECTION_FILTERS.map((d) => {
              const allowed = VEHICLE_ALLOWED_DIRECTIONS[vehicle].includes(d);
              return (
                <TabsTrigger
                  key={d}
                  value={d}
                  disabled={!allowed}
                  data-testid={`direction-${d}`}
                  className="h-auto min-h-tap w-full justify-start whitespace-normal rounded-lg border border-white/[0.08] px-3 py-2 text-left text-sm data-active:border-profit/60 data-active:bg-profit/10"
                >
                  {DIRECTION_LABELS[d]}
                </TabsTrigger>
              );
            })}
          </TabsList>
        </Tabs>
        <details data-testid="direction-more" className="min-w-0 rounded-lg border border-white/[0.06] px-3">
          <summary className="min-h-tap cursor-pointer py-2.5 text-sm font-medium text-foreground/90">
            Aur jaano
          </summary>
          <p
            className="wrap-break-word pb-3 text-xs text-muted-foreground leading-relaxed"
            data-testid="direction-record-note"
          >
            {SINGLE_SIDE_NOTE}
          </p>
        </details>
      </section>

      {/* ── STEP 4 · Signal aane par kya ho ─────────────────────────────────
          A list, not a dropdown: a closed dropdown cuts these long choices on a phone. */}
      <section data-testid="settings-step-mode" hidden={step !== 3} className="min-w-0 space-y-2">
        <div role="radiogroup" aria-label="Signal aane par kya ho" data-testid="execution-mode-select" className="space-y-1.5">
          {EXECUTION_MODES.map((m) => (
            <button
              key={m}
              type="button"
              role="radio"
              aria-checked={mode === m}
              data-testid={`execution-mode-${m}`}
              onClick={() => setMode(m)}
              className={cn(
                "w-full min-w-0 min-h-tap rounded-lg border px-3 py-2 text-left text-sm wrap-break-word",
                mode === m ? "border-profit/60 bg-profit/10 text-foreground" : "border-white/[0.08] text-foreground/80",
              )}
            >
              {EXECUTION_MODE_LABELS[m]}
            </button>
          ))}
        </div>
        {/* Paper toggle — the customer's own draft; the banner above shows what is SAVED. */}
        <label className="flex min-h-tap min-w-0 items-center gap-2 cursor-pointer">
          <input
            type="checkbox"
            checked={isPaper}
            onChange={(e) => setIsPaper(e.target.checked)}
            className="h-5 w-5 shrink-0 accent-accent-blue"
            data-testid="is-paper-toggle"
          />
          <span className="min-w-0 wrap-break-word text-sm text-foreground/90">
            Seekhne wala mode (paper trading) — nakli order, asli paisa nahi
          </span>
        </label>
        <details data-testid="mode-more" className="min-w-0 rounded-lg border border-white/[0.06] px-3">
          <summary className="min-h-tap cursor-pointer py-2.5 text-sm font-medium text-foreground/90">
            Aur jaano
          </summary>
          <p className="wrap-break-word pb-3 text-xs text-muted-foreground leading-relaxed">{EXECUTION_MODE_HELP}</p>
        </details>
      </section>

      {/* Moving between steps: quiet buttons, never the primary. Back keeps every choice. */}
      <div data-testid="settings-step-nav" className="flex min-w-0 gap-2">
        {step > 0 ? (
          <Button type="button" variant="outline" className="h-auto min-h-tap min-w-0 flex-1 whitespace-normal py-2" onClick={() => goTo(step - 1)} data-testid="settings-back">
            <ChevronLeft className="h-4 w-4 shrink-0" /> Pichhla kadam (kuch nahi mitega)
          </Button>
        ) : null}
        {next ? (
          <Button type="button" variant="outline" className="h-auto min-h-tap min-w-0 flex-1 whitespace-normal py-2" onClick={() => goTo(step + 1)} data-testid="settings-next">
            Agla: {next.short} <ChevronRight className="h-4 w-4 shrink-0" />
          </Button>
        ) : null}
      </div>

      {/* THE one primary action, always on screen: sticky above the phone's bottom bar,
          in the flow (so it never covers the last line — it is the last line). */}
      <div
        data-testid="settings-save-bar"
        className="sticky bottom-[var(--bottom-chrome,0px)] z-20 -mx-1 border-t border-white/[0.06] bg-surface-deep/95 px-1 pt-2 pb-[max(0.5rem,env(safe-area-inset-bottom))] backdrop-blur"
      >
        <Button
          onClick={save}
          disabled={saving || lotsError != null}
          type="button"
          data-testid="save-settings"
          className="min-h-12 w-full text-base"
        >
          {saving ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <Save className="h-4 w-4" />
          )}
          Settings save karo
        </Button>
      </div>
    </div>
  );
}
