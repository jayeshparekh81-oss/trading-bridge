"use client";

/**
 * Risk-Template Card — sidebar item on the standalone Risk
 * Builder page. Click loads the template into the editor; the
 * trash button deletes it (the parent runs the API call so the
 * card stays presentational).
 */

import { motion } from "framer-motion";
import { ChevronRight, Trash2 } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

export interface RiskTemplateCardData {
  id: string;
  name: string;
  description: string | null;
  risk_rules: Record<string, unknown>;
  created_at: string;
}

interface RiskTemplateCardProps {
  template: RiskTemplateCardData;
  active: boolean;
  onLoad: (template: RiskTemplateCardData) => void;
  onDelete: (templateId: string) => void;
}

interface RiskChip {
  key: string;
  label: string;
}

function summariseRules(rules: Record<string, unknown>): RiskChip[] {
  const chips: RiskChip[] = [];
  if (typeof rules.maxDailyLossPercent === "number") {
    chips.push({
      key: "daily",
      label: `Daily ≤${rules.maxDailyLossPercent}%`,
    });
  }
  if (typeof rules.maxCapitalPerTradePercent === "number") {
    chips.push({
      key: "capital",
      label: `Cap/Tr ${rules.maxCapitalPerTradePercent}%`,
    });
  }
  if (typeof rules.maxTradesPerDay === "number") {
    chips.push({
      key: "trades",
      label: `${rules.maxTradesPerDay} tr/day`,
    });
  }
  if (typeof rules.maxLossStreak === "number") {
    chips.push({
      key: "streak",
      label: `Streak ${rules.maxLossStreak}`,
    });
  }
  return chips;
}

export function RiskTemplateCard({
  template,
  active,
  onLoad,
  onDelete,
}: RiskTemplateCardProps) {
  const chips = summariseRules(template.risk_rules);
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
          {chips.length === 0 ? (
            <Badge className="bg-white/[0.04] text-muted-foreground border-white/[0.06] text-[10px]">
              no caps
            </Badge>
          ) : (
            chips.map((chip) => (
              <Badge
                key={chip.key}
                className="bg-accent-blue/15 text-accent-blue border-accent-blue/30 text-[10px]"
              >
                {chip.label}
              </Badge>
            ))
          )}
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
