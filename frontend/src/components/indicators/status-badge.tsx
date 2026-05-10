"use client";

import { ShieldAlert, ShieldCheck, ShieldQuestion, Sparkles, Trash2 } from "lucide-react";
import { cn } from "@/lib/utils";

interface Props {
  status: string;
  source?: "registry_default" | "override" | string;
  /** Show a small "(override)" tag when the status is admin-imposed. */
  showSource?: boolean;
}

/**
 * Renders an indicator's effective status as a coloured chip.
 * Drop-in for indicator pickers, strategy detail, compliance views.
 */
export function StatusBadge({ status, source, showSource = false }: Props) {
  const palette = paletteFor(status);
  const Icon = palette.icon;
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-md px-2 py-0.5 text-[10px] uppercase border tabular-nums",
        palette.cls,
      )}
    >
      <Icon className="h-3 w-3" />
      {status}
      {showSource && source === "override" ? (
        <span className="opacity-70">(override)</span>
      ) : null}
    </span>
  );
}

function paletteFor(status: string): {
  cls: string;
  icon: typeof ShieldCheck;
} {
  switch (status) {
    case "active":
      return {
        cls: "bg-profit/10 text-profit/90 border-profit/20",
        icon: ShieldCheck,
      };
    case "coming_soon":
      return {
        cls: "bg-yellow-500/10 text-yellow-300 border-yellow-500/25",
        icon: Sparkles,
      };
    case "experimental":
      return {
        cls: "bg-accent-purple/10 text-accent-purple border-accent-purple/25",
        icon: ShieldAlert,
      };
    case "deprecated":
      return {
        cls: "bg-loss/10 text-loss border-loss/25",
        icon: Trash2,
      };
    default:
      return {
        cls: "bg-white/[0.04] text-muted-foreground border-white/[0.06]",
        icon: ShieldQuestion,
      };
  }
}
