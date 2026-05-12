/**
 * PaperTradeList — collapsible bottom drawer showing the paper-trade
 * markers for the currently-selected strategy.
 *
 * Day-3 integration. Two-way highlight wiring with the chart canvas:
 *   * Click a marker → ChartContainer routes the marker's id into
 *     ``highlightedMarkerId`` → the matching list row scrolls into
 *     view + flashes a highlight ring.
 *   * Click a list row → ChartContainer routes its id into the chart
 *     for the same flash on the canvas (TODO: chart-side flash is
 *     a v2 polish — for v1 we just centre the time-range on the
 *     marker via ``setVisibleRange``).
 *
 * Layout
 *   * Desktop (md+): inline panel of fixed 280px height anchored to
 *     the bottom of the chart container. Always visible when a
 *     strategy is selected.
 *   * Mobile (< md): full-screen drawer that slides up from the
 *     bottom on tap of a "Trades" affordance. Uses the same DOM —
 *     Tailwind responsive classes swap the layout.
 */

"use client";

import { useEffect, useRef } from "react";

import type { ChartMarker } from "@/lib/chart/types";

// ─── Helpers ───────────────────────────────────────────────────────────

/** Stable per-marker id derived from kind + time. The backend doesn't
 *  hand us a database id (markers are derived from trades), so we
 *  fingerprint by (kind, time) which is unique within one strategy
 *  window — entries and exits never share a timestamp because the
 *  paper-trading engine writes them at the end of two distinct
 *  candle ticks. */
export function markerId(m: ChartMarker): string {
  return `${m.kind}:${m.time}`;
}

function formatPrice(value: number): string {
  return value.toLocaleString("en-IN", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}

function formatTimestamp(epochSeconds: number): string {
  const d = new Date(epochSeconds * 1000);
  return d.toLocaleString("en-IN", {
    hour: "2-digit",
    minute: "2-digit",
    day: "2-digit",
    month: "short",
    timeZone: "Asia/Kolkata",
  });
}

const KIND_BADGE: Record<ChartMarker["kind"], { label: string; cls: string }> = {
  ENTRY: { label: "ENTRY", cls: "bg-green-500/15 text-green-400" },
  TP_HIT: { label: "TP HIT", cls: "bg-blue-500/15 text-blue-400" },
  SL_HIT: { label: "SL HIT", cls: "bg-red-500/15 text-red-400" },
  EXIT: { label: "EXIT", cls: "bg-neutral-500/15 text-neutral-300" },
};

// ─── Empty + status states ─────────────────────────────────────────────

function EmptyState({ message }: { message: string }) {
  return (
    <div
      data-testid="paper-trade-list-empty"
      className="flex h-full items-center justify-center px-4 text-center text-xs text-neutral-400"
    >
      {message}
    </div>
  );
}

// ─── Main component ────────────────────────────────────────────────────

export interface PaperTradeListProps {
  /** Resolved markers from useChartMarkers. */
  markers: ChartMarker[];
  /** True while the markers fetch is in flight. */
  isLoading: boolean;
  /** Once the first fetch resolved (success OR failure). */
  hasLoaded: boolean;
  /** Last fetch error or ``null``. */
  error: Error | null;
  /** ``null`` when no strategy is selected — shown as a helpful
   *  "select a strategy" empty state. */
  strategySelected: boolean;
  /** Currently-highlighted marker id (driven by chart click). The
   *  matching row scrolls into view + flashes. */
  highlightedMarkerId: string | null;
  /** Click on a row routes back up to the chart for the inverse
   *  highlight. */
  onRowClick: (m: ChartMarker) => void;
  /** Drawer open/close state on mobile. Desktop ignores this. */
  isOpen: boolean;
  onClose: () => void;
}

export function PaperTradeList({
  markers,
  isLoading,
  hasLoaded,
  error,
  strategySelected,
  highlightedMarkerId,
  onRowClick,
  isOpen,
  onClose,
}: PaperTradeListProps) {
  const listRef = useRef<HTMLDivElement | null>(null);
  const rowRefs = useRef<Map<string, HTMLButtonElement>>(new Map());

  // Scroll the highlighted row into view + flash. ``behavior: smooth``
  // is the dashboard convention (matches the strategies-list scroll
  // behaviour on row select).
  useEffect(() => {
    if (highlightedMarkerId === null) return;
    const row = rowRefs.current.get(highlightedMarkerId);
    if (!row) return;
    // jsdom doesn't implement scrollIntoView — guard so unit tests
    // don't blow up. In the browser the call is always present.
    if (typeof row.scrollIntoView === "function") {
      row.scrollIntoView({ behavior: "smooth", block: "nearest" });
    }
  }, [highlightedMarkerId]);

  // Pick the right empty-state copy based on which precondition is
  // missing. Hinglish copy mirrors the dashboard's tone — short,
  // direct, never apologetic.
  let body: React.ReactNode;
  if (!strategySelected) {
    body = (
      <EmptyState message="Strategy select karo to paper trades dikhenge." />
    );
  } else if (error !== null) {
    body = (
      <EmptyState
        message={`Trades load nahi ho paaye — ${error.message}`}
      />
    );
  } else if (isLoading && !hasLoaded) {
    body = <EmptyState message="Loading…" />;
  } else if (markers.length === 0) {
    body = (
      <EmptyState message="Is window mein koi paper trade nahi mila." />
    );
  } else {
    body = (
      <div
        ref={listRef}
        className="h-full overflow-y-auto"
        data-testid="paper-trade-list-rows"
      >
        <table className="w-full text-xs">
          <thead className="sticky top-0 bg-neutral-900 text-left text-[10px] uppercase tracking-wide text-neutral-500">
            <tr>
              <th className="px-3 py-2">Kind</th>
              <th className="px-3 py-2">Time</th>
              <th className="px-3 py-2 text-right">Price</th>
              <th className="px-3 py-2 text-right">Qty</th>
              <th className="px-3 py-2">Side</th>
              <th className="px-3 py-2 text-right">P&amp;L</th>
            </tr>
          </thead>
          <tbody>
            {markers.map((m) => {
              const id = markerId(m);
              const isHighlighted = id === highlightedMarkerId;
              const badge = KIND_BADGE[m.kind];
              return (
                <tr
                  key={id}
                  className={
                    isHighlighted
                      ? "bg-neutral-800 ring-1 ring-inset ring-neutral-500"
                      : "hover:bg-neutral-900/60"
                  }
                  data-testid={`trade-row-${id}`}
                  data-highlighted={isHighlighted ? "true" : undefined}
                >
                  <td className="px-3 py-1.5">
                    <button
                      ref={(el) => {
                        if (el) rowRefs.current.set(id, el);
                        else rowRefs.current.delete(id);
                      }}
                      type="button"
                      className={`rounded px-1.5 py-0.5 text-[10px] font-semibold ${badge.cls}`}
                      onClick={() => onRowClick(m)}
                    >
                      {badge.label}
                    </button>
                  </td>
                  <td className="px-3 py-1.5 font-mono text-neutral-300">
                    {formatTimestamp(m.time)}
                  </td>
                  <td className="px-3 py-1.5 text-right font-mono text-neutral-200">
                    ₹{formatPrice(m.price)}
                  </td>
                  <td className="px-3 py-1.5 text-right font-mono text-neutral-300">
                    {m.quantity}
                  </td>
                  <td className="px-3 py-1.5 text-neutral-300">{m.side}</td>
                  <td
                    className={`px-3 py-1.5 text-right font-mono ${
                      m.pnl === null
                        ? "text-neutral-500"
                        : m.pnl >= 0
                          ? "text-green-500"
                          : "text-red-400"
                    }`}
                  >
                    {m.pnl === null ? "—" : `₹${formatPrice(m.pnl)}`}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    );
  }

  return (
    <div
      data-testid="paper-trade-list"
      data-open={isOpen ? "true" : "false"}
      className={[
        // Desktop: inline panel, fixed height, always visible
        "md:relative md:block md:h-[280px] md:border-t md:border-border",
        // Mobile: bottom sheet, slides over the chart, toggled by isOpen
        "fixed bottom-0 left-0 right-0 z-20 h-[60vh] border-t border-border bg-[#0a0a0a] transition-transform md:transform-none",
        isOpen ? "translate-y-0" : "translate-y-full md:translate-y-0",
      ].join(" ")}
    >
      <div className="flex items-center justify-between border-b border-border px-3 py-1.5">
        <span className="text-xs font-semibold uppercase tracking-wide text-neutral-300">
          Paper Trades
          {markers.length > 0 && (
            <span className="ml-2 text-neutral-500">({markers.length})</span>
          )}
        </span>
        <button
          type="button"
          data-testid="paper-trade-list-close"
          className="text-xs text-neutral-400 hover:text-neutral-100 md:hidden"
          onClick={onClose}
          aria-label="Close trades panel"
        >
          Close
        </button>
      </div>
      {body}
    </div>
  );
}
