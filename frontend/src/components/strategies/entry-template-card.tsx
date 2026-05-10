"use client";

/**
 * Entry-Template Card — sidebar item on the standalone Entry
 * Builder page. Click loads the template into the editor; the
 * trash button deletes it (the parent runs the API call so the
 * card stays presentational).
 */

import { motion } from "framer-motion";
import { ChevronRight, Trash2 } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

export interface EntryTemplateCardData {
  id: string;
  name: string;
  description: string | null;
  side: string;
  operator: string;
  conditions: Array<Record<string, unknown>>;
  created_at: string;
}

interface EntryTemplateCardProps {
  template: EntryTemplateCardData;
  active: boolean;
  onLoad: (template: EntryTemplateCardData) => void;
  onDelete: (templateId: string) => void;
}

export function EntryTemplateCard({
  template,
  active,
  onLoad,
  onDelete,
}: EntryTemplateCardProps) {
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
          <Badge
            className={cn(
              "uppercase text-[10px]",
              template.side === "BUY"
                ? "bg-profit/15 text-profit border-profit/30"
                : "bg-loss/15 text-loss border-loss/30",
            )}
          >
            {template.side}
          </Badge>
          <Badge className="bg-white/[0.04] text-muted-foreground border-white/[0.06] text-[10px]">
            {template.operator}
          </Badge>
          <Badge className="bg-white/[0.04] text-muted-foreground border-white/[0.06] text-[10px]">
            {template.conditions.length} cond
          </Badge>
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
