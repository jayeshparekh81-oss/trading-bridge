/**
 * IndicatorsDropdown — top-bar control that toggles which indicator
 * overlays are visible on the chart.
 *
 * Day 6 frontend lite (overnight #2 / Phase 2). Persists each toggle
 * in localStorage so the operator's per-context preferences survive
 * navigation. Mirrors the StrategySelector's storage pattern.
 *
 * Default state (matches the brief):
 *   * SMA(20) = on
 *   * EMA(50) = on
 *   * RSI(14) = on (Phase 3 wire-up)
 *   * MACD    = off (Phase 3 wire-up)
 *
 * "Add custom indicator" button is a placeholder that fires a
 * sonner toast — the real pipeline lands after smoke green.
 */

"use client";

import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";

const STORAGE_KEY = "tb_chart_indicators";

export interface IndicatorToggles {
  sma20: boolean;
  ema50: boolean;
  rsi: boolean;
  macd: boolean;
  /** Phase 4 — volume pane visibility. Defaults to ``true`` on
   *  desktop and ``false`` on mobile (saves vertical real estate
   *  on phone viewports). Operator can override via the dropdown. */
  volume: boolean;
}

const DEFAULT_TOGGLES_DESKTOP: IndicatorToggles = {
  sma20: true,
  ema50: true,
  rsi: true,
  macd: false,
  volume: true,
};

function isMobileViewport(): boolean {
  if (typeof window === "undefined") return false;
  if (typeof window.matchMedia !== "function") return false;
  // Tailwind ``md`` breakpoint is 768px.
  return window.matchMedia("(max-width: 767px)").matches;
}

export function loadPersistedToggles(): IndicatorToggles {
  const baseDefault: IndicatorToggles = {
    ...DEFAULT_TOGGLES_DESKTOP,
    volume: !isMobileViewport(),
  };
  if (typeof window === "undefined") return baseDefault;
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return baseDefault;
    const parsed = JSON.parse(raw) as Partial<IndicatorToggles>;
    return {
      sma20:
        typeof parsed.sma20 === "boolean"
          ? parsed.sma20
          : baseDefault.sma20,
      ema50:
        typeof parsed.ema50 === "boolean"
          ? parsed.ema50
          : baseDefault.ema50,
      rsi:
        typeof parsed.rsi === "boolean" ? parsed.rsi : baseDefault.rsi,
      macd:
        typeof parsed.macd === "boolean"
          ? parsed.macd
          : baseDefault.macd,
      volume:
        typeof parsed.volume === "boolean"
          ? parsed.volume
          : baseDefault.volume,
    };
  } catch {
    return baseDefault;
  }
}

function persistToggles(t: IndicatorToggles): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(t));
  } catch {
    /* private browsing — silently degrade */
  }
}

export interface IndicatorsDropdownProps {
  value: IndicatorToggles;
  onChange: (next: IndicatorToggles) => void;
}

export function IndicatorsDropdown({
  value,
  onChange,
}: IndicatorsDropdownProps) {
  const [open, setOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement | null>(null);

  // Outside-click closes the menu. ``mousedown`` (not ``click``) so
  // the menu doesn't briefly stay open when the user clicks straight
  // through to a toggle button outside the menu.
  useEffect(() => {
    if (!open) return;
    function handler(e: MouseEvent) {
      if (!containerRef.current) return;
      if (!containerRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [open]);

  function update(patch: Partial<IndicatorToggles>) {
    const next = { ...value, ...patch };
    onChange(next);
    persistToggles(next);
  }

  const activeCount = Object.values(value).filter(Boolean).length;

  return (
    <div
      ref={containerRef}
      className="relative"
      data-testid="indicators-dropdown"
    >
      <button
        type="button"
        data-testid="indicators-dropdown-toggle"
        className="rounded-md border border-neutral-700 bg-neutral-900 px-2 py-1 text-xs text-neutral-200 hover:bg-neutral-800 focus:outline-none focus:ring-1 focus:ring-neutral-500"
        onClick={() => setOpen((o) => !o)}
        aria-haspopup="menu"
        aria-expanded={open}
      >
        Indicators
        <span className="ml-1.5 text-neutral-500">({activeCount})</span>
      </button>
      {open && (
        <div
          data-testid="indicators-dropdown-menu"
          className="absolute right-0 top-full z-30 mt-1 w-48 rounded-md border border-neutral-700 bg-neutral-900 p-1 text-xs shadow-lg"
          role="menu"
        >
          <Toggle
            label="SMA(20)"
            color="text-yellow-400"
            checked={value.sma20}
            testid="indicator-toggle-sma20"
            onChange={(v) => update({ sma20: v })}
          />
          <Toggle
            label="EMA(50)"
            color="text-purple-400"
            checked={value.ema50}
            testid="indicator-toggle-ema50"
            onChange={(v) => update({ ema50: v })}
          />
          <div className="my-1 h-px bg-neutral-700" />
          <Toggle
            label="RSI(14)"
            color="text-cyan-400"
            checked={value.rsi}
            testid="indicator-toggle-rsi"
            onChange={(v) => update({ rsi: v })}
          />
          <Toggle
            label="MACD"
            color="text-orange-400"
            checked={value.macd}
            testid="indicator-toggle-macd"
            onChange={(v) => update({ macd: v })}
          />
          <div className="my-1 h-px bg-neutral-700" />
          <Toggle
            label="Volume"
            color="text-neutral-300"
            checked={value.volume}
            testid="indicator-toggle-volume"
            onChange={(v) => update({ volume: v })}
          />
          <div className="my-1 h-px bg-neutral-700" />
          <button
            type="button"
            data-testid="indicator-add-custom"
            className="flex w-full items-center gap-2 rounded px-2 py-1.5 text-left text-neutral-300 hover:bg-neutral-800"
            onClick={() => {
              toast.info(
                "Custom indicators jaldi aayenge — abhi sirf default 4 hain.",
              );
              setOpen(false);
            }}
          >
            <span className="text-neutral-500">+</span>
            Add custom indicator
          </button>
        </div>
      )}
    </div>
  );
}

interface ToggleProps {
  label: string;
  color: string;
  checked: boolean;
  testid: string;
  onChange: (next: boolean) => void;
}

function Toggle({ label, color, checked, testid, onChange }: ToggleProps) {
  return (
    <label
      className="flex cursor-pointer items-center gap-2 rounded px-2 py-1.5 hover:bg-neutral-800"
      role="menuitemcheckbox"
      aria-checked={checked}
    >
      <input
        type="checkbox"
        data-testid={testid}
        className="h-3 w-3 cursor-pointer accent-neutral-300"
        checked={checked}
        onChange={(e) => onChange(e.target.checked)}
      />
      <span className={`flex-1 ${color}`}>{label}</span>
    </label>
  );
}
