/**
 * StrategySelector — dropdown that scopes the chart's marker overlay
 * to one of the user's paper-trading strategies.
 *
 * Day-3 integration. The selection is persisted in localStorage keyed
 * by ``(symbol, timeframe)`` so an operator who routinely chart-
 * watches NIFTY 5m with one strategy and BANKNIFTY 15m with another
 * doesn't have to re-pick on every navigation.
 *
 * Empty + loading states mirror the dashboard's existing
 * ``/strategies`` page so the UX feels native to the rest of TRADETRI.
 */

"use client";

import { useEffect, useMemo, useState } from "react";

import { fetchUserStrategies } from "@/lib/chart/strategies";
import type {
  ChartStrategySummary,
  Timeframe,
} from "@/lib/chart/types";

const STORAGE_KEY_PREFIX = "tb_chart_strategy";

function storageKey(symbol: string, timeframe: Timeframe): string {
  return `${STORAGE_KEY_PREFIX}:${symbol.toUpperCase()}:${timeframe}`;
}

export function loadPersistedStrategyId(
  symbol: string,
  timeframe: Timeframe,
): string | null {
  if (typeof window === "undefined") return null;
  try {
    return window.localStorage.getItem(storageKey(symbol, timeframe));
  } catch {
    // Private browsing / disabled storage — silently degrade to no
    // persistence rather than crash the chart.
    return null;
  }
}

function persistStrategyId(
  symbol: string,
  timeframe: Timeframe,
  strategyId: string | null,
): void {
  if (typeof window === "undefined") return;
  try {
    if (strategyId === null) {
      window.localStorage.removeItem(storageKey(symbol, timeframe));
    } else {
      window.localStorage.setItem(storageKey(symbol, timeframe), strategyId);
    }
  } catch {
    /* see loadPersistedStrategyId */
  }
}

export interface StrategySelectorProps {
  symbol: string;
  timeframe: Timeframe;
  /** Currently-selected strategy id (or ``null`` for "no strategy"). */
  value: string | null;
  onChange: (strategyId: string | null) => void;
  /** Test-injection override of the env-based mock toggle. */
  forceMock?: boolean;
}

export function StrategySelector({
  symbol,
  timeframe,
  value,
  onChange,
  forceMock,
}: StrategySelectorProps) {
  const [strategies, setStrategies] = useState<ChartStrategySummary[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Fetch on mount only — the user's strategy list is small and
  // changes rarely; a periodic refresh would burn API calls. Refresh
  // happens implicitly when the user navigates away and back to the
  // chart route.
  useEffect(() => {
    let alive = true;
    setIsLoading(true);
    setError(null);
    fetchUserStrategies({ forceMock })
      .then((resp) => {
        if (!alive) return;
        setStrategies(resp.strategies);
        setIsLoading(false);
      })
      .catch((err) => {
        if (!alive) return;
        setError(
          err instanceof Error
            ? err.message
            : "Strategies load nahi ho paayi",
        );
        setIsLoading(false);
      });
    return () => {
      alive = false;
    };
  }, [forceMock]);

  // Restore persisted selection on (symbol, timeframe) change. If the
  // persisted id no longer matches a real strategy (deleted), drop it
  // silently. Skip when the parent already has a non-null value.
  useEffect(() => {
    if (value !== null) return;
    if (isLoading) return;
    const persisted = loadPersistedStrategyId(symbol, timeframe);
    if (persisted === null) return;
    if (strategies.some((s) => s.id === persisted)) {
      onChange(persisted);
    } else {
      persistStrategyId(symbol, timeframe, null);
    }
  }, [symbol, timeframe, isLoading, value, strategies, onChange]);

  // Sort: active first (alphabetical), then inactive (alphabetical).
  // Active strategies are 99% of the use-case so they go to the top.
  const sortedStrategies = useMemo(() => {
    return [...strategies].sort((a, b) => {
      if (a.is_active !== b.is_active) return a.is_active ? -1 : 1;
      return a.name.localeCompare(b.name);
    });
  }, [strategies]);

  function handleChange(e: React.ChangeEvent<HTMLSelectElement>) {
    const next = e.target.value === "" ? null : e.target.value;
    onChange(next);
    persistStrategyId(symbol, timeframe, next);
  }

  return (
    <div
      className="flex items-center gap-2"
      data-testid="strategy-selector"
    >
      <label
        htmlFor="strategy-select"
        className="text-xs text-neutral-400"
      >
        Strategy
      </label>
      <select
        id="strategy-select"
        data-testid="strategy-select"
        className="rounded-md border border-neutral-700 bg-neutral-900 px-2 py-1 text-xs text-neutral-200 focus:outline-none focus:ring-1 focus:ring-neutral-500"
        value={value ?? ""}
        onChange={handleChange}
        disabled={isLoading || error !== null}
      >
        <option value="">
          {isLoading
            ? "Loading…"
            : error !== null
              ? "—"
              : strategies.length === 0
                ? "Koi strategy nahi"
                : "None (markers off)"}
        </option>
        {sortedStrategies.map((s) => (
          <option key={s.id} value={s.id}>
            {s.name}
            {!s.is_active ? " (paused)" : ""}
          </option>
        ))}
      </select>
      {error !== null && (
        <span
          data-testid="strategy-selector-error"
          className="text-xs text-red-400"
        >
          {error}
        </span>
      )}
    </div>
  );
}
