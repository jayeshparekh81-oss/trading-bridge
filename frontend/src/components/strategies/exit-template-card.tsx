"use client";

/**
 * Exit-Template Card — sidebar item on the standalone Exit
 * Builder page. Click loads the template into the editor; the
 * trash button deletes it (the parent runs the API call so the
 * card stays presentational).
 */

import { motion } from "framer-motion";
import { ChevronRight, Trash2 } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

export interface ExitTemplateCardData {
  id: string;
  name: string;
  description: string | null;
  exit_rules: Record<string, unknown>;
  created_at: string;
}

interface ExitTemplateCardProps {
  template: ExitTemplateCardData;
  active: boolean;
  onLoad: (template: ExitTemplateCardData) => void;
  onDelete: (templateId: string) => void;
}

interface ExitSummary {
  primaries: string[];
  extras: number;
}

function summariseRules(rules: Record<string, unknown>): ExitSummary {
  const primaries: string[] = [];
  if (typeof rules.targetPercent === "number") {
    primaries.push(`T ${rules.targetPercent}%`);
  }
  if (typeof rules.stopLossPercent === "number") {
    primaries.push(`SL ${rules.stopLossPercent}%`);
  }
  if (typeof rules.trailingStopPercent === "number") {
    primaries.push(`Tr ${rules.trailingStopPercent}%`);
  }

  let extras = 0;
  if (typeof rules.squareOffTime === "string" && rules.squareOffTime) {
    extras += 1;
  }
  if (Array.isArray(rules.partialExits) && rules.partialExits.length > 0) {
    extras += 1;
  }
  if (Array.isArray(rules.indicatorExits) && rules.indicatorExits.length > 0) {
    extras += 1;
  }
  if (rules.reverseSignalExit === true) extras += 1;

  return { primaries: primaries.slice(0, 3), extras };
}

export function ExitTemplateCard({
  template,
  active,
  onLoad,
  onDelete,
}: ExitTemplateCardProps) {
  const summary = summariseRules(template.exit_rules);
  return (
    <motion.div
      whileHover={{ scale: 1.01 }}
      whileTap={{ scale: 0.99 }}
      className={cn(
        "rounded-lg border p-3 transition-colors",
        active
          ? "bg-accent-blue/[0.08] border-accent-blue/40"
          : "bg-white/[0.02] border-white/[0.06] hover:bg-white/[0.04]",
      )}
    >
      <button
        type="button"
        onClick={() => onLoad(template)}
        className="w-full text-left space-y-1.5"
      >
        <div className="flex items-start justify-between gap-2">
          <span className="text-sm font-semibold truncate min-w-0">
            {template.name}
          </span>
          <ChevronRight className="h-3.5 w-3.5 text-muted-foreground shrink-0 mt-0.5" />
        </div>
        {template.description ? (
          <p className="text-[11px] text-muted-foreground line-clamp-2 leading-relaxed">
            {template.description}
          </p>
        ) : null}
        <div className="flex items-center gap-1.5 flex-wrap">
          {summary.primaries.length === 0 ? (
            <Badge className="bg-white/[0.04] text-muted-foreground border-white/[0.06] text-[10px]">
              custom exit
            </Badge>
          ) : (
            summary.primaries.map((p) => (
              <Badge
                key={p}
                className="bg-accent-blue/15 text-accent-blue border-accent-blue/30 text-[10px]"
              >
                {p}
              </Badge>
            ))
          )}
          {summary.extras > 0 ? (
            <Badge className="bg-white/[0.04] text-muted-foreground border-white/[0.06] text-[10px]">
              +{summary.extras} more
            </Badge>
          ) : null}
        </div>
      </button>
      <div className="flex justify-end pt-1">
        <Button
          variant="ghost"
          size="sm"
          onClick={() => onDelete(template.id)}
          type="button"
          className="text-loss/70 hover:text-loss"
        >
          <Trash2 className="h-3 w-3" />
        </Button>
      </div>
    </motion.div>
  );
}
