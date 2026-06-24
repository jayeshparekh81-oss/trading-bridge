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
import { Loader2, Save, ShieldAlert } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { api, ApiError } from "@/lib/api";
import {
  EXECUTION_MODE_HELP,
  EXECUTION_MODE_LABELS,
  EXECUTION_MODES,
  type ExecutionMode,
  type SubscriptionSettings,
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
  const [mode, setMode] = useState<ExecutionMode>("paper");
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

  async function save() {
    if (lotsError) return;
    setSaving(true);
    try {
      const res = await api.patch<SubscriptionSettings>(
        `/marketplace/subscriptions/${subscriptionId}/settings`,
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
        {/* Lots override */}
        <label className="space-y-1 block">
          <span className="text-[11px] font-medium text-foreground/90">
            Lots per signal{" "}
            <span className="text-muted-foreground font-normal">
              (even, 2-20 — blank = listing default)
            </span>
          </span>
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
            placeholder="e.g. 2"
            data-testid="lots-override-input"
          />
          {lotsError ? (
            <span className="text-[10px] text-loss" data-testid="lots-error">
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
