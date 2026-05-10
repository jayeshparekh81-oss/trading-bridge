"use client";

import { useState } from "react";
import {
  Hash,
  ArrowRight,
  Target,
  Shield,
  ChevronDown,
  ChevronUp,
  FileJson,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

/**
 * Reads a partially-typed StrategyJSON-shaped dict and renders a
 * compact visual block — indicators chips + entry conditions + exit
 * primitives. We treat the input as ``Record<string, unknown>`` and
 * narrow defensively so a rough partial conversion still renders
 * something useful instead of crashing on missing keys.
 */
interface Props {
  strategy: Record<string, unknown>;
  /** When true, the raw-JSON expander is collapsed by default. */
  jsonCollapsed?: boolean;
}

interface IndicatorView {
  id: string;
  type: string;
  paramText: string;
}

interface ConditionView {
  type: string;
  /** Human-readable summary line (e.g. "ema_fast crossover ema_slow"). */
  summary: string;
}


export function ConvertedStrategyView({ strategy, jsonCollapsed = true }: Props) {
  const indicators = readIndicators(strategy);
  const entry = readEntry(strategy);
  const exit = readExit(strategy);

  return (
    <div className="space-y-3">
      {/* Indicators */}
      {indicators.length > 0 ? (
        <Section icon={<Hash className="h-3.5 w-3.5 text-accent-blue" />} title="Indicators">
          <div className="flex flex-wrap gap-1.5">
            {indicators.map((ind) => (
              <Badge
                key={ind.id}
                className="bg-accent-blue/15 text-accent-blue border-accent-blue/30 gap-1"
              >
                <span className="font-mono text-[10px]">{ind.id}</span>
                <span className="text-[10px] opacity-80">· {ind.type}</span>
                {ind.paramText ? (
                  <span className="text-[10px] opacity-70">({ind.paramText})</span>
                ) : null}
              </Badge>
            ))}
          </div>
        </Section>
      ) : null}

      {/* Entry */}
      {entry ? (
        <Section
          icon={<ArrowRight className="h-3.5 w-3.5 text-profit" />}
          title="Entry"
          accent={
            <Badge className="bg-profit/15 text-profit border-profit/30 text-[10px]">
              {entry.side}
            </Badge>
          }
        >
          <div className="space-y-1.5">
            <div className="text-[11px] text-muted-foreground uppercase tracking-wide">
              Joined with{" "}
              <Badge className="bg-accent-blue/15 text-accent-blue border-accent-blue/30 text-[10px] ml-1">
                {entry.operator}
              </Badge>
            </div>
            {entry.conditions.length === 0 ? (
              <p className="text-[11px] text-muted-foreground italic">
                No entry conditions parsed.
              </p>
            ) : (
              <ul className="space-y-1">
                {entry.conditions.map((c, idx) => (
                  <li
                    key={idx}
                    className="text-[12px] rounded-md bg-white/[0.02] border border-white/[0.04] px-2.5 py-1.5"
                  >
                    <span className="font-mono">{c.summary}</span>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </Section>
      ) : null}

      {/* Exit */}
      {exit && exit.length > 0 ? (
        <Section
          icon={<Target className="h-3.5 w-3.5 text-accent-blue" />}
          title="Exit"
        >
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
            {exit.map((tile) => (
              <div
                key={tile.label}
                className="rounded-md bg-white/[0.02] border border-white/[0.04] px-3 py-2"
              >
                <div className="flex items-center gap-1.5 text-[11px] uppercase tracking-wide text-muted-foreground">
                  {tile.icon}
                  {tile.label}
                </div>
                <div className="text-sm font-medium tabular-nums mt-0.5">
                  {tile.value}
                </div>
              </div>
            ))}
          </div>
        </Section>
      ) : null}

      <RawJsonExpander payload={strategy} collapsedByDefault={jsonCollapsed} />
    </div>
  );
}


function Section({
  icon,
  title,
  accent,
  children,
}: {
  icon: React.ReactNode;
  title: string;
  accent?: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <div className="rounded-lg bg-white/[0.02] border border-white/[0.04] p-3 space-y-2">
      <div className="flex items-center gap-1.5">
        {icon}
        <h3 className="text-xs uppercase tracking-wide text-muted-foreground font-medium">
          {title}
        </h3>
        {accent ? <div className="ml-auto">{accent}</div> : null}
      </div>
      {children}
    </div>
  );
}


function RawJsonExpander({
  payload,
  collapsedByDefault,
}: {
  payload: unknown;
  collapsedByDefault: boolean;
}) {
  const [open, setOpen] = useState(!collapsedByDefault);
  const text = (() => {
    try {
      return JSON.stringify(payload, null, 2);
    } catch {
      return "{}";
    }
  })();
  return (
    <div className="rounded-lg bg-white/[0.02] border border-white/[0.04]">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        className="w-full flex items-center gap-2 px-3 py-2 text-left"
      >
        <FileJson className="h-3.5 w-3.5 text-accent-blue" />
        <span className="text-xs uppercase tracking-wide text-muted-foreground font-medium">
          Raw JSON
        </span>
        <span className="ml-auto text-[10px] text-muted-foreground">
          {open ? "Hide" : "Show"}
        </span>
        {open ? (
          <ChevronUp className="h-3.5 w-3.5 text-muted-foreground" />
        ) : (
          <ChevronDown className="h-3.5 w-3.5 text-muted-foreground" />
        )}
      </button>
      {open ? (
        <div className="border-t border-white/[0.04]">
          <pre
            className={cn(
              "text-[11px] leading-snug p-3 overflow-x-auto max-h-72 overflow-y-auto",
              "font-mono text-foreground/90 bg-black/30",
            )}
          >
            <code>{text}</code>
          </pre>
        </div>
      ) : null}
    </div>
  );
}


// ─── Defensive readers ─────────────────────────────────────────────────


function readIndicators(strategy: Record<string, unknown>): IndicatorView[] {
  const raw = strategy["indicators"];
  if (!Array.isArray(raw)) return [];
  const out: IndicatorView[] = [];
  for (const item of raw) {
    if (!item || typeof item !== "object") continue;
    const it = item as Record<string, unknown>;
    const id = typeof it.id === "string" ? it.id : null;
    const type = typeof it.type === "string" ? it.type : null;
    if (!id || !type) continue;
    let paramText = "";
    if (it.params && typeof it.params === "object") {
      const parts: string[] = [];
      for (const [k, v] of Object.entries(it.params as Record<string, unknown>)) {
        if (typeof v === "number" || typeof v === "string") {
          parts.push(`${k}=${v}`);
        }
      }
      paramText = parts.join(", ");
    }
    out.push({ id, type, paramText });
  }
  return out;
}


function readEntry(strategy: Record<string, unknown>): {
  side: string;
  operator: string;
  conditions: ConditionView[];
} | null {
  const raw = strategy["entry"];
  if (!raw || typeof raw !== "object") return null;
  const r = raw as Record<string, unknown>;
  const side = typeof r.side === "string" ? r.side : "BUY";
  const operator = typeof r.operator === "string" ? r.operator : "AND";
  const conditionsRaw = Array.isArray(r.conditions) ? r.conditions : [];
  const conditions: ConditionView[] = [];
  for (const c of conditionsRaw) {
    if (!c || typeof c !== "object") continue;
    conditions.push(summariseCondition(c as Record<string, unknown>));
  }
  return { side, operator, conditions };
}


function summariseCondition(c: Record<string, unknown>): ConditionView {
  const t = typeof c.type === "string" ? c.type : "?";
  if (t === "indicator") {
    const left = c.left ?? "?";
    const op = c.op ?? "?";
    const rhs = c.right !== undefined && c.right !== null ? c.right : c.value;
    return { type: t, summary: `${left} ${op} ${rhs ?? "?"}` };
  }
  if (t === "candle") {
    return { type: t, summary: `candle: ${c.pattern ?? "?"}` };
  }
  if (t === "time") {
    return {
      type: t,
      summary: `time ${c.op ?? "?"} ${c.value ?? "?"}${
        c.end ? `..${c.end}` : ""
      }`,
    };
  }
  if (t === "price") {
    return {
      type: t,
      summary: `price ${c.op ?? "?"}${c.value !== undefined ? ` ${c.value}` : ""}`,
    };
  }
  return { type: t, summary: JSON.stringify(c) };
}


interface ExitTile {
  label: string;
  value: string;
  icon: React.ReactNode;
}


function readExit(strategy: Record<string, unknown>): ExitTile[] | null {
  const raw = strategy["exit"];
  if (!raw || typeof raw !== "object") return null;
  const r = raw as Record<string, unknown>;
  const out: ExitTile[] = [];
  if (typeof r.targetPercent === "number") {
    out.push({
      label: "Target",
      value: `+${r.targetPercent}%`,
      icon: <Target className="h-3 w-3 text-profit" />,
    });
  }
  if (typeof r.stopLossPercent === "number") {
    out.push({
      label: "Stop Loss",
      value: `-${r.stopLossPercent}%`,
      icon: <Shield className="h-3 w-3 text-loss" />,
    });
  }
  if (typeof r.trailingStopPercent === "number") {
    out.push({
      label: "Trailing Stop",
      value: `${r.trailingStopPercent}%`,
      icon: <Target className="h-3 w-3 text-accent-blue" />,
    });
  }
  if (typeof r.squareOffTime === "string" && r.squareOffTime) {
    out.push({
      label: "Square-off",
      value: r.squareOffTime,
      icon: <Target className="h-3 w-3 text-muted-foreground" />,
    });
  }
  return out;
}


