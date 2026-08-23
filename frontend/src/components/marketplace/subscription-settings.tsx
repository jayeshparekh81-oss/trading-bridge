"use client";

/**
 * Per-subscription sizing + execution-mode controls.
 *
 * Lets a subscriber set an even-lots override (2-20), an execution mode, and the
 * paper toggle. Validation is client-side (even / min-2) AND server-side. The
 * backend persists these only after the fan-out (M4) merge — until then it
 * returns ``applied: false`` and we render a paper-only PREVIEW (honest copy:
 * nothing trades for real yet).
 *
 * Pure access/config UI — no trading code, no broker calls.
 */

import { useEffect, useState } from "react";
import { Loader2, Minus, Plus, Save, ShieldAlert } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { api, ApiError } from "@/lib/api";
import {
  DIRECTION_FILTERS,
  DIRECTION_LABELS,
  type DirectionFilter,
  EXECUTION_MODE_HELP,
  EXECUTION_MODE_LABELS,
  EXECUTION_MODES,
  type ExecutionMode,
  LOTS_MAX,
  LOTS_MIN,
  LOTS_STEP,
  type SubscriptionSettings,
  type Vehicle,
  VEHICLE_ALLOWED_DIRECTIONS,
  VEHICLE_LABELS,
  VEHICLES,
  validateLotsOverride,
} from "@/lib/billing/subscription-settings";
import { toast } from "sonner";

interface Props {
  subscriptionId: string;
  /** Historical max drawdown % for the risk note, when known. */
  maxDrawdownPct?: number | null;
}

export function SubscriptionSettings({ subscriptionId, maxDrawdownPct }: Props) {
  const [settings, setSettings] = useState<SubscriptionSettings | null>(null);
  const [lots, setLots] = useState<string>("");
  // MANUAL by default — matches the backend's new-subscription default
  // (execution_mode 'offline' since migration 040). Overwritten by the GET
  // below when settings load; this fallback governs only the GET-failure case.
  const [mode, setMode] = useState<ExecutionMode>("offline");
  const [isPaper, setIsPaper] = useState(true);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        const s = await api.get<SubscriptionSettings>(
          `/marketplace/subscriptions/${subscriptionId}/settings`,
        );
        if (!alive) return;
        setSettings(s);
        setLots(s.lots_override != null ? String(s.lots_override) : "");
        setMode(s.execution_mode);
        setIsPaper(s.is_paper);
      } catch {
        // Leave defaults — the form still works against the contract.
      } finally {
        if (alive) setLoading(false);
      }
    })();
    return () => {
      alive = false;
    };
  }, [subscriptionId]);

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

  // Direction + Vehicle — PREVIEW ONLY (not persisted; see save() below).
  // Vehicle is a PLACEHOLDER: its real value is the strategy's instrument_type
  // once the backend exposes it. Direction defaults to Both ('all'); vehicle
  // constrains it (Cash = long-only).
  const [direction, setDirection] = useState<DirectionFilter>("all");
  const [vehicle, setVehicle] = useState<Vehicle>("futures");
  const allowedDirections = VEHICLE_ALLOWED_DIRECTIONS[vehicle];

  function onVehicleChange(next: Vehicle) {
    setVehicle(next);
    // Keep the chosen direction valid for the new vehicle (Cash = long-only).
    if (!VEHICLE_ALLOWED_DIRECTIONS[next].includes(direction)) {
      setDirection("long");
    }
  }

  async function save() {
    if (lotsError) return;
    setSaving(true);
    try {
      const res = await api.patch<SubscriptionSettings>(
        `/marketplace/subscriptions/${subscriptionId}/settings`,
        // direction_filter + vehicle are DELIBERATELY not sent: the backend
        // SubscriptionSettingsUpdate schema is extra='forbid' and does not
        // accept them yet (sending would 422). WIRE-UP POINT: once the backend
        // adds direction_filter to the PATCH schema + persists it, add
        // `direction_filter: direction` here (Both === 'all'). Vehicle stays
        // DERIVED from the strategy's instrument_type — never sent from here.
        { lots_override: lotsNum, execution_mode: mode, is_paper: isPaper },
      );
      setSettings(res);
      if (res.applied) {
        toast.success("Settings saved.");
      } else {
        toast.info(
          "Saved as preview — sizing + execution controls activate when live trading rolls out (Phase 3).",
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
      <p className="text-[11px] text-muted-foreground flex items-center gap-1.5">
        <Loader2 className="h-3 w-3 animate-spin" /> Loading settings…
      </p>
    );
  }

  const preview = settings?.applied === false;

  return (
    <div className="space-y-3 pt-1" data-testid="subscription-settings">
      {preview ? (
        <div className="rounded-md bg-amber-400/10 border border-amber-300/30 px-3 py-2 text-[11px] text-amber-200/90 leading-relaxed">
          Preview — these controls take effect when live trading is enabled
          (Phase&nbsp;3 / empanelment). Everything runs <strong>paper</strong>{" "}
          (simulated) for now.
        </div>
      ) : null}

      <div className="grid sm:grid-cols-2 gap-3">
        {/* Lots override — even-qty stepper (LIVE: persists via the PATCH) */}
        <label className="space-y-1 block">
          <span className="text-[11px] font-medium text-foreground/90">
            Lots per signal{" "}
            <span className="text-muted-foreground font-normal">
              (even, 2-20 — blank = listing default)
            </span>
          </span>
          <div className="flex items-center gap-1.5">
            <Button
              type="button"
              variant="outline"
              size="icon-sm"
              onClick={() => stepLots(-LOTS_STEP)}
              disabled={decDisabled}
              aria-label="Decrease lots by 2"
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
              aria-label="Lots per signal"
              placeholder="—"
              className="w-16 text-center"
              data-testid="lots-override-input"
            />
            <Button
              type="button"
              variant="outline"
              size="icon-sm"
              onClick={() => stepLots(LOTS_STEP)}
              disabled={incDisabled}
              aria-label="Increase lots by 2"
              data-testid="lots-inc"
            >
              <Plus className="h-3.5 w-3.5" />
            </Button>
          </div>
          <span className="text-[10px] text-muted-foreground block">
            Saved:{" "}
            {settings?.lots_override != null
              ? `${settings.lots_override} lots`
              : "listing default"}
          </span>
          {lotsError ? (
            <span className="text-[10px] text-loss block" data-testid="lots-error">
              {lotsError}
            </span>
          ) : null}
        </label>

        {/* Execution mode */}
        <label className="space-y-1 block">
          <span className="text-[11px] font-medium text-foreground/90">
            Execution mode
          </span>
          <select
            value={mode}
            onChange={(e) => setMode(e.target.value as ExecutionMode)}
            aria-label="Execution mode"
            data-testid="execution-mode-select"
            className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-xs outline-none focus-visible:ring-2 focus-visible:ring-ring/50"
          >
            {EXECUTION_MODES.map((m) => (
              <option key={m} value={m}>
                {EXECUTION_MODE_LABELS[m]}
              </option>
            ))}
          </select>
          <span className="text-[10px] text-muted-foreground leading-relaxed block">
            {EXECUTION_MODE_HELP}
          </span>
        </label>

        {/* Vehicle — PLACEHOLDER (real value = strategy.instrument_type once the
            backend exposes it). Drives the Direction constraint below. */}
        <label className="space-y-1 block">
          <span className="text-[11px] font-medium text-foreground/90">
            Vehicle
          </span>
          <Tabs
            value={vehicle}
            onValueChange={(v) => onVehicleChange(v as Vehicle)}
          >
            <TabsList className="w-full">
              {VEHICLES.map((v) => (
                <TabsTrigger key={v} value={v} data-testid={`vehicle-${v}`}>
                  {VEHICLE_LABELS[v]}
                </TabsTrigger>
              ))}
            </TabsList>
          </Tabs>
          <span className="text-[10px] text-muted-foreground block">
            Strategy ke instrument se aayega — abhi placeholder.
          </span>
        </label>

        {/* Direction — PREVIEW ONLY (not persisted yet; see save()). Cash is
            long-only, so Short/Both are disabled for a Cash vehicle. */}
        <label className="space-y-1 block">
          <span className="text-[11px] font-medium text-foreground/90">
            Direction
          </span>
          <Tabs
            value={direction}
            onValueChange={(v) => setDirection(v as DirectionFilter)}
          >
            <TabsList className="w-full">
              {DIRECTION_FILTERS.map((d) => (
                <TabsTrigger
                  key={d}
                  value={d}
                  disabled={!allowedDirections.includes(d)}
                  data-testid={`direction-${d}`}
                >
                  {DIRECTION_LABELS[d]}
                </TabsTrigger>
              ))}
            </TabsList>
          </Tabs>
          {vehicle === "cash" ? (
            <span className="text-[10px] text-muted-foreground block">
              Cash mein short nahi ho sakta — Long-only.
            </span>
          ) : null}
          <span className="text-[10px] text-amber-300/80 block">
            Preview — abhi save nahi hota (backend wiring pending).
          </span>
        </label>
      </div>

      {/* Paper toggle */}
      <label className="flex items-center gap-2 cursor-pointer w-fit">
        <input
          type="checkbox"
          checked={isPaper}
          onChange={(e) => setIsPaper(e.target.checked)}
          className="h-4 w-4 accent-accent-blue"
          data-testid="is-paper-toggle"
        />
        <span className="text-[11px] text-foreground/90">
          Paper trading (simulated — no real orders)
        </span>
      </label>

      {/* Risk note — honest, never a guaranteed return */}
      <div className="flex items-start gap-2 rounded-md bg-white/[0.02] border border-white/[0.05] px-3 py-2">
        <ShieldAlert className="h-3.5 w-3.5 text-amber-300/80 mt-0.5 shrink-0" />
        <p className="text-[10px] text-muted-foreground leading-relaxed">
          {typeof maxDrawdownPct === "number" ? (
            <>
              Historical max drawdown ~
              <span className="text-loss">{Math.abs(maxDrawdownPct).toFixed(1)}%</span>.
              Bigger size = bigger swings.{" "}
            </>
          ) : (
            <>Trading involves risk — size up gradually. </>
          )}
          Past performance does not guarantee future results.
        </p>
      </div>

      <Button
        size="sm"
        onClick={save}
        disabled={saving || lotsError != null}
        type="button"
        data-testid="save-settings"
      >
        {saving ? (
          <Loader2 className="h-3.5 w-3.5 animate-spin" />
        ) : (
          <Save className="h-3.5 w-3.5" />
        )}
        Save settings
      </Button>
    </div>
  );
}
